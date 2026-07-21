# Relatório de Entrega — Tech Challenge Fase 4 (POSTECH - FIAP)
## Observabilidade Total e Self-Healing no Ecossistema ToggleMaster

**Integrantes do Grupo:**
| Nome Completo | RM | Username GitHub |
|---|---|---|
| *Preencher* | *RM00000* | *@username* |

**Links:**
- Repositório GitHub: *preencher*
- Vídeo de demonstração: *preencher*

Este relatório reúne o detalhamento de todas as ações realizadas para a implementação da Fase 4 do projeto **ToggleMaster**, bem como as justificativas técnicas adotadas para garantir alta performance, segurança, resiliência e controle de custos dentro do cluster EKS.

---

## 1. Resumo das Ações Executadas

### A. Instrumentação de Código com OpenTelemetry (OTel)
* **Microsserviços em Go (`auth` e `evaluation`):**
  * Criado o helper [telemetry.go](services/auth/telemetry.go) (com réplica idêntica em `evaluation`) para inicialização do `TracerProvider` **e do `MeterProvider`** do SDK OpenTelemetry, com exportadores OTLP via gRPC (`otlptracegrpc` e `otlpmetricgrpc`). Com o `MeterProvider` global ativo, o middleware `otelhttp` emite automaticamente a métrica `http.server.duration` (histograma com `http.status_code`), que alimenta o alerta de 5xx e o dashboard. As dependências foram pinadas no `go.mod` (SDK OTel v1.24.0, `otelhttp` v0.49.0) para garantir nomes de métricas estáveis.
  * Modificado o arquivo [main.go](services/auth/main.go) para inicializar a telemetria e envelopar as rotas HTTP com o middleware `otelhttp.NewHandler`, permitindo métricas e traces de requisição automáticos.
  * No `evaluation-service`, adaptamos as funções internas em [evaluator.go](services/evaluation/evaluator.go) e os handlers em [handlers.go](services/evaluation/handlers.go) para aceitarem e propagarem o `context.Context` nas goroutines assíncronas.
  * O `HttpClient` do `evaluation` foi instrumentado com `otelhttp.NewTransport(http.DefaultTransport)`. Isso permite que o ID de trace (W3C Trace Context) seja propagado nas chamadas HTTP downstream para os serviços de `flag` e `targeting`, garantindo o **Tracing Distribuído**.
* **Microsserviços em Python (`flag`, `targeting` e `analytics`):**
  * Criado o helper [telemetry.py](services/flag/telemetry.py) (e réplicas em `targeting` e `analytics`) para configurar o SDK OTel em Python.
  * Utilizamos a instrumentação automática do Flask (`FlaskInstrumentor().instrument_app(app)`) e da biblioteca de requisições HTTP (`RequestsInstrumentor().instrument()`) para propagar o contexto de trace nas chamadas subsequentes (como a validação de token no `auth-service`).
  * O helper configura os **três sinais** do OpenTelemetry: traces (`TracerProvider`), métricas (`MeterProvider` com `PeriodicExportingMetricReader` — o Flask passa a emitir `http.server.duration`) e logs (`LoggerProvider` + `LoggingHandler` acoplado ao `logging` padrão do Python, enviando os logs de aplicação via OTLP para o OTel Collector, que os roteia ao Loki).
  * Atualizados os arquivos `requirements.txt` com as dependências do OpenTelemetry API, SDK e exportadores OTLP.

