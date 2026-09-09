"""Conditional writes keep game transitions and abuse limits consistent across replicas."""
from copy import deepcopy
import hashlib
from threading import Lock
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from .game import GameError

AWS_CONFIG = Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 2, "mode": "standard"})


class MemoryStore:
    """Only for tests and the explicitly enabled local demo."""
    def __init__(self):
        self.rooms, self.rates, self.lock = {}, {}, Lock()

    def get(self, room_id):
        with self.lock:
            item = deepcopy(self.rooms.get(room_id))
        return checked(item)

    def put(self, room, expected=None):
        with self.lock:
            old = self.rooms.get(room["game_id"])
            if (old and old["version"] != expected) or (not old and expected is not None):
                raise GameError("Another player updated the room. Reload and try again.")
            if expected is not None:
                room["version"] = expected + 1
            self.rooms[room["game_id"]] = deepcopy(room)

    def limit(self, user, action, maximum, period):
        key = (user, action, int(time.time()) // period)
        with self.lock:
            self.rates[key] = self.rates.get(key, 0) + 1
            if self.rates[key] > maximum:
                raise GameError("Too many requests. Please try again later.", 429)


def checked(item):
    if not item or int(item.get("expires_at", 0)) <= time.time():
        raise GameError("This room does not exist or its seven-day invite has expired.", 404)
    return item


class DynamoStore:
    def __init__(self, table_name, region):
        self.table = boto3.resource("dynamodb", region_name=region, config=AWS_CONFIG).Table(table_name)

    def get(self, room_id):
        return checked(self.table.get_item(Key={"game_id": room_id}, ConsistentRead=True).get("Item"))

    def put(self, room, expected=None):
        item = deepcopy(room)
        args = {"ConditionExpression": "attribute_not_exists(game_id)"}
        if expected is not None:
            item["version"] = int(expected) + 1
            args = {"ConditionExpression": "#v = :v", "ExpressionAttributeNames": {"#v": "version"},
                    "ExpressionAttributeValues": {":v": expected}}
        try:
            self.table.put_item(Item=item, **args)
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise GameError("Another player updated the room. Reload and try again.") from error
            raise
        room.update(item)

    def limit(self, user, action, maximum, period):
        now = int(time.time())
        identity = hashlib.sha256(user.encode()).hexdigest()
        key = f"rate#{identity}#{action}#{now // period}"
        try:
            self.table.update_item(
                Key={"game_id": key}, UpdateExpression="SET expires_at = :ttl ADD #n :one",
                ConditionExpression="attribute_not_exists(#n) OR #n < :maximum",
                ExpressionAttributeNames={"#n": "requests"},
                ExpressionAttributeValues={":ttl": now + period * 2, ":one": 1, ":maximum": maximum},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise GameError("Too many requests. Please try again later.", 429) from error
            raise
