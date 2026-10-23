# FraudGuard — Production-Ready AWS Terraform Infrastructure as Code (IaC)
# Region: eu-north-1 (Stockholm) | Architecture: Serverless-First (Lambda Python 3.12 + DynamoDB + API Gateway HTTP API)
#
# Student AWS Account Safeguards Built-In:
# - Local Terraform state by default (commented S3 + DynamoDB state-locking backend ready for multi-dev migration)
# - Amazon Kinesis Data Streams gated behind `var.enable_kinesis_stream` (default = false; blocked on student AWS account)
# - Public Lambda Function URL gated behind `var.enable_public_lambda_url` (default = false; blocked on student AWS account)
# - Amazon API Gateway v2 (HTTP API) provisioned as the student-account-compatible serverless HTTP ingestion & query trigger
# - DynamoDB PAY_PER_REQUEST with mandatory TTL (`ttl_expiry`) and `AccountTimestampIndex` GSI on both tables
# - CloudWatch Log Group with strict 30-day retention and least-privilege IAM Role

terraform {
  required_version = ">= 1.3.0"

  # ---------------------------------------------------------------------------
  # TERRAFORM STATE BACKEND (Default: Local State for Student Account)
  # ---------------------------------------------------------------------------
  # ARCHITECT FLAG: Local state (`terraform.tfstate`) is active by default so
  # `terraform init` works out-of-the-box without pre-existing S3 buckets.
  # To migrate to a shared S3 backend with DynamoDB state locking:
  #   1. Create an S3 bucket (`fraudguard-terraform-state-eu-north-1`) with versioning & SSE-S3
  #   2. Create a DynamoDB table (`fraudguard-terraform-locks`) with Partition Key `LockID` (String)
  #   3. Uncomment the `backend "s3"` block below and run `terraform init -migrate-state`
  #
  # backend "s3" {
  #   bucket         = "fraudguard-terraform-state-eu-north-1"
  #   key            = "prod/fraudguard.tfstate"
  #   region         = "eu-north-1"
  #   dynamodb_table = "fraudguard-terraform-locks"
  #   encrypt        = true
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "random_string" "generated_quarantine_api_key" {
  length  = 32
  special = false
}

locals {
  effective_quarantine_api_key = var.quarantine_release_api_key != "" ? var.quarantine_release_api_key : random_string.generated_quarantine_api_key.result
}

# -----------------------------------------------------------------------------
# SERVICE 1: AMAZON KINESIS DATA STREAMS (Optional — Gated for Student Account)
# -----------------------------------------------------------------------------
resource "aws_kinesis_stream" "kinesis_stream" {
  count            = var.enable_kinesis_stream ? 1 : 0
  name             = "fraudguard-transactions-stream-${random_string.suffix.result}"
  shard_count      = 1
  retention_period = 24

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
    Module      = "CloudInfrastructure-AWS"
  }
}

# -----------------------------------------------------------------------------
# SERVICE 2A: AMAZON DYNAMODB — MAIN TRANSACTIONS TABLE (90-Day TTL + GSIs)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "audit_log_db" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S"
  }

  attribute {
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "decision"
    type = "S"
  }

  # Feature 2: GSI on account_id + timestamp sort key for Traceback & Velocity queries
  global_secondary_index {
    name            = "AccountTimestampIndex"
    hash_key        = "account_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Analyst query index on decision (ALLOW / REVIEW_QUEUE / BLOCK)
  global_secondary_index {
    name            = "DecisionIndex"
    hash_key        = "decision"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Point-in-time recovery for audit durability
  point_in_time_recovery {
    enabled = true
  }

  # Architect Rule #2: Every DynamoDB table must have TTL configured (ttl_expiry)
  ttl {
    attribute_name = "ttl_expiry"
    enabled        = true
  }

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
    TTL_Days    = "90"
  }
}

