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

PUBLIC_METADATA_FIELDS = (
    "route",
    "agent",
    "classification",
    "intent",
    "intent_list",
    "needs_clarification",
    "out_of_scope",
    "out_of_scope_type",
    "expert_handoff_triggered",
    "report_generation_triggered",
    "evaluation_mode",
    "address",
    "address_from_user",
    "address_location_hint",
    "requested_address",
    "epc_record_address",
    "same_building_multiple_addresses",
    "address_context_note",
    "brf_name",
    "selected_brf_building_id",
    "selected_brf_addresses",
    "selected_brf_lookup_address",
    "building_id_from_user",
    "pending_brf_resolution",
    "brf_resolution",
    "brf_candidate_buildings",
    "building_id",
    "byggnadsid",
    "building_match",
    "building_identity_check",
    "retrieved_facts",
    "vector_sources",
    "grounding",
    "data_freshness",
    "uncertainty",
    "clarification",
    "boundary_handling",
    "safety_boundary",
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


def _is_present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _public_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}

    return {
        field: metadata[field]
        for field in PUBLIC_METADATA_FIELDS
        if field in metadata and _is_present(metadata[field])
    }


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

    metadata = _public_metadata(message.get("metadata"))
    if metadata:
        public_payload["metadata"] = metadata

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
