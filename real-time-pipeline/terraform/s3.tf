# Artifacts bucket (unchanged)
resource "aws_s3_bucket" "artifacts" {
  bucket = "${local.name}-artifacts-${random_id.suffix.hex}"
  tags   = local.tags
}

resource "random_id" "suffix" {
  byte_length = 3
}

resource "aws_s3_bucket_versioning" "artifacts_v" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration { status = "Enabled" }
}

# ⬇️ REMOVE the archive_file data source (we're not re-zipping)
# data "archive_file" "lambda_zip" { ... }  ← delete this whole block

# ⬇️ USE your existing zip file on disk
# NOTE: keep forward slashes for portability (works on Windows too)
locals {
  lambda_zip_path = "${path.module}/../src/lambda/lambda_function.zip"
}

resource "aws_s3_object" "lambda_pkg" {
  bucket = aws_s3_bucket.artifacts.id
  key    = "lambda/${local.name}/lambda_function.zip"
  source = local.lambda_zip_path
  etag   = filemd5(local.lambda_zip_path)
  tags   = local.tags
}
