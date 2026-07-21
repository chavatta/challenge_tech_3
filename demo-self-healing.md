# 🎬 Roteiro — Demonstração do Self-Healing (para o vídeo)

Pré-requisito: `aws eks update-kubeconfig --region us-east-1 --name togglemaster-dev-eks`

## Como funciona a simulação

O `/validate` do auth devolve 401 até em erro de banco, então o jeito confiável de gerar
**5xx de verdade** é o `POST /admin/keys` com o banco sem a tabela `api_keys`:
apontamos o auth temporariamente para o banco do *flag* (postgres válido → o pod sobe,
mas o INSERT falha → HTTP 500 a cada chamada).

## Passo 1 — Quebrar o auth de propósito

```bash
# Aponta o auth para o banco do flag (que não tem a tabela api_keys)
CUR=$(kubectl get secret -n togglemaster auth-service-secret -o jsonpath='{.data.DATABASE_URL}' | base64 -d)
SWAP=$(printf '%s' "$CUR" | sed 's|@togglemaster-dev-auth\.|@togglemaster-dev-flag.|')
kubectl patch secret -n togglemaster auth-service-secret -p "{\"stringData\":{\"DATABASE_URL\":\"$SWAP\"}}"
kubectl rollout restart deploy/auth-service -n togglemaster
kubectl rollout status deploy/auth-service -n togglemaster --timeout=180s
```

## Passo 2 — Gerar os 5xx (deixe rodando ~3 minutos)

```bash
MK=$(kubectl get secret -n togglemaster auth-service-secret -o jsonpath='{.data.MASTER_KEY}' | base64 -d)
kubectl port-forward -n togglemaster svc/auth-service 18081:80 &
sleep 5
for i in $(seq 1 200); do
  curl -s -o /dev/null -w "%{http_code} " -X POST http://localhost:18081/admin/keys \
    -H "Authorization: Bearer $MK" -H "Content-Type: application/json" -d '{"name":"demo"}'
  sleep 1
done
```
Cada `500` impresso alimenta a métrica `http_server_duration` com `http_status_code=5xx`.

## Passo 3 — Mostrar o alerta subindo (em outro terminal)

```bash
kubectl port-forward -n monitoring svc/togglemaster-prometheus-ku-prometheus 9090:9090 &
# Abrir http://localhost:9090/alerts → AuthServiceHighErrorRate: inactive → Pending → FIRING
```
📸 Print do gráfico de erro no Grafana e do alerta FIRING.

## Passo 4 — Mostrar cada integração reagindo

```bash
# Self-healing detectando e agindo:
kubectl logs -n togglemaster -l app=self-healing-service -f
# Esperado: "Handling firing alert: AuthServiceHighErrorRate" + "Rollout restart patch successfully applied"

# Pods do auth reiniciando:
kubectl get pods -n togglemaster -w
```
- **PagerDuty** (https://app.pagerduty.com → Incidents): incidente criado no serviço `togglemaster` 📸
- **Discord** (canal de alertas): mensagem **firing** com o nome do alerta 📸

## Passo 5 — Restaurar e mostrar a resolução

```bash
CUR=$(kubectl get secret -n togglemaster auth-service-secret -o jsonpath='{.data.DATABASE_URL}' | base64 -d)
FIXED=$(printf '%s' "$CUR" | sed 's|@togglemaster-dev-flag\.|@togglemaster-dev-auth.|')
kubectl patch secret -n togglemaster auth-service-secret -p "{\"stringData\":{\"DATABASE_URL\":\"$FIXED\"}}"
kubectl rollout restart deploy/auth-service -n togglemaster
```
Após ~2 min sem 5xx: alerta volta a `inactive`, o Discord recebe a mensagem **resolved** 📸
e o incidente no PagerDuty muda para **Resolved** automaticamente 📸.

## Dica de capacidade

Se um rollout ficar preso com pods `Pending` (os nós t3.medium ficam no limite de pods),
delete os ReplicaSets antigos do deployment:
```bash
kubectl get rs -n togglemaster | grep auth-service
kubectl delete rs -n togglemaster <NOME-DO-RS-ANTIGO>
```
