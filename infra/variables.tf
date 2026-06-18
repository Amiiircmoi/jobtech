variable "region" {
  description = "Région AWS (Paris par défaut, cohérent avec le marché EU)"
  type        = string
  default     = "eu-west-3"
}

variable "project" {
  description = "Préfixe de nommage / tag de coût (FinOps)"
  type        = string
  default     = "jobtech"
}

variable "name_suffix" {
  description = "Suffixe d'unicité des ressources (local, dev, prod…)"
  type        = string
  default     = "local"
}

variable "enable_replication" {
  description = "Active la réplication S3 inter-région. Désactivée en local, activée sur AWS réel."
  type        = bool
  default     = false
}

variable "aws_endpoint_url" {
  description = "Vide = AWS réel. Sinon URL d'un émulateur local (LocalStack), ex. http://localhost:4566."
  type        = string
  default     = ""
}

variable "enable_lifecycle" {
  description = "Cycle de vie S3. Off pour LocalStack Community, on sur AWS réel."
  type        = bool
  default     = true
}

variable "enable_relational" {
  description = "Active Glue + Athena (schéma relationnel cloud). Désactivé en local (non émulé par LocalStack Community), activé sur AWS réel."
  type        = bool
  default     = false
}
