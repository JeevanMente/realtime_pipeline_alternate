resource "aws_sqs_queue" "dlq" {
  name                       = "${local.name}-tx-dlq"
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  tags                       = local.tags
}

resource "aws_sqs_queue" "transactions" {
  name                               = "${local.name}-tx"
  visibility_timeout_seconds         = var.lambda_timeout_s + 30
  sqs_managed_sse_enabled            = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
  tags = local.tags
}

# Restrictive resource policy (only same account may SendMessage; require TLS)
data "aws_caller_identity" "me" {}

resource "aws_sqs_queue_policy" "tx_policy" {
  queue_url = aws_sqs_queue.transactions.id
  policy    = data.aws_iam_policy_document.sqs_policy.json
}

data "aws_iam_policy_document" "sqs_policy" {
  statement {
    sid = "AllowAccountSend"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.transactions.arn]
    condition {
      test     = "ArnEquals"
      variable = "aws:PrincipalArn"
      values   = ["arn:aws:iam::${data.aws_caller_identity.me.account_id}:root"]
    }
  }

  statement {
    sid = "DenyInsecureTransport"
    effect = "Deny"
    principals { 
        type = "AWS"
        identifiers = ["*"] 
    }
    actions   = ["sqs:*"]
    resources = [aws_sqs_queue.transactions.arn]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}
