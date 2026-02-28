resource "aws_iam_role" "lambda_execution_role" {
  name = "promptTrace-lambda-execution-role-${local.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "promptTrace Lambda Execution Role"
    Environment = local.environment
    Project     = local.project_name
  }
}

resource "aws_iam_role_policy" "lambda_s3_policy" {
  name   = "promptTrace-lambda-s3-policy"
  role   = aws_iam_role.lambda_execution_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.eval_logs.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.eval_logs.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_bedrock_policy" {
  name   = "promptTrace-lambda-bedrock-policy"
  role   = aws_iam_role.lambda_execution_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-5-haiku-20241022"
      }
    ]
  })
}