# -----------------------------------------------------------------------------
# SERVICE 2B: AMAZON DYNAMODB — QUARANTINE TABLE (7-Day TTL + GSIs)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "quarantine_db" {
  name         = var.quarantine_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S"
  }

  attribute {
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "quarantine_ts"
    type = "S"
  }

  # GSI on account_id + timestamp sort key for Account Quarantine History lookups
  global_secondary_index {
    name            = "AccountTimestampIndex"
    hash_key        = "account_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Analyst queue index by status + quarantine_ts
  global_secondary_index {
    name            = "QuarantineStatusIndex"
    hash_key        = "status"
    range_key       = "quarantine_ts"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  # Architect Rule #2: Every DynamoDB table must have TTL configured (ttl_expiry)
  ttl {
    attribute_name = "ttl_expiry"
    enabled        = true
  }

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
    TTL_Days    = "7"
  }
}

# -----------------------------------------------------------------------------
# SERVICE 3: AMAZON S3 BUCKET (ML Model & Data Artifact Storage)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "ml_bucket" {
  bucket        = "fraudguard-ml-artifacts-${random_string.suffix.result}"
  force_destroy = true

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
  }
}

# -----------------------------------------------------------------------------
# SERVICE 4: IAM ROLE & STRICT LEAST-PRIVILEGE POLICY FOR AWS LAMBDA ROUTER
# -----------------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec_role" {
  name = "fraudguard_lambda_exec_role_${random_string.suffix.result}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "lambda_least_privilege" {
  name = "fraudguard_lambda_least_privilege_policy"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "DynamoDBLeastPrivilegeAccess"
          Effect = "Allow"
          Action = [
            "dynamodb:PutItem",
            "dynamodb:GetItem",
            "dynamodb:UpdateItem",
            "dynamodb:Query",
            "dynamodb:Scan",
            "dynamodb:DescribeTable"
          ]
          Resource = [
            aws_dynamodb_table.audit_log_db.arn,
            "${aws_dynamodb_table.audit_log_db.arn}/index/*",
            aws_dynamodb_table.quarantine_db.arn,
            "${aws_dynamodb_table.quarantine_db.arn}/index/*"
          ]
        },
        {
          Sid    = "CloudWatchLogsScopedAccess"
          Effect = "Allow"
          Action = [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
          ]
          Resource = [
            aws_cloudwatch_log_group.lambda_logs.arn,
            "${aws_cloudwatch_log_group.lambda_logs.arn}:*"
          ]
        },
        {
          Sid    = "CloudWatchMetricsNamespaceScoped"
          Effect = "Allow"
          Action = [
            "cloudwatch:PutMetricData"
          ]
          Resource = "*"
          Condition = {
            StringEquals = {
              "cloudwatch:namespace" = [
                "FraudGuard",
                "FraudGuard/Security"
              ]
            }
          }
        }
      ],
      var.enable_kinesis_stream ? [
        {
          Sid    = "KinesisStreamConsumerAccess"
          Effect = "Allow"
          Action = [
            "kinesis:GetRecords",
            "kinesis:GetShardIterator",
            "kinesis:DescribeStream",
            "kinesis:DescribeStreamSummary",
            "kinesis:ListShards"
          ]
          Resource = [
            aws_kinesis_stream.kinesis_stream[0].arn
          ]
        }
      ] : []
    )
  })
}

# -----------------------------------------------------------------------------
# SERVICE 5: AWS LAMBDA (FraudGuard-Serverless-Router, Python 3.12, 30-Day Logs)
# -----------------------------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda_router.zip"
}

# Architect Rule #3: Every Lambda must have a CloudWatch log group with 30-day retention
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = 30

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
  }
}

resource "aws_lambda_function" "fraud_router" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = var.lambda_function_name
  role             = aws_iam_role.lambda_exec_role.arn
  handler          = "lambda_function.handler"
  runtime          = "python3.12"
  memory_size      = 256
  timeout          = 10
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE             = aws_dynamodb_table.audit_log_db.name
      QUARANTINE_TABLE           = aws_dynamodb_table.quarantine_db.name
      QUARANTINE_RELEASE_API_KEY = local.effective_quarantine_api_key
      USE_AWS_DYNAMODB           = "true"
      PII_MOCK_STORE_PATH        = "data/mock_pii_store.json"
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda_logs]

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
  }
}

