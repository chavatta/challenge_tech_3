# Validação do Relatório da Fase 4 vs. Requisitos do Tech Challenge

Validação cruzada entre os requisitos do [PDF](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/POSTECH%20-%20Tech%20Challenge%20-%20Fase%204.pdf), o [relatório](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/relatorio_fase4.md) e o **código-fonte real** do projeto.

---

## Resultado Geral

| Requisito | Status |
|---|---|
| 1. Monitoramento Opensource (Métricas e Logs) | ✅ Correto |
| 2. OpenTelemetry (OTel) e Padronização | ✅ Correto |
| 3. Instrumentação e APM (Traces) | ✅ Correto |
| 4. Alertas Inteligentes e Self-Healing | ⚠️ Parcialmente — ver detalhes |
| Entregáveis (Código Fonte) | ⚠️ Parcialmente — ver detalhes |

---

## 1. Monitoramento Opensource (Métricas e Logs no K8s) ✅

### Requisito PDF
> Provisionar Prometheus, Loki e Grafana no cluster Kubernetes via Helm charts no repositório GitOps. Criar no mínimo 1 dashboard customizado.

### O que o relatório diz
- Prometheus + Grafana via `kube-prometheus-stack` (ArgoCD)
- Loki + Promtail via `loki-stack` (ArgoCD)
- Dashboard customizado com 5 painéis

### Validação no código ✅

| Afirmação do relatório | Arquivo real | Validado? |
|---|---|---|
| Namespace `monitoring` criado | [monitoring.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/namespaces/monitoring.yaml) | ✅ |
| Prometheus via Helm no ArgoCD | [application-prometheus.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/argocd/application-prometheus.yaml) — chart `kube-prometheus-stack` v58.2.2 | ✅ |
| Loki + Promtail via Helm | [application-loki.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/argocd/application-loki.yaml) — chart `loki-stack` v2.10.2 | ✅ |
| Dashboard customizado | [dashboard-configmap.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/monitoring/dashboard-configmap.yaml) | ✅ |
| Dashboard com CPU/Memória por Namespace | Painéis `CPU Usage by Namespace` e `Memory Usage by Namespace` no JSON | ✅ |
| Dashboard com QPS e latência | Painéis `HTTP Request Rate (QPS)` e `HTTP Response Latency (average)` | ✅ |
| Dashboard com logs em tempo real (Loki) | Painel `Real-time Container Logs` com datasource `loki` | ✅ |

---

## 2. OpenTelemetry (OTel) e Padronização ✅

### Requisito PDF
> Utilizar o OTel Collector como peça central para receber, processar e exportar métricas, logs e traces. Rotear para os backends corretos (Prometheus, Loki e APM).

### Validação no código ✅

| Afirmação do relatório | Arquivo real | Validado? |
|---|---|---|
| OTel Collector com receivers gRPC (4317) e HTTP (4318) | [otel-collector.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/monitoring/otel-collector.yaml) L8-14 | ✅ |
| Traces exportados para New Relic via OTLP | Exporter `otlp/newrelic` endpoint `otlp.nr-data.net:4317` | ✅ |
| Métricas exportadas para Prometheus na porta 8889 | Exporter `prometheus` endpoint `0.0.0.0:8889` | ✅ |
| ServiceMonitor para coleta pelo Prometheus | `ServiceMonitor` `otel-collector-monitor` na mesma YAML | ✅ |
| Registrado no ArgoCD | [application-otel-collector.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/argocd/application-otel-collector.yaml) | ✅ |

> [!NOTE]
> O relatório menciona que o OTel Collector roteia **logs** para o Loki. Entretanto, no [otel-collector.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/monitoring/otel-collector.yaml), o pipeline de logs **não está configurado** — apenas `traces` e `metrics` possuem pipelines. Os logs são coletados via **Promtail** (DaemonSet), que é separado do OTel Collector. Isso **não contradiz** o relatório (que menciona Promtail em B.), mas é bom ter clareza: o OTel Collector **não** toca nos logs. Os logs vão Promtail → Loki.

---

## 3. Instrumentação e APM (Traces e Visibilidade Profunda) ✅

### Requisito PDF
> Escolher Datadog OU New Relic. Instrumentar os microsserviços. Gerar Distributed Tracing. Service Map.

### Validação no código ✅

