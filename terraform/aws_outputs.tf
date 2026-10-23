# FraudGuard — AWS Terraform Outputs for Team Integration (eu-north-1)

output "aws_region" {
  value       = var.aws_region
  description = "Configured AWS Region (eu-north-1)"
}

output "service_1_kinesis_stream_name" {
  value       = var.enable_kinesis_stream ? aws_kinesis_stream.kinesis_stream[0].name : "DISABLED_STUDENT_ACCOUNT_RESTRICTION"
  description = "Module 1/2: Amazon Kinesis Stream name for ingestion (when enabled)"
}

output "service_1_kinesis_stream_arn" {
  value       = var.enable_kinesis_stream ? aws_kinesis_stream.kinesis_stream[0].arn : "DISABLED_STUDENT_ACCOUNT_RESTRICTION"
  description = "Kinesis Data Stream ARN (when enabled)"
}

output "service_2_dynamodb_table_name" {
  value       = aws_dynamodb_table.audit_log_db.name
  description = "Module 6: Amazon DynamoDB Table name for Fraud Transactions & Audit Log (90-day TTL on ttl_expiry)"
}

output "service_2b_quarantine_table_name" {
  value       = aws_dynamodb_table.quarantine_db.name
  description = "Feature 5: Amazon DynamoDB Quarantine Table name (7-day TTL on ttl_expiry)"
}

output "service_3_s3_bucket_name" {
  value       = aws_s3_bucket.ml_bucket.id
  description = "Module 4: Amazon S3 Bucket for ML model artifacts"
}

output "service_5_lambda_function_name" {
  value       = aws_lambda_function.fraud_router.function_name
  description = "Module 5: AWS Lambda Router Function Name (Python 3.12)"
}

output "service_5_lambda_function_arn" {
  value       = aws_lambda_function.fraud_router.arn
  description = "AWS Lambda Function ARN"
}

output "service_5_api_gateway_http_endpoint" {
  value       = aws_apigatewayv2_api.http_api.api_endpoint
  description = "Student-Account-Compatible HTTPS API Gateway v2 Endpoint for FraudGuard Lambda Router"
}

output "service_5_lambda_function_url" {
  value       = var.enable_public_lambda_url ? aws_lambda_function_url.router_url[0].function_url : aws_apigatewayv2_api.http_api.api_endpoint
  description = "Public HTTPS Endpoint for FraudGuard Decision Router (API Gateway HTTP API by default)"
}