### B. Stack de Monitoramento no Kubernetes via GitOps (ArgoCD)
* **Namespace `monitoring`:** Criado o manifesto [monitoring.yaml](gitops/namespaces/monitoring.yaml).
* **Prometheus e Grafana:** Criado o manifesto [application-prometheus.yaml](gitops/argocd/application-prometheus.yaml) apontando para o chart de Helm da comunidade `kube-prometheus-stack` (gerenciado pelo ArgoCD).
* **Loki e Promtail:** Criado o manifesto [application-loki.yaml](gitops/argocd/application-loki.yaml) apontando para `loki-stack` no Helm. O Promtail é executado como DaemonSet em cada nó do cluster EKS, coletando automaticamente todos os logs gravados no `stdout`/`stderr` de todos os pods.
* **OpenTelemetry Collector:** Criado o manifesto de implantação [otel-collector.yaml](gitops/apps/monitoring/otel-collector.yaml) e registrado no ArgoCD via [application-otel-collector.yaml](gitops/argocd/application-otel-collector.yaml). O collector atua como barramento central de telemetria dentro do cluster:
  * Recebe **traces, métricas e logs** via OTLP gRPC (porta 4317) e HTTP (porta 4318).
  * Pipeline de **traces**: exporta para a plataforma APM **New Relic** (via OTLP seguro).
  * Pipeline de **métricas**: expõe as métricas consolidadas em `/metrics` (porta 8889, exporter Prometheus com `resource_to_telemetry_conversion` para incluir o label `service_name`), coletadas pelo Prometheus através de um `ServiceMonitor`; as métricas também são replicadas ao New Relic.
  * Pipeline de **logs**: exporta os logs de aplicação recebidos via OTLP para o **Loki** (exporter `loki`, com `service.name` promovido a label de stream), cumprindo o papel de roteador central dos três sinais para os backends (Prometheus, Loki e APM).

### C. Configuração do Painel Grafana Customizado
* Criado o ConfigMap [dashboard-configmap.yaml](gitops/apps/monitoring/dashboard-configmap.yaml) com a especificação JSON do dashboard. Ele é injetado automaticamente na UI do Grafana graças ao sidecar do Prometheus Operator. O dashboard inclui:
  1. Uso de recursos do cluster (CPU e Memória de cada Namespace).
  2. Taxa de Requisições (QPS) e latência média por microsserviço, calculadas a partir da métrica `http_server_duration` exposta pelo OTel Collector (queries agregadas por `service_name`).
  3. Terminal de Logs em Tempo Real integrado diretamente ao banco do Loki para depuração instantânea de erros nos contêineres.

### D. Alertas Inteligentes e Autorrecuperação (Self-Healing)
* **Webhook Receiver de Self-Healing:** Criado um microsserviço minimalista em Python [self-healing-service](services/self-healing/app.py) rodando no cluster.
* **Segurança e RBAC:** Criado o arquivo [rbac.yaml](gitops/apps/self-healing/rbac.yaml) definindo uma `ServiceAccount` (`self-healing-sa`), `Role` e `RoleBinding` que limitam as permissões do pod a apenas listar, ler e aplicar patches em deployments no namespace `togglemaster`.
* **Deployment no ArgoCD:** Criados manifests de implantação [deployment.yaml](gitops/apps/self-healing/deployment.yaml) e [service.yaml](gitops/apps/self-healing/service.yaml) e registrado no ArgoCD em [application-self-healing.yaml](gitops/argocd/application-self-healing.yaml).
* **Pipeline de CI/CD:** Criado o pipeline [.github/workflows/ci-self-healing.yml](.github/workflows/ci-self-healing.yml) para compilar o Dockerfile, executar testes (`pytest`) e auditoria de segurança (`bandit`), enviar a imagem para o ECR e atualizar automaticamente o manifesto no GitOps via `yq` (mantendo o fluxo GitOps da esteira).
* **Regras de Alerta no Kubernetes:** Criado o manifesto [prometheus-rules.yaml](gitops/apps/monitoring/prometheus-rules.yaml) que registra a regra `AuthServiceHighErrorRate`. Se a taxa de erros HTTP 5xx do `auth-service` passar de 5% por mais de 10 segundos, o alerta dispara (`firing`).
* **Ligação Alerta -> Webhook:** Configuramos os Helm values em [application-prometheus.yaml](gitops/argocd/application-prometheus.yaml) para rotear os alertas do Alertmanager para a URL interna `http://self-healing-service.togglemaster.svc.cluster.local:8080/webhook`.

