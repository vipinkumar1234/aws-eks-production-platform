"""Resolve account-specific workflow inputs before Terraform initialization."""
import json
import os
import re
from pathlib import Path
import boto3

ACCOUNT = '001495086648'
ROLE = f'arn:aws:iam::{ACCOUNT}:role/AutomationAdminAll'
ROOT = f'arn:aws:iam::{ACCOUNT}:root'


def github_oidc_subject(repository, environment, owner_id=None, repository_id=None):
    if owner_id and repository_id and os.getenv('GITHUB_REPOSITORY') == repository:
        owner, repo = repository.split('/', 1)
        return f'repo:{owner}@{owner_id}/{repo}@{repository_id}:environment:{environment}'
    return f'repo:{repository}:environment:{environment}'


def prepare(environment, repository, region, overrides, ami, kubernetes_version='1.36'):
    if environment not in ('dev', 'prod'):
        raise ValueError('Unknown environment')
    if not isinstance(overrides, dict):
        raise ValueError('TFVARS_JSON must be an object')
    if kubernetes_version not in ('1.35', '1.36'):
        raise ValueError('KUBERNETES_VERSION must be 1.35 or 1.36')
    if overrides.get('kubernetes_version', kubernetes_version) != kubernetes_version:
        raise ValueError('TFVARS_JSON kubernetes_version must match the workflow Kubernetes version input')
    expected_region = 'ap-southeast-1' if environment == 'dev' else 'us-east-1'
    if region != expected_region or overrides.get('aws_region', region) != region:
        raise ValueError('Workflow region must match the environment')
    values = {
        'owner': 'vipin', 'cost_center': 'gaming-test', 'admin_role_arns': [ROLE, ROOT],
        'github_oidc_subjects': [github_oidc_subject(
            repository,
            environment,
            os.getenv('GITHUB_REPOSITORY_OWNER_ID'),
            os.getenv('GITHUB_REPOSITORY_ID'),
        )],
        'github_oidc_provider_arn': f'arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com',
        'karpenter_ami_id': ami,
        'kubernetes_version': kubernetes_version,
    }
    values.update(overrides)
    for name in ('owner', 'cost_center', 'project'):
        value = values.get(name, 'eks-platform')
        if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,31}', value):
            raise ValueError(f'Invalid {name}: use a short lowercase identifier')
    return values


def main():
    environment, region = os.environ['ENVIRONMENT'], os.environ['REGION']
    kubernetes_version = os.getenv('KUBERNETES_VERSION') or os.getenv('TF_VAR_kubernetes_version') or '1.36'
    if kubernetes_version not in ('1.35', '1.36'):
        raise SystemExit('KUBERNETES_VERSION must be 1.35 or 1.36')
    session = boto3.Session(region_name=region)
    if session.client('sts').get_caller_identity()['Account'] != ACCOUNT:
        raise SystemExit(f'Refusing to deploy outside account {ACCOUNT}')
    overrides = json.loads(os.getenv('ROOT_INPUTS') or '{}')
    if not isinstance(overrides, dict):
        raise SystemExit('TFVARS_JSON must be an object')
    ami = overrides.get('karpenter_ami_id') or os.getenv('PINNED_AMI')
    if not ami:
        parameter_name = f'/aws/service/eks/optimized-ami/{kubernetes_version}/amazon-linux-2023/x86_64/standard/recommended/image_id'
        ami = session.client('ssm').get_parameter(Name=parameter_name)['Parameter']['Value']
    values = prepare(environment, os.environ['GITHUB_REPOSITORY'], region, overrides, ami, kubernetes_version)
    # Empty dispatch input preserves an existing optional zone from TFVARS_JSON.
    if os.getenv('DNS_ZONE_NAME'):
        values['dns_zone_name'] = os.environ['DNS_ZONE_NAME']
    root = Path(__file__).resolve().parents[1]
    (root / 'terraform/environments' / environment / 'ci.auto.tfvars.json').write_text(json.dumps(values), encoding='utf-8')
    bucket = os.getenv('STATE_BUCKET') or f'eks-platform-{ACCOUNT}-{region}-{environment}-tfstate'
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
        raise ValueError('Invalid S3 state bucket name')
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as output:
        output.write(f'STATE_BUCKET={bucket}\n')
        for name in ('owner', 'cost_center', 'project'):
            output.write(f'TF_VAR_{name}={values.get(name, "eks-platform")}\n')
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'state_bucket={bucket}\n')
    print(f'Prepared {environment} in account {ACCOUNT}; EKS {values["kubernetes_version"]}; AMI {values["karpenter_ami_id"]}; state bucket {bucket}')


if __name__ == '__main__':
    main()
