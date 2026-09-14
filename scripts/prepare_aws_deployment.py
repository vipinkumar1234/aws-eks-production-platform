"""Resolve account-specific workflow inputs before Terraform initialization."""
import json
import os
import re
from pathlib import Path
import boto3

ACCOUNT = '001495086648'
ROLE = f'arn:aws:iam::{ACCOUNT}:role/AutomationAdminAll'


def github_oidc_subject(repository, environment, owner_id=None, repository_id=None):
    if owner_id and repository_id:
        owner, repo = repository.split('/', 1)
        return f'repo:{owner}@{owner_id}/{repo}@{repository_id}:environment:{environment}'
    return f'repo:{repository}:environment:{environment}'


def prepare(environment, repository, region, overrides, ami):
    if environment not in ('dev', 'prod'):
        raise ValueError('Unknown environment')
    if not isinstance(overrides, dict):
        raise ValueError('TFVARS_JSON must be an object')
    expected_region = 'ap-southeast-1' if environment == 'dev' else 'us-east-1'
    if region != expected_region or overrides.get('aws_region', region) != region:
        raise ValueError('Workflow region must match the environment')
    values = {
        'owner': 'vipin', 'cost_center': 'gaming-test', 'admin_role_arns': [ROLE],
        'github_oidc_subjects': [github_oidc_subject(
            repository,
            environment,
            os.getenv('GITHUB_REPOSITORY_OWNER_ID'),
            os.getenv('GITHUB_REPOSITORY_ID'),
        )],
        'github_oidc_provider_arn': f'arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com',
        'karpenter_ami_id': ami,
    }
    values.update(overrides)
    for name in ('owner', 'cost_center', 'project'):
        value = values.get(name, 'eks-platform')
        if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{1,31}', value):
            raise ValueError(f'Invalid {name}: use a short lowercase identifier')
    return values


def main():
    environment, region = os.environ['ENVIRONMENT'], os.environ['REGION']
    session = boto3.Session(region_name=region)
    if session.client('sts').get_caller_identity()['Account'] != ACCOUNT:
        raise SystemExit(f'Refusing to deploy outside account {ACCOUNT}')
    overrides = json.loads(os.getenv('ROOT_INPUTS') or '{}')
    if not isinstance(overrides, dict):
        raise SystemExit('TFVARS_JSON must be an object')
    ami = overrides.get('karpenter_ami_id') or os.getenv('PINNED_AMI')
    if not ami:
        ami = session.client('ssm').get_parameter(Name='/aws/service/eks/optimized-ami/1.34/amazon-linux-2023/x86_64/standard/recommended/image_id')['Parameter']['Value']
    values = prepare(environment, os.environ['GITHUB_REPOSITORY'], region, overrides, ami)
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
    print(f'Prepared {environment} in account {ACCOUNT}; AMI {values["karpenter_ami_id"]}; state bucket {bucket}')


if __name__ == '__main__':
    main()
