# Deploy the application on EKS with Karpenter

Run commands from the repository root using Bash/WSL unless noted. Python scripts also work directly in PowerShell. Install Python 3.12, Terraform 1.14.0, AWS CLI v2, kubectl compatible with EKS 1.34, Helm and Docker. Install Python dependencies with `python -m pip install -r application/sample-app/requirements.txt`. Authenticate to your chosen AWS account (for example `aws sso login --profile YOUR_PROFILE`, then export `AWS_PROFILE`).

## 1. Supply account-specific inputs

Copy `terraform/environments/dev/terraform.tfvars.example` to `terraform.tfvars` in the same directory. Replace the administrator IAM role, real domain, public Route 53 zone, GitHub OIDC subject, `owner`, `cost_center`, and `karpenter_ami_id`. See the production checklist below before applying. The domain must belong to that zone. Dev is ap-southeast-1; prod is us-east-1. Use separate bucket names and state roots. If deploying both in one account, set the second environment's `github_oidc_provider_arn` to the existing account-level provider ARN.

The EKS endpoint is private by default. Run kubectl/Helm from a host connected to the VPC, or explicitly set `cluster_endpoint_public_access_cidrs` to your administrator's public `/32`. Do not use `0.0.0.0/0`. AWS account IDs, domain ownership and credentials are intentionally not guessed.

## 2. Create state storage, then initialize

```bash
export ENVIRONMENT=dev
export TF_VAR_project=eks-platform
export TF_VAR_owner=platform-team
export TF_VAR_cost_center=engineering
export TF_STATE_BUCKET_DEV=YOUR-GLOBALLY-UNIQUE-DEV-STATE-BUCKET
python scripts/terraform_init.py --environment dev
terraform -chdir=terraform/environments/dev plan -lock-timeout=5m -out=tfplan
terraform -chdir=terraform/environments/dev apply -lock-timeout=5m tfplan
```

`terraform_init.py` calls the AWS SDK first: verify account ownership, create a missing bucket, wait for existence, verify region, merge naming/ownership tags, block all public access, enforce bucket-owner ownership, enable versioning, preserve existing encryption (or enable AES256), and merge a deny-insecure-transport policy. Any failure stops before init. It then initializes with `use_lockfile=true` and `encrypt=true`. It never creates a DynamoDB lock table. A normal re-run preserves objects and existing policy statements. Use a dedicated state bucket because bootstrap hardens bucket-level access settings.

The bootstrap principal needs `sts:GetCallerIdentity`, S3 bucket creation/configuration/read permissions (including `s3:GetBucketTagging` and `s3:PutBucketTagging`) on the named bucket, `s3:ListBucket`, and object access. Terraform needs `s3:GetObject`/`s3:PutObject` on `eks/dev/terraform.tfstate`, plus `s3:GetObject`/`s3:PutObject`/`s3:DeleteObject` on `eks/dev/terraform.tfstate.tflock`. Existing KMS-encrypted buckets also require key permissions. State includes sensitive session-key material; only infrastructure administrators/CI should access it. No lifecycle rule expires state versions. Retain the bucket after cluster destruction.

