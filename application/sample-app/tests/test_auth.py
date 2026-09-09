import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from src.auth import CognitoAuth
from src.game import GameError


class AuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.auth = CognitoAuth('https://login.example.com', 'client', 'https://issuer.example.com')
        self.auth.jwks = Mock()
        self.auth.jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key=self.key.public_key())
        self.claims = {'sub': 'player', 'iss': 'https://issuer.example.com', 'aud': 'client',
                       'iat': int(time.time()), 'exp': int(time.time()) + 300, 'token_use': 'id',
                       'email': 'player@example.com', 'email_verified': True}

    def verify(self, **changes):
        return self.auth.verify(jwt.encode(self.claims | changes, self.key, algorithm='RS256'))

    def test_verified_identity(self):
        self.assertEqual(self.verify()['sub'], 'player')

    def test_wrong_issuer_audience_expiry_and_token_type(self):
        for changes in ({'iss': 'https://evil.example'}, {'aud': 'other'},
                        {'exp': 1}, {'token_use': 'access'}, {'email_verified': False}):
            with self.subTest(changes=changes), self.assertRaises(GameError):
                self.verify(**changes)

    def test_unsigned_token_rejected(self):
        with self.assertRaises(GameError):
            self.auth.verify(jwt.encode(self.claims, key='', algorithm='none'))
