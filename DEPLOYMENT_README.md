# Deploy ArenaGrid on EKS without buying a domain

The application uses `https://<generated-id>.cloudfront.net`. No registered domain, Route 53 hosted zone, DNS record or custom ACM certificate is needed. Terraform creates CloudFront and an internal ALB before Kubernetes bootstrap, so Cognito callback/logout URLs are configured automatically in the same apply.

Traffic: browser HTTPS -> CloudFront + WAF -> VPC origin -> private HTTP ALB -> application pods. TLS terminates at CloudFront; the origin hop is HTTP inside the VPC, restricted by security groups. This is not end-to-end TLS. EKS API access remains private by default. AWS infrastructure and CloudFront usage are billable even though no domain purchase is required.

## 1. One-time AWS trust setup for your existing role

The workflow is configured for account **001495086648**, role **AutomationAdminAll**, repository **vipinkumar1234/aws-eks-production-platform**. The role ARN is not a credential and is committed directly in the workflow. No AWS access keys are stored in GitHub.

Create GitHub environments **dev** and **prod** in repository Settings -> Environments. These are used for OIDC trust. Also create approval environments **dev-apply**, **dev-destroy**, **prod-apply** and **prod-destroy**. Restrict all of them to the **main** branch and enable required reviewers on the approval environments. Terraform `apply` waits on `<environment>-apply`; Terraform `destroy` waits on `<environment>-destroy`; the AWS credential step still uses **dev** or **prod** so the OIDC subject stays stable. Anyone able to run trusted deployment code can use this role's permissions, so protect main and these environments.

Push the updated files to main. Use the normal AWS CloudShell user, authenticated as an administrator in account 001495086648. Do not run `sudo su -`: it changes the home directory and Python environment. If your prompt currently starts with `[root@`, run `exit` once to return to the CloudShell user. For a fresh checkout:

```bash
cd ~
git clone https://github.com/vipinkumar1234/aws-eks-production-platform.git
cd aws-eks-production-platform
aws sts get-caller-identity
test -f scripts/setup_github_oidc.py || { echo "Push the setup script to GitHub main first"; exit 1; }
python3 -c 'import boto3; print("Boto3 available:", boto3.__version__)'
python3 scripts/setup_github_oidc.py
python3 scripts/setup_github_oidc.py --check-only
```

If you already cloned the repository, use `cd ~/aws-eks-production-platform` and `git pull --ff-only origin main` instead of cloning again; keep your local changes and resolve any Git conflict before proceeding. Private repositories require your normal GitHub authentication. Check that STS reports account `001495086648` before running setup.

CloudShell normally includes Boto3 and pip, so no package installation is needed when the import check succeeds. If Boto3 is missing, run these commands as the normal CloudShell user, then retry the setup script:

```bash
# Install the Python package manager only if python3 -m pip --version fails.
sudo dnf install -y python3-pip
python3 -m pip install --user boto3==1.43.89
python3 scripts/setup_github_oidc.py
```

`can't open file '/root/scripts/setup_github_oidc.py'` means Python was launched from `/root`, not the repository directory. Installing pip will not fix that path error. The setup file must also have been committed and pushed from your local workspace before CloudShell can clone it.

The script checks the account and existing role, creates/reuses GitHub's OIDC provider, and merges exact dev/prod environment trust into AutomationAdminAll without replacing its other trust statements. Re-running it does not add duplicate statements. It does not attach IAM permissions. The invoking identity needs IAM GetRole, GetOpenIDConnectProvider, CreateOpenIDConnectProvider, AddClientIDToOpenIDConnectProvider and UpdateAssumeRolePolicy as needed, plus STS identity access.

This initial authorization cannot be performed by a GitHub workflow that AWS does not yet trust. If the provider and exact environment trust already exist, skip the script. This repository currently uses GitHub's customized numeric subject format, so the role trust must include `repo:vipinkumar1234@110930371/aws-eks-production-platform@1359084778:environment:dev` and the matching `prod` subject. The `Show OIDC trust claims` workflow step prints the exact safe `sub` value to use if GitHub changes the subject template. [GitHub's AWS OIDC documentation](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws) explains the audience and environment subject requirements.

