# Optional custom-domain preparation; the default CloudFront test URL needs no DNS.
variable "dns_zone_name" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional public zone for a domain you control; does not register a domain or change the game URL"
  validation {
    condition     = var.dns_zone_name == null ? true : can(regex("^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$", var.dns_zone_name))
    error_message = "Use a lowercase domain without a scheme, path or trailing dot, or null to skip DNS."
  }
}

resource "aws_route53_zone" "optional" {
  count   = var.dns_zone_name == null ? 0 : 1
  name    = var.dns_zone_name
  comment = "Optional game DNS; default game URL remains CloudFront"
  tags    = merge(local.tags, { Name = var.dns_zone_name })
  lifecycle { prevent_destroy = true }
}

output "dns_zone" {
  value = {
    enabled      = var.dns_zone_name != null
    name         = var.dns_zone_name
    zone_id      = try(aws_route53_zone.optional[0].zone_id, null)
    name_servers = try(aws_route53_zone.optional[0].name_servers, [])
  }
}
