# FraudGuard — AWS Terraform Variables

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Target AWS Region for FraudGuard infrastructure"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment"
}