AutomationAdminAll must have permission to provision the resources in this repository, including IAM/PassRole/service-linked roles, VPC/EC2/ELB, EKS, S3, ECR, KMS, Secrets Manager, Cognito, DynamoDB, CloudWatch, SSM parameter reads, WAF and CloudFront. Its name alone does not prove these policies are attached. No role permissions have been inspected or changed by this repository update.

## 2. Defaults: no required infrastructure secrets or variables

After trust setup, dispatch the **deploy** workflow. It uses these built-in defaults:

| Setting | Automatic value |
|---|---|
| Deployment and EKS administrator principals | `arn:aws:iam::001495086648:role/AutomationAdminAll` and `arn:aws:iam::001495086648:root` |
| Account | `001495086648`; authentication and preflight reject another account |
| Dev region | `ap-southeast-1` |
| Prod region | `us-east-1` |
| Dev state bucket | `eks-platform-001495086648-ap-southeast-1-dev-tfstate` |
| Prod state bucket | `eks-platform-001495086648-us-east-1-prod-tfstate` |
| GitHub OIDC provider | Existing account-level provider created/reused in step 1 |
| Image-role trust subject | GitHub numeric repository subject and selected GitHub environment |
| Owner / cost centre | `vipin` / `gaming-test` |
| Kubernetes version | EKS 1.36 for new clusters; existing 1.34 clusters must run one approved apply at 1.35 before applying 1.36 |
| Karpenter AMI | Regional Amazon AL2023 x86_64 recommendation for the selected Kubernetes version resolved through SSM |
| Game URL | AWS-generated `https://<id>.cloudfront.net` |

The role, provider, administrator list and GitHub trust subject no longer need to be copied into secrets/variables. `AWS_TERRAFORM_ROLE_ARN`, `ADMIN_ROLE_ARNS`, `GITHUB_OIDC_SUBJECTS`, `OWNER` and `COST_CENTER` are no longer read individually by this workflow. During GitHub Actions runs, `scripts/prepare_aws_deployment.py` builds the image-role trust subject from `GITHUB_REPOSITORY_OWNER_ID` and `GITHUB_REPOSITORY_ID` so it matches the customized numeric OIDC subject. It also grants EKS cluster-admin access to the account root principal because this lab environment is being administered from the root console session.

Optional GitHub environment settings:

- Secret `TF_STATE_BUCKET`: retain your existing bucket if this environment was deployed previously. Do not change backend names for an existing deployment without explicitly migrating state.
- Variable `KARPENTER_AMI_ID`: pin a reviewed regional AMI for the selected Kubernetes version; otherwise each run resolves the current SSM recommendation. A later apply may select a newer AMI than an earlier plan run. During a 1.34 -> 1.35 -> 1.36 staged upgrade, leave this unset or update the pin to match the selected Kubernetes version.
- Variable `TFVARS_JSON`: reviewed Terraform overrides, for example `{"owner":"vipin","cost_center":"gaming-test","karpenter_cpu_limit":16}`. These override defaults; a pinned AMI in this JSON takes precedence over KARPENTER_AMI_ID. The workflow rejects region mismatches.
- Variable `DNS_ZONE_NAME`: optional zone creation, described below.

The project still includes two system nodes plus Karpenter workloads. EC2, EKS, NAT, CloudFront and other AWS usage is billable. An AMI lookup chooses an official image, not a workload-tested image; pin it after dev verification.

## 3. Test URL and optional automatic Route 53 zone

For testing, leave `DNS_ZONE_NAME` unset. CloudFront supplies the hostname and HTTPS certificate; no domain registration, hosted zone, delegation or certificate-validation action is required. [AWS documents its generated CloudFront domain and default certificate](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesGeneral.html).

If you also want a Route 53 public zone, set the GitHub environment variable `DNS_ZONE_NAME` to a domain you control, then dispatch apply. Terraform creates the zone and outputs its ID and name servers automatically; there is no ROUTE53_ZONE_ID input. Alternatively supply `dns_zone_name` through TFVARS_JSON. Keep the setting stable: the zone has prevent_destroy, so removing/changing it will stop a plan that would delete it.

Creating a zone does **not** register a domain, delegate its name servers, or attach a custom hostname to CloudFront. The game continues using the generated HTTPS test URL. A custom hostname additionally requires registrar delegation, ACM validation and distribution alias configuration; those are not claimed as automated by the optional zone resource. Arbitrary domain names cannot be used as owned HTTPS domains. For this test deployment, skip the unused zone and its cost.

