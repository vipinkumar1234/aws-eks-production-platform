"""Render isolated GitOps trees; shared templates remain unchanged."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOKENS = {
    "TERRAFORM_CLUSTER_NAME": "cluster_name", "CLUSTER_NAME": "cluster_name",
    "TERRAFORM_VPC_ID": "vpc_id", "ALB_CONTROLLER_ROLE_ARN": "alb_controller_role_arn",
    "FLUENT_BIT_ROLE_ARN": "fluent_bit_role_arn", "LOGS_BUCKET_NAME": "logs_bucket_name",
    "ACM_CERTIFICATE_ARN": "certificate_arn", "APP_DOMAIN": "app_domain",
    "WAF_WEB_ACL_ARN": "waf_web_acl_arn", "GAME_TABLE_NAME": "game_table_name",
    "GAME_ROLE_ARN": "game_role_arn", "SESSION_SECRET_ARN": "session_secret_arn",
    "COGNITO_ISSUER": "cognito_issuer",
    "COGNITO_USER_POOL_ARN": "cognito_user_pool_arn",
    "COGNITO_CLIENT_ID": "cognito_user_pool_client_id",
    "COGNITO_USER_POOL_DOMAIN": "cognito_user_pool_domain",
    "RESOURCE_PREFIX": "resource_prefix", "PROJECT": "project",
    "OWNER": "owner", "COST_CENTER": "cost_center",
    "CLUSTER_ENDPOINT": "cluster_endpoint",
    "NODE_SECURITY_GROUP_ID": "node_security_group_id",
    "KARPENTER_INSTANCE_PROFILE": "karpenter_instance_profile",
    "KARPENTER_QUEUE_NAME": "karpenter_queue_name",
    "KARPENTER_AMI_ID": "karpenter_ami_id",
    "KARPENTER_CPU_LIMIT": "karpenter_cpu_limit",
    "VPC_CIDR": "vpc_cidr", "AWS_REGION": "aws_region",
}


def render(environment, outputs, repository, image):
    if environment not in ("dev", "prod"):
        raise ValueError("Environment must be dev or prod")
    if not re.fullmatch(r"https://github.com/[\w.-]+/[\w.-]+\.git", repository):
        raise ValueError("Repository must be an HTTPS GitHub .git URL")
    ecr = outputs["ecr_repository_url"]["value"]
    if not re.fullmatch(re.escape(ecr) + r"@sha256:[a-f0-9]{64}", image):
        raise ValueError("IMAGE_URI must be this environment's ECR URL@sha256:digest")
    values = {"REPLACE_WITH_" + key: str(outputs[name]["value"]) for key, name in TOKENS.items()}
    values.update({"REPLACE_WITH_ENVIRONMENT": environment})
    rendered = {}
    for source in (ROOT / "gitops").rglob("*.yaml"):
        relative = source.relative_to(ROOT / "gitops")
        if relative.parts[0] == "environments":
            continue
        content = source.read_text(encoding="utf-8")
        content = content.replace("REPLACE_WITH_ECR_URL:IMAGE_TAG", image)
        for token, value in values.items():
            content = content.replace(token, value)
        content = content.replace("https://github.com/vipinkumar1234/aws-eks-production-platform.git", repository)
        content = content.replace("$values/gitops/", f"$values/gitops/environments/{environment}/")
        content = content.replace("path: gitops/", f"path: gitops/environments/{environment}/")
        if re.search(r"REPLACE_WITH_[A-Z_]+|IMAGE_TAG", content):
            raise ValueError(f"Unresolved placeholders in {relative}")
        rendered[relative] = content
    return rendered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["dev", "prod"], default=os.getenv("ENVIRONMENT"), required=not os.getenv("ENVIRONMENT"))
    args = parser.parse_args()
    outputs = json.loads(subprocess.check_output(["terraform", f"-chdir={ROOT / 'terraform/environments' / args.environment}", "output", "-json"], text=True))
    files = render(args.environment, outputs, os.environ["GITOPS_REPO_URL"], os.environ["IMAGE_URI"])
    destination = ROOT / "gitops/environments" / args.environment
    for relative, content in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    print(f"Rendered {len(files)} files into {destination}; review and commit before bootstrap.")


if __name__ == "__main__":
    main()
