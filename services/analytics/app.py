import os
import sys
import threading
import json
import uuid
import time
import logging
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from flask import Flask, jsonify
from dotenv import load_dotenv

# Configura o logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Carrega .env para desenvolvimento local
load_dotenv()

# --- Configuração ---
# Observacao: para o demo local do PDF (DynamoDB Local), o worker de SQS pode ser
# desativado (AWS_SQS_URL vazio) e/ou o endpoint do Dynamo pode ser customizado.
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SQS_QUEUE_URL = os.getenv("AWS_SQS_URL", "")
DYNAMODB_TABLE_NAME = os.getenv("AWS_DYNAMODB_TABLE", "ToggleMasterAnalytics")

# Ex.: http://dynamodb-local:8000
DYNAMODB_ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL", "")

# Quando usar DynamoDB Local, crie a tabela automaticamente para simplificar o demo.
DYNAMODB_CREATE_TABLE = os.getenv("DYNAMODB_CREATE_TABLE", "0") == "1"

# Para DynamoDB local, boto3 pode exigir credenciais; em local usamos credenciais dummy.
DYNAMODB_USE_DUMMY_CREDS = os.getenv("DYNAMODB_USE_DUMMY_CREDS", "1") == "1"

# --- Clientes Boto3 ---
try:
    session_kwargs = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT_URL and DYNAMODB_USE_DUMMY_CREDS:
        session_kwargs.update(
            {
                "aws_access_key_id": "dummy",
                "aws_secret_access_key": "dummy",
                "aws_session_token": "dummy",
            }
        )

    session = boto3.Session(**session_kwargs)
    if DYNAMODB_ENDPOINT_URL:
        dynamodb_client = session.client("dynamodb", endpoint_url=DYNAMODB_ENDPOINT_URL)
    else:
        dynamodb_client = session.client("dynamodb")

    sqs_client = None
    if SQS_QUEUE_URL:
        sqs_client = session.client("sqs")

    log.info(f"Clientes Boto3 inicializados na região {AWS_REGION}")
except NoCredentialsError:
    # Mantemos como erro fatal porque SQS e DynamoDB nao funcionam sem credenciais na nuvem.
    log.critical("Credenciais da AWS não encontradas. Verifique seu ambiente.")
    sys.exit(1)
except Exception as e:
    log.critical(f"Erro ao inicializar o Boto3: {e}")
    sys.exit(1)


def ensure_dynamodb_table():
    """Garante a tabela esperada no DynamoDB (util para DynamoDB Local)."""
    if not DYNAMODB_CREATE_TABLE:
        return

    try:
        dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        log.info(f"Tabela DynamoDB '{DYNAMODB_TABLE_NAME}' já existe.")
        return
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        # Para local, o codigo pode variar; tentamos criar se nao existir.
        if code and code.lower().find("notfound") == -1 and code.lower() != "resourcenotfoundexception":
            raise

    log.info(f"Criando tabela DynamoDB '{DYNAMODB_TABLE_NAME}' (DynamoDB CreateTable)...")
    dynamodb_client.create_table(
        TableName=DYNAMODB_TABLE_NAME,
        AttributeDefinitions=[{"AttributeName": "event_id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "event_id", "KeyType": "HASH"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1},
    )

    # Espera ficar ACTIVE (principalmente para o dynamodb-local).
    for _ in range(30):
        resp = dynamodb_client.describe_table(TableName=DYNAMODB_TABLE_NAME)
        if resp.get("Table", {}).get("TableStatus") == "ACTIVE":
            log.info("Tabela DynamoDB ativa.")
            return
        time.sleep(1)

    log.warning("Tabela DynamoDB ainda nao ficou ACTIVE dentro do timeout.")


# --- SQS Worker ---

def process_message(message):
    """ Processa uma única mensagem SQS e a insere no DynamoDB """
    try:
        log.info(f"Processando mensagem ID: {message['MessageId']}")
        body = json.loads(message['Body'])
        
        # Gera um ID único para o item no DynamoDB
        event_id = str(uuid.uuid4())
        
        # Constrói o item no formato do DynamoDB
        item = {
            'event_id': {'S': event_id},
            'user_id': {'S': body['user_id']},
            'flag_name': {'S': body['flag_name']},
            'result': {'BOOL': body['result']},
            'timestamp': {'S': body['timestamp']}
        }
        
        # Insere no DynamoDB
        dynamodb_client.put_item(
            TableName=DYNAMODB_TABLE_NAME,
            Item=item
        )
        
        log.info(f"Evento {event_id} (Flag: {body['flag_name']}) salvo no DynamoDB.")
        
        # Se tudo deu certo, deleta a mensagem da fila (worker SQS precisa estar habilitado)
        if sqs_client and SQS_QUEUE_URL:
            sqs_client.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=message["ReceiptHandle"],
            )
        
    except json.JSONDecodeError:
        log.error(f"Erro ao decodificar JSON da mensagem ID: {message['MessageId']}")
        # Não deleta a mensagem, pode ser uma "poison pill"
    except ClientError as e:
        log.error(f"Erro do Boto3 (DynamoDB ou SQS) ao processar {message['MessageId']}: {e}")
        # Não deleta a mensagem, tenta novamente
    except Exception as e:
        log.error(f"Erro inesperado ao processar {message['MessageId']}: {e}")
        # Não deleta a mensagem, tenta novamente

def sqs_worker_loop():
    """ Loop principal do worker que ouve a fila SQS """
    log.info("Iniciando o worker SQS...")
    while True:
        try:
            # Long-polling: espera até 20s por mensagens
            response = sqs_client.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,  # Processa em lotes de até 10
                WaitTimeSeconds=20
            )
            
            messages = response.get('Messages', [])
            if not messages:
                # Nenhuma mensagem, continua o loop
                continue
                
            log.info(f"Recebidas {len(messages)} mensagens.")
            
            for message in messages:
                process_message(message)
                
        except ClientError as e:
            log.error(f"Erro do Boto3 no loop principal do SQS: {e}")
            time.sleep(10) # Pausa antes de tentar novamente
        except Exception as e:
            log.error(f"Erro inesperado no loop principal do SQS: {e}")
            time.sleep(10)

# --- Servidor Flask (Apenas para Health Check) ---

app = Flask(__name__)
from telemetry import instrument_app
instrument_app(app, "analytics-service")

@app.route('/health')
def health():
    # Uma verificação de saúde real poderia checar a conexão com o DynamoDB/SQS
    return jsonify({"status": "ok"})

# --- Inicialização ---

def start_worker():
    """ Inicia o worker SQS em uma thread separada """
    if not SQS_QUEUE_URL or not sqs_client:
        log.warning("AWS_SQS_URL nao definido; worker SQS desativado.")
        return
    worker_thread = threading.Thread(target=sqs_worker_loop, daemon=True)
    worker_thread.start()

# Se for DynamoDB Local e o usuário pediu, cria a tabela no boot.
ensure_dynamodb_table()

# Inicia o worker SQS em uma thread de background (se SQS estiver habilitado)
start_worker()

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8005))
    app.run(host='0.0.0.0', port=port, debug=False)