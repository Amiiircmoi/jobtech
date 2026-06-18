variable "project" { type = string }
variable "name_suffix" { type = string }

variable "datalake_bucket" {
  description = "Nom du bucket S3 du datalake (contient la couche gold/ en Parquet)"
  type        = string
}

variable "kms_key_arn" {
  description = "Clé KMS du datalake (chiffrement des résultats Athena)"
  type        = string
}

variable "enable_relational" {
  description = <<-EOT
    Active Glue Data Catalog + Athena (schéma relationnel sur la couche gold).
    OFF en local : Glue/Athena ne sont PAS émulés par LocalStack Community.
    ON sur AWS réel : `terraform validate` reste vert dans les deux cas.
  EOT
  type        = bool
  default     = false
}
