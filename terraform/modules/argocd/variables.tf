variable "chart_version" {
  type        = string
  description = "Versão fixa do chart argo-cd (evita drift)."
  default     = "7.7.16"
}

variable "admin_password" {
  type        = string
  description = "Senha em texto plano do admin do ArgoCD. Se vazio, usa a senha gerada automaticamente."
  default     = ""
  sensitive   = true
}
