############################################
# iam.tf — Lambda execution role & policy
############################################

# Assume-role trust policy for Lambda
data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "${local.name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
  tags               = local.tags
}

# Inline least-privilege policy for the Lambda function
data "aws_iam_policy_document" "lambda_inline" {
  # CloudWatch Logs
  statement {
    sid       = "LogsBasic"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"]
  }

  # SQS polling done on your function's role (for event source mapping)
  statement {
    sid = "SQSRead"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:ChangeMessageVisibility"
    ]
    resources = [
      aws_sqs_queue.transactions.arn
    ]
  }

  # DynamoDB write
  statement {
    sid       = "DynamoDBPutItem"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.orders.arn]
  }

  # Publish to business topics used by Lambda
  statement {
    sid     = "SNSPublishBusinessTopics"
    actions = ["sns:Publish"]
    resources = [
      aws_sns_topic.large_orders.arn,
      aws_sns_topic.invalid_txn.arn
    ]
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name   = "${local.name}-lambda-inline"
  policy = data.aws_iam_policy_document.lambda_inline.json
}

resource "aws_iam_role_policy_attachment" "lambda_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}
