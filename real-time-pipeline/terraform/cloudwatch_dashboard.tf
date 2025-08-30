resource "aws_cloudwatch_dashboard" "rt_dashboard" {
  count          = var.dashboard_enabled ? 1 : 0
  dashboard_name = "${local.name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        "type": "metric", "x": 0, "y": 0, "width": 12, "height": 6,
        "properties": {
          "title": "Lambda Invocations & Errors",
          "region": var.aws_region,
          "view": "timeSeries",
          "metrics": [
            [ "AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.processor.function_name ],
            [ ".", "Errors", ".", "." ]
          ],
          "stacked": false
        }
      },
      {
        "type": "metric", "x": 12, "y": 0, "width": 12, "height": 6,
        "properties": {
          "title": "SQS Queue Depth & Age",
          "region": var.aws_region,
          "view": "timeSeries",
          "metrics": [
            [ "AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.transactions.name ],
            [ ".", "ApproximateAgeOfOldestMessage", ".", "." ]
          ]
        }
      },
      {
        "type": "metric", "x": 0, "y": 6, "width": 12, "height": 6,
        "properties": {
          "title": "DynamoDB ThrottledRequests",
          "region": var.aws_region,
          "view": "timeSeries",
          "metrics": [
            [ "AWS/DynamoDB", "ThrottledRequests", "TableName", aws_dynamodb_table.orders.name ]
          ]
        }
      }
    ]
  })
}
