import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional
from urllib.parse import urlencode


AIO_VISIT_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
AIO_EVENT_SLUG_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,63}$")
AIO_POSTBACK_BASE_URL = (os.getenv("AIO_POSTBACK_BASE_URL") or "https://app.aio.tech/api/v1/trigger/conversion-request").strip()
AIO_FIELD_TRIGGER_BASE_URL = (os.getenv("AIO_FIELD_TRIGGER_BASE_URL") or "https://app.aio.tech/api/v1/trigger/field").strip()
AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID = (os.getenv("AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID") or "").strip()
AIO_POCKET_FTD_CONVERSION_TYPE_UUID = (os.getenv("AIO_POCKET_FTD_CONVERSION_TYPE_UUID") or "").strip()
AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID = (os.getenv("AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID") or "").strip()
AIO_USER_FIELD_NAMES = frozenset(
    {
        "tg_first_name",
        "tg_username",
        "tgid",
        "tg_trader_id",
        "tg_first_dep",
        "tg_sum_dep",
    }
    | {f"tg_question{index}" for index in range(1, 11)}
)


def normalize_aio_visit_uuid(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not AIO_VISIT_UUID_RE.fullmatch(raw):
        return None
    return raw.lower()


def extract_aio_visit_uuid_from_start_text(text: Optional[str]) -> Optional[str]:
    raw = str(text or "").strip()
    if not raw:
        return None
    parts = raw.split(maxsplit=1)
    if parts and parts[0].lower().startswith("/start"):
        payload = parts[1] if len(parts) > 1 else ""
    else:
        payload = raw
    return normalize_aio_visit_uuid(payload)


def normalize_aio_event_slug(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip().lower().replace(" ", "_")
    if not raw:
        return None
    if not AIO_EVENT_SLUG_RE.fullmatch(raw):
        return None
    return raw


def normalize_aio_revenue(value: Optional[object]) -> str:
    raw = str(value if value is not None else "0").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        amount = Decimal("0")
    if amount < 0:
        amount = Decimal("0")
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _configured_uuid(env_name: str, default_value: str) -> str:
    value = (os.getenv(env_name) or default_value or "").strip()
    if not normalize_aio_visit_uuid(value):
        raise ValueError(f"{env_name} is not configured")
    return value.lower()


def build_aio_postback_url(
    aio_visit_uuid: str,
    event_slug: str,
    revenue: Optional[object] = None,
    currency: Optional[str] = None,
    unique_key: Optional[str] = None,
) -> str:
    visit_uuid = normalize_aio_visit_uuid(aio_visit_uuid)
    normalized_event_slug = normalize_aio_event_slug(event_slug)
    if not visit_uuid:
        raise ValueError("AIO visit UUID is invalid")
    if not normalized_event_slug:
        raise ValueError("AIO event slug is invalid")

    params = {
        "visit_uuid": visit_uuid,
        "conversion_type_uuid": normalized_event_slug,
        "arrived_revenue": normalize_aio_revenue(revenue),
    }
    normalized_currency = str(currency or "").strip().upper()
    if normalized_currency:
        params["currency"] = normalized_currency
    normalized_unique_key = str(unique_key or "").strip()
    if normalized_unique_key:
        params["unique"] = normalized_unique_key
    return f"{AIO_POSTBACK_BASE_URL}?{urlencode(params)}"


def build_aio_pocket_registration_conversion_url(aio_visit_uuid: str, tgid: object, tg_trader_id: object) -> str:
    visit_uuid = normalize_aio_visit_uuid(aio_visit_uuid)
    if not visit_uuid:
        raise ValueError("AIO visit UUID is invalid")

    query = urlencode(
        {
            "visit_uuid": visit_uuid,
            "conversion_type_uuid": _configured_uuid(
                "AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID",
                AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID,
            ),
            "tgid": str(tgid if tgid is not None else "").strip(),
            "tg_trader_id": str(tg_trader_id if tg_trader_id is not None else "").strip(),
        }
    )
    return f"{AIO_POSTBACK_BASE_URL}?{query}"


def _build_aio_pocket_revenue_conversion_url(
    aio_visit_uuid: str,
    conversion_env_name: str,
    conversion_default: str,
    revenue: object,
    tgid: object,
    tg_trader_id: object,
) -> str:
    visit_uuid = normalize_aio_visit_uuid(aio_visit_uuid)
    if not visit_uuid:
        raise ValueError("AIO visit UUID is invalid")
    query = urlencode(
        {
            "visit_uuid": visit_uuid,
            "conversion_type_uuid": _configured_uuid(conversion_env_name, conversion_default),
            "arrived_revenue": normalize_aio_revenue(revenue),
            "tgid": str(tgid if tgid is not None else "").strip(),
            "tg_trader_id": str(tg_trader_id if tg_trader_id is not None else "").strip(),
        }
    )
    return f"{AIO_POSTBACK_BASE_URL}?{query}"


def build_aio_pocket_ftd_conversion_url(aio_visit_uuid: str, revenue: object, tgid: object, tg_trader_id: object) -> str:
    return _build_aio_pocket_revenue_conversion_url(
        aio_visit_uuid,
        "AIO_POCKET_FTD_CONVERSION_TYPE_UUID",
        AIO_POCKET_FTD_CONVERSION_TYPE_UUID,
        revenue,
        tgid,
        tg_trader_id,
    )


def build_aio_pocket_deposit_conversion_url(aio_visit_uuid: str, revenue: object, tgid: object, tg_trader_id: object) -> str:
    return _build_aio_pocket_revenue_conversion_url(
        aio_visit_uuid,
        "AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID",
        AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID,
        revenue,
        tgid,
        tg_trader_id,
    )


def build_aio_field_trigger_url(aio_visit_uuid: str, field_name: str, field_value: object) -> str:
    visit_uuid = normalize_aio_visit_uuid(aio_visit_uuid)
    normalized_field_name = str(field_name or "").strip()
    if not visit_uuid:
        raise ValueError("AIO visit UUID is invalid")
    if normalized_field_name not in AIO_USER_FIELD_NAMES:
        raise ValueError("AIO field name is invalid")

    return (
        f"{AIO_FIELD_TRIGGER_BASE_URL}/{visit_uuid}/"
        f"?{urlencode({normalized_field_name: str(field_value if field_value is not None else '')})}"
    )
