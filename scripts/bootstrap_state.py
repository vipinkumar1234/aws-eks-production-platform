"""Create and secure a dedicated state bucket before Terraform initialization."""
import json

import boto3
from botocore.exceptions import ClientError


def ensure_bucket(bucket, region, check_only=False, tags=None):
    session = boto3.Session(region_name=region)
    owner = session.client('sts').get_caller_identity()['Account']
    s3 = session.client('s3')
    args = {'Bucket': bucket, 'ExpectedBucketOwner': owner}
    try:
        s3.head_bucket(**args)
    except ClientError as error:
        if str(error.response['Error']['Code']) not in ('404', 'NoSuchBucket', 'NotFound') or check_only:
            raise
        create = {'Bucket': bucket, 'ObjectOwnership': 'BucketOwnerEnforced'}
        if region != 'us-east-1':
            create['CreateBucketConfiguration'] = {'LocationConstraint': region}
        s3.create_bucket(**create)
        s3.get_waiter('bucket_exists').wait(**args)
    location = s3.get_bucket_location(**args).get('LocationConstraint') or 'us-east-1'
    if location == 'EU':
        location = 'eu-west-1'
    if location != region:
        raise ValueError(f'State bucket region is {location}, expected {region}')
    if check_only:
        return
    try:
        existing_tags = {item['Key']: item['Value'] for item in s3.get_bucket_tagging(**args)['TagSet']}
    except ClientError as error:
        if error.response['Error']['Code'] != 'NoSuchTagSet':
            raise
        existing_tags = {}
    existing_tags.update({'Name': bucket, 'Region': region, 'ManagedBy': 'terraform-bootstrap'})
    existing_tags.update(tags or {})
    s3.put_bucket_tagging(**args, Tagging={'TagSet': [
        {'Key': key, 'Value': value} for key, value in sorted(existing_tags.items())
    ]})
    s3.put_public_access_block(**args, PublicAccessBlockConfiguration={
        'BlockPublicAcls': True, 'IgnorePublicAcls': True,
        'BlockPublicPolicy': True, 'RestrictPublicBuckets': True,
    })
    s3.put_bucket_ownership_controls(**args, OwnershipControls={'Rules': [{'ObjectOwnership': 'BucketOwnerEnforced'}]})
    s3.put_bucket_versioning(**args, VersioningConfiguration={'Status': 'Enabled'})
    # Keep an existing customer-managed KMS configuration if one is present.
    try:
        s3.get_bucket_encryption(**args)
    except ClientError as error:
        if error.response['Error']['Code'] != 'ServerSideEncryptionConfigurationNotFoundError':
            raise
        s3.put_bucket_encryption(**args, ServerSideEncryptionConfiguration={
            'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}],
        })
    try:
        policy = json.loads(s3.get_bucket_policy(**args)['Policy'])
    except ClientError as error:
        if error.response['Error']['Code'] != 'NoSuchBucketPolicy':
            raise
        policy = {'Version': '2012-10-17', 'Statement': []}
    statements = policy['Statement']
    if isinstance(statements, dict):
        statements = [statements]
    policy['Statement'] = [s for s in statements if s.get('Sid') != 'TerraformStateDenyInsecureTransport']
    partition = session.get_partition_for_region(region)
    arn = f'arn:{partition}:s3:::{bucket}'
    policy['Statement'].append({
        'Sid': 'TerraformStateDenyInsecureTransport', 'Effect': 'Deny',
        'Principal': '*', 'Action': 's3:*', 'Resource': [arn, arn + '/*'],
        'Condition': {'Bool': {'aws:SecureTransport': 'false'}},
    })
    s3.put_bucket_policy(**args, Policy=json.dumps(policy))
    print(f'State bucket {bucket} ready in {region}; existing state retained.')
