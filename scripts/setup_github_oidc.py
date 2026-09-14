"""One-time setup using existing AWS administrator credentials, never access keys in GitHub."""
import argparse
import json
import boto3
from botocore.exceptions import ClientError

ACCOUNT = '001495086648'
ROLE = 'AutomationAdminAll'
REPOSITORY = 'vipinkumar1234/aws-eks-production-platform'
REPOSITORY_OWNER_ID = '110930371'
REPOSITORY_ID = '1359084778'
PROVIDER = f'arn:aws:iam::{ACCOUNT}:oidc-provider/token.actions.githubusercontent.com'


def trust_statement():
    return {
        'Sid': 'ArenaGridGitHubEnvironments', 'Effect': 'Allow',
        'Principal': {'Federated': PROVIDER}, 'Action': 'sts:AssumeRoleWithWebIdentity',
        'Condition': {'StringEquals': {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
            'token.actions.githubusercontent.com:sub': [
                f'repo:vipinkumar1234@{REPOSITORY_OWNER_ID}/aws-eks-production-platform@{REPOSITORY_ID}:environment:dev',
                f'repo:vipinkumar1234@{REPOSITORY_OWNER_ID}/aws-eks-production-platform@{REPOSITORY_ID}:environment:prod',
            ],
        }},
    }


def merge_trust(policy):
    statements = policy.get('Statement', [])
    if isinstance(statements, dict):
        statements = [statements]
    return dict(policy, Statement=[s for s in statements if s.get('Sid') != 'ArenaGridGitHubEnvironments'] + [trust_statement()])


def check_configuration(provider, policy):
    errors = []
    if provider.get('Url', '').removeprefix('https://').rstrip('/') != 'token.actions.githubusercontent.com':
        errors.append('OIDC provider URL must be https://token.actions.githubusercontent.com')
    if 'sts.amazonaws.com' not in provider.get('ClientIDList', []):
        errors.append('OIDC provider audience must include sts.amazonaws.com')
    statements = policy.get('Statement', [])
    if isinstance(statements, dict):
        statements = [statements]
    expected = trust_statement()
    # Verify the exact statement managed by this script, without accepting wildcard trust.
    if expected not in statements:
        errors.append('Exact dev/prod GitHub trust statement missing; run this script without --check-only')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Inspect provider and role trust without modifying AWS')
    args = parser.parse_args()
    session = boto3.Session()
    if session.client('sts').get_caller_identity()['Account'] != ACCOUNT:
        raise SystemExit(f'Authenticate to account {ACCOUNT} before running setup.')
    iam = session.client('iam')
    # Check role access before making any changes. Preserve existing trust statements.
    role = iam.get_role(RoleName=ROLE)['Role']
    if args.check_only:
        try:
            provider = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=PROVIDER)
        except ClientError as error:
            if error.response['Error']['Code'] == 'NoSuchEntity':
                raise SystemExit('GitHub OIDC provider is missing. Run setup without --check-only.') from None
            raise
        errors = check_configuration(provider, role['AssumeRolePolicyDocument'])
        print(json.dumps({'Account': ACCOUNT, 'Role': role['Arn'], 'Provider': PROVIDER,
                          'Audience': provider.get('ClientIDList', []),
                          'ExpectedSubjects': trust_statement()['Condition']['StringEquals']['token.actions.githubusercontent.com:sub']}, indent=2))
        if errors:
            raise SystemExit('\n'.join(errors))
        print('Provider and script-managed trust configuration verified. Start a new GitHub run to test STS token acceptance.')
        return
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
