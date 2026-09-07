import json
import os
from threading import Lock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import boto3
except ImportError:
    boto3 = None

GAME = {"board": [None] * 9, "next_player": "red", "winner": None}
GAME_LOCK = Lock()
GAME_ID = os.getenv("GAME_ID", "default")
TABLE_NAME = os.getenv("DYNAMODB_TABLE")
TABLE = boto3.resource("dynamodb").Table(TABLE_NAME) if boto3 and TABLE_NAME else None


def load_game():
    if TABLE is None:
        return GAME.copy()
    item = TABLE.get_item(Key={"game_id": GAME_ID}).get("Item")
    return item or {"board": [None] * 9, "next_player": "red", "winner": None}


def save_game(game):
    if TABLE is not None:
        TABLE.put_item(Item={"game_id": GAME_ID, **game})


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.respond(200, {"status": "ok"})
        elif self.path == "/api/game/state":
            with GAME_LOCK:
                self.respond(200, load_game())
        elif self.path == "/":
            self.respond(200, {"service": "arena-api", "environment": os.getenv("ENVIRONMENT", "unknown"), "game": "tic-tac-toe"})
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/game/move":
            self.respond(404, {"error": "not found"})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            player = payload["player"]
            position = int(payload["position"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.respond(400, {"error": "player and position are required"})
            return
        with GAME_LOCK:
            game = load_game()
            if player not in ("red", "blue") or position not in range(9):
                self.respond(400, {"error": "player must be red or blue and position must be 0-8"})
            elif game["winner"] or game["board"][position] is not None:
                self.respond(409, {"error": "move is not available"})
            elif player != game["next_player"]:
                self.respond(409, {"error": "wait for the other player"})
            else:
                game["board"][position] = player
                game["winner"] = player if has_winner(game["board"], player) else None
                game["next_player"] = "blue" if player == "red" else "red"
                save_game(game)
                self.respond(200, game)

    def log_message(self, format, *args):
        return

    def respond(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def has_winner(board, player):
    return any(all(board[index] == player for index in line) for line in (
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    ))


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()