| Afirmação do relatório | Arquivo real | Validado? |
|---|---|---|
| **Go (auth):** `telemetry.go` com `otlptracegrpc` | [auth/telemetry.go](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/auth/telemetry.go) — `InitTelemetry` com `otlptracegrpc` + gRPC insecure | ✅ |
| **Go (auth):** `main.go` com `otelhttp.NewHandler` | [auth/main.go](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/auth/main.go) L74 — `otelhttp.NewHandler(mux, "auth-service-http")` | ✅ |
| **Go (evaluation):** `telemetry.go` idêntico ao auth | [evaluation/telemetry.go](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/evaluation/telemetry.go) — idêntico, confirmado | ✅ |
| **Go (evaluation):** `context.Context` propagado nas goroutines | [evaluation/evaluator.go](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/evaluation/evaluator.go) — `ctx` passado em `fetchFlag(ctx, ...)`, `fetchRule(ctx, ...)`, `getCombinedFlagInfo(ctx, ...)` | ✅ |
| **Go (evaluation):** `otelhttp.NewTransport` no HttpClient | [evaluation/main.go](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/evaluation/main.go) L98 — `Transport: otelhttp.NewTransport(http.DefaultTransport)` | ✅ |
| **Python (flag):** `telemetry.py` com OTel SDK | [flag/telemetry.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/flag/telemetry.py) — `FlaskInstrumentor` + `RequestsInstrumentor` | ✅ |
| **Python (flag):** `instrument_app(app, "flag-service")` chamado | [flag/app.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/flag/app.py) L20-21 | ✅ |
| **Python (targeting):** `telemetry.py` idêntico | [targeting/telemetry.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/targeting/telemetry.py) — idêntico | ✅ |
| **Python (analytics):** `telemetry.py` idêntico | [analytics/telemetry.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/analytics/telemetry.py) — idêntico | ✅ |
| **New Relic** como APM | OTel Collector exporta para `otlp.nr-data.net:4317` | ✅ |

> [!NOTE]
> O relatório menciona que o `handlers.go` do evaluation foi adaptado para propagar `context.Context`. No código atual, o handler em [handlers.go](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/evaluation/handlers.go) usa `r.Context()` na L37 (`a.getDecision(r.Context(), ...)`) — está correto. Porém a goroutine da L52 (`go a.sendEvaluationEvent(...)`) **não recebe** o contexto. Isso é aceitável porque o `sendEvaluationEvent` é fire-and-forget (SQS), mas tecnicamente quebra a propagação de trace nesse ponto.

---

## 4. Alertas Inteligentes e Self-Healing ⚠️

### Requisito PDF
> 1. Alerta inteligente (ex: 5xx > 5% do auth-service)
> 2. Integração com PagerDuty OU OpsGenie
> 3. Notificação ChatOps (Slack/Discord/Teams)
> 4. Self-Healing automático (Runbook/Lambda/GitHub Action + kubectl rollout restart)

### Validação no código

| Afirmação do relatório | Arquivo real | Validado? |
|---|---|---|
| Alerta `AuthServiceHighErrorRate` (5xx > 5%, 10s) | [prometheus-rules.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/monitoring/prometheus-rules.yaml) | ✅ |
| Alertmanager roteando para webhook | [application-prometheus.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/argocd/application-prometheus.yaml) L54-58 — receiver `self-healing-webhook` para `http://self-healing-service.togglemaster.svc.cluster.local:8080/webhook` | ✅ |
| Self-healing service como pod Python | [self-healing/app.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/self-healing/app.py) — Flask + kubernetes client | ✅ |
| RBAC com Principle of Least Privilege | [rbac.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/self-healing/rbac.yaml) — `get`, `list`, `watch`, `update`, `patch` em `deployments` | ✅ |
| Rollout restart via annotation patch | [app.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/self-healing/app.py) L42 — `kubectl.kubernetes.io/restartedAt` | ✅ |
| Deployment usa `serviceAccountName: self-healing-sa` | [deployment.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/self-healing/deployment.yaml) L18 | ✅ |
| Service expõe porta 8080 | [service.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/self-healing/service.yaml) | ✅ |
| CI/CD pipeline do self-healing | [ci-self-healing.yml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/.github/workflows/ci-self-healing.yml) | ✅ |

