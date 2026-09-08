variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}
variable "bucket_name" {
  type    = string
  default = "worldofaws-app-terraform-state-001495086648"
}
variable "tags" {
  type = map(string)
  default = {
    ManagedBy = "terraform-bootstrap"
    Purpose   = "terraform-state"
  }
}