## 4. Deploy the full stack with one ordered workflow

Use Actions -> **deploy** -> Run workflow -> **main**. Choose the environment and Kubernetes version. This is the recommended first-run workflow because it enforces the correct order:

1. Validate Terraform, Kubernetes manifests, scripts and app tests.
2. Wait at the `dev-apply` or `prod-apply` approval environment.
3. Apply Terraform infrastructure.
4. Build, scan and push the application image to ECR.
5. Render `gitops/environments/<environment>` from Terraform outputs and the immutable image digest.
6. Commit the rendered GitOps tree directly to `main`.
7. Run the Kubernetes bootstrap from a VPC-connected self-hosted runner.
8. Wait for Karpenter, Argo CD, AWS Load Balancer Controller, sample app rollout and healthy ALB targets.

For a new cluster, select Kubernetes version **1.36**. For an existing cluster already created at **1.34**, do not select 1.36 first. EKS rejects skipped minor upgrades, so run **dev / apply / 1.35**, wait for it to finish, then run **dev / apply / 1.36**. Use the same sequence for prod when it already exists at 1.34.

The separate **terraform** workflow is still available for plan, apply and destroy operations when you need to operate only the infrastructure layer:

| Action | What it does | Approval gate |
|---|---|---|
| `plan` | Runs `validate`, then a separate `plan` job. No resources are changed. | No approval gate |
| `apply` | Runs `validate`, waits at `apply_approval`, then runs the separate `apply` job using the selected Kubernetes version. | Uses `dev-apply` or `prod-apply` |
| `destroy` | Runs `validate`, waits at `destroy_approval`, disables DynamoDB deletion protection for the managed game table, then destroys the environment. | Uses `dev-destroy` or `prod-destroy` |

Configure required reviewers on the `*-apply` and `*-destroy` GitHub environments to make the approval gate active. Without required reviewers, GitHub still records the deployment environment, but it will not pause for approval. A `plan` run intentionally shows `apply_approval` and `destroy_approval` as skipped. An `apply` run must show `apply_approval` waiting before the `apply` job starts; a `destroy` run must show `destroy_approval` waiting before the `destroy` job starts. If the approval job is skipped during an apply or destroy run, confirm the workflow was manually dispatched from the **main** branch with action **apply** or **destroy**.

The bootstrap creates/secures the state bucket before init: ownership checks, public-access block, owner-enforced ownership, versioning, naming tags, encryption preservation and deny-insecure-transport policy. Its role needs S3 bucket configuration/read permissions including GetBucketTagging/PutBucketTagging, plus state-object GetObject/PutObject and lock-object GetObject/PutObject/DeleteObject. Existing KMS-encrypted state buckets also require key permissions. There is no DynamoDB state-lock table; Terraform uses the native S3 `.tflock`. Never delete the bucket during normal cleanup.

Terraform creates the private ALB/listener/target group, CloudFront VPC origin/distribution, CloudFront-scoped WAF, EKS, data/auth resources and Karpenter AWS resources. CloudFront deployment can take several minutes. The workflow summary displays **app_url**, **github_actions_role_arn** and **ecr_repository_url**. The URL can return 503 until the bootstrap job registers healthy application pod IPs; the ordered **deploy** workflow waits for that before reporting completion.

Terraform computes Cognito URLs from the CloudFront domain: `https://<id>.cloudfront.net/auth/callback` and `https://<id>.cloudfront.net/`. Distribution recreation changes that address and requires rendering/redeploying the workload configuration.

## 5. Component workflows for recovery and partial changes

The **application** workflow is retained as a manual component workflow for rebuilding and redeploying the app after infrastructure already exists. It does not auto-run on pushes to main, so the ordered **deploy** workflow remains the first-run entry point. After Terraform has created ECR, add this optional GitHub environment variable if you do not want to use the automatic repository name:

| Type | Name | Value |
|---|---|---|
| Variable | ECR_REPOSITORY | Repository name, e.g. `eks-platform-apse1-dev-sample-app`, not the full registry URL |

