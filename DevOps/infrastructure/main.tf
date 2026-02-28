terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  environment   = var.environment
  project_name  = "promptTrace"
  bucket_suffix = data.aws_caller_identity.current.account_id
}

data "aws_caller_identity" "current" {}
