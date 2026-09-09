# AWS resource naming and tagging

AWS defines different naming constraints for each service, rather than a single mandatory universal naming format. This repository uses `<project>-<region-short>-<environment>-<purpose>` consistently, retaining its existing prefix order. Examples: `eks-platform-apse1-dev-eks`, `eks-platform-use1-prod-sample-app`, and `eks-platform-use1-prod-karpenter-controller`. See [AWS tagging best practices](https://docs.aws.amazon.com/whitepapers/latest/tagging-best-practices/tagging-best-practices.html).

Project identifiers are validated as 3-13 lowercase alphanumeric/hyphen characters, starting with a letter and ending alphanumeric. Region short names are 3-5 lowercase alphanumeric characters. Dev/prod are fixed environment suffixes. These bounds leave room for the ALB 32-character limit and IAM 64-character names, including module-generated uniqueness suffixes. Use an unambiguous regional abbreviation. Changing either identifier is a resource migration, not a cosmetic rename.

| Resources | Naming behavior |
|---|---|
| EKS cluster | `<prefix>-eks`; AWS control-plane logs retain `/aws/eks/<cluster>/cluster` |
| Managed node group / launch template | `<prefix>-eks-system` plus module uniqueness suffix where applicable |
| Managed node / control-plane IAM roles | Short `<prefix>-eks-sys` / `<prefix>-eks-ctl` prefixes leave room for generated suffixes |
| Karpenter controller role/policy | `<prefix>-karpenter-controller` |
| Karpenter node role / instance profile | `<prefix>-karpenter-node`; instance profile is Terraform-managed |
| Interruption queue | `<prefix>-karpenter-interruptions` |
| EventBridge rules | `<first-8-prefix-chars>-<6-char-prefix-hash>-<upstream-event-type>-<unique-suffix>` to meet EventBridge name-prefix limits; full ownership remains in tags. Upstream event names use AWS-permitted mixed case |
| Karpenter EC2 instances, volumes and launch templates | `Name=<prefix>-workload` where Karpenter propagates tags; IDs/launch template names remain controller-generated |
| VPC, subnets, routes, NAT, gateways, security groups | Module-generated purpose/AZ names derived from the prefix; common tags no longer overwrite every resource's Name |
| VPC flow-log IAM role/policy and log group | `<prefix>-vpc-flow` prefix and `/aws/vpc/<prefix>-vpc/...` |
| S3/DynamoDB VPC endpoints | `<prefix>-vpc-s3-endpoint` / `<prefix>-vpc-dynamodb-endpoint` Name tags |
| ECR repository | `<prefix>-sample-app` |
| ALB | `<prefix>-app`; target groups/security groups retain controller-generated names and cluster/stack tags |
| ACM and validation records | Certificate has `<prefix>-app-certificate` Name tag; certificate ARN and DNS validation names are AWS-generated |
| WAF | `<prefix>-web-acl`; rule and metric names remain service-compatible |
| Cognito / DynamoDB | `<prefix>-arena-grid`; client adds `-game`; Cognito domain includes account ID for uniqueness |
| KMS | `alias/<prefix>-platform`; key IDs are AWS-generated |
| Log bucket | `<prefix>-logs-<account-id>` for global uniqueness |
| Session secret | `<prefix>/game-session` (Secrets Manager supports hierarchical paths) |
| Application IAM roles/policies | Purpose-specific suffixes such as `-game`, `-fluent-bit`, `-session`, `-game-kms`; inline policies now have explicit names |
| Terraform state bucket | Choose `<prefix>-tfstate-<account-id>` before bootstrap; never rename an existing backend without explicit state migration |

The state bootstrap preserves existing tags and adds Name, Region, ManagedBy and Environment; export `TF_VAR_project`, `TF_VAR_owner` and `TF_VAR_cost_center` locally to include ownership tags. CI maps owner/cost-center and reads the project from `TFVARS_JSON` (default `eks-platform`).

All Terraform resources supporting provider default tags receive `Project`, `Environment`, `Region`, `ManagedBy`, `InfraVersion`, `Owner`, and `CostCenter`. Karpenter and ALB resources are created outside Terraform, so their manifests explicitly supply ownership/cost tags. AWS IDs, ARNs, ENIs, EKS-managed ASGs and controller-generated resource names cannot all be replaced with custom names. Relationships, ownership tags and AWS-generated suffixes identify those resources. Untaggable objects (inline policies, policy attachments, DNS records, secret versions) inherit identity from their named parent; they cannot have arbitrary tags added.

Existing installation: inspect `terraform plan` before applying. Node-group/IAM/flow-log naming changes can replace resources; the ALB name annotation applies when a load balancer is created and may require a separate ingress migration for existing ALBs. Do not delete a working ingress merely to change its name. Preserve DNS and data, back up state, and use a reviewed maintenance or blue/green migration where a replacement causes downtime. Fixed Karpenter IAM names require separate prefixes or accounts across environments; only one stack should own an account-level OIDC provider.
