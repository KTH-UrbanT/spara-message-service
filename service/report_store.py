import json
import os
from typing import Any, Dict, Optional

import redis

from config import settings


REPORT_KEY_PREFIX = os.getenv("DRAFT_REPORT_KEY_PREFIX", "draft_report")

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True,
)


def get_report_payload(report_id: str) -> Optional[Dict[str, Any]]:
    if not report_id:
        return None

    raw = redis_client.get(f"{REPORT_KEY_PREFIX}:{report_id}")
    if not raw:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
