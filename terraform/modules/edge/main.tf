# Terraform owns the ALB so its CloudFront URL is available before GitOps bootstrap.
resource "aws_security_group" "alb" {
  name        = "${var.name}-edge-alb"
  description = "Private ALB: CloudFront VPC origin ingress only"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-edge-alb" })
}
resource "aws_lb" "app" {
  name                       = "${var.name}-edge"
  internal                   = true
  load_balancer_type         = "application"
  subnets                    = var.private_subnets
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
  tags                       = merge(var.tags, { Name = "${var.name}-edge" })
}
resource "aws_lb_target_group" "app" {
  name                 = "${var.name}-game"
  port                 = 8080
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = var.vpc_id
  deregistration_delay = 30
  health_check {
    path    = "/readyz"
    port    = "traffic-port"
    matcher = "200"
  }
  tags = merge(var.tags, { Name = "${var.name}-game" })
}
# HTTPS terminates at CloudFront. HTTP is confined to the VPC origin path.
resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
  tags = merge(var.tags, { Name = "${var.name}-http" })
}
resource "aws_vpc_security_group_egress_rule" "alb_to_pods" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = var.node_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  description                  = "ALB requests and health checks to application pods"
  tags                         = merge(var.tags, { Name = "${var.name}-alb-to-pods" })
}
resource "aws_vpc_security_group_ingress_rule" "pods_from_alb" {
  security_group_id            = var.node_security_group_id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 8080
  to_port                      = 8080
  description                  = "Application targets accept only the private ALB on port 8080"
  tags                         = merge(var.tags, { Name = "${var.name}-pods-from-alb" })
}
resource "aws_cloudfront_vpc_origin" "app" {
  vpc_origin_endpoint_config {
    name                   = "${var.name}-origin"
    arn                    = aws_lb.app.arn
    http_port              = 80
    https_port             = 443
    origin_protocol_policy = "http-only"
    origin_ssl_protocols {
      items    = ["TLSv1.2"]
      quantity = 1
    }
  }
  tags       = merge(var.tags, { Name = "${var.name}-origin" })
  depends_on = [aws_lb_listener.app]
}
# AWS creates this SG with the VPC origin. Do not create or edit the service SG.
data "aws_security_group" "cloudfront" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
  filter {
    name   = "group-name"
    values = ["CloudFront-VPCOrigins-Service-SG*"]
  }
  depends_on = [aws_cloudfront_vpc_origin.app]
}
resource "aws_vpc_security_group_ingress_rule" "alb_from_cloudfront" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = data.aws_security_group.cloudfront.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
  description                  = "Only the AWS-managed CloudFront VPC origin security group"
  tags                         = merge(var.tags, { Name = "${var.name}-cloudfront-to-alb" })
}
resource "aws_cloudfront_distribution" "app" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.name} gaming application"
  price_class         = "PriceClass_All"
  web_acl_id          = var.web_acl_arn
  wait_for_deployment = true
  origin {
    domain_name = aws_lb.app.dns_name
    origin_id   = "${var.name}-origin"
    vpc_origin_config {
      vpc_origin_id = aws_cloudfront_vpc_origin.app.id
    }
  }
  default_cache_behavior {
    target_origin_id         = "${var.name}-origin"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD"]
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # AWS managed CachingDisabled
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" # AWS managed AllViewer
    compress                 = true
  }
  # Don't retain startup errors or user-specific error responses at the edge.
  dynamic "custom_error_response" {
    for_each = toset([400, 403, 404, 405, 414, 416, 500, 501, 502, 503, 504])
    content {
      error_code            = custom_error_response.value
      error_caching_min_ttl = 0
    }
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate { cloudfront_default_certificate = true }
  tags       = merge(var.tags, { Name = "${var.name}-cdn" })
  depends_on = [aws_vpc_security_group_ingress_rule.alb_from_cloudfront]
}
