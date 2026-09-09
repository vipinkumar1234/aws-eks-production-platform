"""Server-authoritative tic-tac-toe rules; identities never come from move payloads."""
from copy import deepcopy
import secrets
import time

LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6))


class GameError(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status
        super().__init__(message)


def outcome(board):
    for line in LINES:
        if board[line[0]] and len({board[i] for i in line}) == 1:
            return board[line[0]], list(line)
    return ("draw", []) if all(board) else (None, [])


def best_move(board):
    def score(cells, turn):
        result, _ = outcome(cells)
        if result:
            return {"O": 1, "X": -1, "draw": 0}[result]
        scores = []
        for i, cell in enumerate(cells):
            if not cell:
                next_board = cells[:]
                next_board[i] = turn
                scores.append(score(next_board, "X" if turn == "O" else "O"))
        return (max if turn == "O" else min)(scores)
    choices = []
    for index in (4, 0, 2, 6, 8, 1, 3, 5, 7):
        if not board[index]:
            candidate = board[:]
            candidate[index] = "O"
            choices.append((score(candidate, "X"), index))
    return max(choices, key=lambda pair: pair[0])[1]


def create_room(user, mode):
    if mode not in ("solo", "friend"):
        raise GameError("Choose solo or friend mode.", 400)
    return {
        "game_id": secrets.token_hex(8), "mode": mode,
        "players": {"X": user, "O": "computer" if mode == "solo" else ""},
        "board": [""] * 9, "turn": "X", "winner": None, "winning_line": [],
        "status": "playing" if mode == "solo" else "waiting", "version": 1,
        "scores": {"X": 0, "O": 0, "draw": 0}, "round": 1, "rematch": [],
        "expires_at": int(time.time()) + 7 * 86400,
    }


def role(room, user):
    for mark, identity in room["players"].items():
        if identity == user:
            return mark
    raise GameError("This is a private game. Join with its invite first.", 403)


def join(room, user):
    if user in room["players"].values():
        return room
    if room["mode"] != "friend" or room["players"]["O"]:
        raise GameError("This room already has two players.", 403)
    room["players"]["O"] = user
    room["status"] = "playing"
    return room


def move(room, user, position, version):
    mark = role(room, user)
    if type(position) is not int or not 0 <= position <= 8:
        raise GameError("Choose an empty square between 0 and 8.", 400)
    if type(version) is not int or version != room["version"]:
        raise GameError("The board changed. Reload it before moving.")
    if room["status"] != "playing" or room["turn"] != mark or room["board"][position]:
        raise GameError("That move is not available. Wait for your turn.")
    room["board"][position] = mark
    result, line = outcome(room["board"])
    if not result and room["mode"] == "solo":
        room["board"][best_move(room["board"])] = "O"
        result, line = outcome(room["board"])
    room["turn"] = "X" if room["mode"] == "solo" or mark == "O" else "O"
    if result:
        room["winner"], room["winning_line"] = result, line
        room["status"] = "draw" if result == "draw" else "won"
        room["scores"][result] += 1
    return room


def rematch(room, user, version):
    mark = role(room, user)
    if type(version) is not int or version != room["version"]:
        raise GameError("The room changed. Reload it before requesting a rematch.")
    if room["status"] not in ("won", "draw"):
        raise GameError("Finish this round first.")
    if mark not in room["rematch"]:
        room["rematch"].append(mark)
    if room["mode"] == "solo" or len(room["rematch"]) == 2:
        room.update(board=[""] * 9, winner=None, winning_line=[], status="playing", turn="X", rematch=[])
        room["round"] += 1
    return room


def public_room(room, user):
    mark = role(room, user)
    data = deepcopy({key: value for key, value in room.items() if key not in ("players", "expires_at")})
    data["you"] = mark
    data["opponent_joined"] = bool(room["players"]["O"])
    return data
