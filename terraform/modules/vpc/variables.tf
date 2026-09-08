variable "name" { type = string }
variable "region" { type = string }
variable "vpc_cidr" { type = string }
variable "azs" { type = list(string) }
variable "interface_endpoint_services" {
  type    = set(string)
  default = ["ecr.api", "ecr.dkr", "ec2", "sts", "ssm", "ssmmessages", "ec2messages", "logs"]
}
variable "flow_log_kms_key_arn" {
  type    = string
  default = null
}
variable "tags" {
  type    = map(string)
  default = {}
}
