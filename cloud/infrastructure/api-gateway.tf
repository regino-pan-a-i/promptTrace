resource "aws_api_gateway_rest_api" "prompttrace_api" {
  name        = "promptTrace-${local.environment}-api"
  description = "PromptTrace evaluation API"

  tags = {
    Name        = "promptTrace API"
    Environment = local.environment
    Project     = local.project_name
  }
}

# Interact endpoint
resource "aws_api_gateway_resource" "interact" {
  rest_api_id = aws_api_gateway_rest_api.prompttrace_api.id
  parent_id   = aws_api_gateway_rest_api.prompttrace_api.root_resource_id
  path_part   = "interact"
}

resource "aws_api_gateway_method" "interact_post" {
  rest_api_id      = aws_api_gateway_rest_api.prompttrace_api.id
  resource_id      = aws_api_gateway_resource.interact.id
  http_method      = "POST"
  authorization    = "NONE"
  request_models = {
    "application/json" = aws_api_gateway_model.interact_request.id
  }
  request_validator_id = aws_api_gateway_request_validator.all.id
}

resource "aws_api_gateway_integration" "interact_lambda" {
  rest_api_id      = aws_api_gateway_rest_api.prompttrace_api.id
  resource_id      = aws_api_gateway_resource.interact.id
  http_method      = aws_api_gateway_method.interact_post.http_method
  type             = "AWS_PROXY"
  integration_http_method = "POST"
  uri              = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${var.interaction_handler_function_name}/invocations"
  timeout_milliseconds = 30000

  depends_on = [aws_api_gateway_method.interact_post]
}

# Interaction-outcome endpoint
resource "aws_api_gateway_resource" "interaction_outcome" {
  rest_api_id = aws_api_gateway_rest_api.prompttrace_api.id
  parent_id   = aws_api_gateway_rest_api.prompttrace_api.root_resource_id
  path_part   = "interaction-outcome"
}

resource "aws_api_gateway_method" "interaction_outcome_post" {
  rest_api_id      = aws_api_gateway_rest_api.prompttrace_api.id
  resource_id      = aws_api_gateway_resource.interaction_outcome.id
  http_method      = "POST"
  authorization    = "NONE"
  request_models = {
    "application/json" = aws_api_gateway_model.outcome_request.id
  }
  request_validator_id = aws_api_gateway_request_validator.all.id
}

resource "aws_api_gateway_integration" "interaction_outcome_lambda" {
  rest_api_id      = aws_api_gateway_rest_api.prompttrace_api.id
  resource_id      = aws_api_gateway_resource.interaction_outcome.id
  http_method      = aws_api_gateway_method.interaction_outcome_post.http_method
  type             = "AWS_PROXY"
  integration_http_method = "POST"
  uri              = "arn:aws:apigateway:${var.aws_region}:lambda:path/2015-03-31/functions/${var.outcome_logger_function_name}/invocations"
  timeout_milliseconds = 30000

  depends_on = [aws_api_gateway_method.interaction_outcome_post]
}

# Request validators
resource "aws_api_gateway_request_validator" "all" {
  name                        = "all"
  rest_api_id                 = aws_api_gateway_rest_api.prompttrace_api.id
  validate_request_body       = true
  validate_request_parameters = false
}

# Request models
resource "aws_api_gateway_model" "interact_request" {
  rest_api_id  = aws_api_gateway_rest_api.prompttrace_api.id
  name         = "InteractRequest"
  content_type = "application/json"

  schema = jsonencode({
    type = "object"
    properties = {
      candidateToken = { type = "string" }
      taskId         = { type = "string" }
      userMessage    = { type = "string" }
      context = {
        type = "object"
        properties = {
          files = { type = "array" }
          selection = { type = "string" }
          projectSummary = { type = "string" }
        }
      }
    }
    required = ["candidateToken", "taskId", "userMessage", "context"]
  })
}

resource "aws_api_gateway_model" "outcome_request" {
  rest_api_id  = aws_api_gateway_rest_api.prompttrace_api.id
  name         = "OutcomeRequest"
  content_type = "application/json"

  schema = jsonencode({
    type = "object"
    properties = {
      candidateToken = { type = "string" }
      taskId         = { type = "string" }
      requestId      = { type = "string" }
      decisions      = { type = "array" }
      metrics = {
        type = "object"
        properties = {
          testsRun    = { type = "integer" }
          testsPassed = { type = "integer" }
          timeToDecisionMs = { type = "integer" }
        }
      }
    }
    required = ["candidateToken", "taskId", "requestId", "decisions"]
  })
}

# Deployment
resource "aws_api_gateway_deployment" "prompttrace" {
  rest_api_id = aws_api_gateway_rest_api.prompttrace_api.id
  stage_name  = local.environment

  depends_on = [
    aws_api_gateway_integration.interact_lambda,
    aws_api_gateway_integration.interaction_outcome_lambda
  ]
}
