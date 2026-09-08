#!/usr/bin/env bash
set -euo pipefail

: "${AWS_REGION:=ap-southeast-1}"

command -v ansible-playbook >/dev/null || { echo 'ansible-playbook is required'; exit 1; }
ansible-galaxy collection install -r ansible/requirements.yml
ENVIRONMENT=dev AWS_REGION="$AWS_REGION" \
  TF_STATE_BUCKET="${TF_STATE_BUCKET_DEV:-worldofaws-app-terraform-state-dev-001495086648}" \
  ansible-playbook ansible/bootstrap-state.yml

terraform -chdir=terraform/bootstrap/github-oidc init
terraform -chdir=terraform/bootstrap/github-oidc apply \
  -var="aws_region=$AWS_REGION"

cat <<'EOF'
Prerequisites created. Configure the AutomationAdminAll trust policy for:
  repo:vipinkumar1234/aws-eks-production-platform:ref:refs/heads/feat*
  repo:vipinkumar1234/aws-eks-production-platform:ref:refs/heads/main
Then set GitHub secret TF_STATE_BUCKET_DEV and AWS_TERRAFORM_ROLE_ARN.
EOF
