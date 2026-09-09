resource "random_password" "session" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "session" {
  name                    = "${var.name}/game-session"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 7
  tags                    = merge(var.tags, { Name = "${var.name}/game-session" })
}

resource "aws_secretsmanager_secret_version" "session" {
  secret_id     = aws_secretsmanager_secret.session.id
  secret_string = random_password.session.result
}

resource "aws_iam_role_policy" "session" {
  name = "${var.name}-session"
  role = aws_iam_role.game.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.session.arn
  }] })
}

output "session_secret_arn" { value = aws_secretsmanager_secret.session.arn }
