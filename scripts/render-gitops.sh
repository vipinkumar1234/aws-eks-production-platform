#!/usr/bin/env bash
set -euo pipefail
: "${ENVIRONMENT:?Set ENVIRONMENT to dev or prod}"

case "$ENVIRONMENT" in
  dev) REGION=ap-southeast-1 ;;
  prod) REGION=us-east-1 ;;
  *) echo 'ENVIRONMENT must be dev or prod' >&2; exit 1 ;;
esac

ROOT="terraform/environments/$ENVIRONMENT"
out() { terraform -chdir="$ROOT" output -raw "$1"; }

replace_value() {
  local token="$1" value="$2"
  find gitops -type f -not -path '*/.git/*' -exec sed -i "s|$token|$value|g" {} +
}

replace_value REPLACE_WITH_TERRAFORM_CLUSTER_NAME "$(out cluster_name)"
replace_value REPLACE_WITH_TERRAFORM_VPC_ID "$(out vpc_id)"
replace_value REPLACE_WITH_ALB_CONTROLLER_ROLE_ARN "$(out alb_controller_role_arn)"
replace_value REPLACE_WITH_FLUENT_BIT_ROLE_ARN "$(out fluent_bit_role_arn)"
replace_value REPLACE_WITH_LOGS_BUCKET_NAME "$(out logs_bucket_name)"
replace_value REPLACE_WITH_ACM_CERTIFICATE_ARN "$(out certificate_arn)"
replace_value REPLACE_WITH_APP_DOMAIN "$(out app_domain)"
replace_value REPLACE_WITH_WAF_WEB_ACL_ARN "$(out waf_web_acl_arn)"
replace_value REPLACE_WITH_GAME_TABLE_NAME "$(out game_table_name)"
replace_value REPLACE_WITH_GAME_ROLE_ARN "$(out game_role_arn)"
replace_value REPLACE_WITH_KARPENTER_NODE_ROLE_NAME "$(out karpenter_node_role_name)"
replace_value REPLACE_WITH_AWS_REGION "$REGION"
replace_value REPLACE_WITH_ECR_URL "$(out ecr_repository_url)"

echo "Rendered GitOps values for $ENVIRONMENT. Review git diff before committing."