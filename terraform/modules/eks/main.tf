data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "tls_certificate" "github" {
  url = "https://token.actions.githubusercontent.com/.well-known/openid-configuration"
}

resource "aws_iam_openid_connect_provider" "github" {
  count           = var.github_oidc_provider_arn == null ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.github.certificates[0].sha1_fingerprint]
  tags            = var.tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "21.0.0"

  name                         = var.name
  kubernetes_version           = var.kubernetes_version
  endpoint_private_access      = true
  endpoint_public_access       = length(var.endpoint_public_access_cidrs) > 0
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs
  enable_irsa                  = true
  iam_role_name                = "${var.name}-ctl"
  cluster_tags                 = { Name = var.name }
  addons = {
    vpc-cni = {
      before_compute       = true
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
    coredns                = {}
    kube-proxy             = {}
    eks-pod-identity-agent = { before_compute = true }
  }
  enable_cluster_creator_admin_permissions = false

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnets

  encryption_config = { resources = ["secrets"], provider_key_arn = var.kms_key_arn }
  create_kms_key    = false
  enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  access_entries = { for arn in var.admin_role_arns : arn => { principal_arn = arn, policy_associations = { admin = { policy_arn = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy", access_scope = { type = "cluster" } } } } }

  eks_managed_node_groups = {
    system = {
      ami_type             = "AL2023_x86_64_STANDARD"
      name                 = "${var.name}-system"
      use_name_prefix      = true
      iam_role_name        = "${var.name}-sys"
      launch_template_name = "${var.name}-system"
      labels               = { "workload-tier" = "system" }
      instance_types       = ["m6i.large"]
      min_size             = 2
      max_size             = 2
      desired_size         = 2
      capacity_type        = "ON_DEMAND"
      block_device_mappings = {
        root = {
          device_name = "/dev/xvda"
          ebs = {
            encrypted             = true
            volume_size           = 20
            volume_type           = "gp3"
            delete_on_termination = true
          }
        }
      }
      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
      }
      iam_role_additional_policies = {
        ssm = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
      }
    }
  }
  tags = var.tags
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.name}-github-actions"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Federated = (var.github_oidc_provider_arn != null ? var.github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn) }, Action = "sts:AssumeRoleWithWebIdentity", Condition = { StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }, StringLike = { "token.actions.githubusercontent.com:sub" = var.github_oidc_subjects } } }] })
  tags               = var.tags
}

resource "aws_iam_role_policy" "github_actions" {
  name = "${var.name}-ecr-push"
  role = aws_iam_role.github_actions.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages", "ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:UploadLayerPart", "ecr:PutImage", "ecr:InitiateLayerUpload"], Resource = var.ecr_repository_arn }
  ] })
}

moved {
  from = aws_iam_openid_connect_provider.github
  to   = aws_iam_openid_connect_provider.github[0]
}
