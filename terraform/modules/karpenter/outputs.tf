output "instance_profile_name" { value = module.karpenter.instance_profile_name }
output "queue_name" { value = module.karpenter.queue_name }
output "controller_role_arn" { value = module.karpenter.iam_role_arn }
