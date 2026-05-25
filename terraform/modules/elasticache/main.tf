resource "aws_elasticache_subnet_group" "this" {
  name       = replace("${var.name_prefix}-redis-subnet", "_", "-")
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.name_prefix}-redis-subnet"
  }
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = replace("${var.name_prefix}-redis", "_", "-")
  description                = "Redis ToggleMaster"
  engine                     = "redis"
  engine_version             = var.engine_version
  node_type                  = var.node_type
  num_cache_clusters         = var.num_cache_nodes
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [var.redis_security_group_id]
  automatic_failover_enabled = var.num_cache_nodes > 1
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false

  tags = {
    Name = "${var.name_prefix}-redis"
  }
}
