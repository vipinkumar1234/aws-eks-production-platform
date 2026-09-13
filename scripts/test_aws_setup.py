import unittest
from prepare_aws_deployment import prepare, ROLE, ACCOUNT
from setup_github_oidc import merge_trust, trust_statement


class DeploymentSetupTest(unittest.TestCase):
    def test_defaults_match_existing_role_and_repository(self):
        values = prepare('dev', 'vipinkumar1234/aws-eks-production-platform', 'ap-southeast-1', {}, 'ami-0123456789abcdef0')
        self.assertEqual(values['admin_role_arns'], [ROLE])
        self.assertIn(ACCOUNT, values['github_oidc_provider_arn'])
        self.assertEqual(values['github_oidc_subjects'], ['repo:vipinkumar1234/aws-eks-production-platform:environment:dev'])

    def test_prod_and_explicit_ami(self):
        values = prepare('prod', 'org/repo', 'us-east-1', {'karpenter_ami_id': 'ami-pinned'}, 'ami-new')
        self.assertEqual(values['karpenter_ami_id'], 'ami-pinned')
        self.assertEqual(values['github_oidc_subjects'], ['repo:org/repo:environment:prod'])

    def test_region_mismatch_and_bad_input_rejected(self):
        for overrides in ([], {'aws_region': 'us-east-1'}, {'owner': 'name\nINJECT=value'}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                prepare('dev', 'org/repo', 'ap-southeast-1', overrides, 'ami-test')

    def test_trust_merge_preserves_existing_access_and_is_idempotent(self):
        old = {'Sid': 'ExistingAdmin', 'Effect': 'Allow', 'Principal': {'AWS': f'arn:aws:iam::{ACCOUNT}:root'}, 'Action': 'sts:AssumeRole'}
        policy = {'Version': '2012-10-17', 'Statement': [old]}
        merged = merge_trust(policy)
        self.assertEqual(merged['Statement'], [old, trust_statement()])
        self.assertEqual(merge_trust(merged), merged)
        self.assertEqual(policy['Statement'], [old])

    def test_trust_is_exact_and_environment_scoped(self):
        condition = trust_statement()['Condition']['StringEquals']
        self.assertEqual(condition['token.actions.githubusercontent.com:aud'], 'sts.amazonaws.com')
        subjects = condition['token.actions.githubusercontent.com:sub']
        self.assertEqual(len(subjects), 2)
        self.assertTrue(all('*' not in sub and ':environment:' in sub for sub in subjects))
