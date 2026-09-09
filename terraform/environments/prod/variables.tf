variable "aws_region" {
  type    = string
  default = "us-east-1"
}
variable "region_short_name" {
  type    = string
  default = "use1"
  validation {
    condition     = can(regex("^[a-z][a-z0-9]{2,4}$", var.region_short_name))
    error_message = "Region short name must be 3-5 lowercase alphanumeric characters."
  }
}
variable "admin_role_arns" {
  type = list(string)
  validation {
    condition     = length(var.admin_role_arns) > 0
    error_message = "Provide at least one administrator IAM role."
  }
}
variable "github_oidc_subjects" {
  type        = list(string)
  description = "Exact GitHub environment subjects authorized to push app images"
  validation {
    condition     = length(var.github_oidc_subjects) > 0 && alltrue([for subject in var.github_oidc_subjects : startswith(subject, "repo:") && !strcontains(subject, "*")])
    error_message = "Provide exact repository/environment subjects, without wildcards."
  }
}
variable "project" {
  type    = string
  default = "eks-platform"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,11}[a-z0-9]$", var.project))
    error_message = "Project must be 3-13 lowercase letters, digits or hyphens, starting with a letter and ending alphanumeric (ALB and IAM name limits)."
  }
}
variable "app_domain" {
  type    = string
  default = "play.arenagrid.example.com"
}
variable "route53_zone_id" {
  type        = string
  description = "Public Route 53 hosted zone ID that contains app_domain"
}
variable "infra_version" {
  type        = string
  default     = "local"
  description = "Git branch or deployment identifier recorded on AWS resources"
}
variable "cluster_endpoint_public_access_cidrs" {
  type        = list(string)
  default     = []
  description = "Approved administrator CIDRs; empty keeps the EKS API private-only"
  validation {
    condition     = alltrue([for cidr in var.cluster_endpoint_public_access_cidrs : can(cidrhost(cidr, 0)) && !endswith(cidr, "/0")])
    error_message = "Provide valid restricted CIDRs; public /0 access is forbidden."
  }
}

variable "github_oidc_provider_arn" {
  description = "Existing account-level GitHub OIDC provider ARN; null creates it in this state"
  type        = string
  default     = null
}

variable "owner" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,31}$", var.owner))
    error_message = "Supply a 2-32 character lowercase team/cost identifier."
  }
}

variable "cost_center" {
  type = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,31}$", var.cost_center))
    error_message = "Supply a 2-32 character lowercase team/cost identifier."
  }
}

variable "karpenter_ami_id" {
  type        = string
  description = "Tested regional EKS 1.34 AL2023 x86_64 standard AMI; explicitly pinned"
  validation {
    condition     = can(regex("^ami-[0-9a-f]{17}$", var.karpenter_ami_id))
    error_message = "Supply a pinned regional AL2023 x86_64 AMI ID."
  }
}
variable "karpenter_cpu_limit" {
  type    = number
  default = 128
  validation {
    condition     = var.karpenter_cpu_limit >= 8 && var.karpenter_cpu_limit <= 1000 && floor(var.karpenter_cpu_limit) == var.karpenter_cpu_limit
    error_message = "Workload CPU limit must be a whole number between 8 and 1000 vCPUs."
  }
}
