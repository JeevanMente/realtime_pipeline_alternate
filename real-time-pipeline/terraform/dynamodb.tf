resource "aws_dynamodb_table" "orders" {
  name         = "${local.name}-orders"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S"
  }

  tags = local.tags
}
