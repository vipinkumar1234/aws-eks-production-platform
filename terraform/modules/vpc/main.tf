terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "6.0.1"

  name = var.name
  cidr = var.vpc_cidr
  azs  = var.azs

  private_subnets = [for index, _ in var.azs : cidrsubnet(var.vpc_cidr, 4, index)]
  public_subnets  = [for index, _ in var.azs : cidrsubnet(var.vpc_cidr, 4, index + 8)]

  enable_nat_gateway                              = true
  single_nat_gateway                              = var.single_nat_gateway
  enable_flow_log                                 = true
  create_flow_log_cloudwatch_log_group            = true
  create_flow_log_cloudwatch_iam_role             = true
  flow_log_cloudwatch_log_group_retention_in_days = 14
  vpc_flow_log_iam_role_name                      = "${var.name}-flow"
  vpc_flow_log_iam_policy_name                    = "${var.name}-flow"
  flow_log_cloudwatch_log_group_name_prefix       = "/aws/vpc/${var.name}/"
  enable_dns_hostnames                            = true
  enable_dns_support                              = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
    "karpenter.sh/discovery"          = var.cluster_name
  }
  tags = var.tags
}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
  tags              = merge(var.tags, { Name = "${var.name}-s3-endpoint" })
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.private_route_table_ids
  tags              = merge(var.tags, { Name = "${var.name}-dynamodb-endpoint" })
}
