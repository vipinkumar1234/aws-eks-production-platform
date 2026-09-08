# EKS Platform Deployment Guide

This document is the complete deployment checklist for this repository. It deploys an Amazon EKS platform with private worker nodes, KMS encryption, VPC endpoints, Karpenter, AWS Load Balancer Controller, observability, S3 log storage, and ArenaGrid, a multiplayer tic-tac-toe arena API.

## Who can use this guide?

Someone with limited EKS experience can follow this guide in a sandbox or development AWS account if an AWS administrator first provides the required account access and state bucket. It is intentionally guided, not a zero-click installer. You still need to understand who owns the AWS account, which IAM role is safe to assume, what will be publicly reachable, and how to approve or roll back production changes.

This repository does not create the initial AWS administrator role, Terraform state bucket, GitHub repository, GitHub OIDC trust outside the Terraform stack, public Route 53 hosted zone, or GitHub Environment reviewers. It creates the ACM public certificate and DNS validation records after you provide an existing public Route 53 hosted zone ID. Ask an AWS/GitHub administrator to prepare those items before starting. Never experiment first in a production account.

The safest learning path is:

1. Deploy `dev` in a dedicated sandbox account.
2. Verify Terraform, Kubernetes, Argo CD, SSM, logs, and the ALB.
3. Destroy the sandbox only after reviewing the state and retained resources.
4. Promote an immutable image and reviewed GitOps change to `prod` through the approval gate.

## 1. Choose the environment

| Environment | Region | Region alias | Terraform directory |
| --- | --- | --- | --- |
| dev | `ap-southeast-1` | `apse1` | `terraform/environments/dev` |
| prod | `us-east-1` | `use1` | `terraform/environments/prod` |

Run the steps for one environment at a time. Do not use dev values in prod.

## 2. Install prerequisites

Install and authenticate these tools:

- Terraform `>= 1.8`
- AWS CLI
- kubectl
- Helm
- Python 3.12
- Docker or another OCI builder
- kubeconform, tfsec, Trivy, and Git

The AWS identity used for the first apply must be allowed to create VPC, EKS, IAM, KMS, ECR, S3, and CloudWatch resources. Use an assumed role or federation; do not store AWS access keys in GitHub.

On Windows, run the Bash commands through WSL2 or Git Bash. Terraform, AWS CLI, kubectl, and Helm can run from PowerShell, but `scripts/bootstrap.sh` and the repository check scripts require Bash.

Verify access:

```bash
aws sts get-caller-identity
aws configure get region
terraform version
kubectl version --client
helm version
```

## 3. Prepare Terraform state

Create the encrypted, versioned S3 state bucket and GitHub OIDC provider before initializing an environment backend. This repository now includes a local-bootstrap root for both prerequisites:

```bash
export AWS_REGION=ap-southeast-1
bash scripts/bootstrap-prerequisites.sh
```

The example state bucket name is `worldofaws-app-terraform-state-001495086648`. S3 bucket names are globally unique, so change it if AWS reports that the name is already taken. The bucket is not created by the dev/prod backend itself because Terraform must have a backend before it can manage resources in that backend.

Uncomment and customize the backend in both environment `versions.tf` files. Use a different state key for each environment:

```hcl
backend "s3" {
  bucket       = "YOUR_TERRAFORM_STATE_BUCKET"
  key          = "eks/dev/terraform.tfstate"
  region       = "ap-southeast-1"
  encrypt      = true
  use_lockfile = true
}
```

Use `eks/prod/terraform.tfstate` and `us-east-1` for production. Never commit state, plans, credentials, or `terraform.tfvars`.

## 4. Configure Terraform variables

Copy the example for the environment you are deploying:

```bash
cp terraform/environments/dev/terraform.tfvars.example terraform/environments/dev/terraform.tfvars
```

Change these values:

- `project`: lowercase project name.
- `admin_role_arns`: complete IAM role ARNs allowed to administer EKS, for example `arn:aws:iam::<ACCOUNT_ID>:role/platform-admin`.
- `github_oidc_subjects`: exact GitHub subject, for example `repo:ORG/REPO:ref:refs/heads/main`.
- `app_domain`: `dev.worldofaws.app` for dev or `worldofaws.app` for prod.
- `route53_zone_name`: `worldofaws.app`; Terraform fetches its public hosted-zone ID automatically.
- `infra_version`: optional local deployment identifier; CI sets this automatically to the Git branch name.
- `SecurityContact` in the environment `main.tf`: a real support address.
- `region_short_name` only when adding a region; keep `apse1` and `use1` stable.

