from __future__ import annotations

import csv
import json
from datetime import date, datetime
from io import StringIO
from typing import Any, Iterable


CSV_HEADERS = [
    "session_join_key",
    "message_join_key",
    "session_id",
    "session_token",
    "thread_id",
    "user_id",
    "username",
    "query_message_id",
    "answer_message_id",
    "query_sent_at",
    "answer_sent_at",
    "user_message",
    "assistant_content",
    "rating",
    "rating_id",
    "rating_version",
    "route",
    "agent",
    "classification",
    "intent",
    "needs_clarification",
    "out_of_scope",
    "building_id",
    "byggnadsid",
    "address_used",
    "requested_address",
    "address_from_user",
    "epc_record_address",
    "same_building_multiple_addresses",
    "building_match",
    "retrieved_facts",
    "vector_sources",
    "grounding",
    "grounding_status",
    "claim_count",
    "supported_claim_count",
    "unsupported_claim_count",
    "support_ratio",
    "unsupported_claim_rate",
    "citation_coverage",
    "unsupported_claims",
    "data_freshness",
    "uncertainty",
    "boundary_handling",
    "safety_boundary",
    "safety_status",
    "safety_risk_category",
    "safety_action",
    "safety_handled_safely",
    "safety_requires_review",
    "safety_redirect_to",
    "safety_reason_codes",
    "telemetry",
    "total_latency_seconds",
    "model_call_count",
    "retrieval_call_count",
    "sql_call_count",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "token_usage_estimated",
    "estimated_cost_usd",
    "component_latency_seconds",
    "telemetry_failures",
    "evidence",
    "advisor_review_id",
    "advisor_reviewer_user_id",
    "route_correct",
    "building_data_correct",
    "recommendation_correct",
    "personalized",
    "useful",
    "too_generic",
    "needs_minor_edit",
    "needs_major_edit",
    "unsafe_or_misleading",
    "should_have_asked_clarification",
    "should_have_escalated",
    "technical_correctness_score",
    "building_specificity_score",
    "personalization_score",
    "usefulness_score",
    "justification_score",
    "clarity_score",
    "trust_score",
    "safety_score",
    "advisor_confidence",
    "error_tags",
    "correction_actions",
    "corrected_answer",
    "correction_summary",
    "comments",
    "advisor_review",
]


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _as_json_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def evaluation_records_to_jsonl(records: Iterable[dict[str, Any]]) -> str:
    lines = [
        json.dumps(record, ensure_ascii=False, default=_json_default)
        for record in records
    ]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def evaluation_records_to_csv(records: Iterable[dict[str, Any]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()

    for record in records:
        writer.writerow(
            {
                header: _as_json_text(record.get(header))
                for header in CSV_HEADERS
            }
        )

    return output.getvalue()
