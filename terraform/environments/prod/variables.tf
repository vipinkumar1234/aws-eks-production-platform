variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "region_short_name" {
  type    = string
  default = "use1"
}
variable "admin_role_arns" {
  type    = list(string)
  default = []
}
variable "github_oidc_subjects" {
  type    = list(string)
  default = ["repo:ORG/REPO:ref:refs/heads/main"]
}
variable "project" {
  type    = string
  default = "eks-platform"
}
variable "app_domain" {
  type    = string
  default = "worldofaws.app"
}
variable "route53_zone_name" {
  type    = string
  default = "worldofaws.app"
}
variable "infra_version" {
  type        = string
  default     = "local"
  description = "Git branch or deployment identifier recorded on AWS resources"
}
variable "cluster_endpoint_public_access_cidrs" {
  type        = list(string)
  default     = []
  description = "Approved administrator CIDRs; empty keeps the EKS API private-only"
}