No GitHub PR token secret is required. The application workflow uses the built-in `GITHUB_TOKEN` with job-level `contents: write` permission to commit the rendered GitOps tree directly to `main`.

Run Actions -> **application** on main only after infrastructure exists. It tests/scans and pushes the image. If Terraform has not created ECR yet, the workflow exits cleanly and writes a summary telling you to run the ordered **deploy** workflow first. The Docker build upgrades Debian packages before installing the app so the image picks up current base-image security fixes. Trivy fails the build for HIGH/CRITICAL vulnerabilities that have a fix; unfixed OS package findings are ignored so the build is not blocked by base-image CVEs without an upstream patch. After ECR exists, the workflow renders the dev GitOps tree from Terraform outputs, commits `gitops/environments/dev` directly to `main`, then runs the Kubernetes bootstrap job on the VPC-connected runner.

The **platform-bootstrap** workflow is retained for recovery when the image and rendered GitOps tree already exist and only the Kubernetes bootstrap/sync needs to be rerun. The application and platform-bootstrap workflows use `arn:aws:iam::001495086648:role/AutomationAdminAll` directly, just like Terraform. An old `AWS_APP_ROLE_ARN` secret is no longer read. CloudShell is needed for the initial trust setup only; routine infrastructure deployment, image publishing and GitOps rendering run in GitHub Actions. Kubernetes bootstrap is automated too, but the runner must have the network access described in step 6.

### Recover from the reported CI failures

