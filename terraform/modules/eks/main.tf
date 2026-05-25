data "aws_iam_role" "lab_role" {
  count = var.use_lab_role ? 1 : 0
  name  = var.lab_role_name
}

locals {
  cluster_role_arn = var.use_lab_role ? data.aws_iam_role.lab_role[0].arn : var.cluster_role_arn
  node_role_arn    = var.use_lab_role ? data.aws_iam_role.lab_role[0].arn : var.node_role_arn
}

resource "aws_eks_cluster" "this" {
  name     = "${var.name_prefix}-eks"
  role_arn = local.cluster_role_arn
  version  = var.cluster_version

  vpc_config {
    subnet_ids              = concat(var.private_subnet_ids, var.public_subnet_ids)
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.public_access_cidrs
  }

  tags = {
    Name = "${var.name_prefix}-eks"
  }
}

resource "aws_launch_template" "eks_nodes" {
  name_prefix = "${var.name_prefix}-eks-ng-"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tags = {
    Name = "${var.name_prefix}-eks-ng-lt"
  }
}

resource "aws_eks_node_group" "this" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name_prefix}-eks-ng"
  node_role_arn   = local.node_role_arn
  subnet_ids      = var.private_subnet_ids

  launch_template {
    id      = aws_launch_template.eks_nodes.id
    version = aws_launch_template.eks_nodes.latest_version
  }

  scaling_config {
    desired_size = var.node_desired_size
    max_size     = var.node_max_size
    min_size     = var.node_min_size
  }

  instance_types = var.node_instance_types

  update_config {
    max_unavailable = 1
  }

  tags = {
    Name = "${var.name_prefix}-eks-ng"
  }
}
