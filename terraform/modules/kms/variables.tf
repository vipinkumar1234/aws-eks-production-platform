variable "name" { type = string }
variable "description" { type = string }
variable "tags" {
  type    = map(string)
  default = {}
}
