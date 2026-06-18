variable "project" { type = string }
variable "name_suffix" { type = string }
variable "region" { type = string }
variable "enable_replication" {
  type    = bool
  default = false
}

variable "enable_lifecycle" {
  description = "Cycle de vie S3 (archivage/rétention). Off en local (bug d'attente LocalStack Community), on sur AWS réel."
  type        = bool
  default     = true
}
