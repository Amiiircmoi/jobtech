# Orchestration des modules d'infrastructure jobtech (Bloc 3).
# Le module `lake` (datalake S3 chiffré) est la première brique ; serving (DynamoDB)
# et pipelines (Lambda/Kinesis) suivront.

module "lake" {
  source             = "./modules/lake"
  project            = var.project
  name_suffix        = var.name_suffix
  region             = var.region
  enable_replication = var.enable_replication
  enable_lifecycle   = var.enable_lifecycle
}

module "serving" {
  source      = "./modules/serving"
  project     = var.project
  name_suffix = var.name_suffix
}

module "pipelines" {
  source                = "./modules/pipelines"
  project               = var.project
  name_suffix           = var.name_suffix
  indicators_table_name = module.serving.table_name
  indicators_table_arn  = module.serving.table_arn
}

# Schéma relationnel cloud (Glue + Athena) sur la couche gold.
# Gaté (enable_relational, défaut false) car non émulé par LocalStack Community ;
# appliqué sur AWS réel. `terraform validate` reste vert dans les deux cas.
module "relational" {
  source            = "./modules/relational"
  project           = var.project
  name_suffix       = var.name_suffix
  datalake_bucket   = module.lake.bucket_name
  kms_key_arn       = module.lake.kms_key_arn
  enable_relational = var.enable_relational
}
