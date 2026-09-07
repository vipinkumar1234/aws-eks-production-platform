import json
import unittest
from http.client import HTTPConnection
from threading import Thread
from http.server import ThreadingHTTPServer

from src.server import GAME, GAME_LOCK, Handler


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_health(self):
        connection = HTTPConnection(*self.server.server_address)
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"status": "ok"})

    def test_game_move_and_state(self):
        with GAME_LOCK:
            GAME["board"] = [None] * 9
            GAME["next_player"] = "red"
            GAME["winner"] = None
        connection = HTTPConnection(*self.server.server_address)
        body = json.dumps({"player": "red", "position": 0}).encode()
        connection.request("POST", "/api/game/move", body=body, headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read())["board"][0], "red")


if __name__ == "__main__":
    unittest.main()
