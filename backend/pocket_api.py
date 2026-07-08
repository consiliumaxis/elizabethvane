from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import re
from typing import Any, Dict, Optional


POCKET_USER_INFO_ENDPOINT_TEMPLATE = "https://pocketpartners.com/api/user-info/{user_id}/{partner_id}/{hash}"
POCKET_REGISTRATION_EVENT = "registration"
POCKET_FTD_EVENT = "ftd"
POCKET_DEPOSIT_EVENT = "dep"
POCKET_ALLOWED_EVENTS = {
    "registration": POCKET_REGISTRATION_EVENT,
    "register": POCKET_REGISTRATION_EVENT,
    "reg": POCKET_REGISTRATION_EVENT,
    "lead": POCKET_REGISTRATION_EVENT,
    "ftd": POCKET_FTD_EVENT,
    "first_deposit": POCKET_FTD_EVENT,
    "firstdeposit": POCKET_FTD_EVENT,
    "first_dep": POCKET_FTD_EVENT,
    "deposit_first": POCKET_FTD_EVENT,
    "dep": POCKET_DEPOSIT_EVENT,
    "deposit": POCKET_DEPOSIT_EVENT,
    "repeat_deposit": POCKET_DEPOSIT_EVENT,
    "repeatdeposit": POCKET_DEPOSIT_EVENT,
    "repeated_deposit": POCKET_DEPOSIT_EVENT,
    "redeposit": POCKET_DEPOSIT_EVENT,
}


def mask_secret(value: str) -> str:
    secret = str(value or "").strip()
    if not secret:
        return ""
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}{'*' * max(len(secret) - 4, 4)}{secret[-2:]}"


def build_pocket_user_info_url(user_id: str, partner_id: str, api_token: str) -> str:
    trader_id = str(user_id or "").strip()
    cabinet_id = str(partner_id or "").strip()
    token = str(api_token or "").strip()
    signature = hashlib.md5(f"{trader_id}:{cabinet_id}:{token}".encode("utf-8")).hexdigest()
    return f"https://pocketpartners.com/api/user-info/{trader_id}/{cabinet_id}/{signature}"


def _normalize_pocket_text(value: Optional[object], max_length: int = 255) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw[:max_length]


def _first_payload_value(payload: Dict[str, Any], *names: str) -> str:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def normalize_pocket_event(value: Optional[object]) -> Optional[str]:
    raw = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if not raw:
        return POCKET_REGISTRATION_EVENT
    return POCKET_ALLOWED_EVENTS.get(raw)


def normalize_pocket_telegram_id(value: Optional[object]) -> Optional[int]:
    raw = str(value or "").strip()
    if not raw or not re.fullmatch(r"\d{3,20}", raw):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def normalize_pocket_amount(value: Optional[object]) -> str:
    raw = str(value if value is not None else "").strip().replace(",", ".")
    if not raw:
        return "0.00"
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        amount = Decimal("0")
    if amount < 0:
        amount = Decimal("0")
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def normalize_pocket_postback_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_slug = normalize_pocket_event(
        _first_payload_value(payload, "event", "event_slug", "type", "status")
    )
    click_id = _normalize_pocket_text(_first_payload_value(payload, "click_id", "clickid", "click"), 128)
    trader_id = _normalize_pocket_text(_first_payload_value(payload, "trader_id", "traderid", "user_id"), 64)
    site_id = _normalize_pocket_text(_first_payload_value(payload, "site_id", "siteid"), 128)
    cid = _normalize_pocket_text(_first_payload_value(payload, "cid", "campaign_id"), 128)
    sub_id1 = _normalize_pocket_text(_first_payload_value(payload, "sub_id1", "subid1", "sub_id"), 255)
    sub_id2 = _normalize_pocket_text(_first_payload_value(payload, "sub_id2", "subid2"), 255)
    deposit_amount = normalize_pocket_amount(
        _first_payload_value(payload, "sumdep", "deposit_amount", "amount", "payout", "sum")
    )
    telegram_id = normalize_pocket_telegram_id(click_id)
    unique_source = trader_id or cid or sub_id2 or sub_id1 or click_id or "unknown"
    if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT}:
        unique_key = _normalize_pocket_text(
            f"{event_slug or 'unknown'}:{click_id or 'unknown'}:{unique_source}:{deposit_amount}",
            191,
        )
    else:
        unique_key = _normalize_pocket_text(f"{event_slug or 'unknown'}:{click_id or 'unknown'}:{unique_source}", 191)

    return {
        "event_slug": event_slug,
        "telegram_id": telegram_id,
        "click_id": click_id,
        "trader_id": trader_id,
        "site_id": site_id,
        "cid": cid,
        "sub_id1": sub_id1,
        "sub_id2": sub_id2,
        "deposit_amount": deposit_amount,
        "unique_key": unique_key,
    }
