# ── Service « chaud » : DynamoDB pour les indicateurs servis rapidement ──────
# Store NoSQL clé-valeur / document pour les indicateurs « chauds » servis par l'API.
# On-demand (PAY_PER_REQUEST) → coût nul au repos (FinOps) ; chiffrement KMS ;
# point-in-time recovery (sauvegarde continue).

resource "aws_dynamodb_table" "indicators" {
  name         = "${var.project}-indicators-${var.name_suffix}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = true
  }
}
