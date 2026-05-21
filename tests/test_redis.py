import json
from datetime import datetime, timezone

from service.redis import insert_into_redis_client


class FakeRedisClient:
    def __init__(self):
        self.lists = {}
        self.hashes = {}
        self.published = []

    def exists(self, key):
        return key in self.lists

    def lrange(self, key, start, stop):
        values = self.lists.get(key, [])
        return values[start : None if stop == -1 else stop + 1]

    def lset(self, key, index, value):
        self.lists[key][index] = value

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def publish(self, channel, payload):
        self.published.append((channel, payload))

    def hset(self, key, mapping):
        self.hashes[key] = dict(mapping)


def test_insert_into_redis_client_restores_message_metadata_and_thread_meta():
    redis_client = FakeRedisClient()
    sent_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    messages = [
        {
            "message_id": 2,
            "role": "assistant",
            "content": "Hi there!",
            "sent_at": sent_at,
            "rating_id": None,
            "rating": None,
            "version": None,
            "metadata": {
                "route": "generic",
                "agent": "GenericAgent",
                "evaluation_mode": True,
            },
        }
    ]

    insert_into_redis_client(messages, redis_client, "thread-1")

    stored_messages = redis_client.lists["thread:thread-1:messages"]
    assert len(stored_messages) == 1
    assert redis_client.published == []
    payload = json.loads(stored_messages[0])
    assert payload["metadata"] == {
        "route": "generic",
        "agent": "GenericAgent",
        "evaluation_mode": True,
    }
    assert redis_client.hashes["thread:thread-1:meta"] == {
        "route": "generic",
        "agent": "GenericAgent",
        "evaluation_mode": "true",
    }
