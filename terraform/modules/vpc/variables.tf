variable "name" { type = string }
variable "region" { type = string }
variable "vpc_cidr" { type = string }
variable "azs" { type = list(string) }
variable "tags" {
  type    = map(string)
  default = {}
}

variable "single_nat_gateway" {
  type    = bool
  default = false
}

variable "cluster_name" { type = string }