# Optional Kinesis Event Source Mapping (Only created when enable_kinesis_stream = true)
resource "aws_lambda_event_source_mapping" "kinesis_trigger" {
  count             = var.enable_kinesis_stream ? 1 : 0
  event_source_arn  = aws_kinesis_stream.kinesis_stream[0].arn
  function_name     = aws_lambda_function.fraud_router.arn
  starting_position = "LATEST"
  batch_size        = 100
}

# Optional Public Lambda Function URL (Disabled by default on Student AWS accounts)
resource "aws_lambda_function_url" "router_url" {
  count              = var.enable_public_lambda_url ? 1 : 0
  function_name      = aws_lambda_function.fraud_router.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_headers     = ["content-type", "authorization", "x-api-key"]
    max_age           = 86400
  }
}

# -----------------------------------------------------------------------------
# SERVICE 5B: AMAZON API GATEWAY HTTP API (Student-Account-Compatible Trigger)
# -----------------------------------------------------------------------------
resource "aws_apigatewayv2_api" "http_api" {
  name          = "fraudguard-serverless-http-api"
  protocol_type = "HTTP"
  description   = "Serverless HTTP API trigger for FraudGuard Lambda Router (replaces blocked public Lambda URL & Kinesis on student account)"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization", "x-api-key"]
    max_age       = 86400
  }

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
  }
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.fraud_router.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Project     = "FraudGuard"
    Environment = var.environment
  }
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowExecutionFromAPIGatewayHTTPAPI"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fraud_router.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# -----------------------------------------------------------------------------
# SERVICE 6: CLOUDWATCH ALARMS (Production Operational Observability)
# -----------------------------------------------------------------------------

# 1. Quarantine Table Count > 100 (Feature 5 Attack Wave Alarm)
resource "aws_cloudwatch_metric_alarm" "quarantine_attack_wave" {
  alarm_name          = "fraudguard-quarantine-count-over-100"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "QuarantineTableCount"
  namespace           = "FraudGuard/Security"
  period              = 60
  statistic           = "Maximum"
  threshold           = 100
  alarm_description   = "Alert when quarantined transactions exceed 100 (possible attack wave)"
}

# 2. Lambda Error Rate > 5%
resource "aws_cloudwatch_metric_alarm" "lambda_error_rate_high" {
  alarm_name          = "fraudguard-lambda-error-rate-over-5pct"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 5
  alarm_description   = "Alert when Lambda error rate exceeds 5%"

  metric_query {
    id          = "error_rate"
    expression  = "(errors / MAX([invocations, 1])) * 100"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "Errors"
      namespace   = "AWS/Lambda"
      period      = 60
      stat        = "Sum"
      dimensions = {
        FunctionName = aws_lambda_function.fraud_router.function_name
      }
    }
  }

  metric_query {
    id = "invocations"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 60
      stat        = "Sum"
      dimensions = {
        FunctionName = aws_lambda_function.fraud_router.function_name
      }
    }
  }
}

# 3. Lambda Duration > 5s (5000ms)
resource "aws_cloudwatch_metric_alarm" "lambda_duration_high" {
  alarm_name          = "fraudguard-lambda-duration-over-5s"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Maximum"
  threshold           = 5000
  alarm_description   = "Alert when Lambda execution duration exceeds 5000ms (5s)"

  dimensions = {
    FunctionName = aws_lambda_function.fraud_router.function_name
  }
}

# 4. DynamoDB Write Throttles > 0
resource "aws_cloudwatch_metric_alarm" "dynamodb_write_throttles" {
  alarm_name          = "fraudguard-dynamodb-write-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "WriteThrottleEvents"
  namespace           = "AWS/DynamoDB"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Alert when DynamoDB WriteThrottleEvents occur on main transactions table"

  dimensions = {
    TableName = aws_dynamodb_table.audit_log_db.name
  }
}
