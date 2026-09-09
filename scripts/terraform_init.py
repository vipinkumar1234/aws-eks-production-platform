"""Bootstrap S3, then initialize Terraform with native S3 locking (no DynamoDB)."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from bootstrap_state import ensure_bucket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=['dev', 'prod'], required=True)
    parser.add_argument('--bucket')
    parser.add_argument('--region')
    parser.add_argument('--check-only', action='store_true', help='Require an existing bucket; used for destroy')
    args = parser.parse_args()
    bucket = args.bucket or os.environ.get('TF_STATE_BUCKET_' + args.environment.upper())
    if not bucket:
        parser.error('Set --bucket or TF_STATE_BUCKET_DEV/TF_STATE_BUCKET_PROD')
    region = args.region or ('ap-southeast-1' if args.environment == 'dev' else 'us-east-1')
    tags = {'Environment': args.environment, 'Project': json.loads(os.getenv('ROOT_INPUTS') or '{}').get('project', 'eks-platform')}
    for key, variable in [('Project', 'project'), ('Owner', 'owner'), ('CostCenter', 'cost_center')]:
        if os.getenv('TF_VAR_' + variable):
            tags[key] = os.environ['TF_VAR_' + variable]
    ensure_bucket(bucket, region, args.check_only, tags)
    root = Path(__file__).resolve().parents[1] / 'terraform/environments' / args.environment
    subprocess.run([
        'terraform', f'-chdir={root}', 'init', '-input=false',
        f'-backend-config=bucket={bucket}', f'-backend-config=region={region}',
        f'-backend-config=key=eks/{args.environment}/terraform.tfstate',
        '-backend-config=encrypt=true', '-backend-config=use_lockfile=true',
    ], check=True)


if __name__ == '__main__':
    main()
