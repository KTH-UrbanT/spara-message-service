from datetime import datetime, timezone

from service.public_messages import (
    to_public_message_list,
    to_public_message_payload,
)


def test_to_public_message_payload_keeps_safe_evaluation_metadata():
    payload = to_public_message_payload(
        {
            "message_id": 4,
            "role": "assistant",
            "content": "Answer",
            "timestamp": 1710000000.25,
            "sources": [{"name": "Guide", "link": "https://example.com"}],
            "metadata": {
                "route": "combined",
                "agent": "BuildingAgent",
                "building_match": {"matched_address": "Examplegatan 1"},
                "retrieved_facts": {"energy_class": "D"},
                "grounding": {"status": "passed", "unsupported_claim_count": 0},
                "safety_boundary": {"status": "not_applicable", "handled_safely": True},
                "sql_trace": {"query": "internal"},
            },
            "evidence": [{"evidence_type": "sql_trace"}],
            "classification": "building_specific",
        }
    )

    assert payload == {
        "message_id": 4,
        "role": "assistant",
        "content": "Answer",
        "timestamp": 1710000000,
        "sources": [{"name": "Guide", "link": "https://example.com"}],
        "metadata": {
            "route": "combined",
            "agent": "BuildingAgent",
            "building_match": {"matched_address": "Examplegatan 1"},
            "retrieved_facts": {"energy_class": "D"},
            "grounding": {"status": "passed", "unsupported_claim_count": 0},
            "safety_boundary": {"status": "not_applicable", "handled_safely": True},
        },
    }


def test_to_public_message_payload_supports_datetime_sent_at():
    payload = to_public_message_payload(
        {
            "message_id": 1,
            "role": "user",
            "content": "Hello",
            "sent_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "metadata": {"ignored": True},
        }
    )

    assert payload["timestamp"] == 1704067200
    assert "metadata" not in payload


def test_to_public_message_list_filters_system_messages():
    payloads = to_public_message_list(
        [
            {"role": "system", "content": "Ignore", "timestamp": 1},
            {"role": "user", "content": "Keep", "timestamp": 2, "metadata": {"x": 1}},
        ]
    )

    assert payloads == [{"role": "user", "content": "Keep", "timestamp": 2}]
