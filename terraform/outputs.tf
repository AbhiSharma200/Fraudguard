# FraudGuard — Terraform Outputs for Teammates (Modules 2 to 7)

output "resource_group_name" {
  value       = azurerm_resource_group.rg.name
  description = "Provisioned Resource Group name"
}

output "service_1_eventhub_connection_string" {
  value       = azurerm_eventhub_authorization_rule.evh_rule.primary_connection_string
  sensitive   = true
  description = "Module 2 (Teammate 2): Event Hub Connection string for replay script"
}

output "service_1_eventhub_name" {
  value       = azurerm_eventhub.evh.name
  description = "Event Hub name for streaming"
}

output "service_2_stream_analytics_job_name" {
  value       = azurerm_stream_analytics_job.asa_job.name
  description = "Module 3 (Teammate 3): Azure Stream Analytics Job name"
}

output "service_3_azure_ml_workspace_name" {
  value       = azurerm_machine_learning_workspace.aml_ws.name
  description = "Module 4 (Teammate 4): Azure Machine Learning Workspace name"
}

output "service_4_cosmos_db_endpoint" {
  value       = azurerm_cosmosdb_account.cosmos_acc.endpoint
  description = "Module 6 (Teammate 6): Azure Cosmos DB Endpoint URL"
}

output "service_4_cosmos_db_primary_key" {
  value       = azurerm_cosmosdb_account.cosmos_acc.primary_key
  sensitive   = true
  description = "Module 6 (Teammate 6): Azure Cosmos DB Primary Key"
}

output "service_5_function_app_name" {
  value       = azurerm_linux_function_app.func_app.name
  description = "Module 5 (Teammate 5): Azure Function App Router name"
}

output "service_5_function_app_default_hostname" {
  value       = azurerm_linux_function_app.func_app.default_hostname
  description = "Function App HTTP trigger hostname"
}

output "service_6_app_service_dashboard_url" {
  value       = "https://${azurerm_linux_web_app.web_app.default_hostname}"
  description = "Module 7 (Teammate 7): Public URL for Analyst Dashboard"
}
