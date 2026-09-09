variable "name" { type = string }
variable "kubernetes_version" {
  type    = string
  default = "1.34"
}
variable "vpc_id" { type = string }
variable "private_subnets" { type = list(string) }
variable "public_subnets" { type = list(string) }
variable "kms_key_arn" { type = string }
variable "endpoint_public_access_cidrs" {
  type    = list(string)
  default = []
}
variable "admin_role_arns" {
  type    = list(string)
  default = []
}
variable "github_oidc_subjects" {
  type    = list(string)
  default = []
}
variable "tags" {
  type    = map(string)
  default = {}
}

variable "github_oidc_provider_arn" {
  type    = string
  default = null
}
variable "ecr_repository_arn" { type = string }
