import json
from datetime import datetime, timezone

import events.handlers as handlers


class FakeRedisClient:
    def __init__(self):
        self.lists = {}
        self.hashes = {}

    def exists(self, key):
        return key in self.lists

    def lrange(self, key, start, stop):
        values = self.lists.get(key, [])
        return values[start : None if stop == -1 else stop + 1]

    def lset(self, key, index, value):
        self.lists[key][index] = value

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def hset(self, key, mapping=None):
        self.hashes[key] = dict(mapping or {})


def test_hydrate_thread_merges_database_ratings_into_existing_redis(monkeypatch):
    redis_client = FakeRedisClient()
    thread_id = "user@example.com:session-token"
    thread_name = f"thread:{thread_id}:messages"
    sent_at = datetime(2026, 5, 28, 12, 30, tzinfo=timezone.utc)

    redis_client.rpush(
        thread_name,
        json.dumps(
            {
                "message_id": 12,
                "role": "assistant",
                "content": "This is the answer.",
                "timestamp": int(sent_at.timestamp()),
                "rating_id": None,
                "rating": None,
                "version": None,
                "metadata": {"route": "generic"},
            }
        ),
    )

    database_messages = [
        {
            "message_id": 12,
            "role": "assistant",
            "content": "This is the answer.",
            "sent_at": sent_at,
            "rating_id": 77,
            "rating": 4.0,
            "version": "GROUP-A",
            "metadata": {"route": "generic"},
        }
    ]

    monkeypatch.setattr(handlers, "redis_client", redis_client)
    monkeypatch.setattr(
        handlers,
        "get_selected_messages",
        lambda column_name, filter_value: database_messages,
    )

    hydrated_messages = handlers._hydrate_thread_from_database(thread_id, 100)

    assert hydrated_messages == database_messages
    stored_messages = redis_client.lists[thread_name]
    assert len(stored_messages) == 1
    stored_payload = json.loads(stored_messages[0])
    assert stored_payload["rating_id"] == 77
    assert stored_payload["rating"] == 4.0
    assert stored_payload["version"] == "GROUP-A"
