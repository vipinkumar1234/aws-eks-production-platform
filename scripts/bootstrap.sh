#!/usr/bin/env bash
set -euo pipefail
: "${ENVIRONMENT:?Set ENVIRONMENT to dev or prod}"
case "$ENVIRONMENT" in
  dev) REGION=ap-southeast-1; STATE_BUCKET="${TF_STATE_BUCKET_DEV:?Set TF_STATE_BUCKET_DEV}" ;;
  prod) REGION=us-east-1; STATE_BUCKET="${TF_STATE_BUCKET_PROD:?Set TF_STATE_BUCKET_PROD}" ;;
  *) echo 'ENVIRONMENT must be dev or prod' >&2; exit 1 ;;
esac
terraform -chdir="terraform/environments/$ENVIRONMENT" init \
  -backend-config="bucket=$STATE_BUCKET" \
  -backend-config="key=eks/$ENVIRONMENT/terraform.tfstate" \
  -backend-config="region=$REGION" \
  -backend-config="encrypt=true" \
  -backend-config="use_lockfile=true"
terraform -chdir="terraform/environments/$ENVIRONMENT" plan -out=tfplan
terraform -chdir="terraform/environments/$ENVIRONMENT" apply tfplan
aws eks update-kubeconfig --region "$REGION" --name "$(terraform -chdir="terraform/environments/$ENVIRONMENT" output -raw cluster_name)"