For this repository, the dev feature-branch subject is:

```text
repo:vipinkumar1234/aws-eks-production-platform:ref:refs/heads/feat_test
```

The root modules create the KMS key, ECR repository, S3 log bucket, encrypted DynamoDB ArenaGrid table, Cognito authentication, WAF, VPC endpoints, SSM node permissions, ALB controller role, game IRSA role, and Fluent Bit role. Review all IAM and public ALB changes in the plan.

All AWS resources receive an `InfraVersion` tag. GitHub Actions sets it to the branch being deployed, so a production deployment from `main` is tagged `InfraVersion=main`. A local apply uses `InfraVersion=local` unless you set it explicitly:

```bash
terraform -chdir=terraform/environments/dev apply -var='infra_version=feature-game-api'
```

## 5. Validate and deploy dev

From the repository root:

```bash
terraform fmt -check -recursive terraform
terraform -chdir=terraform/environments/dev init \
  -backend-config="bucket=$TF_STATE_BUCKET_DEV" \
  -backend-config="key=eks/dev/terraform.tfstate" \
  -backend-config="region=ap-southeast-1" \
  -backend-config="encrypt=true" \
  -backend-config="use_lockfile=true"
terraform -chdir=terraform/environments/dev validate
terraform -chdir=terraform/environments/dev plan -out=tfplan
terraform -chdir=terraform/environments/dev apply tfplan
aws eks update-kubeconfig --region ap-southeast-1 \
  --name "$(terraform -chdir=terraform/environments/dev output -raw cluster_name)"
```

The convenience script performs the same flow. It runs Ansible first, so the state bucket exists before Terraform initializes its backend:

```bash
$env:ENVIRONMENT = "dev" # PowerShell
$env:TF_STATE_BUCKET_DEV = "your-dev-state-bucket"
bash scripts/bootstrap.sh # Bash, WSL, or Linux
```

Install Ansible before using the script:

```bash
python -m pip install ansible-core
ansible-galaxy collection install -r ansible/requirements.yml
```

The Ansible playbook creates or verifies these region-specific buckets:

```text
worldofaws-app-terraform-state-dev-001495086648
worldofaws-app-terraform-state-prod-001495086648
```

You may override them with `TF_STATE_BUCKET_DEV`, `TF_STATE_BUCKET_PROD`, or the single-run `TF_STATE_BUCKET` variable. The AWS identity running Ansible needs `s3:CreateBucket`, `s3:PutBucketVersioning`, `s3:PutBucketEncryption`, `s3:PutPublicAccessBlock`, `s3:PutBucketPolicy`, and `s3:HeadBucket` permissions.

Record these outputs:

```bash
terraform -chdir=terraform/environments/dev output
```

Important outputs are `cluster_name`, `vpc_id`, `ecr_repository_url`, `alb_controller_role_arn`, `game_role_arn`, `fluent_bit_role_arn`, `logs_bucket_name`, `game_table_name`, `certificate_arn`, `waf_web_acl_arn`, `cognito_user_pool_arn`, `cognito_user_pool_client_id`, and `cognito_user_pool_domain`.

## 6. Configure GitOps values

Replace these placeholders before Argo CD reconciliation:

| File or value | Replace with |
| --- | --- |
| `REPLACE_WITH_TERRAFORM_CLUSTER_NAME` | Terraform `cluster_name` output |
| `REPLACE_WITH_TERRAFORM_VPC_ID` | Terraform `vpc_id` output |
| `REPLACE_WITH_ALB_CONTROLLER_ROLE_ARN` | Terraform `alb_controller_role_arn` output |
| `REPLACE_WITH_FLUENT_BIT_ROLE_ARN` | Terraform `fluent_bit_role_arn` output |
| `REPLACE_WITH_LOGS_BUCKET_NAME` | Terraform `logs_bucket_name` output |
| `REPLACE_WITH_ACM_CERTIFICATE_ARN` | Terraform `certificate_arn` output |
| `REPLACE_WITH_WAF_WEB_ACL_ARN` | Terraform `waf_web_acl_arn` output |
| `REPLACE_WITH_GAME_TABLE_NAME` | Terraform `game_table_name` output |
| `REPLACE_WITH_GAME_ROLE_ARN` | Terraform `game_role_arn` output |
| Cognito auth annotation values | Terraform Cognito outputs |
| `REPLACE_WITH_APP_DOMAIN` | `dev.worldofaws.app` or Terraform `app_domain` output |
| `REPLACE_WITH_AWS_REGION` | `ap-southeast-1` or `us-east-1` |
| `REPLACE_WITH_ECR_URL` | Terraform `ecr_repository_url` output |
| `ORG/REPO` | GitHub organization and repository in Argo and Terraform files |
| `worldofaws.app` | Existing public Route 53 zone and owned DNS domain |

