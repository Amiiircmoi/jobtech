# ── Datalake médaillon sur S3 : chiffré (KMS), versionné, archivage par cycle de vie ──
# Datalake cloud + archivage, réplication, chiffrement at-rest, stockage massif/redondant.

locals {
  bucket_name  = "${var.project}-datalake-${var.name_suffix}"
  replica_name = "${var.project}-datalake-replica-${var.name_suffix}"
}

# ── Chiffrement at-rest (KMS) ──────────────────────────────────────────────
resource "aws_kms_key" "lake" {
  description             = "Chiffrement du datalake ${var.project}"
  enable_key_rotation     = true
  deletion_window_in_days = 7
}

resource "aws_kms_alias" "lake" {
  name          = "alias/${var.project}-datalake-${var.name_suffix}"
  target_key_id = aws_kms_key.lake.key_id
}

# ── Bucket principal ───────────────────────────────────────────────────────
resource "aws_s3_bucket" "lake" {
  bucket = local.bucket_name
}

resource "aws_s3_bucket_versioning" "lake" {
  bucket = aws_s3_bucket.lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.lake.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "lake" {
  bucket                  = aws_s3_bucket.lake.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Cycle de vie : archivage/rétention par couche médaillon (RGPD + FinOps) ──
resource "aws_s3_bucket_lifecycle_configuration" "lake" {
  count  = var.enable_lifecycle ? 1 : 0
  bucket = aws_s3_bucket.lake.id

  rule {
    id     = "bronze-archive-then-expire"
    status = "Enabled"
    filter { prefix = "bronze/" }
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
    expiration { days = 90 }
  }

  rule {
    id     = "silver-cooldown"
    status = "Enabled"
    filter { prefix = "silver/" }
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "gold-keep-cool"
    status = "Enabled"
    filter { prefix = "gold/" }
    # Conservation longue (agrégats anonymes) ; simple refroidissement de coût.
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}

# ── Politique : refuser tout accès non chiffré en transit (TLS obligatoire) ──
data "aws_iam_policy_document" "lake_tls" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    resources = [
      aws_s3_bucket.lake.arn,
      "${aws_s3_bucket.lake.arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "lake" {
  bucket = aws_s3_bucket.lake.id
  policy = data.aws_iam_policy_document.lake_tls.json
}

# ── Réplication : off en local, on sur AWS réel ────────────────────────────
# Même région ici (SRR) pour rester auto-suffisant ; en CRR sur AWS réel on
# pointerait un bucket d'une autre région (provider aliasé).
resource "aws_s3_bucket" "replica" {
  count  = var.enable_replication ? 1 : 0
  bucket = local.replica_name
}

resource "aws_s3_bucket_versioning" "replica" {
  count  = var.enable_replication ? 1 : 0
  bucket = aws_s3_bucket.replica[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_iam_role" "replication" {
  count = var.enable_replication ? 1 : 0
  name  = "${var.project}-s3-replication-${var.name_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "replication" {
  count = var.enable_replication ? 1 : 0
  role  = aws_iam_role.replication[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetReplicationConfiguration", "s3:ListBucket", "s3:GetObjectVersionForReplication"]
        Resource = [aws_s3_bucket.lake.arn, "${aws_s3_bucket.lake.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ReplicateObject", "s3:ReplicateDelete"]
        Resource = "${aws_s3_bucket.replica[0].arn}/*"
      },
    ]
  })
}

resource "aws_s3_bucket_replication_configuration" "lake" {
  count      = var.enable_replication ? 1 : 0
  depends_on = [aws_s3_bucket_versioning.lake]
  role       = aws_iam_role.replication[0].arn
  bucket     = aws_s3_bucket.lake.id

  rule {
    id     = "replicate-all"
    status = "Enabled"
    filter {}
    destination {
      bucket        = aws_s3_bucket.replica[0].arn
      storage_class = "STANDARD"
    }
  }
}
