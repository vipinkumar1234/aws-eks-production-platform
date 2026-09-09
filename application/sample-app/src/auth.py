"""Cognito authorization-code/PKCE login and strict ID-token verification."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import jwt
from .game import GameError


class CognitoAuth:
    def __init__(self, domain, client_id, issuer):
        self.domain, self.client_id, self.issuer = domain.rstrip('/'), client_id, issuer
        self.jwks = jwt.PyJWKClient(issuer + '/.well-known/jwks.json', lifespan=300, timeout=3)

    def verify(self, token):
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=['RS256'], audience=self.client_id,
                                issuer=self.issuer, options={'require': ['exp', 'iat', 'sub', 'aud', 'iss', 'token_use']})
            if claims['token_use'] != 'id' or claims.get('email_verified') is not True or not claims.get('email'):
                raise GameError('Verify your email before playing.', 403)
            return claims
        except jwt.InvalidTokenError as error:
            raise GameError('Your session expired. Please sign in again.', 401) from error

    def exchange(self, code, verifier, redirect_uri):
        body = urlencode({'grant_type': 'authorization_code', 'client_id': self.client_id,
                          'code': code, 'code_verifier': verifier, 'redirect_uri': redirect_uri}).encode()
        request = Request(self.domain + '/oauth2/token', data=body,
                          headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urlopen(request, timeout=5) as response:
            data = json.loads(response.read(32768))
        return data['id_token']
