locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

module "vpc" {
  source = "./modules/vpc"

  name_prefix          = local.name_prefix
  aws_region           = var.aws_region
  cluster_name         = "${local.name_prefix}-eks"
  availability_zones   = slice(data.aws_availability_zones.available.names, 0, 2)
  single_nat_gateway   = true
  enable_dns_hostnames = true
}

module "eks" {
  source = "./modules/eks"

  name_prefix       = local.name_prefix
  cluster_version   = var.eks_cluster_version
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids

  use_lab_role = var.use_lab_role
  lab_role_name = var.lab_role_name

  cluster_role_arn = var.eks_cluster_role_arn
  node_role_arn    = var.eks_node_role_arn

  node_instance_types = var.node_instance_types
  node_desired_size   = var.node_desired_size
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
}

module "security_groups" {
  source = "./modules/security_groups"

  name_prefix                     = local.name_prefix
  vpc_id                          = module.vpc.vpc_id
  eks_cluster_security_group_id   = module.eks.cluster_primary_security_group_id
}

module "rds" {
  source   = "./modules/rds"
  for_each = toset(var.rds_databases)

  name_prefix           = "${local.name_prefix}-${each.key}"
  instance_class        = var.rds_instance_class
  username              = var.db_username
  password              = var.db_password
  private_subnet_ids    = module.vpc.private_subnet_ids
  rds_security_group_id = module.security_groups.rds_security_group_id
}

module "elasticache" {
  source = "./modules/elasticache"

  name_prefix             = local.name_prefix
  node_type               = var.redis_node_type
  private_subnet_ids      = module.vpc.private_subnet_ids
  redis_security_group_id = module.security_groups.redis_security_group_id
}

module "dynamodb" {
  source = "./modules/dynamodb"

  name_prefix = local.name_prefix
  table_name  = "ToggleMasterAnalytics"
}

module "sqs" {
  source = "./modules/sqs"

  name_prefix = local.name_prefix
  queue_name  = "togglemaster-events"
}

module "ecr" {
  source   = "./modules/ecr"
  for_each = toset(var.ecr_repositories)

  repository_name = each.key
}

module "argocd" {
  count  = var.enable_argocd ? 1 : 0
  source = "./modules/argocd"

  depends_on = [module.eks]
}

# --- Kubernetes Secrets (senhas injetadas via pipeline, nunca commitadas) ---

resource "kubernetes_namespace" "togglemaster" {
  metadata {
    name = "togglemaster"
  }

  depends_on = [module.eks]
}

resource "kubernetes_secret" "auth_service" {
  metadata {
    name      = "auth-service-secret"
    namespace = kubernetes_namespace.togglemaster.metadata[0].name
  }

  data = {
    DATABASE_URL = "postgres://${var.db_username}:${var.db_password}@${module.rds["auth"].db_endpoint}:5432/toggledb?sslmode=require"
    MASTER_KEY   = var.master_key
  }

  depends_on = [module.eks, module.rds]
}

resource "kubernetes_secret" "flag_service" {
  metadata {
    name      = "flag-secret"
    namespace = kubernetes_namespace.togglemaster.metadata[0].name
  }

  data = {
    FLAG_DATABASE_URL = "postgres://${var.db_username}:${var.db_password}@${module.rds["flag"].db_endpoint}:5432/toggledb?sslmode=require"
  }

  depends_on = [module.eks, module.rds]
}

resource "kubernetes_secret" "targeting_service" {
  metadata {
    name      = "targeting-secret"
    namespace = kubernetes_namespace.togglemaster.metadata[0].name
  }

  data = {
    TARGETING_DATABASE_URL = "postgres://${var.db_username}:${var.db_password}@${module.rds["targeting"].db_endpoint}:5432/toggledb?sslmode=require"
  }

  depends_on = [module.eks, module.rds]
}

resource "kubernetes_secret" "evaluation_service" {
  metadata {
    name      = "evaluation-secret"
    namespace = kubernetes_namespace.togglemaster.metadata[0].name
  }

  data = {
    SERVICE_API_KEY = var.service_api_key
  }

  depends_on = [module.eks]
}
