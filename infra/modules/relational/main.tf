# ── Schéma RELATIONNEL cloud sur la couche gold (Parquet S3) ─────────────────
# Schéma relationnel cloud, en serverless (pas de RDS → FinOps : zéro coût fixe).
# Glue Data Catalog décrit la
# table de faits gold ; Athena l'interroge en SQL standard directement sur S3.
#
# Right-sizing (cohérent avec « pas de Spark ») : Glue/Athena = SQL serverless
# à la demande, pas un cluster. RDS écarté = coût fixe injustifié au volume.
#
# NB exécution : Glue/Athena ne sont PAS émulés par LocalStack Community → ce
# module est GATÉ (`enable_relational`, défaut false) et appliqué sur AWS réel.
# `terraform validate` reste vert quel que soit le flag.

locals {
  gold_fact_location = "s3://${var.datalake_bucket}/gold/fact_job/"
  athena_results     = "s3://${var.datalake_bucket}/athena-results/"
}

# ── Catalogue de données (base logique) ──────────────────────────────────────
resource "aws_glue_catalog_database" "warehouse" {
  count       = var.enable_relational ? 1 : 0
  name        = "${var.project}_warehouse_${var.name_suffix}"
  description = "Schéma relationnel jobtech (couche gold du datalake)"
}

# ── Table de faits : mappe le Parquet gold/fact_job/ en table SQL ────────────
# Colonnes alignées sur data/gold/fact_job.parquet (vérifié) :
#   5 clés naturelles (string) + 3 mesures salaire (double) + volume (bigint).
resource "aws_glue_catalog_table" "fact_job" {
  count         = var.enable_relational ? 1 : 0
  name          = "fact_job"
  database_name = aws_glue_catalog_database.warehouse[0].name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification        = "parquet"
    "parquet.compression" = "SNAPPY"
    EXTERNAL              = "TRUE"
  }

  storage_descriptor {
    location      = local.gold_fact_location
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "date_posted"
      type = "string"
    }
    columns {
      name = "country_iso2"
      type = "string"
    }
    columns {
      name = "skill"
      type = "string"
    }
    columns {
      name = "company"
      type = "string"
    }
    columns {
      name = "source"
      type = "string"
    }
    columns {
      name = "avg_salary"
      type = "double"
    }
    columns {
      name = "min_salary"
      type = "double"
    }
    columns {
      name = "max_salary"
      type = "double"
    }
    columns {
      name = "job_count"
      type = "bigint"
    }
  }
}

# ── Athena : moteur SQL serverless, résultats chiffrés (KMS) ──────────────────
resource "aws_athena_workgroup" "analytics" {
  count = var.enable_relational ? 1 : 0
  name  = "${var.project}-analytics-${var.name_suffix}"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = local.athena_results
      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = var.kms_key_arn
      }
    }
  }
}
