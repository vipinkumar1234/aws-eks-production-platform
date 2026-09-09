provider "aws" {
  region = var.aws_region
  default_tags { tags = { ManagedBy = "terraform", Project = var.project, Environment = "prod", Region = var.aws_region, InfraVersion = var.infra_version, Owner = var.owner, CostCenter = var.cost_center } }
}

data "aws_caller_identity" "current" {}

locals {
  name = "${var.project}-${var.region_short_name}-prod"
  tags = { Environment = "prod", Region = var.aws_region, InfraVersion = var.infra_version, Project = var.project, ManagedBy = "terraform", Owner = var.owner, CostCenter = var.cost_center }
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
  route53_zone_id = var.route53_zone_id
  tags            = merge(local.tags, { Name = "${local.name}-app-certificate" })
}
module "auth" {
  source        = "../../modules/cognito"
  name          = "${local.name}-arena-grid"
  domain_prefix = "${replace(local.name, "_", "-")}-${data.aws_caller_identity.current.account_id}"
  callback_url  = "https://${var.app_domain}/auth/callback"
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
  source             = "../../modules/vpc"
  name               = "${local.name}-vpc"
  region             = var.aws_region
  cluster_name       = "${local.name}-eks"
  single_nat_gateway = false
  vpc_cidr           = "10.20.0.0/16"
  azs                = ["${var.aws_region}a", "${var.aws_region}b"]
  tags               = local.tags
}
module "eks" {
  source                       = "../../modules/eks"
  name                         = "${local.name}-eks"
  vpc_id                       = module.vpc.vpc_id
  private_subnets              = module.vpc.private_subnets
  public_subnets               = module.vpc.public_subnets
  kms_key_arn                  = module.kms.key_arn
  endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  admin_role_arns              = var.admin_role_arns
  github_oidc_provider_arn     = var.github_oidc_provider_arn
  ecr_repository_arn           = module.ecr.repository_arn
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
  kms_key_arn       = module.kms.key_arn
  tags              = local.tags
}
module "alb_controller" {
  source            = "../../modules/alb-controller"
  name              = local.name
  oidc_provider_arn = module.eks.oidc_provider_arn
  tags              = local.tags
}

module "karpenter" {
  source       = "../../modules/karpenter"
  name         = local.name
  cluster_name = module.eks.cluster_name
  tags         = local.tags
}

# Reject an AMI from the wrong region, publisher, architecture or EKS version.
data "aws_ami" "karpenter" {
  owners = ["amazon"]
  filter {
    name   = "image-id"
    values = [var.karpenter_ami_id]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "name"
    values = ["amazon-eks-node-al2023-x86_64-standard-1.34-*"]
  }
}
