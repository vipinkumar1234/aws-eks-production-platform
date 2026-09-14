variable "name" { type = string }
variable "kms_key_arn" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
variable "deletion_protection_enabled" {
  type    = bool
  default = true
}
