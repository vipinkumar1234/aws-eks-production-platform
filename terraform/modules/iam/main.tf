data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "game_assume_role" {
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
      values   = ["system:serviceaccount:sample-app:sample-app"]
    }
  }
}

resource "aws_iam_role" "game" {
  name               = "${var.name}-game"
  assume_role_policy = data.aws_iam_policy_document.game_assume_role.json
  tags               = merge(var.tags, { Name = "${var.name}-game" })
}

resource "aws_iam_role_policy" "game" {
  name = "${var.name}-game"
  role = aws_iam_role.game.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"], Resource = var.game_table_arn }]
  })
}

data "aws_iam_policy_document" "fluent_bit_assume_role" {
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
      values   = ["system:serviceaccount:observability:fluent-bit"]
    }
  }
}

resource "aws_iam_role" "fluent_bit" {
  name               = "${var.name}-fluent-bit"
  assume_role_policy = data.aws_iam_policy_document.fluent_bit_assume_role.json
  tags               = merge(var.tags, { Name = "${var.name}-fluent-bit" })
}

resource "aws_iam_role_policy" "fluent_bit" {
  name = "${var.name}-fluent-bit"
  role = aws_iam_role.fluent_bit.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["s3:AbortMultipartUpload", "s3:ListBucket", "s3:PutObject", "s3:PutObjectTagging"], Resource = [var.logs_bucket_arn, "${var.logs_bucket_arn}/*"] }]
  })
}

resource "aws_iam_role_policy" "fluent_bit_kms" {
  name   = "${var.name}-fluent-bit-kms"
  role   = aws_iam_role.fluent_bit.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["kms:GenerateDataKey", "kms:Decrypt"], Resource = var.kms_key_arn }] })
}
resource "aws_iam_role_policy" "game_kms" {
  name   = "${var.name}-game-kms"
  role   = aws_iam_role.game.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["kms:Decrypt"], Resource = var.kms_key_arn }] })
}
