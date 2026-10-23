# FraudGuard — Terraform Infrastructure as Code (IaC)
# Module 1: Provisioning 6 Azure Cloud Services

terraform {
  required_version = ">= 1.3.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# -----------------------------------------------------------------------------
# RESOURCE GROUP
# -----------------------------------------------------------------------------
resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-rg-${var.environment}"
  location = var.location

  tags = {
    Project    = "FraudGuard"
    Module     = "Module-1-Infrastructure"
    Course     = "21CSE333P-Essentials-in-Cloud-and-DevOps"
    Environment = var.environment
  }
}

# -----------------------------------------------------------------------------
# SERVICE 1: AZURE EVENT HUBS (Real-Time Stream Ingestion)
# -----------------------------------------------------------------------------
resource "azurerm_eventhub_namespace" "evh_ns" {
  name                = "${var.prefix}-evh-ns-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "Standard"
  capacity            = 1

  tags = azurerm_resource_group.rg.tags
}

resource "azurerm_eventhub" "evh" {
  name                = "transactions-stream"
  namespace_name      = azurerm_eventhub_namespace.evh_ns.name
  resource_group_name = azurerm_resource_group.rg.name
  partition_count     = 2
  message_retention   = 1
}

resource "azurerm_eventhub_authorization_rule" "evh_rule" {
  name                = "ReplayPublisherRule"
  namespace_name      = azurerm_eventhub_namespace.evh_ns.name
  eventhub_name       = azurerm_eventhub.evh.name
  resource_group_name = azurerm_resource_group.rg.name
  listen              = true
  send                = true
  manage              = false
}

# -----------------------------------------------------------------------------
# SERVICE 2: AZURE STREAM ANALYTICS (In-Stream Rule-Based Checks)
# -----------------------------------------------------------------------------
resource "azurerm_stream_analytics_job" "asa_job" {
  name                                     = "${var.prefix}-asa-rules-${random_string.suffix.result}"
  resource_group_name                      = azurerm_resource_group.rg.name
  location                                 = azurerm_resource_group.rg.location
  compatibility_level                      = "1.2"
  data_locale                              = "en-US"
  events_late_arrival_max_delay_in_seconds = 60
  events_out_of_order_max_delay_in_seconds = 10
  events_out_of_order_policy               = "Drop"
  output_error_policy                      = "Drop"
  streaming_units                          = 1

  transformation_query = <<QUERY
    SELECT
        System.Timestamp() AS EventTime,
        transaction_id,
        user_id,
        amount,
        merchant_category,
        velocity_count_1h,
        geo_distance_km,
        CASE
            WHEN velocity_count_1h > 5 THEN 1
            WHEN geo_distance_km > 500 THEN 1
            WHEN amount > 10000 THEN 1
            ELSE 0
        END AS rule_flagged,
        'RULE_CHECK_PASSED' AS status
    INTO
        [CosmosDBOutput]
    FROM
        [EventHubInput]
QUERY

  tags = azurerm_resource_group.rg.tags
}

# -----------------------------------------------------------------------------
# SERVICE 3: AZURE MACHINE LEARNING WORKSPACE (Fraud-Scoring Model)
# -----------------------------------------------------------------------------
resource "azurerm_storage_account" "aml_storage" {
  name                     = "staml${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_key_vault" "aml_kv" {
  name                = "kv-aml-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  tenant_id           = var.tenant_id != "" ? var.tenant_id : "00000000-0000-0000-0000-000000000000"
  sku_name            = "standard"
}

resource "azurerm_application_insights" "aml_appinsights" {
  name                = "appinsights-aml-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  application_type    = "web"
}

resource "azurerm_machine_learning_workspace" "aml_ws" {
  name                    = "${var.prefix}-aml-ws-${random_string.suffix.result}"
  location                = azurerm_resource_group.rg.location
  resource_group_name     = azurerm_resource_group.rg.name
  application_insights_id = azurerm_application_insights.aml_appinsights.id
  key_vault_id            = azurerm_key_vault.aml_kv.id
  storage_account_id      = azurerm_storage_account.aml_storage.id

  identity {
    type = "SystemAssigned"
  }

  tags = azurerm_resource_group.rg.tags
}

# -----------------------------------------------------------------------------
# SERVICE 4: AZURE COSMOS DB (Transaction State & Audit Log)
# -----------------------------------------------------------------------------
resource "azurerm_cosmosdb_account" "cosmos_acc" {
  name                = "${var.prefix}-cosmos-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
  }

  tags = azurerm_resource_group.rg.tags
}

resource "azurerm_cosmosdb_sql_database" "cosmos_db" {
  name                = "FraudGuardDB"
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos_acc.name
}

resource "azurerm_cosmosdb_sql_container" "cosmos_container" {
  name                = "AuditLog"
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos_acc.name
  database_name       = azurerm_cosmosdb_sql_database.cosmos_db.name
  partition_key_path  = "/user_id"
  throughput          = 400
}

# -----------------------------------------------------------------------------
# SERVICE 5: AZURE FUNCTIONS (Routing / Decision Logic)
# -----------------------------------------------------------------------------
resource "azurerm_storage_account" "fn_storage" {
  name                     = "stfn${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_service_plan" "sp_func" {
  name                = "${var.prefix}-sp-func-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "Y1" # Consumption tier
}

resource "azurerm_linux_function_app" "func_app" {
  name                = "${var.prefix}-func-router-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.sp_func.id

  storage_account_name       = azurerm_storage_account.fn_storage.name
  storage_account_access_key = azurerm_storage_account.fn_storage.primary_access_key

  site_config {
    application_stack {
      python_version = "3.10"
    }
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME" = "python"
    "COSMOS_DB_CONNECTION"     = azurerm_cosmosdb_account.cosmos_acc.primary_sql_connection_string
    "EVENTHUB_CONNECTION"      = azurerm_eventhub_authorization_rule.evh_rule.primary_connection_string
  }

  tags = azurerm_resource_group.rg.tags
}

# -----------------------------------------------------------------------------
# SERVICE 6: AZURE APP SERVICE (Analyst Dashboard)
# -----------------------------------------------------------------------------
resource "azurerm_service_plan" "sp_web" {
  name                = "${var.prefix}-sp-web-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "B1" # Basic linux plan
}

resource "azurerm_linux_web_app" "web_app" {
  name                = "${var.prefix}-app-dashboard-${random_string.suffix.result}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.sp_web.id

  site_config {
    application_stack {
      node_version = "18-lts"
    }
  }

  app_settings = {
    "COSMOS_DB_ENDPOINT" = azurerm_cosmosdb_account.cosmos_acc.endpoint
    "COSMOS_DB_KEY"      = azurerm_cosmosdb_account.cosmos_acc.primary_key
    "NODE_ENV"           = "production"
  }

  tags = azurerm_resource_group.rg.tags
}
