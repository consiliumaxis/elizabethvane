import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional
from urllib.parse import urlencode


CHATTERFY_POCKET_POSTBACK_BASE_URL = (os.getenv("CHATTERFY_POCKET_POSTBACK_BASE_URL") or "").strip()

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
