import re
from typing import Any, Dict, Optional


CHATTERFY_START_EVENT = "start_chatterfy"
CHATTERFY_BOT_START_EVENT = "start_bot_chatterfy"
CHATTERFY_CHANNEL_SUBSCRIBE_EVENT = "channel_subscribe"
CHATTERFY_ALLOWED_EVENTS = {
    "start": CHATTERFY_START_EVENT,
    "bot_start": CHATTERFY_START_EVENT,
    "dialog": CHATTERFY_START_EVENT,
    "start_chatterfy": CHATTERFY_START_EVENT,
    "start_bot_chatterfy": CHATTERFY_BOT_START_EVENT,
    "subscribe": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "subscription": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "channel_subscribe": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "channel_subscription": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "subscribe_channel": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "request_subscribe_channel": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "subscribe_telegram_channel": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    "join_request_telegram_channel": CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
}


def normalize_chatterfy_event(value: Optional[object]) -> Optional[str]:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not raw:
        return CHATTERFY_START_EVENT
    return CHATTERFY_ALLOWED_EVENTS.get(raw)


def normalize_telegram_id(value: Optional[object]) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw or not re.fullmatch(r"\d{3,20}", raw):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def normalize_chatterfy_text(value: Optional[object], max_length: int = 255) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw[:max_length]


def first_payload_value(payload: Dict[str, Any], *names: str) -> str:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_chatterfy_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_slug = normalize_chatterfy_event(
        first_payload_value(payload, "event", "event_slug", "conversion", "conversion_type", "type")
    )
    telegram_id = normalize_telegram_id(
        first_payload_value(payload, "tgid", "tg_id", "telegram_id", "telegram_user_id", "user_id")
    )
    chatterfy_id = normalize_chatterfy_text(
        first_payload_value(payload, "chatterfy_id", "chat_id", "contact_id", "subscriber_id", "dialog_id"),
        max_length=128,
    )
    tg_username = normalize_chatterfy_text(
        first_payload_value(payload, "tg_username", "username", "telegram_username"),
        max_length=255,
    ).lstrip("@")
    tg_first_name = normalize_chatterfy_text(
        first_payload_value(payload, "tg_first_name", "first_name", "telegram_first_name", "name"),
        max_length=255,
    )
    unique_source = chatterfy_id or first_payload_value(payload, "unique", "uuid", "event_id") or str(telegram_id or "")
    unique_key = normalize_chatterfy_text(f"{event_slug or 'unknown'}:{telegram_id or 'unknown'}:{unique_source}", 191)
    return {
        "event_slug": event_slug,
        "telegram_id": telegram_id,
        "tg_username": tg_username,
        "tg_first_name": tg_first_name,
        "chatterfy_id": chatterfy_id,
        "unique_key": unique_key,
    }
