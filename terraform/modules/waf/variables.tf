variable "name" { type = string }
variable "rate_limit_per_ip" {
  type    = number
  default = 2000
}
variable "tags" {
  type    = map(string)
  default = {}
}

variable "scope" {
  type    = string
  default = "REGIONAL"
  validation {
    condition     = contains(["REGIONAL", "CLOUDFRONT"], var.scope)
    error_message = "WAF scope must be REGIONAL or CLOUDFRONT."
  }
}
