# FraudGuard — AWS Terraform Outputs for Team Integration

output "aws_region" {
  value       = var.aws_region
  description = "Configured AWS Region"
}

output "service_1_kinesis_stream_name" {
  value       = aws_kinesis_stream.kinesis_stream.name
  description = "Module 1/2: Amazon Kinesis Stream name for ingestion"
}

output "service_1_kinesis_stream_arn" {
  value       = aws_kinesis_stream.kinesis_stream.arn
  description = "Kinesis Data Stream ARN"
}

output "service_2_dynamodb_table_name" {
  value       = aws_dynamodb_table.audit_log_db.name
  description = "Module 6: Amazon DynamoDB Table name for Audit Log"
}

output "service_3_s3_bucket_name" {
  value       = aws_s3_bucket.ml_bucket.id
  description = "Module 4: Amazon S3 Bucket for ML model artifacts"
}

output "service_5_lambda_function_name" {
  value       = aws_lambda_function.router_lambda.function_name
  description = "Module 5: AWS Lambda Router Function Name"
}

output "service_5_lambda_function_arn" {
  value       = aws_lambda_function.router_lambda.arn
  description = "AWS Lambda Function ARN"
}
