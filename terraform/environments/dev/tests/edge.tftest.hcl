# Offline provider mocks: no AWS resources or credentials are used.
mock_provider "aws" {
  mock_resource "aws_lb" {
    defaults = {
      arn      = "arn:aws:elasticloadbalancing:ap-southeast-1:123456789012:loadbalancer/app/test/1234567890123456"
      dns_name = "internal-test.ap-southeast-1.elb.amazonaws.com"
    }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:ap-southeast-1:123456789012:targetgroup/test/1234567890123456" }
  }
  mock_resource "aws_security_group" { defaults = { id = "sg-0123456789abcdef0" } }
  mock_data "aws_security_group" { defaults = { id = "sg-0123456789abcdef1" } }
  mock_resource "aws_cloudfront_distribution" { defaults = { domain_name = "dexample.cloudfront.net" } }
}
run "private_https_edge" {
  command = apply
  module { source = "../../modules/edge" }
  variables {
    name                   = "game-apse1-dev"
    vpc_id                 = "vpc-0123456789abcdef0"
    private_subnets        = ["subnet-0123456789abcdef0", "subnet-0123456789abcdef1"]
    node_security_group_id = "sg-0123456789abcdef2"
    web_acl_arn            = "arn:aws:wafv2:us-east-1:123456789012:global/webacl/game/12345678-1234-1234-1234-123456789012"
    tags                   = { Project = "game", Environment = "dev" }
  }
  assert {
    condition     = aws_lb.app.internal && aws_lb_target_group.app.target_type == "ip"
    error_message = "ALB must be private with IP pod targets."
  }
  assert {
    condition     = aws_cloudfront_distribution.app.viewer_certificate[0].cloudfront_default_certificate && length(coalesce(aws_cloudfront_distribution.app.aliases, toset([]))) == 0
    error_message = "No custom domain or ACM certificate should be needed."
  }
  assert {
    condition     = aws_cloudfront_distribution.app.default_cache_behavior[0].viewer_protocol_policy == "redirect-to-https" && aws_cloudfront_distribution.app.default_cache_behavior[0].cache_policy_id != null
    error_message = "Viewer HTTPS and disabled caching protect login sessions."
  }
  assert {
    condition     = aws_cloudfront_distribution.app.default_cache_behavior[0].origin_request_policy_id != null && contains(aws_cloudfront_distribution.app.default_cache_behavior[0].allowed_methods, "POST")
    error_message = "Login cookies, query strings, Origin header and API methods must reach the app."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.alb_from_cloudfront.referenced_security_group_id == "sg-0123456789abcdef1" && aws_vpc_security_group_ingress_rule.pods_from_alb.from_port == 8080
    error_message = "Traffic must flow CloudFront service SG -> ALB -> pod port."
  }
  assert {
    condition     = output.app_url == "https://dexample.cloudfront.net"
    error_message = "The app origin must use the generated HTTPS address."
  }
}
