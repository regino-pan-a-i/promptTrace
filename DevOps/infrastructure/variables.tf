variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "interaction_handler_function_name" {
  description = "Name of the interaction handler Lambda function"
  type        = string
  default     = "promptTrace-interaction-handler"
}

variable "outcome_logger_function_name" {
  description = "Name of the outcome logger Lambda function"
  type        = string
  default     = "promptTrace-outcome-logger"
}
