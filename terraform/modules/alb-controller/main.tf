data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "assume_role" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_arn, "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "${replace(var.oidc_provider_arn, "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/", "")}:sub"
      values   = ["system:serviceaccount:platform-system:aws-load-balancer-controller"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name}-alb-controller"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = var.tags
}

# AWS Load Balancer Controller requires wildcard resources for discovery and
# dynamically created load balancer, target group, and security group resources.
#tfsec:ignore:aws-iam-no-policy-wildcards
resource "aws_iam_role_policy" "this" {
  role = aws_iam_role.this.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["iam:CreateServiceLinkedRole"], Resource = "*", Condition = { StringEquals = { "iam:AWSServiceName" = "elasticloadbalancing.amazonaws.com" } } },
      { Effect = "Allow", Action = ["ec2:Describe*", "elasticloadbalancing:Describe*"], Resource = "*" },
      { Effect = "Allow", Action = ["ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress", "ec2:CreateSecurityGroup", "ec2:CreateTags", "ec2:DeleteTags", "ec2:DeleteSecurityGroup", "elasticloadbalancing:CreateLoadBalancer", "elasticloadbalancing:CreateTargetGroup", "elasticloadbalancing:CreateListener", "elasticloadbalancing:CreateRule", "elasticloadbalancing:DeleteLoadBalancer", "elasticloadbalancing:DeleteTargetGroup", "elasticloadbalancing:DeleteListener", "elasticloadbalancing:DeleteRule", "elasticloadbalancing:ModifyLoadBalancerAttributes", "elasticloadbalancing:ModifyTargetGroup", "elasticloadbalancing:ModifyTargetGroupAttributes", "elasticloadbalancing:ModifyListener", "elasticloadbalancing:AddTags", "elasticloadbalancing:RemoveTags", "elasticloadbalancing:RegisterTargets", "elasticloadbalancing:DeregisterTargets", "elasticloadbalancing:SetIpAddressType", "elasticloadbalancing:SetSecurityGroups", "elasticloadbalancing:SetSubnets", "elasticloadbalancing:SetWebAcl", "elasticloadbalancing:AddListenerCertificates", "elasticloadbalancing:RemoveListenerCertificates", "elasticloadbalancing:ModifyListenerAttributes", "wafv2:GetWebACL", "wafv2:AssociateWebACL", "wafv2:DisassociateWebACL", "shield:DescribeProtection", "shield:GetSubscriptionState", "cognito-idp:DescribeUserPoolClient"], Resource = "*" }
    ]
  })
}