Native locking details: [HashiCorp S3 backend documentation](https://developer.hashicorp.com/terraform/language/backend/s3). Backend-free `init -backend=false` used for validation does not access state and needs no bucket.

`ENVIRONMENT=dev bash scripts/bootstrap.sh` combines bootstrap, plan, apply and kubeconfig. Review your variables before using it. For prod, set `TF_STATE_BUCKET_PROD` and `ENVIRONMENT=prod`.

## 3. Build and push the image

```bash
export REGION=ap-southeast-1
export ECR_URL=$(terraform -chdir=terraform/environments/dev output -raw ecr_repository_url)
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ECR_URL%%/*}"
export IMAGE_TAG=$(git rev-parse HEAD)
docker build --platform linux/amd64 -t "$ECR_URL:$IMAGE_TAG" application/sample-app
# Run your image scan before pushing/deploying; CI runs Trivy with HIGH/CRITICAL gating.
docker push "$ECR_URL:$IMAGE_TAG"
export IMAGE_URI="$ECR_URL@$(aws ecr describe-images --region "$REGION" --repository-name "${ECR_URL#*/}" --image-ids imageTag="$IMAGE_TAG" --query 'imageDetails[0].imageDigest' --output text)"
```

Use a new tag for a changed image; ECR tags are immutable. `application.yml` runs tests, scans, publishes and opens a dev image PR. The first image is published even if the rendered tree is not yet available; use that digest for the next step.

## 4. Render and deploy GitOps

```bash
export GITOPS_REPO_URL=https://github.com/YOUR_ORG/YOUR_REPO.git
python scripts/render_gitops.py --environment dev
```

Review and commit `gitops/environments/dev` to main. The renderer requires an ECR SHA256 digest, resolves all Terraform outputs, and leaves shared templates untouched. If upgrading an already-rendered tree, remove obsolete cert-manager/Prometheus files from that tree and review Argo CD deletion plans before syncing; this repository change does not remove live cloud resources itself.

Before installing Argo CD, bootstrap the pinned Karpenter CRDs and controller from a host that can reach the EKS API. It uses EKS Pod Identity and runs two controller replicas on the managed system nodes. Helm owns the controller/CRDs; Argo CD owns the NodePool and EC2NodeClass. Do not give both tools ownership of the same objects.

```bash
python scripts/bootstrap_karpenter.py --environment dev
```

For an existing Karpenter installation, review CRD ownership and the release upgrade notes before running the script; it does not automatically take over CRDs owned by a different release.

```bash
aws eks update-kubeconfig --region "$REGION" --name "$(terraform -chdir=terraform/environments/dev output -raw cluster_name)"
# Pinned Argo CD chart; keep the server ClusterIP-only.
export ARGOCD_CHART_VERSION=10.8.2
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm upgrade --install argocd argo/argo-cd --version "$ARGOCD_CHART_VERSION" --namespace argocd --create-namespace -f gitops/argocd/values.yaml --wait --timeout 10m
kubectl apply -f gitops/environments/dev/argocd/projects/platform-project.yaml
kubectl apply -f gitops/environments/dev/argocd/bootstrap/namespace.yaml
kubectl apply --dry-run=server -f gitops/environments/dev/platform/karpenter-resources/nodepool.yaml
kubectl wait --for=condition=Ready ec2nodeclass --all --timeout=5m
kubectl wait --for=condition=Ready nodepool --all --timeout=5m
kubectl -n sample-app rollout status deployment/sample-app --timeout=10m
kubectl -n sample-app get ingress sample-app
```

Argo CD chart [10.8.2](https://github.com/argoproj/argo-helm/releases/tag/argo-cd-10.8.2) is pinned; review upgrades explicitly. For private Git repositories, configure Argo CD repository credentials first using its documented secret format; never commit credentials. Argo CD remains private; use `kubectl -n argocd port-forward svc/argocd-server 8443:443` for administration.

Create a Route 53 alias A record for your app domain pointing to the ALB shown by the ingress. ACM validation records are created by Terraform; the application alias is added after ALB provisioning. Visit the HTTPS domain, sign up, verify email, create a solo game, then test a friend invite in another signed-in browser. Check `/healthz`, `/readyz`, S3 log delivery and rolling restart behavior. These live checks require your AWS account and DNS.

## CI configuration

Create GitHub environments `dev` and optionally `prod`. Restrict prod to main and enable required reviewers. Each environment needs secrets `AWS_TERRAFORM_ROLE_ARN` and `TF_STATE_BUCKET`; variables `APP_DOMAIN`, `ROUTE53_ZONE_ID`, `ADMIN_ROLE_ARNS` (JSON array), `GITHUB_OIDC_SUBJECTS` (JSON array), `OWNER`, `COST_CENTER`, `KARPENTER_AMI_ID`, and optionally `TFVARS_JSON`. Create the initial Terraform OIDC deployment role out of band with a trust policy scoped to this repository/environment; it cannot bootstrap its own credentials. Terraform creates a separate ECR-only role for application builds.

For the application workflow, dev also needs `AWS_APP_ROLE_ARN` (Terraform's `github_actions_role_arn` output), `ECR_REPOSITORY` (repository name, not full URL), and `GITOPS_PR_TOKEN` scoped to creating deployment PRs. Infrastructure CI validates PRs without cloud credentials. Manually dispatch `terraform` on main with action `plan` or `apply`; it creates the backend before init. No automatic production deployment occurs on push.

## Existing infrastructure and cleanup

Review `terraform plan` carefully before adopting this simplified layout: interface endpoints and a third AZ were removed in the earlier layout; this revision adds Karpenter and changes managed node sizing/names; subnet/NAT/node changes can disrupt an existing cluster. The Cognito client changes from ALB authentication to application PKCE login, so users must sign in again. Back up state and game data and drain old nodes before removing their capacity.

For cleanup, first remove application ingresses through Argo CD and wait for ALB deletion; otherwise controller-managed load balancers can block VPC destruction. Stop Argo reconciliation. Drain and delete Karpenter workload nodes/NodeClaims while its controller, IAM role, interruption queue and VPC still exist; confirm the EC2 instances terminate before removing Karpenter. Disable DynamoDB deletion protection only when intentionally deleting game data, and review a `terraform plan -destroy`. Log buckets intentionally require manual retention/emptying decisions. Initialize teardown using `python scripts/terraform_init.py --environment dev --check-only`; this never recreates a missing backend bucket. Never delete the state bucket as part of normal environment cleanup.

## Production deployment checklist

1. **Use separate AWS accounts/state for dev and prod where possible.** In GitHub create the target environment, protect `main`, and require reviewers for prod. Create the initial Terraform OIDC role outside this stack. Scope trust to `repo:ORG/REPO:environment:dev` or `prod`. Give that role the infrastructure provisioning permissions, including Karpenter IAM roles/policies, `iam:PassRole`, EKS access entries/Pod Identity, SQS and EventBridge. The ECR-only app role cannot provision infrastructure.
2. **Choose names once.** Read [AWS naming and tagging](docs/aws-naming.md). Provide `OWNER` and `COST_CENTER` environment variables and the same values in local tfvars. `TFVARS_JSON` can set `project`, `region_short_name`, `github_oidc_provider_arn`, and `karpenter_cpu_limit`. Do not put credentials in it. GitHub environment variables explicitly mapped to `TF_VAR_*` must be populated; do not rely on empty values being replaced by Terraform defaults.
3. **Pin an AMI per region.** Discover the current AWS image with the command below, test it in dev, then set `KARPENTER_AMI_ID` in GitHub and `karpenter_ami_id` in local tfvars. Terraform verifies Amazon ownership, x86_64 architecture and the EKS 1.34 AL2023 image family. Production should promote a tested release, not follow `latest` automatically. The AMI is regional; do not reuse a Singapore AMI ID in Virginia.
4. **Check capacity and network prerequisites.** Verify On-Demand EC2 vCPU quota, available subnet IPs, and supported c/m/r generation 6+ x86 instance types in both AZs. Keep NAT/HTTPS access for EC2, EKS, SSM, STS, SQS, ECR and public chart registries; the private API does not mean the VPC is air-gapped. Prod has one NAT per AZ. Ensure the bootstrap IAM role is in `ADMIN_ROLE_ARNS`, and run Helm/kubectl on a VPC-connected host or through a restricted public endpoint. GitHub-hosted Terraform runs only AWS APIs; it does not bootstrap Kubernetes over the private endpoint.
5. **Run `terraform` plan, review replacements, then apply on main.** Defaults are two `m6i.large` managed system nodes plus Karpenter workload nodes. The workload pool is capped at 32 vCPU in dev and 128 in prod; these limits exclude managed nodes and are eventually consistent, not hard billing caps. Configure AWS Budgets and quota alerts separately.
6. **Publish the app image.** Configure dev secret `AWS_APP_ROLE_ARN`, variable `ECR_REPOSITORY`, and secret `GITOPS_PR_TOKEN`. Run `application`. On the initial deployment it pushes the image and intentionally stops when the rendered tree is absent. Resolve the digest from ECR, set `IMAGE_URI`, render, review and commit the environment tree. Subsequent image PRs must be merged for Argo CD to deploy. The current application workflow targets dev only: for prod, copy/promote the tested image to the prod ECR repository, use its digest when rendering prod, and review/merge the prod manifest change. Do not assume the dev build deploys prod.
7. **Bootstrap in order.** Render GitOps, run `bootstrap_karpenter.py`, install Argo CD, configure repository credentials if private, then apply the AppProject/root applications. If a `kubectl wait` reports no resources yet, wait for Argo CD to create them, inspect its sync status and retry. NodePool pruning is deliberately disabled to prevent an accidental Git deletion terminating workload capacity; remove pools through a reviewed drain procedure.
8. **Complete ingress/DNS and test the service.** Wait for healthy ALB targets and the ACM certificate, create the Route 53 alias for `APP_DOMAIN`, then test HTTPS, login/email delivery, `/healthz`, `/readyz`, a game across two sessions and a rolling restart. Do not use the ALB hostname as the application's login URL: Cognito callbacks and host routing use your configured domain.
9. **Prove scaling and recovery in dev before promotion.** Use the checks below. Establish application SLOs and paging for pending pods, unavailable replicas, Karpenter errors, node readiness, ALB 5xx/latency and exhausted pool capacity. Add metrics collection for Karpenter; this repository does not install a Prometheus backend or a paging destination. Test DynamoDB restore, node failure and credential rotation. Review Cognito MFA/email quotas and production email delivery.

```bash
# Discover a candidate AMI, then test and record the exact ID in configuration.
aws ssm get-parameter --region ap-southeast-1 \
  --name /aws/service/eks/optimized-ami/1.34/amazon-linux-2023/x86_64/standard/recommended/image_id \
  --query Parameter.Value --output text

kubectl -n kube-system get pods -l app.kubernetes.io/name=karpenter -o wide
kubectl get ec2nodeclasses,nodepools,nodeclaims
kubectl get nodes -L workload-tier,karpenter.sh/nodepool,karpenter.sh/capacity-type,topology.kubernetes.io/zone
kubectl -n sample-app get pods -o wide
kubectl -n sample-app get hpa,pdb
kubectl -n kube-system logs deployment/karpenter --all-pods=true --tail=100
kubectl top nodes
```

For a controlled scale-out test, add a temporary dev Deployment to Git with `nodeSelector: {workload-tier: application}` and CPU/memory requests large enough to exceed the current workload nodes, but below the NodePool limit. Use an approved image. Confirm pending pods cause new NodeClaims, nodes join Ready and pods become Running; then remove the test Deployment through Git and observe consolidation after at least five minutes. Do not scale the game manually while its HPA owns the replica count. Delete only the temporary test workload, not the pool or controller. A PodDisruptionBudget or topology constraint can legitimately prevent further consolidation.

## How bin packing works here

Karpenter batches unschedulable pods, evaluates their resource requests and scheduling constraints, and selects suitable instance capacity. `WhenEmptyOrUnderutilized` consolidation can remove or replace underused nodes after a five-minute delay, with at most one voluntary node disruption at a time. This is Karpenter provisioning/consolidation, not a custom Kubernetes `MostAllocated` scheduler configuration. EKS retains its default scheduler. Accurate requests are essential; measure the application's 50m CPU/64Mi memory defaults under real load and tune them before production.

The app is restricted to the workload pool and must span at least two AZs. This intentionally leaves an availability floor rather than packing all replicas onto one node. It also means an AZ outage can leave some replicas Pending until capacity in that AZ returns; test whether this strict policy matches your recovery objectives. Existing replicas in the surviving AZ can continue serving. The managed system pool stays at two nodes; Karpenter does not resize it. Watch its capacity as platform controllers grow.

The default workload pool uses On-Demand only. To permit Spot, review the NodePool capacity requirement and allow `spot` alongside `on-demand` in dev first. Verify/create the account-level EC2 Spot service-linked role before doing so. The interruption queue/EventBridge wiring is already included, but interruptions can exceed voluntary disruption budgets and are not prevented by a PDB. A mixed pool does not guarantee a minimum On-Demand share.

Node expiration is disabled to avoid unplanned age-based drains. Roll out tested AMI pins regularly through Terraform output/rendered GitOps; Karpenter drift replacement uses the disruption budget and respects PDBs. Monitor for blocked drains so nodes do not remain unpatched. Review the [Karpenter compatibility matrix](https://karpenter.sh/docs/upgrading/compatibility/), [NodePool disruption settings](https://karpenter.sh/v1.12/concepts/nodepools/) and [AMI management](https://karpenter.sh/v1.12/tasks/managing-amis/) for upgrades. Controller and CRD chart versions are pinned together to 1.12.0 in `scripts/bootstrap_karpenter.py`; the AWS IAM submodule is pinned to 21.25.0.
