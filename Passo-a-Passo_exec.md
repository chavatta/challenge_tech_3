# 🚀 Passo a Passo — Como Rodar e Validar o Ambiente ToggleMaster (Fase 4)

Este guia detalha como subir, configurar e validar todo o ambiente de observabilidade, alertas e self-healing do projeto ToggleMaster.

> **🎯 O serviço é 100% automatizado via GitFlow.** Basta configurar os secrets no GitHub (uma vez) e fazer push na `main`, ou usar o workflow de Bootstrap. Não é necessário rodar nenhum comando manual para deploy.

---

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Configurar GitHub Secrets (única vez)](#2-configurar-github-secrets-única-vez)
3. [Deploy Automático (Push na Main)](#3-deploy-automático-push-na-main)
4. [Deploy do Zero (Workflow Bootstrap)](#4-deploy-do-zero-workflow-bootstrap)
5. [Validar Stack de Monitoramento](#5-validar-stack-de-monitoramento)
6. [Validar Instrumentação e Traces (New Relic)](#6-validar-instrumentação-e-traces-new-relic)
7. [Validar Alertas e Self-Healing](#7-validar-alertas-e-self-healing)
8. [Validar PagerDuty (Gestão de Incidentes)](#8-validar-pagerduty-gestão-de-incidentes)
9. [Validar ChatOps (Discord)](#9-validar-chatops-discord)
10. [Checklist Final de Entrega](#10-checklist-final-de-entrega)

---

## 1. Pré-requisitos

### Ferramentas Necessárias (somente para validação local)
```bash
# Opcional — só precisa se for validar localmente via kubectl
aws --version          # AWS CLI v2
kubectl version        # kubectl compatível com EKS
```

> **💡 Nota:** Todas as ferramentas de build e deploy (Terraform, Helm, Docker, Git) rodam **dentro do GitHub Actions**. Você só precisa de `aws` e `kubectl` se quiser validar localmente.

### Contas e Acessos
- [x] AWS Academy Lab (com créditos disponíveis — orçamento de $100)
- [x] GitHub com repositório do ToggleMaster
- [x] Conta New Relic (plano gratuito: https://newrelic.com/signup)
- [x] Conta PagerDuty (plano gratuito: https://www.pagerduty.com/sign-up/)
- [x] Servidor Discord com permissão para criar Webhooks

---

## 2. Configurar GitHub Secrets (única vez)

> **⚠️ Esta é a ÚNICA configuração manual necessária.** Depois disso, tudo é automatizado.

### 2.1 Secrets já configurados (do Challenge 3)

| Secret | Descrição |
|---|---|
| `AWS_ACCESS_KEY_ID` | Credencial do AWS Academy Lab |
| `AWS_SECRET_ACCESS_KEY` | Credencial do AWS Academy Lab |
| `AWS_SESSION_TOKEN` | Token de sessão do Lab (renovar a cada sessão) |
| `TF_VAR_DB_PASSWORD` | Senha dos bancos RDS |
| `TF_VAR_ARGO_PASSWORD` | Senha do admin do ArgoCD |

### 2.2 Novos secrets da Fase 4

No GitHub, acesse **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Onde obter | Descrição |
|---|---|---|
| `PAGERDUTY_ROUTING_KEY` | PagerDuty → Service → Integrations → Events API v2 → Integration Key | Chave para abertura automática de incidentes críticos |
| `DISCORD_WEBHOOK_URL` | Discord → Canal → Configurações → Integrações → Webhooks → Copiar URL | URL completa do webhook (ex: `https://discord.com/api/webhooks/...`) |
| `NEW_RELIC_API_KEY` | New Relic → Profile → API Keys → chave do tipo **INGEST - LICENSE** | License Key de ingestão (40 chars, termina em `NRAL`) para envio de traces via OTLP. ⚠️ Não confundir com a User Key (`NRAK-...`), que NÃO funciona para ingestão |

### 2.3 Como obter cada credencial

#### PagerDuty
1. Crie a conta gratuita em https://www.pagerduty.com/sign-up/ (plano Free, até 5 usuários)
2. Acesse **Services** → **Service Directory** → **New Service**
   - Nome: `togglemaster` → em **Integrations**, selecione **Events API V2**
3. Após criar, abra o serviço → aba **Integrations** → copie a **Integration Key** (32 caracteres)
4. Adicione como GitHub Secret `PAGERDUTY_ROUTING_KEY`

#### Discord
1. No Discord, acesse o canal desejado → **Configurações** → **Integrações** → **Webhooks**
2. Clique em **Novo Webhook** → Nomeie (ex: `ToggleMaster Alerts`)
3. Copie a **URL do Webhook**
4. Adicione como GitHub Secret `DISCORD_WEBHOOK_URL`

#### New Relic
1. Acesse https://one.newrelic.com → **Profile** → **API Keys**
2. Localize a chave do tipo **INGEST - LICENSE** ("Original account license key") e copie (⋯ → *Copy key*)
   - ⚠️ **Atenção:** não use a User Key (prefixo `NRAK-`) — o endpoint OTLP `otlp.nr-data.net` só aceita a License Key de ingestão (40 caracteres, termina em `NRAL`)
3. Adicione como GitHub Secret `NEW_RELIC_API_KEY`

---

## 3. Deploy Automático (Push na Main)

O deploy é **100% automatizado via GitFlow**. Ao fazer push na branch `main`, os seguintes workflows rodam automaticamente:

### Fluxo de automação

```
Push na main
    │
    ├── ci-terraform.yml (se alterou terraform/ ou gitops/)
    │     ├── Terraform Plan + Apply (VPC, EKS, RDS, etc.)
    │     ├── Injetar secrets nos manifests (PagerDuty, Discord, New Relic)
    │     ├── kubectl apply namespaces + ArgoCD apps + monitoring + self-healing
    │     └── Rollout restart + verificação
    │
    ├── ci-auth.yml (se alterou services/auth/)
    │     └── Test → Build → Push ECR → Update GitOps manifest → ArgoCD sync
    │
    ├── ci-flag.yml (se alterou services/flag/)
    │     └── Test → Build → Push ECR → Update GitOps manifest → ArgoCD sync
    │
    ├── ci-evaluation.yml (se alterou services/evaluation/)
    │     └── Test → Build → Push ECR → Update GitOps manifest → ArgoCD sync
    │
    ├── ci-targeting.yml (se alterou services/targeting/)
    │     └── Test → Build → Push ECR → Update GitOps manifest → ArgoCD sync
    │
    ├── ci-analytics.yml (se alterou services/analytics/)
    │     └── Test → Build → Push ECR → Update GitOps manifest → ArgoCD sync
    │
    └── ci-self-healing.yml (se alterou services/self-healing/)
          └── Test → Build → Push ECR → Update GitOps manifest → ArgoCD sync
```

### O que acontece automaticamente:

1. **Terraform** provisiona toda a infraestrutura AWS (VPC, EKS, RDS, ElastiCache, DynamoDB, SQS, ECR, ArgoCD)
2. **Pipeline injeta** as API keys de PagerDuty, Discord e New Relic (de GitHub Secrets para os manifests K8s)
3. **Namespaces** `monitoring` e `togglemaster` são criados
4. **ArgoCD Applications** são registradas (Prometheus, Loki, OTel Collector, Self-Healing, microsserviços)
5. **Manifests de monitoring** são aplicados (OTel Collector, Dashboard Grafana, PrometheusRules, NewRelic Secret)
6. **Manifests de self-healing** são aplicados (RBAC, Deployment, Service)
7. **Pods são reiniciados** para aplicar novos secrets
8. **ArgoCD sincroniza** automaticamente via `selfHeal: true`

> **Resultado:** Zero intervenção manual. Basta fazer `git push origin main`.

---

## 4. Deploy do Zero (Workflow Bootstrap)

Para subir o ambiente completo do zero (ex: nova sessão do AWS Academy Lab):

1. No GitHub, acesse **Actions** → **🚀 Bootstrap — Deploy completo do zero**
2. Clique em **Run workflow**
3. Opções:
   - **Skip Terraform:** Marque se a infraestrutura já existe
   - **Skip Microservices:** Marque se as imagens já estão no ECR
4. Clique em **Run workflow**

O bootstrap executa em 3 fases:
1. **Fase 1 — Infraestrutura:** Terraform apply completo (~15 min)
2. **Fase 2 — Build:** Build + push de todos os 6 microsserviços em paralelo (~5 min)
3. **Fase 3 — Deploy GitOps:** Namespaces, ArgoCD, monitoring, self-healing, verificação (~3 min)

> **⏱️ Tempo total estimado: ~25 minutos do zero até ambiente 100% funcional.**

---

## 5. Validar Stack de Monitoramento

### 5.1 Verificar Pods de Monitoramento

```bash
# Configurar kubectl (se validando localmente)
aws eks update-kubeconfig --region us-east-1 --name togglemaster-dev-eks

# Prometheus, Grafana, Alertmanager
kubectl get pods -n monitoring -l app.kubernetes.io/instance=togglemaster-prometheus

# Loki + Promtail
kubectl get pods -n monitoring -l release=togglemaster-loki

# OTel Collector
kubectl get pods -n monitoring -l app=otel-collector

# Self-Healing
kubectl get pods -n togglemaster -l app=self-healing-service
```

### 5.2 Acessar Grafana

```bash
# Obter a URL pública do Grafana (LoadBalancer)
kubectl get svc -n monitoring togglemaster-prometheus-grafana -o wide
```

- **URL:** `http://<EXTERNAL-IP>` (porta 80)
- **Usuário:** `admin`
- **Senha:** `admin`

### 5.3 Verificar Dashboard Customizado

1. No Grafana, vá em **Dashboards** → **Browse**
2. Procure por **"ToggleMaster — Observability Dashboard"**
3. Verifique os 5 painéis:
   - ✅ CPU Usage by Namespace
   - ✅ Memory Usage by Namespace
   - ✅ HTTP Request Rate (QPS)
   - ✅ HTTP Response Latency (average)
   - ✅ Real-time Container Logs (fonte: Loki)

### 5.4 Verificar Datasources no Grafana

1. Vá em **Configuration** → **Data Sources**
2. Confirme que existem:
   - ✅ **Prometheus** (default)
   - ✅ **Loki** (para logs)

---

## 6. Validar Instrumentação e Traces (New Relic)

### 6.1 Gerar Tráfego

```bash
# Obter a URL do auth-service (ou evaluation-service)
kubectl get svc -n togglemaster

# Fazer requisições de teste
curl -X POST http://<AUTH_SERVICE_URL>/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"test"}'

# Repetir algumas vezes para gerar traces suficientes
for i in {1..10}; do
  curl -s http://<EVALUATION_SERVICE_URL>/evaluate \
    -H "Content-Type: application/json" \
    -d '{"flag_key":"test-flag","context":{"user_id":"user123"}}'
done
```

### 6.2 Verificar no New Relic

1. Acesse https://one.newrelic.com
2. Vá em **APM & Services** → Procure pelos serviços:
   - ✅ `auth-service`
   - ✅ `evaluation-service`
   - ✅ `flag-service`
   - ✅ `targeting-service`
   - ✅ `analytics-service`

### 6.3 Verificar Service Map

1. No New Relic, vá em **Service Map**
2. Verifique a árvore de dependências:
   - `evaluation-service` → `flag-service` → `auth-service`
   - `evaluation-service` → `targeting-service` → `auth-service`

### 6.4 Verificar Distributed Tracing

1. No New Relic, vá em **Distributed Tracing**
2. Clique em um trace para ver a jornada completa:
   - Span do `evaluation-service` (início)
   - Span do `flag-service` (chamada downstream)
   - Span do `auth-service` (validação de token)

> **📸 Print:** Faça um screenshot do Service Map e de um Distributed Trace para o relatório.

---

## 7. Validar Alertas e Self-Healing

### 7.1 Verificar Regra de Alerta

```bash
# Confirmar que a PrometheusRule existe
kubectl get prometheusrule -n monitoring

# Ver detalhes
kubectl describe prometheusrule togglemaster-alert-rules -n monitoring
```

### 7.2 Simular Incidente (Gerar Erros 5xx no auth-service)

```bash
# Opção 1: Fazer requisições que resultem em erro 500
# (ex: tentar autenticar com credenciais que causem erro interno)
for i in {1..100}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    http://<AUTH_SERVICE_URL>/some-invalid-endpoint
done

# Opção 2: Escalar para zero replicas e depois restaurar (simula crash)
kubectl scale deployment auth-service -n togglemaster --replicas=0
sleep 30
kubectl scale deployment auth-service -n togglemaster --replicas=1
```

### 7.3 Acompanhar o Alerta

```bash
# Verificar status dos alertas no Prometheus (via port-forward)
kubectl port-forward svc/togglemaster-prometheus-kube-prometheus 9090:9090 -n monitoring &

# Acessar http://localhost:9090/alerts
# Verificar AuthServiceHighErrorRate: Pending → Firing
```

### 7.4 Verificar Self-Healing em Ação

```bash
# Monitorar logs do self-healing service em tempo real
kubectl logs -n togglemaster -l app=self-healing-service -f

# Esperado: mensagens como:
# "Webhook received payload: ..."
# "Handling firing alert: AuthServiceHighErrorRate for service: auth-service"
# "Triggering rollout restart for deployment/auth-service in namespace togglemaster..."
# "Rollout restart patch successfully applied to deployment/auth-service."

# Verificar que novos pods estão subindo
kubectl get pods -n togglemaster -w
```

> **📸 Print:** Faça um screenshot dos logs do self-healing mostrando a detecção e ação automática.

---

## 8. Validar PagerDuty (Gestão de Incidentes)

### 8.1 Verificar Incidente Criado

1. Acesse https://app.pagerduty.com → **Incidents**
2. Verifique que o alerta `AuthServiceHighErrorRate` criou um incidente no serviço `togglemaster` com:
   - **Urgência:** High (severity `critical`)
   - **Título:** "High 5xx error rate on auth-service"
   - **Custom Details:** `alertname`, `namespace` e descrição do erro
3. Após o Self-Healing restaurar o serviço, verifique que o incidente muda para **Resolved** automaticamente (`send_resolved: true`)

### 8.2 Verificar Alertmanager Routing

```bash
# Verificar configuração do Alertmanager
kubectl port-forward svc/togglemaster-prometheus-kube-alertmanager 9093:9093 -n monitoring &

# Acessar http://localhost:9093/#/status
# Verificar receivers: self-healing-webhook, pagerduty-critical, discord-chatops
```

> **📸 Print:** Faça um screenshot do incidente aberto (triggered) e resolvido (resolved) no PagerDuty.

---

## 9. Validar ChatOps (Discord)

### 9.1 Verificar Notificação no Canal

1. Abra o canal do Discord configurado para receber alertas
2. Verifique que a mensagem de alerta `firing` foi recebida com:
   - Nome do alerta: `AuthServiceHighErrorRate`
   - Status: `firing`
   - Descrição do incidente

### 9.2 Verificar Notificação de Resolução

1. Após o Self-Healing resolver o problema (rollout restart concluído)
2. Verifique que uma mensagem `resolved` apareceu no canal

> **📸 Print:** Faça um screenshot das mensagens de alerta (firing + resolved) no Discord.

---

## 10. Checklist Final de Entrega

### Automação via GitFlow

| # | Item | Como é automatizado |
|---|---|---|
| 1 | Infraestrutura AWS | `ci-terraform.yml` → Terraform Apply |
| 2 | Kubernetes Secrets | Terraform `main.tf` (auth, flag, targeting, evaluation) |
| 3 | ArgoCD Applications | `ci-terraform.yml` → `kubectl apply -f gitops/argocd/` |
| 4 | Monitoring stack | `ci-terraform.yml` → `kubectl apply -f gitops/apps/monitoring/` |
| 5 | Self-Healing deploy | `ci-terraform.yml` → `kubectl apply -f gitops/apps/self-healing/` |
| 6 | PagerDuty Routing Key | GitHub Secret → `sed` no pipeline → `application-prometheus.yaml` |
| 7 | Discord Webhook | GitHub Secret → `sed` no pipeline → `application-prometheus.yaml` |
| 8 | New Relic API Key | GitHub Secret → `sed` no pipeline → `newrelic-secret.yaml` |
| 9 | Build microsserviços | `ci-*.yml` → Build → ECR → GitOps commit → ArgoCD sync |
| 10 | Bootstrap do zero | `ci-bootstrap.yml` → workflow_dispatch (1 clique) |

### Entregáveis de Código

| # | Item | Comando de Verificação |
|---|---|---|
| 1 | Prometheus + Grafana no cluster | `kubectl get pods -n monitoring -l app.kubernetes.io/instance=togglemaster-prometheus` |
| 2 | Loki + Promtail no cluster | `kubectl get pods -n monitoring -l release=togglemaster-loki` |
| 3 | OTel Collector no cluster | `kubectl get pods -n monitoring -l app=otel-collector` |
| 4 | Dashboard customizado no Grafana | Grafana UI → Dashboards → "ToggleMaster" |
| 5 | Instrumentação OTel nos 5 microsserviços | New Relic → APM → 5 services |
| 6 | Distributed Tracing no New Relic | New Relic → Distributed Tracing |
| 7 | Alerta `AuthServiceHighErrorRate` | `kubectl get prometheusrule -n monitoring` |
| 8 | Self-Healing automático | `kubectl logs -n togglemaster -l app=self-healing-service` |
| 9 | PagerDuty integrado | PagerDuty → Incidents (incidente criado e resolvido) |
| 10 | Discord ChatOps | Canal Discord (mensagem firing + resolved) |

### Entregáveis do Relatório

| # | Item | Status |
|---|---|---|
| 1 | Nomes, RMs e usernames | ⬜ Preencher em `relatorio_fase4.md` |
| 2 | Links do repositório e vídeo | ⬜ Preencher em `relatorio_fase4.md` |
| 3 | Print do Dashboard Grafana | ⬜ Fazer após deploy |
| 4 | Print de Distributed Trace no New Relic | ⬜ Fazer após deploy |
| 5 | Print de incidente no PagerDuty | ⬜ Fazer após simulação |
| 6 | Print de notificação no Discord | ⬜ Fazer após simulação |
| 7 | Print do log/execução do Self-Healing | ⬜ Fazer após simulação |
| 8 | Justificativa New Relic vs Datadog | ✅ Seção 2.A |
| 9 | Justificativa OTel Collector | ✅ Seção 2.B |
| 10 | Justificativa PagerDuty vs OpsGenie | ✅ Seção 2.F |

---

## Troubleshooting

### Pods não iniciam em `monitoring`
```bash
kubectl describe pod <POD_NAME> -n monitoring
kubectl get events -n monitoring --sort-by='.metadata.creationTimestamp'
```

### Alertmanager não envia para PagerDuty
```bash
# Verificar configuração ativa do Alertmanager
kubectl exec -it -n monitoring \
  $(kubectl get pod -n monitoring -l app.kubernetes.io/name=alertmanager -o jsonpath='{.items[0].metadata.name}') \
  -- cat /etc/alertmanager/config/alertmanager.yaml
```

### OTel Collector não envia traces
```bash
# Verificar logs do OTel Collector
kubectl logs -n monitoring -l app=otel-collector

# Verificar se o Secret foi montado
kubectl exec -it -n monitoring \
  $(kubectl get pod -n monitoring -l app=otel-collector -o jsonpath='{.items[0].metadata.name}') \
  -- env | grep NEW_RELIC
```

### Grafana sem dados
```bash
# Verificar se o Prometheus está raspando métricas
kubectl port-forward svc/togglemaster-prometheus-kube-prometheus 9090:9090 -n monitoring &
# Acessar http://localhost:9090/targets — verificar se todos estão UP
```

### GitHub Actions falha
```bash
# Verificar se os secrets estão configurados
# GitHub → Settings → Secrets → Verifique todos os 8 secrets listados na Seção 2
```