Use complete IAM role ARNs for IRSA annotations. A role name such as `eks-platform-apse1-dev-alb-controller` is not a valid replacement for the ARN.

After Terraform apply, render the account-specific GitOps values automatically:

```bash
export ENVIRONMENT=dev
bash scripts/render-gitops.sh
git diff -- gitops
```

Review the rendered values, commit them through code review, and let Argo CD reconcile. Do not commit Terraform state, credentials, or generated plan files.

The ALB controller is configured in `gitops/platform/applications.yaml`. The application ALB is declared in `gitops/apps/sample-app/ingress.yaml`; the controller creates the ALB and dynamically registers pod IPs.

## 7. Install Argo CD and bootstrap applications

Install Argo CD into the cluster using the version approved by your organization. A basic Helm installation is:

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm upgrade --install argocd argo/argo-cd \
  --namespace argocd --create-namespace
```

Before applying bootstrap manifests, replace `https://github.com/ORG/REPO.git` in these files with the repository URL:

- `gitops/argocd/bootstrap/namespace.yaml`
- `gitops/argocd/projects/platform-project.yaml`

Then apply the bootstrap:

```bash
kubectl apply -f gitops/argocd/bootstrap/namespace.yaml
kubectl apply -f gitops/argocd/projects/platform-project.yaml
```

Argo CD will reconcile:

- `gitops/platform`: AWS Load Balancer Controller, Karpenter, cert-manager, and metrics-server.
- `gitops/observability`: Prometheus, Grafana, Alertmanager, and Fluent Bit.
- `gitops/apps/sample-app`: namespace, deployment, Service, Ingress, and network policies.

Check status:

```bash
kubectl get applications -n argocd
kubectl get pods -A
kubectl -n platform-system get pods
kubectl -n sample-app get deployment,service,ingress
```

## 8. Build and publish the application

Run tests locally:

```bash
cd application/sample-app
python -m unittest discover -s tests -v
cd ../..
```

Build, scan, and push an immutable image to the Terraform-created ECR repository. The GitHub Actions application workflow does this on a push to `main` under the `dev` environment. Configure:

- `AWS_APP_ROLE_ARN`: GitHub OIDC role allowed to push to ECR.
- `ECR_REPOSITORY`: exact repository name from Terraform.

The workflow updates the dev GitOps image tag with the commit SHA. Promote the same image digest to production through a reviewed GitOps change; do not rebuild a different production image.

## 9. Access the application through ALB

The application Service remains `ClusterIP`. The AWS Load Balancer Controller creates an internet-facing ALB from the Ingress:

```bash
kubectl -n sample-app get ingress sample-app
```

Create a DNS alias record for the configured application domain pointing to the reported ALB hostname. The ACM module creates the certificate validation record; you still need the application DNS record. Then test over HTTPS:

```bash
curl https://game.example.com/healthz
curl https://game.example.com/api/game/state
curl -X POST https://game.example.com/api/game/move \
  -H 'Content-Type: application/json' \
  -d '{"player":"red","position":0}'
```

The Ingress configures ACM HTTPS and redirects HTTP to HTTPS. WAF and per-IP rate limiting are configured by Terraform. Add authentication and authorization for mutation endpoints before broad public exposure. ArenaGrid game state is stored in encrypted DynamoDB with point-in-time recovery; WebSocket presence and matchmaking remain future extensions.

## 10. SSM access to nodes

EKS managed nodes and Karpenter nodes receive `AmazonSSMManagedInstanceCore`. The VPC includes SSM, SSMMessages, EC2 Messages, and CloudWatch Logs endpoints.

Find managed instances and start a session:

```bash
aws ssm describe-instance-information --region ap-southeast-1
aws ssm start-session --target <INSTANCE_ID> --region ap-southeast-1
```

Use SSM instead of opening SSH to worker nodes.

## 11. Logs and encryption

The deployment creates:

- A customer-managed KMS key for EKS secrets, ECR, and S3 logs.
- A private, versioned S3 bucket for Kubernetes logs.
- A Fluent Bit IRSA role restricted to that bucket.
- CloudWatch and AWS service VPC endpoints for private node operation.

Verify log delivery:

```bash
kubectl -n observability get pods
aws s3 ls s3://<logs_bucket_name>/kubernetes/ --region ap-southeast-1
```

