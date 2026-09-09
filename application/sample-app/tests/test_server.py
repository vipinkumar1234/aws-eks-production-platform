import unittest
from unittest.mock import Mock
from src.server import create_app
from src.storage import MemoryStore


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.store = MemoryStore()
        self.app = create_app({'TESTING': True, 'LOCAL_DEMO': True, 'ENVIRONMENT': 'local',
                              'SECRET_KEY': 's' * 64, 'APP_ORIGIN': 'http://localhost'}, store=self.store)
        self.client = self.app.test_client()

    def post(self, path, data, client=None):
        return (client or self.client).post(path, json=data, headers={'Origin': 'http://localhost'})

    def room(self, mode='solo'):
        response = self.post('/api/rooms', {'mode': mode})
        self.assertEqual(response.status_code, 201)
        return response.json

    def test_health_and_headers(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.json, {'status': 'ok'})
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
        self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])

    def test_solo_and_stale_write(self):
        room = self.room()
        path = '/api/rooms/' + room['game_id'] + '/move'
        response = self.post(path, {'position': 0, 'version': room['version']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['board'].count('X'), 1)
        self.assertEqual(response.json['board'].count('O'), 1)
        self.assertEqual(self.post(path, {'position': 1, 'version': room['version']}).status_code, 409)

    def test_private_room_and_turns(self):
        room = self.room('friend')
        second, stranger = self.app.test_client(), self.app.test_client()
        path = '/api/rooms/' + room['game_id']
        self.assertEqual(second.get(path).status_code, 403)
        joined = self.post(path + '/join', {}, second)
        self.assertEqual(joined.status_code, 200)
        self.assertNotIn('players', joined.json)
        self.assertEqual(self.post(path + '/join', {}, stranger).status_code, 403)
        self.assertEqual(self.post(path + '/move', {'position': 0, 'version': joined.json['version']}, second).status_code, 409)

    def test_csrf_and_body_validation(self):
        self.assertEqual(self.client.post('/api/rooms', json={'mode': 'solo'}).status_code, 403)
        self.assertEqual(self.client.post('/api/rooms', json={}, headers={'Origin': 'https://evil.example'}).status_code, 403)
        self.assertEqual(self.post('/api/rooms', []).status_code, 400)
        self.assertEqual(self.post('/api/rooms', {'mode': 'invalid'}).status_code, 400)

    def test_boolean_position_rejected(self):
        room = self.room()
        self.assertEqual(self.post('/api/rooms/' + room['game_id'] + '/move', {'position': True, 'version': room['version']}).status_code, 400)

    def test_expiration(self):
        room = self.room()
        self.store.rooms[room['game_id']]['expires_at'] = 1
        self.assertEqual(self.client.get('/api/rooms/' + room['game_id']).status_code, 404)

    def test_rate_limit(self):
        for _ in range(20):
            self.room('friend')
        self.assertEqual(self.post('/api/rooms', {'mode': 'friend'}).status_code, 429)

    def test_demo_forbidden_in_eks(self):
        with self.assertRaises(RuntimeError):
            create_app({'LOCAL_DEMO': True, 'ENVIRONMENT': 'dev'})

    def test_auth_required_and_oauth_state(self):
        auth = Mock()
        app = create_app({'TESTING': True, 'LOCAL_DEMO': False, 'ENVIRONMENT': 'prod',
                          'SECRET_KEY': 's' * 64, 'APP_ORIGIN': 'https://game.example.com',
                          'COGNITO_DOMAIN': 'https://login.example.com', 'COGNITO_CLIENT_ID': 'client'},
                         store=self.store, auth=auth)
        client = app.test_client()
        self.assertEqual(client.get('/api/me').status_code, 401)
        login = client.get('/login', base_url='https://game.example.com')
        self.assertIn('code_challenge_method=S256', login.location)
        self.assertEqual(client.get('/auth/callback?state=wrong&code=fake', base_url='https://game.example.com').status_code, 400)
        auth.exchange.assert_not_called()