1. Commit and push these fixes to **main**. Start new workflow runs on that commit; rerunning an old failed run uses its old workflow definition.
2. Create/check GitHub environments **dev** and **prod**, restricting deployment branches to **main**. Both workflows request `id-token: write` and audience `sts.amazonaws.com`.
3. In normal-user CloudShell, update your repository checkout and run the setup and `--check-only` commands in step 1 above. An administrator policy alone does not authorize GitHub federation: the account needs the OIDC provider and environment-scoped role trust.
4. Run a new **deploy** workflow from main. Approve `dev-apply` or `prod-apply` when GitHub asks. The workflow creates infrastructure first, then builds the image, renders GitOps, commits it and bootstraps Kubernetes.
5. Use the separate **application** workflow only for later app-only rebuilds. The source image placeholder is a rendering template and must never be deployed directly.
6. If AWS still reports an invalid web identity token after the configuration check passes, collect the full new authentication error and the safe `--check-only` output. The check validates configuration, not a live GitHub token. Investigate AWS STS/provider validation using the [AWS troubleshooting guide](https://repost.aws/knowledge-center/iam-sts-invalididentitytoken); do not share raw OIDC tokens or delete a shared provider.

The deployment now explicitly uses UID/GID 10001, `imagePullPolicy: Always`, and digest-based image rendering. CI keeps all Kubernetes security checks enabled. Actions were updated to Node.js 24 runtimes, including configure-aws-credentials v6, which accepts `allowed-account-ids`. tfsec receives `--minimum-severity HIGH --exclude-downloaded-modules` through its supported `additional_args` input and receives `github_token` to authenticate GitHub API requests. The scan excludes downloaded `.terraform/modules` internals because the authored EKS wrapper already enables secret encryption with the platform KMS key. These address the reported configuration warnings; future action releases, service errors and rate limits still require checking new runs.

Images use immutable Git commit tags. If a workflow is rerun for a commit SHA that already exists in ECR, the application workflow now reuses that existing digest and skips rebuild/push so ECR immutability does not fail the run. The workflow then renders and commits GitOps with that digest.

## 6. Bootstrap from automation, not manual kubectl steps

The repository includes automation for the Kubernetes layer. Terraform owns AWS infrastructure. The application workflow renders GitOps after publishing an image, commits it to main, installs Karpenter, Argo CD, the AWS Load Balancer Controller, observability and the sample app, then waits until the target group has healthy pod IPs.

The application workflow's `bootstrap` job, and the manual **platform-bootstrap** recovery workflow, run on a self-hosted runner labeled `self-hosted`, `linux`, `eks-platform-vpc`. That runner must be inside the EKS VPC or a connected network because the EKS API endpoint is private and resolves to `10.x` addresses. A GitHub-hosted runner can provision AWS infrastructure, but it cannot reach the default private Kubernetes endpoint. [AWS documents that private EKS endpoints require VPC or connected-network access](https://repost.aws/knowledge-center/eks-troubleshoot-kubectl-commands), and [CloudShell VPC environments inherit VPC network access](https://docs.aws.amazon.com/cloudshell/latest/userguide/using-cshell-in-vpc.html).

Production flow:

1. Run Terraform **dev / apply** and approve `dev-apply`.
2. Run the **application** workflow. It builds/scans/pushes the image, commits rendered GitOps and runs the bootstrap job from the VPC-connected self-hosted runner.
3. Open `app_url`.

Until you create the self-hosted runner, you can run the same automation as one command from CloudShell VPC after the application workflow commits GitOps:

```bash
cd ~/aws-eks-production-platform
git pull --ff-only origin main
python3 scripts/bootstrap_platform.py --environment dev
```

This single command replaces the previous manual sequence of `bootstrap_karpenter.py`, Helm install, Argo CD bootstrap, rollout checks and target-health checks.

You still need one VPC-connected execution place: CloudShell VPC, a bastion, VPN-connected workstation, or self-hosted GitHub runner in the VPC. Alternatively, explicitly allow only your administrator's public `/32` through `cluster_endpoint_public_access_cidrs` in Terraform; never use `0.0.0.0/0`.

The EKS console shows `Unauthorized` when the currently signed-in AWS principal is not listed in EKS access entries. Even the AWS root user needs an EKS access entry when `enable_cluster_creator_admin_permissions = false`. The generated defaults now include `arn:aws:iam::001495086648:root`; run a new Terraform `dev` `apply`, wait a minute for EKS access-entry propagation, then refresh the EKS console. Verify with `aws eks list-access-entries --region ap-southeast-1 --cluster-name eks-platform-apse1-dev-eks`.

Install Python 3.12, Terraform 1.14.0, AWS CLI v2, Helm and kubectl compatible with EKS 1.36. Commands below use Bash/WSL from the repository root. Python scripts also work from PowerShell. Authenticate to the correct AWS account, for example with AWS SSO and your selected AWS_PROFILE.

```bash
python -m pip install boto3==1.43.89 PyYAML==6.0.2 jsonschema==4.26.0
export ENVIRONMENT=dev
export REGION=ap-southeast-1
export TF_STATE_BUCKET_DEV=YOUR_STATE_BUCKET
# Match the ownership tags used by CI.
export TF_VAR_project=eks-platform
export TF_VAR_owner=platform-team
export TF_VAR_cost_center=engineering
python scripts/terraform_init.py --environment dev

export GITOPS_REPO_URL=https://github.com/YOUR_ORG/YOUR_REPO.git
export ECR_URL=$(terraform -chdir=terraform/environments/dev output -raw ecr_repository_url)
# Set the exact commit SHA built by the application workflow, not a later GitOps commit.
export IMAGE_TAG=YOUR_BUILT_COMMIT_SHA
export IMAGE_DIGEST=$(aws ecr describe-images --region "$REGION" \
  --repository-name "${ECR_URL#*/}" --image-ids imageTag="$IMAGE_TAG" \
  --query 'imageDetails[0].imageDigest' --output text)
export IMAGE_URI="$ECR_URL@$IMAGE_DIGEST"
python scripts/render_gitops.py --environment dev
```

The manual render command is kept for local recovery only. In normal CI, the application workflow runs it and commits the rendered tree. Terraform outputs supply the generated app address and target group ARN; no manual URL editing is needed. If you also plan/apply locally, copy that environment's terraform.tfvars.example to terraform.tfvars and fill the same inputs used by CI. Merely initializing/reading existing state does not require supplying all plan inputs.

## 7. Bootstrap Karpenter and Argo CD

Prefer the **platform-bootstrap** workflow or `python3 scripts/bootstrap_platform.py --environment dev`. The lower-level commands below are for break-glass debugging when you need to run one phase at a time.

```bash
python scripts/bootstrap_karpenter.py --environment dev
aws eks update-kubeconfig --region "$REGION" \
  --name "$(terraform -chdir=terraform/environments/dev output -raw cluster_name)"
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm upgrade --install argocd argo/argo-cd --version 10.8.2 \
  --namespace argocd --create-namespace \
  -f gitops/environments/dev/argocd/values.yaml --wait --timeout 10m
```

For a private GitHub repository, configure Argo CD repository credentials before applying root applications. Use a read-only deploy key or appropriate repository credential secret and do not commit the credentials. Argo CD remains private; administer it with `kubectl -n argocd port-forward svc/argocd-server 8443:443`.

```bash
kubectl apply -f gitops/environments/dev/argocd/projects/platform-project.yaml
kubectl apply -f gitops/environments/dev/argocd/bootstrap/namespace.yaml
kubectl -n argocd get applications
```

Wait for platform applications to sync. The load balancer controller installs the TargetGroupBinding CRD/webhook. Argo may retry the game sync until these exist. A TargetGroupBinding registers Service pod IPs with Terraform's target group; it does not create another ALB. Terraform owns all relevant security-group rules. Do not manually create an Ingress or LoadBalancer Service for this app.

## 8. Verify the application

Run after Argo creates the resources; a `NotFound` means check Argo sync and retry rather than assume success:

```bash
kubectl -n platform-system rollout status deployment/aws-load-balancer-controller --timeout=10m
kubectl wait --for=condition=Established crd/targetgroupbindings.elbv2.k8s.aws --timeout=5m
kubectl apply --dry-run=server -f gitops/environments/dev/apps/sample-app/targetgroupbinding.yaml
kubectl apply --dry-run=server -f gitops/environments/dev/platform/karpenter-resources/nodepool.yaml
kubectl wait --for=condition=Ready ec2nodeclass --all --timeout=5m
kubectl wait --for=condition=Ready nodepool --all --timeout=5m
kubectl -n sample-app rollout status deployment/sample-app --timeout=10m
kubectl -n sample-app get targetgroupbinding,pods,hpa,pdb
aws elbv2 describe-target-health --region "$REGION" \
  --target-group-arn "$(terraform -chdir=terraform/environments/dev output -raw app_target_group_arn)"
export APP_URL=$(terraform -chdir=terraform/environments/dev output -raw app_url)
curl --fail "$APP_URL/healthz"
curl --fail "$APP_URL/readyz"
echo "$APP_URL"
```

Open APP_URL in your browser. Sign up, verify email, log in, play solo, invite another signed-in player and log out. Verify responses say `Cache-Control: no-store`, authenticated responses are not edge-cached, API POSTs work and HTTP redirects to HTTPS. Test a rolling restart. The private ALB should be unreachable from the public internet and reject VPC callers outside CloudFront's service security group. Keep using the CloudFront address; the ALB address is not an alternative login URL.

Troubleshooting: 503 commonly means targets aren't registered/healthy; check TargetGroupBinding events, controller logs, app readiness and port 8080 rules. 502/504 suggests origin connectivity or app failure; check VPC origin status and ALB ingress from the AWS-managed CloudFront SG. Login redirect mismatch means the rendered app URL and Cognito callback differ. 403 can mean WAF rules or an invalid Origin header; inspect WAF metrics and the browser request without disabling protection globally. Namespace NetworkPolicies permit VPC ingress to the application and AWS HTTPS egress.

## 9. Validate scaling and production readiness

Karpenter 1.12.0 runs two controllers on the managed system group. The managed system group uses two `t3.medium` Spot nodes. The workload pool uses Spot t/c/m generation 6+ amd64 capacity with 2 or 4 vCPUs. It batches pending pods and consolidates underused nodes after five minutes, with at most one voluntary disruption at a time. EKS retains its default scheduler; this is Karpenter bin packing/consolidation. The HPA scales two to four game replicas. Accurate resource requests are necessary; load-test the initial 50m CPU / 64Mi memory requests.

```bash
kubectl get nodepools,nodeclaims,ec2nodeclasses
kubectl get nodes -L workload-tier,karpenter.sh/nodepool,topology.kubernetes.io/zone
kubectl -n kube-system logs deployment/karpenter --all-pods=true --tail=100
kubectl top nodes
```

For a dev scale test, deploy a temporary approved workload with `nodeSelector: {workload-tier: application}` and sufficient resource requests to require more nodes, staying within the CPU cap. Verify NodeClaims become Ready and pods run. Remove that workload and observe eligible node consolidation. Do not manually scale the game against its HPA. Two-AZ spreading/PDBs can legitimately prevent consolidation; strict spreading can leave replicas Pending during an AZ outage. Karpenter does not resize system nodes.

Node expiration is disabled; rotate tested AMI pins through Terraform and GitOps regularly and verify drift replacement. Spot interruptions can evict system and app pods, so keep this cost-optimized setting for dev/testing unless you have validated interruption handling, budgets and alerts. No guaranteed On-Demand baseline remains after this change.

Before serving production users, configure paging/SLOs, quota and cost alerts, Karpenter metrics collection, DynamoDB restore drills, Cognito email/MFA policy, dependency patching and load/recovery tests. Existing Fluent Bit/S3 and EKS/VPC logs remain. This stack does not configure CloudFront/ALB access-log delivery, a metrics backend or paging destination. Default CloudFront certificate TLS policy is AWS-controlled; a custom minimum TLS policy/end-to-end TLS would require a different certificate architecture.

## 10. Production promotion

Repeat with GitHub environment prod, prod account/roles, separate bucket, prod AMI and region us-east-1. Require production reviewers. The application workflow currently builds dev only: promote a tested image into prod ECR, render prod using its immutable digest, review/merge that tree, then bootstrap prod from its authorized host. Do not reuse the dev ECR URL or regional AMI. Run all live checks again.

## Existing Installations and Destroy

Do not apply this change blindly to a running domain-based deployment. The old ACM resources leave the active Terraform graph, WAF changes from REGIONAL to CLOUDFRONT in us-east-1, and supported AZ selection can change subnet/node placement. These can destroy/replace resources. Back up state/data, review the full plan and use a staged migration or a new environment if continuity matters. Existing external Route 53 aliases are not removed automatically.

The new ALB uses the distinct `-edge` name to avoid colliding with the old controller-owned `-app` ALB. Rendering removes only the obsolete generated `apps/sample-app/ingress.yaml`. Review that deletion: Argo pruning the old Ingress deletes its ALB. Remove obsolete copies from any other GitOps paths before enabling reconciliation. The TargetGroupBinding may not coexist with the old ingress-based deployment as a seamless cutover without a deliberate migration plan.

Before destroy, remove the app TargetGroupBinding through Git/Argo and wait for pod deregistration while the controller still runs. Drain/delete Karpenter NodeClaims and confirm EC2 termination while its controller/IAM/VPC remain. Stop Argo reconciliation so it does not recreate Kubernetes resources while Terraform removes AWS infrastructure.

To destroy from GitHub Actions, run Actions -> **terraform** -> Run workflow -> **main**, choose the environment, and set action **destroy**. GitHub uses `dev-destroy` or `prod-destroy` as the manual approval gate. The destroy job sets `TF_VAR_dynamodb_deletion_protection_enabled=false`, applies that single table update only if the table is already in Terraform state, then runs `terraform destroy`. This is intentional because the game table uses deletion protection by default for normal deploys.

Terraform removes CloudFront before its VPC origin/private ALB and then networking; AWS-managed VPC-origin ENIs may take time to disappear. Retain the state bucket and decide log retention explicitly. Never delete the state bucket as part of normal cleanup. If destroy fails because resources are still attached, wait for AWS cleanup or remove the remaining Kubernetes bindings/controllers, then rerun the same approved destroy action.

## Validation and references

CI runs Terraform validation, mocked edge tests, YAML checks, official Karpenter/TargetGroupBinding schema checks and security gates. Locally use `python -m unittest discover -s scripts -p 'test_*.py' -v`, `python scripts/validate_yaml.py`, `python scripts/validate_karpenter.py`, and `python scripts/validate_targetgroupbinding.py`. Schema checks download pinned upstream CRDs; Kubernetes server-side dry-run is still required for webhook/CEL checks. Tests do not prove AWS quota, IAM or live networking readiness.

- [AWS CloudFront VPC origins, security groups and supported AZs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [CloudFront default HTTPS certificate](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesGeneral.html)
- [AWS Load Balancer Controller TargetGroupBinding](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.13/guide/targetgroupbinding/targetgroupbinding/)
- [Karpenter compatibility](https://karpenter.sh/docs/upgrading/compatibility/)
- [S3 Terraform native locking](https://developer.hashicorp.com/terraform/language/backend/s3)