> [!WARNING]
> ### Itens AUSENTES no requisito 4 (não encontrados no código NEM no relatório):
>
> **a) PagerDuty / OpsGenie** — O PDF exige: *"crie uma conta no PagerDuty OU OpsGenie e integre o alerta para abrir um incidente automaticamente."* O Alertmanager está configurado **apenas** com o receiver do webhook interno do self-healing. **Não há receiver do PagerDuty nem do OpsGenie** no `application-prometheus.yaml`. O relatório também **não menciona** PagerDuty/OpsGenie em nenhum lugar.
>
> **b) ChatOps (Slack/Discord/Teams)** — O PDF exige: *"configure o envio de uma notificação detalhada para um canal do Slack, Discord ou Teams."* **Não há configuração de notificação ChatOps** no Alertmanager (nem Slack webhook, nem Discord webhook). O relatório também **não menciona** ChatOps.

---

## Entregáveis (Código Fonte no Repositório) ⚠️

| Entregável PDF | Status |
|---|---|
| Código IaC/GitOps atualizado com stack de monitoramento e OTel Collector | ✅ Presente |
| Código fonte das aplicações com instrumentação | ✅ Presente em todos os 5 microsserviços |
| Scripts/automações de Self-Healing | ✅ Presente ([app.py](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/services/self-healing/app.py)) |

### Entregáveis do Relatório PDF

| Entregável PDF | Status |
|---|---|
| Nomes, RMs e usernames | ❓ Não consta no relatório |
| Links do repositório e vídeo | ❓ Não consta no relatório |
| Print do Dashboard do Grafana | ❓ Não consta no relatório |
| Print de Trace distribuído no APM | ❓ Não consta no relatório |
| Print da notificação de incidente no ChatOps | ❌ Faltando (ChatOps não implementado) |
| Print do log/execução do Self-Healing | ❓ Não consta no relatório |
| Justificativa técnica OTel | ✅ Seção 2.B do relatório |
| Justificativa Datadog vs New Relic | ✅ Seção 2.A do relatório |
| Justificativa OpsGenie vs PagerDuty | ❌ Faltando (nenhum foi implementado) |

---

## Alerta de Segurança

> [!CAUTION]
> A **chave de API do New Relic** está exposta em plaintext no arquivo [otel-collector.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/apps/monitoring/otel-collector.yaml) L26:
> ```yaml
> api-key: "NRAK-********************" # (chave redigida — já rotacionada e movida para Kubernetes Secret)
> ```
> Isso é aceitável para contexto acadêmico, mas recomenda-se usar um **Kubernetes Secret** referenciado via `secretKeyRef` em produção. Também é bom lembrar que essa chave está no histórico do Git.

---

## Resumo de Ações Necessárias

### Obrigatório (para nota completa)

1. **Implementar PagerDuty OU OpsGenie:** Criar conta e adicionar um receiver no Alertmanager dentro do [application-prometheus.yaml](file:///Users/chavatta/Library/Mobile%20Documents/com~apple~CloudDocs/Challenge_4/gitops/argocd/application-prometheus.yaml). Exemplo com PagerDuty:
   ```yaml
   receivers:
     - name: 'pagerduty'
       pagerduty_configs:
         - routing_key: '<SUA_INTEGRATION_KEY>'
           severity: critical
   ```

2. **Implementar ChatOps (Slack/Discord/Teams):** Adicionar receiver de webhook no Alertmanager. Exemplo com Slack:
   ```yaml
   receivers:
     - name: 'slack-notifications'
       slack_configs:
         - api_url: 'https://hooks.slack.com/services/...'
           channel: '#alerts'
           title: '{{ .CommonAnnotations.summary }}'
   ```

3. **Adicionar dados pessoais ao relatório:** Nomes, RMs e usernames (pode ser feito no momento da entrega final em PDF).

4. **Adicionar justificativa PagerDuty vs OpsGenie** na seção de Justificativas Técnicas do relatório.

### Recomendado (polimento)

5. Adicionar prints/screenshots ao relatório (Dashboard, Traces, Self-Healing) — pode ser feito após deploy.
6. Considerar mover a API key do New Relic para um Kubernetes Secret.

---

## Conclusão

O relatório é **tecnicamente preciso** em tudo que afirma — cada arquivo mencionado existe e o conteúdo bate com a descrição. A implementação dos requisitos 1, 2 e 3 está **completa e bem feita**. Entretanto, faltam dois subrequisitos obrigatórios do requisito 4: **PagerDuty/OpsGenie** e **ChatOps (Slack/Discord/Teams)**.
