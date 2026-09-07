variable "name" { type = string }
variable "oidc_provider_arn" { type = string }
variable "cluster_name" { type = string }
variable "logs_bucket_arn" { type = string }
variable "game_table_arn" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