### E. Integração com PagerDuty (Gestão de Incidentes)
* **Plataforma escolhida:** PagerDuty — plano gratuito (até 5 usuários) com integração nativa com Alertmanager via Events API v2.
* **Configuração no Alertmanager:** Adicionado o receiver `pagerduty-critical` no [application-prometheus.yaml](gitops/argocd/application-prometheus.yaml). Quando um alerta de severidade `critical` é disparado, o Alertmanager cria automaticamente um **incidente de urgência alta** no PagerDuty com severity `critical`, descrição do alerta e metadados (`alertname`, `namespace`, `class: self-healing`, `group: togglemaster`).
* **Resolução automática:** Configurado `send_resolved: true` — quando o Self-Healing normaliza o serviço e o alerta sai do estado `firing`, o Alertmanager envia o evento de `resolve` e o incidente é **fechado automaticamente** no PagerDuty, sem intervenção humana.
* **Roteamento multi-receiver:** Utilizado o atributo `continue: true` nas rotas do Alertmanager para que alertas críticos sejam enviados simultaneamente para PagerDuty (incidente), Discord (ChatOps) e Self-Healing (remediação automática), garantindo visibilidade completa e ação imediata.

### F. Notificação ChatOps via Discord
* **Canal escolhido:** Discord — via webhook nativo integrado ao Alertmanager.
* **Configuração no Alertmanager:** Adicionado o receiver `discord-chatops` no [application-prometheus.yaml](gitops/argocd/application-prometheus.yaml). O Alertmanager envia uma notificação detalhada para o canal do Discord contendo o nome do alerta, severity, descrição e status (firing/resolved), permitindo que a equipe acompanhe incidentes em tempo real.
* **Notificações de Resolução:** Configurado `send_resolved: true` para que o canal também receba a notificação quando o incidente é resolvido automaticamente pelo Self-Healing.

### G. Segurança — API Key do New Relic em Kubernetes Secret
* **Secret criado:** Criado o manifesto [newrelic-secret.yaml](gitops/apps/monitoring/newrelic-secret.yaml) do tipo `Opaque` para armazenar a chave da API do New Relic.
* **OTel Collector atualizado:** Modificado o [otel-collector.yaml](gitops/apps/monitoring/otel-collector.yaml) para referenciar a chave via `secretKeyRef` e substituição de variável de ambiente (`${env:NEW_RELIC_API_KEY}`), eliminando a exposição de credenciais em plaintext no repositório.

---

## 2. Justificativas Técnicas das Decisões de Arquitetura

### A. Escolha do New Relic como APM Comercial
Optamos pelo **New Relic** em detrimento ao Datadog pelas seguintes razões:
1. **Compatibilidade OTLP Nativa:** O New Relic fornece endpoints OTLP nativos e seguros que aceitam cargas gRPC padrão diretamente. Isso simplifica drasticamente a configuração de exportação no OTel Collector.
2. **Arquitetura sem Agente Proprietário:** Não precisamos implantar o agente pesado do Datadog como DaemonSet em cada nó do cluster. Isso economizou significativamente memória RAM e CPU no cluster EKS.
3. **Gratuidade Estudantil/Developer:** O modelo de licenciamento de 100 GB/mês gratuitos do New Relic atende perfeitamente ao escopo acadêmico sem riscos de faturamento.

### B. O Papel Centralizador do OpenTelemetry Collector
Em vez de fazer cada aplicação conter a URL e a credencial do New Relic para enviar traces individuais para a internet, implementamos o **OTel Collector** no cluster como um gateway:
1. **Redução de Overhead de Rede:** As aplicações fazem conexões rápidas via localhost/rede local gRPC. O Collector gerencia em background o loteamento (`batch processor`) e a compressão antes de exportar os traces para o New Relic via internet.
2. **Segurança de Credenciais:** A chave de API do New Relic fica guardada em um único local seguro (no configmap/deployment do OTel Collector), eliminando a necessidade de expor credenciais nas configurações individuais de cada microsserviço.
3. **Múltiplos Destinos:** A telemetria é unificada. O OTel Collector recebe uma vez os dados das aplicações e distribui as métricas localmente para o Prometheus e os traces externamente para o New Relic.

