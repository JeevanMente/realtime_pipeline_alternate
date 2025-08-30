# (keeps your existing alerts + alarms; adds large_orders + invalid_txn)

# Optional: a generic business alerts topic you already had
resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email != null && var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# === NEW: Large orders topic (matches lambda.tf → TOPIC_LARGE_ARN) ===
resource "aws_sns_topic" "large_orders" {
  name = "${local.name}-large-orders"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "large_orders_email" {
  count     = var.alert_email != null && var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.large_orders.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# === NEW: Invalid transactions topic (matches lambda.tf → TOPIC_INVALID_ARN) ===
resource "aws_sns_topic" "invalid_txn" {
  name = "${local.name}-invalid-txn"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "invalid_txn_email" {
  count     = var.invalid_email != null && var.invalid_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.invalid_txn.arn
  protocol  = "email"
  endpoint  = var.invalid_email
}

# Ops alarms (unchanged)
resource "aws_sns_topic" "alarms" {
  name = "${local.name}-alarms"
  tags = local.tags
}

resource "aws_sns_topic_subscription" "alarms_email" {
  count     = var.alarm_email != null && var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}
