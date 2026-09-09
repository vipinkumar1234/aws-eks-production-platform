# AWS-only bootstrap; Helm/CRDs are installed from a VPC-connected host.
module "karpenter" {
  source                          = "terraform-aws-modules/eks/aws//modules/karpenter"
  version                         = "21.25.0"
  cluster_name                    = var.cluster_name
  namespace                       = "kube-system"
  service_account                 = "karpenter"
  create_pod_identity_association = true
  create_instance_profile         = true
  enable_inline_policy            = true
  iam_role_name                   = "${var.name}-karpenter-controller"
  iam_role_use_name_prefix        = false
  iam_policy_name                 = "${var.name}-karpenter-controller"
  iam_policy_use_name_prefix      = false
  node_iam_role_name              = "${var.name}-karpenter-node"
  node_iam_role_use_name_prefix   = false
  queue_name                      = "${var.name}-karpenter-interruptions"
  # EventBridge prefixes allow only 38 characters, including the upstream event type.
  rule_name_prefix = "${substr(var.name, 0, 8)}-${substr(sha1(var.name), 0, 6)}-"
  tags             = merge(var.tags, { Name = "${var.name}-karpenter" })
}