### C. Arquitetura do Mecanismo de Self-Healing (Webhook Interno)
Para o requisito obrigatório de Self-Healing, em vez de criarmos scripts complexos externos (como AWS Lambda fora do cluster) ou acionarmos webhooks públicos que trariam riscos de segurança, implementamos o **Self-Healing Webhook** como um pod nativo interno:
1. **Princípio do Privilégio Mínimo (RBAC):** O pod roda com a `ServiceAccount` `self-healing-sa` que só tem permissões de leitura e patch em `deployments` dentro do namespace `togglemaster`. Ele não possui acesso a outros segredos ou namespaces.
2. **Rollout Restart Nativo:** O script Python utiliza a API oficial do Kubernetes para aplicar uma anotação de data/hora no template do pod do deployment. O Kubernetes detecta a mudança e gerencia de forma transparente uma reinicialização progressiva (Rolling Update), garantindo que a aplicação nunca fique fora do ar durante a mitigação.
3. **Integração Declarativa com Alertmanager:** Toda a configuração de ligação alerta-recuperação é mantida em código no repositório GitOps (Helm values e PrometheusRule), garantindo rastreabilidade e facilidade de manutenção.

### D. Centralização de Logs com Loki + Promtail
1. **Economia de Recursos:** O Loki indexa apenas os metadados (como namespace, pod, container), armazenando o conteúdo dos logs comprimido. Isso reduz drasticamente o consumo de memória RAM comparado ao Elasticsearch (stack ELK).
2. **Coleta Não Invasiva:** Ao utilizar o Promtail para raspar logs do `/var/log/pods` de cada nó, os microsserviços não precisam de bibliotecas pesadas de escrita ou de pacotes específicos. Basta gravarem logs estruturados no `stdout`/`stderr` do console e o Promtail cuida do resto de forma transparente.
3. **Arquitetura Híbrida de Logs:** Adotamos dois caminhos complementares até o Loki: o **Promtail** captura os logs de contêiner de *todos* os pods do cluster (incluindo componentes de infraestrutura que não controlamos), enquanto os **logs de aplicação** dos microsserviços Python são enviados via OTLP ao **OTel Collector**, que os roteia ao Loki com o label `service_name` — atendendo ao requisito do OTel como peça central de roteamento também para logs, com metadados mais ricos (correlação com trace).

### E. Dimensionamento de Recursos Controlado
Dado o limite estrito de **$100** do laboratório da AWS Academy, todos os recursos instalados via Helm charts (Prometheus Operator, Grafana, Loki e Promtail) foram limitados a valores baixos de consumo de CPU/Memória nas declarações do ArgoCD:
* Prometheus limits: 500m CPU / 512Mi RAM.
* Grafana limits: 250m CPU / 256Mi RAM.
* Loki limits: 250m CPU / 256Mi RAM.
Isso impede que a instalação da stack de observabilidade exaura os recursos dos nós `t3.medium` do cluster e cause travamentos ou cobranças excessivas de escala.

### F. Escolha do PagerDuty vs OpsGenie (Gestão de Incidentes)
Optamos pelo **PagerDuty** em detrimento ao OpsGenie pelas seguintes razões:
1. **Descontinuação do OpsGenie:** A Atlassian descontinuou o OpsGenie — encerrou a venda para novos clientes em 2025 e está migrando a base existente para o Jira Service Management. Não é mais possível criar novas contas, o que inviabiliza a ferramenta para um projeto novo. O PagerDuty, por outro lado, é um produto maduro, líder de mercado em incident response e com continuidade garantida.
2. **Plano Gratuito Suficiente para o Escopo:** O plano free do PagerDuty (até 5 usuários) cobre integralmente o requisito do desafio: receber eventos do Alertmanager via Events API v2, abrir incidentes automaticamente, notificar os responsáveis e resolver o incidente quando o alerta é normalizado. As limitações do free tier (escalation policies avançadas, analytics, SSO) não afetam nenhum requisito da Fase 4.
3. **Integração Nativa com Alertmanager:** O Prometheus Alertmanager possui suporte de primeira classe ao PagerDuty via o campo `pagerduty_configs` (Events API v2, autenticação por `routing_key`), sem necessidade de middleware ou adaptadores. A configuração é declarativa e direta nos Helm values, mantendo o fluxo GitOps.
4. **Ciclo de Vida Completo do Incidente:** Com `send_resolved: true`, o PagerDuty abre o incidente quando o alerta dispara (`trigger`) e o fecha automaticamente quando o Self-Healing restaura o serviço (`resolve`) — demonstrando o ciclo completo de detecção → remediação → resolução sem intervenção humana.

