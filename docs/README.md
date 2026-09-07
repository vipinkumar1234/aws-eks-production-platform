# Deploying the EKS Gaming Platform

This runbook covers the values that must be changed before using this repository. It assumes one AWS account per environment, private EKS worker nodes, Argo CD, and GitHub Actions with OIDC.

## Naming and regions

Names use lowercase kebab case: `<project>-<region-alias>-<environment>-<component>`. Use the AWS region aliases below:

| AWS region | Alias | Example cluster name |
| --- | --- | --- |
| `ap-southeast-1` | `apse1` | `eks-platform-apse1-dev-eks` |
| `us-east-1` | `use1` | `eks-platform-use1-prod-eks` |

For another region, set `aws_region`, `region_short_name`, and the three AZs together. Keep aliases stable because they become part of resource names.

## Values to change

1. Copy the environment file:

   ```bash
   cp terraform/environments/dev/terraform.tfvars.example terraform/environments/dev/terraform.tfvars
   ```

2. Replace `ORG/REPO` in `github_oidc_subjects` with the exact GitHub repository. Replace `admin_role_arns` with the IAM role ARN used by platform administrators, for example `arn:aws:iam::<ACCOUNT_ID>:role/eks-platform-admin`.
3. Configure an encrypted, versioned Terraform state bucket and DynamoDB lock table in the environment `versions.tf` before `terraform init`.
4. Change `SecurityContact` in each environment root to a real platform contact.
5. After Terraform apply, collect these outputs:

   ```bash
   terraform -chdir=terraform/environments/dev output
   ```

   Replace the GitOps placeholders as follows:

   | Placeholder | Terraform output |
   | --- | --- |
   | `REPLACE_WITH_TERRAFORM_CLUSTER_NAME` | `cluster_name` |
   | `REPLACE_WITH_TERRAFORM_VPC_ID` | `vpc_id` |
   | `REPLACE_WITH_ALB_CONTROLLER_ROLE_ARN` | `alb_controller_role_arn` |
   | `REPLACE_WITH_FLUENT_BIT_ROLE_ARN` | `fluent_bit_role_arn` |
   | `REPLACE_WITH_LOGS_BUCKET_NAME` | `logs_bucket_name` |
   | `REPLACE_WITH_AWS_REGION` | `aws_region` from the tfvars file |
   | `REPLACE_WITH_ECR_URL` | `ecr_repository_url` |

   The ALB role ARN belongs in the controller Helm values. The Fluent Bit role ARN belongs in `gitops/observability/fluent-bit/values.yaml`. The bucket name belongs in the Fluent Bit S3 output. Do not replace an ARN with an IAM role name: IRSA requires the complete ARN.

## Production approval gate

The Terraform workflow validates both environments, creates a production plan on a merge to `main`, uploads the readable `prod-plan.txt` and exact binary `prod.tfplan` for seven days, and waits at the `apply-prod` job. Configure a GitHub Environment named exactly `prod` with required reviewers and deployment branch restrictions. Add `AWS_PROD_TERRAFORM_ROLE_ARN` as a repository or organization secret and as an environment secret for `prod`. Review `prod-plan.txt` and workflow checks before approving. The apply job uses the approved environment and applies the exact uploaded `prod.tfplan`.

## Provision and bootstrap

```bash
export ENVIRONMENT=dev
bash scripts/bootstrap.sh
aws eks update-kubeconfig --region ap-southeast-1 --name "$(terraform -chdir=terraform/environments/dev output -raw cluster_name)"
kubectl apply -f gitops/argocd/bootstrap/namespace.yaml
kubectl apply -f gitops/argocd/projects/platform-project.yaml
```

Install Argo CD using the version approved by your organization, then apply the platform and observability Argo applications. Commit environment-specific GitOps values through review. Do the same with `prod` only after promoting the exact image digest and approving the production GitHub environment.

## Application access

ArenaGrid is a multiplayer tic-tac-toe arena. Two players, `red` and `blue`, take turns claiming board positions `0` through `8`. It exposes `/healthz`, `/api/game/state`, and `POST /api/game/move`. Game state is stored in encrypted DynamoDB with point-in-time recovery, while WebSocket presence and matchmaking remain future extensions.

Terraform creates a public ACM certificate using DNS validation in the supplied Route 53 hosted zone. The dedicated `terraform/modules/alb-controller` module creates the controller's IRSA role. Argo CD installs the AWS Load Balancer Controller, and [gitops/apps/sample-app/ingress.yaml](../gitops/apps/sample-app/ingress.yaml) creates the application internet-facing AWS ALB with HTTPS at runtime. This separation is intentional: a static Terraform ALB cannot target Kubernetes pods safely before the cluster service exists. Replace `REPLACE_WITH_APP_DOMAIN` and `REPLACE_WITH_ACM_CERTIFICATE_ARN` in that Ingress file, then point the application DNS record to the ALB hostname shown by:

```bash
kubectl -n sample-app get ingress sample-app
```

Open `https://game.example.com/` after DNS propagation. Do not expose the app without an approved domain, WAF policy, rate limits, and authentication.

## SSM access to EC2 nodes

Managed EKS nodes receive `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore`. Ensure the VPC endpoints for `ssm`, `ssmmessages`, `ec2messages`, and `logs` remain enabled and that node security groups allow HTTPS egress. Find managed instances with:

```bash
aws ssm describe-instance-information --region ap-southeast-1
aws ssm start-session --target <INSTANCE_ID> --region ap-southeast-1
```

Use SSM instead of SSH. Karpenter-created nodes use a separate node role; attach the same managed policy there before enabling SSM sessions for Karpenter capacity.

## Logs and encryption

The platform creates one customer-managed KMS key for EKS secrets, ECR, and the log bucket. It also creates a private S3 bucket with versioning, public access blocked, and lifecycle expiration. Fluent Bit assumes its dedicated IRSA role and writes Kubernetes logs to that bucket. Set a retention period appropriate to compliance, and add an S3 bucket policy or organization controls if centralized logging requires cross-account delivery.

## Checks

```bash
(cd application/sample-app && bash check.sh)
(cd terraform && bash check.sh)
(cd gitops && bash argocd/check.sh && bash platform/check.sh && bash observability/check.sh && bash apps/sample-app/check.sh)
```

Run `terraform plan` for both environments and review IAM, public ALB, NAT, endpoint, KMS, and S3 changes before applying. This repository is production-shaped, not a complete production game platform: add durable game state, TLS, WAF, authentication, backup/restore testing, alert routing, and managed database/Redis capacity before a public launch.