resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
  }
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.chart_version
  namespace  = kubernetes_namespace.argocd.metadata[0].name

  set {
    name  = "server.service.type"
    value = "LoadBalancer"
  }

  set {
    name  = "server.service.annotations.service\\.beta\\.kubernetes\\.io/aws-load-balancer-name"
    value = "togglemaster-argocd"
  }

  set {
    name  = "server.insecure"
    value = "true"
  }

  dynamic "set_sensitive" {
    for_each = var.admin_password != "" ? [var.admin_password] : []
    content {
      name  = "configs.secret.argocdServerAdminPassword"
      value = bcrypt(set_sensitive.value)
    }
  }

  lifecycle {
    ignore_changes = [set_sensitive]
  }

  timeout = 600
}
