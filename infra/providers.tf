terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Provider AWS « standard » : le même code cible le VRAI AWS (var.aws_endpoint_url
# vide) OU un émulateur local (moto/LocalStack) quand l'endpoint est renseigné.
# → approche « local d'abord » sans aucune dépendance émulateur dans le code (réel-ready).
provider "aws" {
  region = var.region

  # Mode émulateur local : credentials factices + on saute les vérifs réseau AWS.
  access_key                  = var.aws_endpoint_url == "" ? null : "test"
  secret_key                  = var.aws_endpoint_url == "" ? null : "test"
  skip_credentials_validation = var.aws_endpoint_url != ""
  skip_metadata_api_check     = var.aws_endpoint_url != ""
  skip_requesting_account_id  = var.aws_endpoint_url != ""
  s3_use_path_style           = var.aws_endpoint_url != ""

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Env       = var.name_suffix
    }
  }

  dynamic "endpoints" {
    for_each = var.aws_endpoint_url == "" ? [] : [1]
    content {
      s3             = var.aws_endpoint_url
      dynamodb       = var.aws_endpoint_url
      kms            = var.aws_endpoint_url
      iam            = var.aws_endpoint_url
      sts            = var.aws_endpoint_url
      lambda         = var.aws_endpoint_url
      kinesis        = var.aws_endpoint_url
      apigateway     = var.aws_endpoint_url
      apigatewayv2   = var.aws_endpoint_url
      cloudwatchlogs = var.aws_endpoint_url
    }
  }
}
