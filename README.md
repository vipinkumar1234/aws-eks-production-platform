# AWS EKS Production Platform

Production-shaped EKS platform code for learning and operating the complete path from GitHub commit to a running Kubernetes workload.

## Environments

| Environment | AWS region | Terraform root | Purpose |
| --- | --- | --- | --- |
| dev | `ap-southeast-1` | `terraform/environments/dev` | Development and integration |
| prod | `us-east-1` | `terraform/environments/prod` | Production promotion |

Resource names follow `<project>-<region-alias>-<environment>-<component>`, for example `eks-platform-apse1-dev-eks`. Region aliases are the AWS abbreviations `apse1` for `ap-southeast-1` and `use1` for `us-east-1`.

AWS resources are tagged with `InfraVersion`. CI populates it from the deployed Git branch; local Terraform runs default to `local`.

## Repository layout

- `terraform/modules`: reusable VPC, EKS, ECR, ACM certificate, IAM, ALB controller, logs, and Karpenter modules.
- `terraform/environments`: isolated regional roots and state keys.
- `gitops/argocd`: Argo CD bootstrap and project policy.
- `gitops/platform`: Karpenter and platform controller values/manifests.
- `gitops/observability`: Prometheus, Grafana, Alertmanager, and Fluent Bit values.
- `gitops/apps/sample-app`: restricted sample workload, service, and network policy.
- `gitops/apps/sample-app/ingress.yaml`: application ALB definition managed by AWS Load Balancer Controller.
- `application/sample-app`: ArenaGrid multiplayer game API and tests.
- `.github/workflows`: Terraform, application, GitOps, and secret scanning pipelines.
- `docs`: architecture and operational notes.
- `docs/README.md`: end-to-end deployment, replacement values, access, SSM, and operations runbook.
- `DEPLOYMENT_README.md`: complete step-by-step deployment, GitOps bootstrap, ALB access, logging, rollback, and production approval guide.
- `COMPONENTS_README.md`: one-line explanations of every major component and production term, including bin packing and GitOps.

## Prerequisites

Install approved versions of Terraform >= 1.8, AWS CLI, kubectl, Helm, kubeconform, tfsec, Trivy, and Python 3.12. Authenticate locally with an AWS role that can bootstrap the account. Never use access keys in GitHub.

Ansible creates or verifies the encrypted S3 state bucket before any environment Terraform backend initializes. Use `bash scripts/bootstrap.sh` for an environment, or `bash scripts/bootstrap-prerequisites.sh` for the initial state/OIDC bootstrap. Dev and prod use separate state buckets under `eks/dev` and `eks/prod` keys. Create a public Route 53 hosted zone named `worldofaws.app`; Terraform fetches its hosted-zone ID automatically.

## Configure GitHub OIDC

1. Replace `ORG/REPO` in both `terraform.tfvars.example` files with the exact repository.
2. Provide an administrator role ARN through `admin_role_arns` for initial EKS access.
3. Apply Terraform using a bootstrap role, then set GitHub environment variables/secrets:
	- `AWS_TERRAFORM_ROLE_ARN`: role created for Terraform operations.
	- `AWS_APP_ROLE_ARN`: role allowed to push to the environment ECR repository.
	- `ECR_REPOSITORY`: exact Terraform ECR repository name.
4. Restrict GitHub environments so `prod` requires reviewers and only protected branches can deploy.

For the configured repository, GitHub Actions assumes AWS through OIDC using `arn:aws:iam::001495086648:role/AutomationAdminAll`; configure that role's trust policy for `vipinkumar1234/aws-eks-production-platform` and the allowed `feat*` and `main` branch subjects. The workflow verifies the resulting AWS account ID before Terraform runs.

Production Terraform uses a two-stage workflow: `plan-prod` creates an immutable plan artifact, then `apply-prod` targets the protected `prod` GitHub Environment. Configure `AWS_PROD_TERRAFORM_ROLE_ARN` as a repository or organization secret, and configure the `prod` Environment with the same secret plus required reviewers. The apply job cannot start until those reviewers approve it, and it applies the uploaded plan rather than creating a new unreviewed plan.

Branches beginning with `feat` can deploy Terraform changes to `dev` through the reviewed `deploy-dev` job. The job tags resources with that branch name in `InfraVersion`. Other branch pushes do not deploy infrastructure. Only `main` can start the production plan and apply path.

The trust policy is subject-scoped to repository and branch. Tighten it further to GitHub environments if your organization uses them.

## Provision dev

From the repository root:

```bash
cp terraform/environments/dev/terraform.tfvars.example terraform/environments/dev/terraform.tfvars
# edit the placeholder account, repository, and role values
export ENVIRONMENT=dev
bash scripts/bootstrap.sh
```

After Terraform completes, update the `REPLACE_WITH_*` values under `gitops/platform` and `gitops/apps/sample-app` from Terraform outputs, commit those environment-specific values through your normal review process, and install Argo CD. Apply `gitops/argocd/bootstrap/namespace.yaml` and `gitops/argocd/projects/platform-project.yaml`, then let Argo CD reconcile the three root applications.

Do not commit generated kubeconfigs, Terraform plans, state, credentials, or plaintext Kubernetes secrets. Use AWS Secrets Manager with External Secrets for application secrets.

## Promotion flow

1. A pull request runs Terraform validation/tfsec, GitOps policy validation, application tests, and secret scanning.
2. A merge to `main` builds and scans an immutable image tagged with the commit SHA, pushes it to ECR, and updates the dev GitOps image reference.
3. Argo CD synchronizes dev; promote the same image digest to prod through a reviewed GitOps change.
4. Promote the same image digest to prod after approval. Keep prod GitHub environment approval enabled.

## Local checks

```bash
(cd terraform && bash check.sh)
(cd gitops && bash argocd/check.sh && bash platform/check.sh && bash observability/check.sh && bash apps/sample-app/check.sh)
(cd application/sample-app && bash check.sh)
```

Some checks require the named security tools to be installed. The CI workflows install or invoke their corresponding actions.

## Security baseline

EKS secrets use KMS encryption, control-plane audit logs are enabled, nodes run in private subnets, NAT is multi-AZ, ECR scans immutable images, GitHub uses short-lived OIDC credentials, and application pods run as non-root with dropped capabilities, read-only filesystems, probes, resource limits, and default-deny ingress/egress policy. Review the generated Terraform plan and AWS IAM permissions before applying in a real account.