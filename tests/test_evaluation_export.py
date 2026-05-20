import csv
import json
from datetime import datetime, timezone
from io import StringIO

from service.evaluation_export import (
    evaluation_records_to_csv,
    evaluation_records_to_jsonl,
)


def test_evaluation_records_to_jsonl_serializes_one_record_per_line():
    payload = evaluation_records_to_jsonl(
        [
            {
                "answer_message_id": 12,
                "answer_sent_at": datetime(2026, 5, 18, tzinfo=timezone.utc),
                "route": "combined",
                "retrieved_facts": {"energy_class": "D"},
            }
        ]
    )

    lines = payload.strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["answer_message_id"] == 12
    assert record["answer_sent_at"] == "2026-05-18T00:00:00+00:00"
    assert record["retrieved_facts"] == {"energy_class": "D"}


def test_evaluation_records_to_csv_flattens_structured_fields_as_json():
    payload = evaluation_records_to_csv(
        [
            {
                "session_id": 1,
                "answer_message_id": 12,
                "user_message": "What is our energy class?",
                "assistant_content": "Energy class D",
                "route": "building_specific",
                "rating": 4,
                "building_match": {"matched_address": "Examplegatan 1"},
                "retrieved_facts": {"energy_class": "D"},
                "grounding": {
                    "status": "needs_review",
                    "claim_count": 3,
                    "supported_claim_count": 2,
                    "unsupported_claim_count": 1,
                    "support_ratio": 0.6667,
                    "unsupported_claim_rate": 0.3333,
                    "citation_coverage": 0.5,
                    "unsupported_claims": ["Unsupported recommendation."],
                },
                "grounding_status": "needs_review",
                "claim_count": 3,
                "supported_claim_count": 2,
                "unsupported_claim_count": 1,
                "support_ratio": 0.6667,
                "unsupported_claim_rate": 0.3333,
                "citation_coverage": 0.5,
                "unsupported_claims": ["Unsupported recommendation."],
                "telemetry": {
                    "operation": "live_chat_turn",
                    "model_call_count": 2,
                    "retrieval_call_count": 1,
                    "sql_call_count": 1,
                    "total_tokens": 1200,
                    "component_latency_seconds": {"router_agent": 0.5},
                },
                "total_latency_seconds": 3.25,
                "model_call_count": 2,
                "retrieval_call_count": 1,
                "sql_call_count": 1,
                "prompt_tokens": 900,
                "completion_tokens": 300,
                "total_tokens": 1200,
                "token_usage_estimated": False,
                "estimated_cost_usd": 0.0042,
                "component_latency_seconds": {"router_agent": 0.5},
                "telemetry_failures": [],
                "safety_boundary": {
                    "status": "passed",
                    "risk_category": "legal_advice",
                    "action": "redirected",
                    "handled_safely": True,
                    "requires_review": False,
                    "redirect_to": "relevant_authority_or_legal_expert",
                    "reason_codes": [],
                },
                "safety_status": "passed",
                "safety_risk_category": "legal_advice",
                "safety_action": "redirected",
                "safety_handled_safely": True,
                "safety_requires_review": False,
                "safety_redirect_to": "relevant_authority_or_legal_expert",
                "safety_reason_codes": [],
                "route_correct": True,
                "error_tags": ["retrieval"],
                "correction_actions": [
                    {"type": "remove_unsupported_claim", "field": "recommendation"}
                ],
                "corrected_answer": "Energy class D. Check the latest declaration before deciding.",
                "correction_summary": "Removed unsupported payback claim.",
                "comments": "Good but cite the source more clearly.",
            }
        ]
    )

    rows = list(csv.DictReader(StringIO(payload)))
    assert rows[0]["session_id"] == "1"
    assert rows[0]["route"] == "building_specific"
    assert rows[0]["rating"] == "4"
    assert rows[0]["route_correct"] == "True"
    assert rows[0]["grounding_status"] == "needs_review"
    assert rows[0]["claim_count"] == "3"
    assert rows[0]["supported_claim_count"] == "2"
    assert rows[0]["unsupported_claim_count"] == "1"
    assert rows[0]["support_ratio"] == "0.6667"
    assert rows[0]["unsupported_claim_rate"] == "0.3333"
    assert rows[0]["citation_coverage"] == "0.5"
    assert rows[0]["total_latency_seconds"] == "3.25"
    assert rows[0]["model_call_count"] == "2"
    assert rows[0]["retrieval_call_count"] == "1"
    assert rows[0]["sql_call_count"] == "1"
    assert rows[0]["prompt_tokens"] == "900"
    assert rows[0]["completion_tokens"] == "300"
    assert rows[0]["total_tokens"] == "1200"
    assert rows[0]["token_usage_estimated"] == "False"
    assert rows[0]["estimated_cost_usd"] == "0.0042"
    assert rows[0]["safety_status"] == "passed"
    assert rows[0]["safety_risk_category"] == "legal_advice"
    assert rows[0]["safety_action"] == "redirected"
    assert rows[0]["safety_handled_safely"] == "True"
    assert rows[0]["safety_requires_review"] == "False"
    assert rows[0]["safety_redirect_to"] == "relevant_authority_or_legal_expert"
    assert rows[0]["safety_reason_codes"] == ""
    assert json.loads(rows[0]["error_tags"]) == ["retrieval"]
    assert json.loads(rows[0]["correction_actions"]) == [
        {"type": "remove_unsupported_claim", "field": "recommendation"}
    ]
    assert rows[0]["corrected_answer"] == "Energy class D. Check the latest declaration before deciding."
    assert rows[0]["correction_summary"] == "Removed unsupported payback claim."
    assert rows[0]["comments"] == "Good but cite the source more clearly."
    assert json.loads(rows[0]["grounding"])["status"] == "needs_review"
    assert json.loads(rows[0]["unsupported_claims"]) == ["Unsupported recommendation."]
    assert json.loads(rows[0]["safety_boundary"])["action"] == "redirected"
    assert json.loads(rows[0]["telemetry"])["model_call_count"] == 2
    assert json.loads(rows[0]["component_latency_seconds"]) == {"router_agent": 0.5}
    assert rows[0]["telemetry_failures"] == ""
    assert json.loads(rows[0]["building_match"]) == {
        "matched_address": "Examplegatan 1"
    }
    assert json.loads(rows[0]["retrieved_facts"]) == {"energy_class": "D"}
