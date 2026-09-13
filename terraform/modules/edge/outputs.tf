output "app_domain" { value = aws_cloudfront_distribution.app.domain_name }
output "app_url" { value = "https://${aws_cloudfront_distribution.app.domain_name}" }
output "distribution_id" { value = aws_cloudfront_distribution.app.id }
output "target_group_arn" { value = aws_lb_target_group.app.arn }
output "alb_arn" { value = aws_lb.app.arn }
