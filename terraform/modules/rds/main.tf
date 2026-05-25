resource "aws_db_subnet_group" "this" {
  name_prefix = "${replace(var.name_prefix, "_", "-")}-db-subnet-"
  subnet_ids  = var.private_subnet_ids

  tags = {
    Name = "${var.name_prefix}-db-subnet"
  }
}

resource "aws_db_instance" "this" {
  identifier                 = replace(var.name_prefix, "_", "-")
  engine                     = "postgres"
  engine_version             = var.engine_version
  instance_class             = var.instance_class
  allocated_storage          = var.allocated_storage
  db_name                    = var.db_name
  username                   = var.username
  password                   = var.password
  skip_final_snapshot        = var.skip_final_snapshot
  publicly_accessible        = false
  vpc_security_group_ids     = [var.rds_security_group_id]
  db_subnet_group_name       = aws_db_subnet_group.this.name
  backup_retention_period    = var.backup_retention_period
  deletion_protection        = var.deletion_protection
  auto_minor_version_upgrade = true

  tags = {
    Name = "${var.name_prefix}-db"
  }
}
