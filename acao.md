# Plano de Ação: Execução da Fase 4 (Observabilidade e Self-Healing)

Este documento descreve as etapas para implementar a observabilidade completa e autorrecuperação no ecossistema do **ToggleMaster**.

## Etapas do Plano de Ação

- [ ] **1. Instrumentação de Código (OpenTelemetry)**
  - Adicionar bibliotecas OpenTelemetry nos microsserviços em Go (`auth` e `evaluation`) e em Python (`flag`, `targeting`, `analytics`).
  - Implementar o módulo `telemetry.go` / `telemetry.py` para inicializar a exportação de traces/métricas para o OTel Collector.
  - Instrumentar os roteadores HTTP (Flask e `net/http`) e propagar o contexto de trace nas chamadas entre microsserviços.

- [ ] **2. Provisionamento da Stack de Monitoramento no Kubernetes**
  - Configurar as aplicações do ArgoCD para os Helm charts do **Prometheus**, **Loki**, **Grafana** e **OpenTelemetry Collector** no namespace `monitoring`.
  - Configurar o OTel Collector para rotear métricas locais para o Prometheus, logs para o Loki e traces distribuídos para o APM comercial (New Relic).

- [ ] **3. Painel Grafana Customizado**
  - Desenvolver um Dashboard no Grafana unificando recursos do cluster (CPU/Memória), taxa de requisições por microsserviço (QPS), latência e exibição de logs em tempo real.

- [ ] **4. Alertas e Self-Healing**
  - Desenvolver o serviço `self-healing-service` (webhook receiver em Python).
  - Configurar as regras de alerta no Alertmanager e integrar notificações (ChatOps).
  - Configurar permissões de RBAC no Kubernetes para permitir que o webhook do self-healing reinicie os deployments afetados.

---

### Como prosseguir:
Por favor, revise o plano detalhado no artefato do sistema e confirme se deseja prosseguir para a execução. Assim que aprovado, começarei a criar as modificações nos microsserviços e manifestos GitOps.
