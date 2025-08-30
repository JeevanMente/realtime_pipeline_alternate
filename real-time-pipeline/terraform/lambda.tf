resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}-processor"
  retention_in_days = 14
  tags              = local.tags
}

resource "aws_lambda_function" "processor" {
  function_name = "${local.name}-processor"
  role          = aws_iam_role.lambda_role.arn

  # Pull code from S3 where we uploaded your existing zip
  s3_bucket        = aws_s3_bucket.artifacts.id
  s3_key           = aws_s3_object.lambda_pkg.key

  # ⬇️ Important: hash the SAME local zip to trigger updates on code change
  source_code_hash = filebase64sha256(local.lambda_zip_path)

  # Match the file INSIDE the zip: lambda_function.py → lambda_handler(...)
  handler = "lambda_function.lambda_handler"
  runtime = "python3.11"

  memory_size = var.lambda_memory_mb
  timeout     = var.lambda_timeout_s

  environment {
    variables = {
      TABLE_NAME            = aws_dynamodb_table.orders.name
      TOPIC_LARGE_ARN       = aws_sns_topic.large_orders.arn        # or your single alerts topic
      TOPIC_INVALID_ARN     = aws_sns_topic.invalid_txn.arn         # remove if not using invalid topic
      LARGE_ORDER_THRESHOLD = tostring(var.large_order_amount)
      LOG_LEVEL             = var.log_level
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
  tags       = local.tags
}

# SQS → Lambda event source
resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn                   = aws_sqs_queue.transactions.arn
  function_name                      = aws_lambda_function.processor.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 1
}
