# FraudGuard — Terraform Infrastructure as Code (IaC)
# AWS Cloud Integration: Provisioning 6 AWS Cloud Services

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.0"
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

# -----------------------------------------------------------------------------
# SERVICE 1: AMAZON KINESIS DATA STREAMS (Real-Time Ingestion)
# -----------------------------------------------------------------------------
resource "aws_kinesis_stream" "kinesis_stream" {
  name             = "fraudguard-transactions-stream-${random_string.suffix.result}"
  shard_count      = 1
  retention_period = 24

  tags = {
    Project     = "FraudGuard"
    Environment = "Production"
    Module      = "CloudInfrastructure-AWS"
  }
}

# -----------------------------------------------------------------------------
# SERVICE 2: AMAZON DYNAMODB (Transaction State & Audit Log)
# -----------------------------------------------------------------------------
resource "aws_dynamodb_table" "audit_log_db" {
  name           = "FraudGuardAuditLog"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "transaction_id"

  attribute {
    name = "transaction_id"
    type = "S"
  }

  tags = {
    Project     = "FraudGuard"
    Environment = "Production"
  }
}

# -----------------------------------------------------------------------------
# SERVICE 3: AMAZON S3 BUCKET (ML Model & Data Artifact Storage)
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "ml_bucket" {
  bucket        = "fraudguard-ml-artifacts-${random_string.suffix.result}"
  force_destroy = true

  tags = {
    Project = "FraudGuard"
  }
}

# -----------------------------------------------------------------------------
# SERVICE 4: IAM ROLE FOR AWS LAMBDA ROUTER
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
}

resource "aws_iam_role_policy_attachment" "lambda_kinesis" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaKinesisExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

# -----------------------------------------------------------------------------
# SERVICE 5: AWS LAMBDA (Decision Router Engine)
# -----------------------------------------------------------------------------
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_router.zip"
  
  source {
    content  = <<EOF
import json
import os

def lambda_handler(event, context):
    records = event.get('Records', [])
    processed = []
    
    for r in records:
        tx = json.loads(r['kinesis']['data'])
        amount = float(tx.get('amount', 0))
        txn_type = tx.get('txn_type', 'CREDIT')
        
        is_suspicious = (amount > 150.0 and txn_type in ['WIRE', 'CHECK']) or (amount > 180.0)
        decision = 'BLOCK' if is_suspicious else 'ALLOW'
        
        processed.append({
            'transaction_id': tx.get('transaction_id'),
            'decision': decision,
            'amount': amount
        })
        
    return {
        'statusCode': 200,
        'body': json.dumps({'processed': processed})
    }
EOF
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "router_lambda" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "fraudguard_router_${random_string.suffix.result}"
  role             = aws_iam_role.lambda_exec_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.10"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.audit_log_db.name
    }
  }
}

# -----------------------------------------------------------------------------
# SERVICE 6: AMAZON SAGEMAKER / ML MODEL ENDPOINT (Placeholder Config)
# -----------------------------------------------------------------------------
resource "aws_ssm_parameter" "ml_endpoint_param" {
  name  = "/fraudguard/sagemaker_endpoint"
  type  = "String"
  value = "https://sagemaker.aws.fraudguard.internal/score"
}
