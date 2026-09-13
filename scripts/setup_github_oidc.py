"""One-time setup using existing AWS administrator credentials, never access keys in GitHub."""
import json
import boto3
from botocore.exceptions import ClientError

ACCOUNT = '001495086648'
ROLE = 'AutomationAdminAll'
REPOSITORY = 'vipinkumar1234/aws-eks-production-platform'
PROVIDER = f'arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com'


def trust_statement():
    return {
        'Sid': 'ArenaGridGitHubEnvironments', 'Effect': 'Allow',
        'Principal': {'Federated': PROVIDER}, 'Action': 'sts:AssumeRoleWithWebIdentity',
        'Condition': {'StringEquals': {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
            'token.actions.githubusercontent.com:sub': [
                f'repo:{REPOSITORY}:environment:dev', f'repo:{REPOSITORY}:environment:prod',
            ],
        }},
    }


def merge_trust(policy):
    statements = policy.get('Statement', [])
    if isinstance(statements, dict):
        statements = [statements]
    return dict(policy, Statement=[s for s in statements if s.get('Sid') != 'ArenaGridGitHubEnvironments'] + [trust_statement()])


def main():
    session = boto3.Session()
    if session.client('sts').get_caller_identity()['Account'] != ACCOUNT:
        raise SystemExit(f'Authenticate to account {ACCOUNT} before running setup.')
    iam = session.client('iam')
    # Check role access before making any changes. Preserve existing trust statements.
    role = iam.get_role(RoleName=ROLE)['Role']
    try:
        provider = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=PROVIDER)
        if 'sts.amazonaws.com' not in provider['ClientIDList']:
            iam.add_client_id_to_open_id_connect_provider(OpenIDConnectProviderArn=PROVIDER, ClientID='sts.amazonaws.com')
    except ClientError as error:
        if error.response['Error']['Code'] != 'NoSuchEntity':
            raise
        iam.create_open_id_connect_provider(Url='https://token.actions.githubusercontent.com', ClientIDList=['sts.amazonaws.com'])
    iam.update_assume_role_policy(RoleName=ROLE, PolicyDocument=json.dumps(merge_trust(role['AssumeRolePolicyDocument'])))
    print(f'GitHub OIDC trust configured for {REPOSITORY}, dev/prod, on {role["Arn"]}. Existing role permissions were not changed.')


if __name__ == '__main__':
    main()