### G. Escolha do Discord para ChatOps
Optamos pelo **Discord** como canal de ChatOps pelas seguintes razões:
1. **Suporte Nativo no Alertmanager:** O Discord permite criar Incoming Webhooks em qualquer canal com poucos cliques, e o Alertmanager (≥ 0.25, incluso no kube-prometheus-stack) possui o receiver nativo `discord_configs`, que formata a notificação no padrão esperado pelo Discord (título, status firing/resolved e descrição do alerta) sem necessidade de adaptadores.
2. **Gratuidade Total:** Diferente do Slack (que limita o histórico de mensagens no plano gratuito) e do Teams (que requer licença Microsoft 365), o Discord é totalmente gratuito sem limitações de histórico ou integrações.
3. **Uso Acadêmico:** Muitos times de desenvolvimento acadêmico já utilizam Discord como ferramenta de comunicação, reduzindo a barreira de adoção.

---

## 3. Guia de Validação Prática

Para apresentar e validar o funcionamento da Fase 4 no vídeo de entrega:

1. **Commit e Push:** Faça o push das modificações para o seu repositório GitHub para acionar as pipelines de CI/CD.
2. **Verificar ArgoCD:** Acesse o painel do seu ArgoCD e certifique-se de que os novos Applications (`togglemaster-prometheus`, `togglemaster-loki`, `togglemaster-otel-collector` e `togglemaster-self-healing`) estão com status `Synced` e `Healthy`.
3. **Acessar Grafana:**
   * Obtenha a URL pública do LoadBalancer do Grafana: `kubectl get svc -n monitoring togglemaster-prometheus-grafana`
   * Faça login (Usuário: `admin` / Senha: `admin`).
   * Abra o dashboard **"ToggleMaster — Observability Dashboard"** e mostre os gráficos de CPU, Memória, QPS e o painel de logs ativos integrados ao Loki.
4. **Verificar Service Map e Traces no New Relic:**
   * Abra a interface do New Relic APM.
   * Navegue em **"Service Map"** para visualizar a árvore de interações entre os 5 microsserviços do ToggleMaster.
   * Realize uma chamada (ex: no `evaluation-service`) e abra o painel **"Distributed Tracing"** para detalhar a jornada da requisição (do `evaluation` -> `flag` -> `auth`).
5. **Demonstração do Self-Healing:**
   * Simule um incidente gerando requisições com falha propositadamente no `auth-service` ou injete erro em seu banco de dados.
   * Mostre o gráfico de erro subindo no Grafana.
   * Acompanhe a mudança de status do alerta `AuthServiceHighErrorRate` de `Pending` para `Firing`.
   * Monitore os logs do container do self-healing (`kubectl logs -n togglemaster -l app=self-healing-service`) e veja a detecção do alerta e a execução do patch.
   * Mostre os novos pods do `auth-service` iniciando no Kubernetes (`kubectl get pods -n togglemaster`) comprovando que a autorrecuperação automática mitigou a falha sem intervenção humana.
6. **Verificar Incidente no PagerDuty:**
   * Acesse o painel do PagerDuty (https://app.pagerduty.com) → **Incidents**.
   * Verifique que o alerta `AuthServiceHighErrorRate` criou automaticamente um incidente de urgência alta no serviço `togglemaster`.
   * Mostre os detalhes do incidente: descrição, severity `critical` e os custom details (`alertname`, `namespace`).
   * Após o Self-Healing atuar, mostre o incidente mudando para **Resolved** automaticamente.
7. **Verificar Notificação no Discord (ChatOps):**
   * Abra o canal do Discord configurado para receber alertas.
   * Verifique que a mensagem de alerta `firing` foi recebida com detalhes do incidente.
   * Após o Self-Healing resolver o problema, verifique que a mensagem `resolved` também foi recebida no canal.
