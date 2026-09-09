import json
import unittest
from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
from bootstrap_state import ensure_bucket
import terraform_init


def missing(code):
    return ClientError({'Error': {'Code': code, 'Message': 'test'}}, 'Test')


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.s3, self.sts = Mock(), Mock()
        self.session.client.side_effect = lambda name: {'s3': self.s3, 'sts': self.sts}[name]
        self.session.get_partition_for_region.return_value = 'aws'
        self.sts.get_caller_identity.return_value = {'Account': '123456789012'}
        self.s3.get_bucket_location.return_value = {'LocationConstraint': None}
        self.s3.get_bucket_policy.side_effect = missing('NoSuchBucketPolicy')
        self.s3.get_bucket_tagging.return_value = {'TagSet': [{'Key': 'Retain', 'Value': 'yes'}]}

    def ensure(self, region='us-east-1', check_only=False):
        with patch('bootstrap_state.boto3.Session', return_value=self.session):
            ensure_bucket('test-state', region, check_only)

    def test_create_and_security(self):
        self.s3.head_bucket.side_effect = missing('404')
        self.ensure()
        self.s3.create_bucket.assert_called_once_with(Bucket='test-state', ObjectOwnership='BucketOwnerEnforced')
        self.s3.get_waiter.assert_called_once_with('bucket_exists')
        self.s3.put_bucket_versioning.assert_called_once()
        self.s3.put_public_access_block.assert_called_once()
        policy = json.loads(self.s3.put_bucket_policy.call_args.kwargs['Policy'])
        self.assertEqual(policy['Statement'][0]['Condition']['Bool']['aws:SecureTransport'], 'false')

    def test_bucket_tags_preserve_existing_values(self):
        self.ensure()
        tags = {t['Key']: t['Value'] for t in self.s3.put_bucket_tagging.call_args.kwargs['Tagging']['TagSet']}
        self.assertEqual(tags['Retain'], 'yes')
        self.assertEqual(tags['Name'], 'test-state')
        self.assertEqual(tags['Region'], 'us-east-1')

    def test_untagged_bucket_gets_name(self):
        self.s3.get_bucket_tagging.side_effect = missing('NoSuchTagSet')
        self.ensure()
        self.s3.put_bucket_tagging.assert_called_once()

    def test_tag_read_denied_stops_without_overwriting(self):
        self.s3.get_bucket_tagging.side_effect = missing('AccessDenied')
        with self.assertRaises(ClientError):
            self.ensure()
        self.s3.put_bucket_tagging.assert_not_called()

    def test_regional_create(self):
        self.s3.head_bucket.side_effect = missing('404')
        self.s3.get_bucket_location.return_value = {'LocationConstraint': 'ap-southeast-1'}
        self.ensure('ap-southeast-1')
        self.assertEqual(self.s3.create_bucket.call_args.kwargs['CreateBucketConfiguration'], {'LocationConstraint': 'ap-southeast-1'})

    def test_existing_bucket_and_kms_preserved(self):
        self.ensure()
        self.s3.create_bucket.assert_not_called()
        self.s3.put_bucket_encryption.assert_not_called()

    def test_access_denied_never_creates_bucket(self):
        self.s3.head_bucket.side_effect = missing('403')
        with self.assertRaises(ClientError):
            self.ensure()
        self.s3.create_bucket.assert_not_called()

    def test_wrong_region_stops(self):
        with self.assertRaises(ValueError):
            self.ensure('ap-southeast-1')
        self.s3.put_bucket_policy.assert_not_called()

    def test_destroy_never_creates_bucket(self):
        self.s3.head_bucket.side_effect = missing('404')
        with self.assertRaises(ClientError):
            self.ensure(check_only=True)
        self.s3.create_bucket.assert_not_called()

    def test_init_only_after_successful_bootstrap(self):
        with patch('sys.argv', ['terraform_init.py', '--environment', 'dev', '--bucket', 'test-state']), patch('terraform_init.ensure_bucket', side_effect=RuntimeError('failed')), patch('terraform_init.subprocess.run') as run:
            with self.assertRaises(RuntimeError):
                terraform_init.main()
            run.assert_not_called()

    def test_init_enables_native_locking(self):
        events = []
        with patch('sys.argv', ['terraform_init.py', '--environment', 'dev', '--bucket', 'test-state']), patch('terraform_init.ensure_bucket', side_effect=lambda *a: events.append('bucket')), patch('terraform_init.subprocess.run', side_effect=lambda *a, **kw: events.append(a[0])):
            terraform_init.main()
        self.assertEqual(events[0], 'bucket')
        self.assertIn('-backend-config=use_lockfile=true', events[1])
