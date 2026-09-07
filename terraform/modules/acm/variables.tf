variable "domain_name" { type = string }
variable "route53_zone_id" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
