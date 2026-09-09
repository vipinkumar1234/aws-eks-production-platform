"""WSGI game application. Production runs behind an HTTPS ALB with WAF."""
import base64
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import logging
import os
import re
import secrets
import time
from urllib.parse import urlencode

import boto3
from flask import Flask, g, jsonify, redirect, render_template, request, session
from flask.json.provider import DefaultJSONProvider
from werkzeug.exceptions import HTTPException

from .auth import CognitoAuth
from .game import GameError, create_room, join, move, public_room, rematch
from .storage import AWS_CONFIG, DynamoStore, MemoryStore


class GameJSON(DefaultJSONProvider):
    @staticmethod
    def default(value):
        if isinstance(value, Decimal):
            return int(value)
        return DefaultJSONProvider.default(value)


def create_app(config=None, store=None, auth=None):
    app = Flask(__name__)
    app.json = GameJSON(app)
    environment = os.getenv('ENVIRONMENT', 'local')
    demo = os.getenv('LOCAL_DEMO', '') == '1'
    app.config.update(
        ENVIRONMENT=environment, LOCAL_DEMO=demo,
        APP_ORIGIN=os.getenv('APP_ORIGIN', 'http://127.0.0.1:8080'),
        AWS_REGION=os.getenv('AWS_REGION', 'ap-southeast-1'),
        COGNITO_DOMAIN=os.getenv('COGNITO_DOMAIN', ''), COGNITO_CLIENT_ID=os.getenv('COGNITO_CLIENT_ID', ''),
        COGNITO_ISSUER=os.getenv('COGNITO_ISSUER', ''), DYNAMODB_TABLE=os.getenv('DYNAMODB_TABLE', ''),
        MAX_CONTENT_LENGTH=4096, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=not demo, SESSION_COOKIE_NAME='arena_demo' if demo else '__Host-arena',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=1), SESSION_REFRESH_EACH_REQUEST=False,
    )
    if config:
        app.config.update(config)
    demo = app.config['LOCAL_DEMO']
    if demo and app.config['ENVIRONMENT'] != 'local':
        raise RuntimeError('LOCAL_DEMO is forbidden outside the local environment')
    if not app.config.get('TESTING') and not demo:
        for key in ('COGNITO_DOMAIN', 'COGNITO_CLIENT_ID', 'COGNITO_ISSUER', 'DYNAMODB_TABLE'):
            if not app.config[key]:
                raise RuntimeError(f'{key} is required; authentication never falls back to demo mode')
        if not app.config['APP_ORIGIN'].startswith('https://'):
            raise RuntimeError('Production requires an HTTPS APP_ORIGIN')
    if not app.config.get('SECRET_KEY'):
        if demo:
            app.config['SECRET_KEY'] = secrets.token_hex(32)
        else:
            secret_arn = os.environ['SESSION_SECRET_ARN']
            app.config['SECRET_KEY'] = boto3.client('secretsmanager', region_name=app.config['AWS_REGION'], config=AWS_CONFIG).get_secret_value(SecretId=secret_arn)['SecretString']
    if len(app.config['SECRET_KEY']) < 32:
        raise RuntimeError('Session key must have at least 32 characters')
    app.extensions['store'] = store or (MemoryStore() if demo else DynamoStore(app.config['DYNAMODB_TABLE'], app.config['AWS_REGION']))
    app.extensions['auth'] = auth or (None if demo else CognitoAuth(app.config['COGNITO_DOMAIN'], app.config['COGNITO_CLIENT_ID'], app.config['COGNITO_ISSUER']))
    storage = app.extensions['store']

    def identity():
        if demo:
            if 'demo_user' not in session:
                session['demo_user'] = secrets.token_hex(16)
            return {'sub': session['demo_user'], 'email': 'Local demo player'}
        token = session.get('id_token')
        if not token:
            raise GameError('Sign in with your verified email to play.', 401)
        return app.extensions['auth'].verify(token)

    @app.before_request
    def protect():
        g.started = time.monotonic()
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.headers.get('Origin') != app.config['APP_ORIGIN'] or not request.is_json:
                raise GameError('This request must come from the game website.', 403)
        if request.path.startswith('/api/'):
            g.user = identity()
            if request.method == 'POST':
                storage.limit(g.user['sub'], 'actions', 90, 60)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers['Cache-Control'] = 'no-store'
        if not demo:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        # Do not log OAuth query strings, email, tokens, room IDs, or request bodies.
        app.logger.info(json.dumps({'event': 'request', 'route': str(request.url_rule), 'status': response.status_code,
                                    'duration_ms': round((time.monotonic() - g.started) * 1000)}))
        return response

    @app.errorhandler(GameError)
    def game_error(error):
        return jsonify(error=error.message), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        app.logger.error(json.dumps({'event': 'dependency_or_application_error', 'type': type(error).__name__}))
        return jsonify(error='The service is temporarily unavailable. Please try again.'), 503

    @app.get('/')
    def home():
        return render_template('index.html', demo=demo)

    @app.get('/healthz')
    def health():
        return jsonify(status='ok')

    @app.get('/readyz')
    def ready():
        if not demo:
            # Low-volume sentinel lookup checks the table and IAM without mutating game data.
            storage.table.get_item(Key={'game_id': 'readiness'}, ConsistentRead=True)
        return jsonify(status='ready')

    @app.get('/login')
    @app.get('/signup')
    def login():
        if demo:
            return redirect('/')
        state, verifier, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        session.clear()
        session['oauth'] = {'state': state, 'verifier': verifier, 'nonce': nonce, 'created': time.time()}
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params = {'client_id': app.config['COGNITO_CLIENT_ID'], 'response_type': 'code', 'scope': 'openid email',
                  'redirect_uri': app.config['APP_ORIGIN'] + '/auth/callback', 'state': state, 'nonce': nonce,
                  'code_challenge': challenge, 'code_challenge_method': 'S256'}
        endpoint = '/signup' if request.path == '/signup' else '/oauth2/authorize'
        return redirect(app.config['COGNITO_DOMAIN'] + endpoint + '?' + urlencode(params))

    @app.get('/auth/callback')
    def callback():
        flow = session.pop('oauth', None)
        if not flow or time.time() - flow['created'] > 600 or not secrets.compare_digest(request.args.get('state', ''), flow['state']):
            raise GameError('Login expired or could not be verified. Start sign-in again.', 400)
        code = request.args.get('code', '')
        if not code or len(code) > 4096:
            raise GameError('Login was cancelled. Start sign-in again.', 400)
        token = app.extensions['auth'].exchange(code, flow['verifier'], app.config['APP_ORIGIN'] + '/auth/callback')
        claims = app.extensions['auth'].verify(token)
        if not secrets.compare_digest(claims.get('nonce', ''), flow['nonce']):
            raise GameError('Login could not be verified. Start sign-in again.', 400)
        session.clear()
        session['id_token'] = token
        session.permanent = True
        return redirect('/')

    @app.post('/api/logout')
    def logout():
        session.clear()
        target = '/' if demo else app.config['COGNITO_DOMAIN'] + '/logout?' + urlencode({'client_id': app.config['COGNITO_CLIENT_ID'], 'logout_uri': app.config['APP_ORIGIN'] + '/'})
        return jsonify(redirect=target)

    @app.get('/api/me')
    def me():
        return jsonify(email=g.user['email'], demo=demo)

    @app.post('/api/rooms')
    def new_room():
        payload = body()
        storage.limit(g.user['sub'], 'new_rooms', 20, 3600)
        room = create_room(g.user['sub'], payload.get('mode'))
        storage.put(room)
        return jsonify(public_room(room, g.user['sub'])), 201

    def load(room_id):
        if not re.fullmatch(r'[0-9a-f]{16}', room_id):
            raise GameError('Invalid room code.', 400)
        return storage.get(room_id)

    def body():
        value = request.get_json()
        if not isinstance(value, dict):
            raise GameError('Expected a JSON object.', 400)
        return value

    @app.get('/api/rooms/<room_id>')
    def state(room_id):
        return jsonify(public_room(load(room_id), g.user['sub']))

    @app.post('/api/rooms/<room_id>/join')
    def join_room(room_id):
        room = load(room_id)
        version = room['version']
        if g.user['sub'] not in room['players'].values():
            join(room, g.user['sub'])
            storage.put(room, version)
        return jsonify(public_room(room, g.user['sub']))

    @app.post('/api/rooms/<room_id>/move')
    def play(room_id):
        payload, room = body(), load(room_id)
        version = room['version']
        move(room, g.user['sub'], payload.get('position'), payload.get('version'))
        storage.put(room, version)
        return jsonify(public_room(room, g.user['sub']))

    @app.post('/api/rooms/<room_id>/rematch')
    def again(room_id):
        payload, room = body(), load(room_id)
        version = room['version']
        rematch(room, g.user['sub'], payload.get('version'))
        storage.put(room, version)
        return jsonify(public_room(room, g.user['sub']))

    logging.basicConfig(level=logging.INFO)
    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=8080, debug=False)
