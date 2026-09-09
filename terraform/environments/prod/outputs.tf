output "cluster_name" { value = module.eks.cluster_name }
output "ecr_repository_url" { value = module.ecr.repository_url }
output "github_actions_role_arn" { value = module.eks.github_actions_role_arn }
output "vpc_id" { value = module.vpc.vpc_id }
output "alb_controller_role_arn" { value = module.alb_controller.role_arn }
output "fluent_bit_role_arn" { value = module.iam.fluent_bit_role_arn }
output "logs_bucket_name" { value = module.logs.bucket_name }
output "kms_key_arn" { value = module.kms.key_arn }
output "certificate_arn" { value = module.acm.certificate_arn }
output "app_domain" { value = module.acm.certificate_domain }
output "waf_web_acl_arn" { value = module.waf.web_acl_arn }
output "game_table_name" { value = module.game_data.table_name }
output "game_role_arn" { value = module.iam.game_role_arn }
output "cognito_user_pool_arn" { value = module.auth.user_pool_arn }
output "cognito_user_pool_client_id" { value = module.auth.user_pool_client_id }
output "cognito_user_pool_domain" { value = module.auth.user_pool_domain }

output "aws_region" { value = var.aws_region }
output "vpc_cidr" { value = "10.20.0.0/16" }

output "session_secret_arn" { value = module.iam.session_secret_arn }
output "cognito_issuer" { value = module.auth.issuer }

output "resource_prefix" { value = local.name }
output "owner" { value = var.owner }
output "cost_center" { value = var.cost_center }
output "project" { value = var.project }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "node_security_group_id" { value = module.eks.node_security_group_id }
output "karpenter_instance_profile" { value = module.karpenter.instance_profile_name }
output "karpenter_queue_name" { value = module.karpenter.queue_name }
output "karpenter_controller_role_arn" { value = module.karpenter.controller_role_arn }
output "karpenter_ami_id" { value = data.aws_ami.karpenter.id }
output "karpenter_cpu_limit" { value = var.karpenter_cpu_limit }
