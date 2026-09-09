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
  tags               = merge(var.tags, { Name = "${var.name}-alb-controller" })
}

# Upstream v2.13.0 policy matches chart 1.13.0; review together when upgrading.
resource "aws_iam_role_policy" "this" {
  name   = "${var.name}-this"
  role   = aws_iam_role.this.id
  policy = file("${path.module}/iam_policy.json")
}
