# Alarms
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.name}-lambda-errors>=1"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  dimensions = { FunctionName = aws_lambda_function.processor.function_name }
  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "sqs_age_oldest" {
  alarm_name          = "${local.name}-sqs-age-oldest>=120s"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 120
  dimensions = { QueueName = aws_sqs_queue.transactions.name }
  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]
  tags          = local.tags
}

resource "aws_cloudwatch_metric_alarm" "ddb_throttles" {
  alarm_name          = "${local.name}-ddb-throttles>=1"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ThrottledRequests"
  namespace           = "AWS/DynamoDB"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  dimensions = { TableName = aws_dynamodb_table.orders.name }
  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]
  tags          = local.tags
}

# Composite alarm: if any of the above is ALARM, raise a single consolidated alarm
resource "aws_cloudwatch_composite_alarm" "pipeline_health" {
  alarm_name = "${local.name}-pipeline-health"
  alarm_rule = "ALARM(${aws_cloudwatch_metric_alarm.lambda_errors.alarm_name}) OR ALARM(${aws_cloudwatch_metric_alarm.sqs_age_oldest.alarm_name}) OR ALARM(${aws_cloudwatch_metric_alarm.ddb_throttles.alarm_name})"
  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]
  tags          = local.tags
}
