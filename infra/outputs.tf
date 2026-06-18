output "datalake_bucket" {
  description = "Nom du bucket S3 du datalake médaillon"
  value       = module.lake.bucket_name
}

output "datalake_kms_key_arn" {
  description = "ARN de la clé KMS de chiffrement at-rest du datalake"
  value       = module.lake.kms_key_arn
}

output "indicators_table" {
  description = "Table DynamoDB des indicateurs chauds"
  value       = module.serving.table_name
}

output "api_endpoint" {
  description = "Endpoint API Gateway (GET /indicators)"
  value       = module.pipelines.api_endpoint
}

output "rest_api_id" {
  description = "Id de l'API REST (pour l'URL LocalStack _user_request_)"
  value       = module.pipelines.rest_api_id
}

output "kinesis_stream" {
  description = "Flux Kinesis des offres fraîches (temps réel)"
  value       = module.pipelines.kinesis_stream
}

output "glue_database" {
  description = "Base Glue (schéma relationnel cloud sur gold) ; null si enable_relational=false"
  value       = module.relational.glue_database
}

output "athena_workgroup" {
  description = "Workgroup Athena (SQL serverless sur gold) ; null si enable_relational=false"
  value       = module.relational.athena_workgroup
}
