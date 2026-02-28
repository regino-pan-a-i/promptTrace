resource "aws_s3_bucket" "eval_logs" {
  bucket = "ai-eval-logs-${local.environment}-${local.bucket_suffix}"

  tags = {
    Name        = "promptTrace Evaluation Logs"
    Environment = local.environment
    Project     = local.project_name
  }
}

resource "aws_s3_bucket_versioning" "eval_logs" {
  bucket = aws_s3_bucket.eval_logs.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "eval_logs" {
  bucket = aws_s3_bucket.eval_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "eval_logs" {
  bucket = aws_s3_bucket.eval_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "eval_logs" {
  bucket = aws_s3_bucket.eval_logs.id

  rule {
    id     = "delete-after-7-days"
    status = "Enabled"

    filter {}

    expiration {
      days = 7
    }
  }
}

resource "aws_s3_bucket_policy" "eval_logs" {
  bucket = aws_s3_bucket.eval_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyUnencryptedObjectUploads"
        Effect = "Deny"
        Principal = "*"
        Action = "s3:PutObject"
        Resource = "${aws_s3_bucket.eval_logs.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      }
    ]
  })
}
