# FraudGuard — Terraform Variables

variable "prefix" {
  type        = string
  default     = "fraudguard"
  description = "Prefix applied to all Azure resource names"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment environment (dev, stage, prod)"
}

variable "location" {
  type        = string
  default     = "eastus"
  description = "Azure Region for all FraudGuard services"
}

variable "tenant_id" {
  type        = string
  default     = ""
  description = "Azure Active Directory Tenant ID"
}
