# Archive the Lambda function code
data "archive_file" "interaction_handler_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../interaction-handler"
  output_path = "${path.module}/.terraform/interaction-handler.zip"
}

data "archive_file" "outcome_logger_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../outcome-logger"
  output_path = "${path.module}/.terraform/outcome-logger.zip"
}

data "archive_file" "metrics_calculator_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../metrics-calculator"
  output_path = "${path.module}/.terraform/metrics-calculator.zip"
}

# Lambda function: Interaction Handler
resource "aws_lambda_function" "interaction_handler" {
  filename      = data.archive_file.interaction_handler_zip.output_path
  function_name = var.interaction_handler_function_name
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  timeout       = 60

  source_code_hash = data.archive_file.interaction_handler_zip.output_base64sha256

  environment {
    variables = {
      MODEL_ID    = "anthropic.claude-3-5-haiku-20241022"
      LOG_BUCKET  = aws_s3_bucket.eval_logs.id
      ENVIRONMENT = local.environment
    }
  }

  tags = {
    Name        = "promptTrace Interaction Handler"
    Environment = local.environment
    Project     = local.project_name
  }
}

# Lambda function: Outcome Logger
resource "aws_lambda_function" "outcome_logger" {
  filename      = data.archive_file.outcome_logger_zip.output_path
  function_name = var.outcome_logger_function_name
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  timeout       = 30

  source_code_hash = data.archive_file.outcome_logger_zip.output_base64sha256

  environment {
    variables = {
      LOG_BUCKET  = aws_s3_bucket.eval_logs.id
      ENVIRONMENT = local.environment
    }
  }

  tags = {
    Name        = "promptTrace Outcome Logger"
    Environment = local.environment
    Project     = local.project_name
  }
}

# Lambda function: Metrics Calculator
resource "aws_lambda_function" "metrics_calculator" {
  filename      = data.archive_file.metrics_calculator_zip.output_path
  function_name = var.metrics_calculator_function_name
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  timeout       = 120  # Extended timeout for reading and processing multiple logs

  source_code_hash = data.archive_file.metrics_calculator_zip.output_base64sha256

  environment {
    variables = {
      LOG_BUCKET  = aws_s3_bucket.eval_logs.id
      ENVIRONMENT = local.environment
    }
  }

  tags = {
    Name        = "promptTrace Metrics Calculator"
    Environment = local.environment
    Project     = local.project_name
  }
}

# API Gateway permission for interaction-handler
resource "aws_lambda_permission" "allow_api_gateway_interact" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.interaction_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.prompttrace_api.execution_arn}/*/*"
}

# API Gateway permission for outcome-logger
resource "aws_lambda_permission" "allow_api_gateway_outcome" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.outcome_logger.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.prompttrace_api.execution_arn}/*/*"
}

# API Gateway permission for metrics-calculator
resource "aws_lambda_permission" "allow_api_gateway_finalize" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.metrics_calculator.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.prompttrace_api.execution_arn}/*/*"
}
