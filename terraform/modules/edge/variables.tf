variable "name" { type = string }
variable "vpc_id" { type = string }
variable "private_subnets" { type = list(string) }
variable "node_security_group_id" { type = string }
variable "web_acl_arn" { type = string }
variable "tags" { type = map(string) }
