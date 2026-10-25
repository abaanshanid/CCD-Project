resource "aws_dynamodb_table" "batches" {
  name         = "${var.project_name}-batches-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "batchId"
  range_key = "itemId"

  attribute {
    name = "batchId"
    type = "S"
  }

  attribute {
    name = "itemId"
    type = "S"
  }

  ttl {
    attribute_name = "expiresAt"
    enabled        = true
  }
}