Set retention and cross-account controls according to your compliance requirements.

## 12. Production deployment and approval

Production Terraform is deployed only through `.github/workflows/terraform.yml`:

1. `validate` checks both Terraform roots.
2. `plan-prod` creates `prod.tfplan` and readable `prod-plan.txt` after a merge to `main`.
3. A GitHub Environment named exactly `prod` pauses `apply-prod` for required reviewers.
4. `apply-prod` applies the exact uploaded plan after approval.

Configure GitHub before using this flow:

- Create Environment `prod`.
- Add required reviewers.
- Restrict deployments to `main`.
- Add `AWS_PROD_TERRAFORM_ROLE_ARN` as a repository or organization secret and as a `prod` environment secret.
- Ensure the production role can access the production state backend and account.

## GitHub OIDC AWS trust policy

Configure the AWS role `arn:aws:iam::001495086648:role/AutomationAdminAll` to trust the GitHub OIDC provider. The trust policy must include the exact repository and allowed branches:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::001495086648:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": [
          "repo:vipinkumar1234/aws-eks-production-platform:ref:refs/heads/feat*",
          "repo:vipinkumar1234/aws-eks-production-platform:ref:refs/heads/main"
        ]
      }
    }
  }]
}
```

This AWS trust-policy change is performed once by an account administrator. GitHub Actions then obtains temporary credentials through OIDC; no local AWS CLI credentials are available or required on the runner.

## Required GitHub dev settings

Create a GitHub Environment named exactly `dev` and add these environment secrets:

| Secret | Value |
| --- | --- |
| `AWS_TERRAFORM_ROLE_ARN` | `arn:aws:iam::001495086648:role/AutomationAdminAll` |
| `TF_STATE_BUCKET_DEV` | Existing encrypted S3 state bucket name |
| `AWS_APP_ROLE_ARN` | Role allowed to push to the dev ECR repository |

Add the ECR repository name as an environment variable named `ECR_REPOSITORY`. Configure required reviewers if dev deployment approval is required.

Never bypass the environment approval by running an unreviewed local production apply. If emergency access is required, record the incident and review the resulting Terraform state afterward.

Branch deployment rules are enforced in `.github/workflows/terraform.yml`:

- Branches beginning with `feat` such as `feat_test` or `feature-login` can trigger the `deploy-dev` job.
- The `deploy-dev` job targets the `dev` GitHub Environment and requires its configured reviewers before applying.
- `InfraVersion` is set to the feature branch name.
- Other branch pushes do not deploy infrastructure.
- Only `main` can trigger the production plan and apply jobs.

Configure the `dev` Environment with required reviewers and the `AWS_TERRAFORM_ROLE_ARN` secret. Configure the `prod` Environment with required reviewers, protected deployment branches limited to `main`, and `AWS_PROD_TERRAFORM_ROLE_ARN`. GitHub Environment protection is required for the manual approval; the YAML job target alone does not create reviewers.

## 13. Verification and rollback

Run repository checks before merging:

```bash
(cd application/sample-app && bash check.sh)
(cd terraform && bash check.sh)
(cd gitops && bash argocd/check.sh && bash platform/check.sh && bash observability/check.sh && bash apps/sample-app/check.sh)
```

For an application rollback, revert the GitOps image change to the previously approved digest and let Argo CD synchronize. For infrastructure rollback, create a reviewed Terraform change; do not delete the state file or manually remove managed resources. Check ALB target health, pod readiness, Argo sync status, CloudWatch/EKS control-plane logs, and S3 Fluent Bit output during incident response.

## 14. Destroy after testing

The Terraform workflow includes a manual `workflow_dispatch` destroy path. It never runs from a push. In GitHub Actions, open the `terraform` workflow and select **Run workflow**:

1. Choose `dev` or `prod`.
2. Type `DESTROY-DEV` or `DESTROY-PROD` exactly.
3. Review the destroy plan in the job log.
4. Wait for the selected GitHub Environment approval if reviewers are configured.
5. The workflow applies the destroy plan.

The workflow uses the environment-specific AWS role and region. Production still requires the `prod` Environment protection configured earlier. Destroying an environment removes the EKS cluster, VPC, IAM resources, KMS key, ECR repository, and log bucket managed by that Terraform state. The S3 log bucket is protected from accidental non-empty deletion, so empty it manually first when required:

```bash
aws s3 rm s3://<logs_bucket_name> --recursive --region ap-southeast-1
```

Treat this as permanent data deletion. Export any logs or artifacts required for audit before destroying the environment.
