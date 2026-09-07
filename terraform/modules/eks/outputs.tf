output "cluster_name" { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "cluster_arn" { value = module.eks.cluster_arn }
output "oidc_provider_arn" { value = module.eks.oidc_provider_arn }
output "github_actions_role_arn" { value = aws_iam_role.github_actions.arn }
output "node_security_group_id" { value = module.eks.node_security_group_id }
output "cluster_kms_key_arn" { value = var.kms_key_arn }
