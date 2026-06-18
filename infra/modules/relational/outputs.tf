output "glue_database" {
  description = "Base Glue (schéma relationnel) — vide si enable_relational=false"
  value       = try(aws_glue_catalog_database.warehouse[0].name, null)
}

output "athena_workgroup" {
  description = "Workgroup Athena — vide si enable_relational=false"
  value       = try(aws_athena_workgroup.analytics[0].name, null)
}
