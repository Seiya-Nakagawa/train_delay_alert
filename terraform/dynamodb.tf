resource "aws_dynamodb_table" "users" {
  name         = "${local.name_prefix}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "line_user_id"
  deletion_protection_enabled = true
  attribute {
    name = "line_user_id"
    type = "S"
  }

  ttl {
    enabled        = true
    attribute_name = "ttl"
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-users"
  })
}

resource "aws_dynamodb_table" "train_status" {
  name         = "${local.name_prefix}-train-status"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "route_id"
  deletion_protection_enabled = true
  attribute {
    name = "route_id"
    type = "S"
  }

  ttl {
    enabled        = true
    attribute_name = "ttl"
  }

  server_side_encryption {
    enabled = true
  }
  tags = merge(local.tags, {
    Name = "${local.name_prefix}-train-status"
  })
}