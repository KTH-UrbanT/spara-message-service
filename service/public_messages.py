from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


PUBLIC_MESSAGE_FIELDS = (
    "message_id",
    "role",
    "content",
    "timestamp",
    "rating_id",
    "rating",
    "version",
    "sources",
    "downloadable_report",
)


def _coerce_timestamp(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            pass
        try:
            normalized = stripped.replace("Z", "+00:00")
            return int(datetime.fromisoformat(normalized).timestamp())
        except ValueError:
            return None
    return None


def to_public_message_payload(message: Dict[str, Any]) -> Dict[str, Any]:
    message = message or {}
    public_payload: Dict[str, Any] = {}

    timestamp = _coerce_timestamp(message.get("timestamp"))
    if timestamp is None:
        timestamp = _coerce_timestamp(message.get("sent_at"))

    for field in PUBLIC_MESSAGE_FIELDS:
        if field == "timestamp":
            if timestamp is not None:
                public_payload[field] = timestamp
            continue

        value = message.get(field)
        if value is not None:
            public_payload[field] = value

    return public_payload


def to_public_message_list(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    public_messages: List[Dict[str, Any]] = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "system":
            continue
        public_messages.append(to_public_message_payload(message))
    return public_messages
