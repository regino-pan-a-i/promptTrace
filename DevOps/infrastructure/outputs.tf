output "api_endpoint_url" {
  description = "API Gateway endpoint URL (will be available once Lambda functions are deployed)"
  value       = "Pending: Deploy Lambda functions and uncomment integrations/deployment in api-gateway.tf"
}

output "logs_bucket_name" {
  description = "S3 bucket for storing interaction and outcome logs"
  value       = aws_s3_bucket.eval_logs.id
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = aws_iam_role.lambda_execution_role.arn
}

output "bedrock_model_id" {
  description = "Claude Haiku model ID"
  value       = "anthropic.claude-3-5-haiku-20241022"
}
