import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional
from urllib.parse import urlencode, urlsplit


CHATTERFY_POCKET_POSTBACK_BASE_URL = (os.getenv("CHATTERFY_POCKET_POSTBACK_BASE_URL") or "").strip()
CHATTERFY_BOT_POCKET_POSTBACK_BASE_URL = (
    os.getenv("CHATTERFY_BOT_POCKET_POSTBACK_BASE_URL")
    or "https://api.chatterfy.ai/api/postbacks/01a00f6f-d580-77f4-8df1-646adad11d0f/bot-postback"
).strip().rstrip("?")

CHATTERFY_BOT_POCKET_STEP_IDS = {
    "registration": (
        os.getenv("CHATTERFY_BOT_REGISTRATION_STEP_ID")
        or "01a006d7-5a3d-7dba-8e44-b31c8d0bbb20"
    ).strip(),
    "dep": (
        os.getenv("CHATTERFY_BOT_DEPOSIT_STEP_ID")
        or "01a006d7-5a71-7c1c-8997-8694739020c2"
    ).strip(),
    "ftd": (
        os.getenv("CHATTERFY_BOT_FTD_STEP_ID")
        or "01a006d7-5a6f-7315-bd36-6db8c5ca29a7"
    ).strip(),
}

CHATTERFY_BOT_POCKET_STEP_ENV_NAMES = {
    "registration": "CHATTERFY_BOT_REGISTRATION_STEP_ID",
    "ftd": "CHATTERFY_BOT_FTD_STEP_ID",
    "dep": "CHATTERFY_BOT_DEPOSIT_STEP_ID",
}

CHATTERFY_POCKET_EVENT_SLUGS = {
    "registration": "registration",
    "ftd": "sale",
    "dep": "resale",
}


def _normalize_revenue(value: Optional[object]) -> str:
    raw = str(value if value is not None else "").strip().replace(",", ".")
    if not raw:
        return ""
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        amount = Decimal("0")
    if amount < 0:
        amount = Decimal("0")
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _base_url() -> str:
    value = (os.getenv("CHATTERFY_POCKET_POSTBACK_BASE_URL") or CHATTERFY_POCKET_POSTBACK_BASE_URL or "").strip()
    if not value:
        raise ValueError("CHATTERFY_POCKET_POSTBACK_BASE_URL is not configured")
    return value


def build_chatterfy_pocket_postback_url(
    *,
    event_slug: str,
    clickid: str,
    trader_id: str,
    trader_aio_id: str,
    tgid: object,
    revenue: Optional[object] = None,
    unique_key: Optional[str] = None,
) -> str:
    chatterfy_event = CHATTERFY_POCKET_EVENT_SLUGS.get(str(event_slug or "").strip())
    if not chatterfy_event:
        raise ValueError("Unsupported Chatterfy Pocket event")

    params = {
        "tracker.event": chatterfy_event,
        "clickid": str(clickid or "").strip(),
    }
    normalized_revenue = _normalize_revenue(revenue)
    if normalized_revenue:
        params["tracker.cost"] = normalized_revenue
        params["tracker.currency"] = "usd"
    normalized_unique_key = str(unique_key or "").strip()
    if normalized_unique_key:
        params["tracker.tid"] = normalized_unique_key
    params.update(
        {
            "fields.trader_id": str(trader_id or "").strip(),
            "fields.trader_aio_id": str(trader_aio_id or "").strip(),
            "fields.tgid": str(tgid if tgid is not None else "").strip(),
        }
    )
    return f"{_base_url()}?{urlencode(params)}"


def build_chatterfy_bot_pocket_postback_url(*, event_slug: str, tgid: object) -> str:
    normalized_event_slug = str(event_slug or "").strip().lower()
    step_env_name = CHATTERFY_BOT_POCKET_STEP_ENV_NAMES.get(normalized_event_slug)
    if not step_env_name:
        raise ValueError("Unsupported Chatterfy bot Pocket event")
    step_id = str(
        os.getenv(step_env_name)
        or CHATTERFY_BOT_POCKET_STEP_IDS.get(normalized_event_slug)
        or ""
    ).strip()
    if not step_id:
        raise ValueError("Unsupported Chatterfy bot Pocket event")

    telegram_id = str(tgid if tgid is not None else "").strip()
    if not re.fullmatch(r"\d{3,20}", telegram_id):
        raise ValueError("Valid Telegram chat ID is required")

    base_url = (
        os.getenv("CHATTERFY_BOT_POCKET_POSTBACK_BASE_URL")
        or CHATTERFY_BOT_POCKET_POSTBACK_BASE_URL
        or ""
    ).strip().rstrip("?")
    parsed_url = urlsplit(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("Invalid Chatterfy bot Pocket postback URL")

    return f"{base_url}?{urlencode({'chat_id': telegram_id, 'step_id': step_id, 'status': 'auto'})}"
