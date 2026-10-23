# FraudGuard — AWS Terraform Variables (eu-north-1 Serverless Architecture)

variable "aws_region" {
  type        = string
  default     = "eu-north-1"
  description = "Target AWS Region for FraudGuard infrastructure (Stockholm)"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment (dev, staging, production)"
}

variable "dynamodb_table_name" {
  type        = string
  default     = "fraud-detection-transactions"
  description = "Main DynamoDB table for real-time fraud transactions and audit trail (90-day TTL)"
}

variable "quarantine_table_name" {
  type        = string
  default     = "fraud-quarantine"
  description = "DynamoDB quarantine table for flagged REVIEW_QUEUE / BLOCK transactions (7-day TTL)"
}

variable "lambda_function_name" {
  type        = string
  default     = "FraudGuard-Serverless-Router"
  description = "AWS Lambda function name for the FraudGuard Decision & Ingestion Router"
}

variable "enable_kinesis_stream" {
  type        = bool
  default     = false
  description = "Enable Amazon Kinesis Data Stream & event source mapping (disabled by default due to student AWS account restriction)"
}

variable "enable_public_lambda_url" {
  type        = bool
  default     = false
  description = "Enable public Lambda Function URL with AuthType NONE (disabled by default due to student AWS account restriction; API Gateway HTTP API is used instead)"
}

variable "quarantine_release_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "API key required to release quarantined transactions via /release. Leave empty to auto-generate a secure random token via Terraform."
}
