provider "aws" {
  region = var.aws_region
  default_tags { tags = { ManagedBy = "terraform", Project = var.project, Environment = "prod", Region = var.aws_region, InfraVersion = var.infra_version } }
}

data "aws_caller_identity" "current" {}
data "aws_route53_zone" "app" {
  name         = var.route53_zone_name
  private_zone = false
}

locals {
  name = "${var.project}-${var.region_short_name}-prod"
  tags = { Name = local.name, Environment = "prod", Region = var.aws_region, InfraVersion = var.infra_version, SecurityContact = "platform@example.com" }
}

module "kms" {
  source      = "../../modules/kms"
  name        = "${local.name}-platform"
  description = "Customer managed key for ${local.name} EKS, ECR, and logs"
  tags        = local.tags
}
module "acm" {
  source          = "../../modules/acm"
  domain_name     = var.app_domain
  route53_zone_id = data.aws_route53_zone.app.zone_id
  tags            = local.tags
}
module "auth" {
  source        = "../../modules/cognito"
  name          = "${local.name}-arena-grid"
  domain_prefix = replace(local.name, "_", "-")
  callback_url  = "https://${var.app_domain}/oauth2/idpresponse"
  logout_url    = "https://${var.app_domain}/"
  tags          = local.tags
}
module "waf" {
  source = "../../modules/waf"
  name   = "${local.name}-web-acl"
  tags   = local.tags
}
module "game_data" {
  source      = "../../modules/dynamodb"
  name        = "${local.name}-arena-grid"
  kms_key_arn = module.kms.key_arn
  tags        = local.tags
}

module "vpc" {
  source               = "../../modules/vpc"
  name                 = "${local.name}-vpc"
  region               = var.aws_region
  vpc_cidr             = "10.20.0.0/16"
  azs                  = ["us-east-1a", "us-east-1b", "us-east-1c"]
  flow_log_kms_key_arn = module.kms.key_arn
  tags                 = local.tags
}
module "eks" {
  source                       = "../../modules/eks"
  name                         = "${local.name}-eks"
  vpc_id                       = module.vpc.vpc_id
  private_subnets              = module.vpc.private_subnets
  public_subnets               = module.vpc.public_subnets
  kms_key_arn                  = module.kms.key_arn
  ecr_repository_arn           = module.ecr.repository_arn
  endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  admin_role_arns              = var.admin_role_arns
  github_oidc_subjects         = var.github_oidc_subjects
  tags                         = local.tags
}
module "ecr" {
  source      = "../../modules/ecr"
  name        = "${local.name}-sample-app"
  kms_key_arn = module.kms.key_arn
  tags        = local.tags
}
module "logs" {
  source      = "../../modules/logs"
  name        = "${local.name}-logs-${data.aws_caller_identity.current.account_id}"
  kms_key_arn = module.kms.key_arn
  tags        = local.tags
}
module "iam" {
  source            = "../../modules/iam"
  name              = local.name
  cluster_name      = module.eks.cluster_name
  oidc_provider_arn = module.eks.oidc_provider_arn
  logs_bucket_arn   = module.logs.bucket_arn
  game_table_arn    = module.game_data.table_arn
  tags              = local.tags
}
module "alb_controller" {
  source            = "../../modules/alb-controller"
  name              = local.name
  oidc_provider_arn = module.eks.oidc_provider_arn
  tags              = local.tags
}
module "karpenter" {
  source            = "../../modules/karpenter"
  cluster_name      = module.eks.cluster_name
  oidc_provider_arn = module.eks.oidc_provider_arn
  tags              = local.tags
}
