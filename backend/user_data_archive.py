import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict


ARCHIVE_VERSION = 1
CLEAR_CACHE_CONFIRMATION_PREFIX = "CLEAR"


def clear_cache_confirmation(user_id: int) -> str:
    return f"{CLEAR_CACHE_CONFIRMATION_PREFIX} {int(user_id)}"


def validate_clear_cache_confirmation(user_id: int, value: Any) -> bool:
    return str(value or "").strip() == clear_cache_confirmation(user_id)


def _json_default(value: Any):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def serialize_archive_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )


def deserialize_archive_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_archive_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    sections = {}
    total_records = 0
    for section_name in ("main_app", "ai_chatter"):
        section = snapshot.get(section_name) or {}
        tables = {}
        section_total = 0
        for table_name, rows in section.items():
            count = len(rows) if isinstance(rows, list) else (1 if rows else 0)
            tables[table_name] = count
            section_total += count
        sections[section_name] = {
            "records": section_total,
            "tables": tables,
        }
        total_records += section_total

    identity = snapshot.get("identity") or {}
    return {
        "version": ARCHIVE_VERSION,
        "display_name": str(identity.get("display_name") or ""),
        "username": str(identity.get("username") or ""),
        "trader_id": str(identity.get("trader_id") or ""),
        "total_records": total_records,
        "sections": sections,
    }
