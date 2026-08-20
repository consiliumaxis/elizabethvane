import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Mapping, Optional
from urllib.parse import urlencode


AIO_VISIT_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
AIO_EVENT_SLUG_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,63}$")
AIO_POSTBACK_BASE_URL = (os.getenv("AIO_POSTBACK_BASE_URL") or "https://app.aio.tech/api/v1/trigger/conversion-request").strip()
AIO_CONVERSION_BASE_URL = (
    os.getenv("AIO_CONVERSION_BASE_URL")
    or "https://app.aio.tech/api/v1/trigger/conversion"
).strip().rstrip("/")
AIO_FIELD_TRIGGER_BASE_URL = (os.getenv("AIO_FIELD_TRIGGER_BASE_URL") or "https://app.aio.tech/api/v1/trigger/field").strip()
AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID = (os.getenv("AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID") or "").strip()
AIO_POCKET_FTD_CONVERSION_TYPE_UUID = (os.getenv("AIO_POCKET_FTD_CONVERSION_TYPE_UUID") or "").strip()
AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID = (os.getenv("AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID") or "").strip()
AIO_CHATTERFY_START_CONVERSION_TYPE_UUID = (
    os.getenv("AIO_CHATTERFY_START_CONVERSION_TYPE_UUID")
    or "a39ea9ab-20ec-4628-8f19-ee8dcd6d25b9"
).strip()
AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID = (
    os.getenv("AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID")
    or "f84ed98b-0882-422a-b0ca-bd89c0b2561d"
).strip()
AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID = (
    os.getenv("AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID")
    or "0a74b0c3-1c23-45d3-828e-9a910043e4a4"
).strip()
AIO_COPY_HOT_DOWN_CONVERSION_TYPE_UUID = (
    os.getenv("AIO_COPY_HOT_DOWN_CONVERSION_TYPE_UUID")
    or "b922aaf1-6ffa-4b2e-a859-e5aecb4cde6f"
).strip()
AIO_VIP_UPGRADE_CONVERSION_TYPE_UUID = (
    os.getenv("AIO_VIP_UPGRADE_CONVERSION_TYPE_UUID")
    or "187edcc0-9508-4ce0-96eb-5f390787f568"
).strip()
AIO_GEO_CONVERSION_TYPE_UUID = (
    os.getenv("AIO_GEO_CONVERSION_TYPE_UUID")
    or "0141c6c0-2772-484f-b808-9419b8c930e8"
).strip().lower()
AIO_USER_FIELD_NAMES = frozenset(
    {
        "tg_first_name",
        "tg_username",
        "tgid",
        "tg_trader_id",
        "tg_first_dep",
        "tg_sum_dep",
        "tg_dep_ok",
        "tg_vip",
        "tg_copy",
    }
    | {f"tg_question{index}" for index in range(1, 11)}
)
AIO_INITIAL_ONLY_PROFILE_STATUS_FIELDS = ("tg_vip", "tg_copy")


def normalize_aio_visit_uuid(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if not AIO_VISIT_UUID_RE.fullmatch(raw):
        return None
    return raw.lower()


def is_unresolved_aio_visit_uuid_placeholder(value: Optional[object]) -> bool:
    """Return True for an unresolved Chatterfy ``start0`` template value."""
    raw = str(value or "").strip()
    if not raw:
        return False
    return bool(re.fullmatch(r"\{+\s*start0\s*\}+", raw, re.IGNORECASE)) or raw.lower() == "start0"


def normalize_aio_country_code(value: Optional[object]) -> Optional[str]:
    raw = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", raw):
        return None
    return raw


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


def _normalize_binary_status(value: object) -> int:
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes", "on"} else 0
    return 1 if bool(value) else 0


def select_aio_profile_status_fields(
    deposit_access_enabled: object,
    synced_values: Mapping[str, object],
    visit_changed: bool = False,
) -> dict[str, int]:
    """Return profile fields that may be synchronized automatically.

    Deposit access keeps following the active access rule. VIP and Copy are
    deliberately initialized to zero only; their future positive states will
    be delivered by a separate integration flow instead of deposit thresholds.
    """
    normalized_synced_values = dict(synced_values or {})
    desired_deposit_access = _normalize_binary_status(deposit_access_enabled)
    fields_to_send: dict[str, int] = {}

    synced_deposit_access = normalized_synced_values.get("tg_dep_ok")
    if (
        visit_changed
        or synced_deposit_access is None
        or _normalize_binary_status(synced_deposit_access) != desired_deposit_access
    ):
        fields_to_send["tg_dep_ok"] = desired_deposit_access

    for field_name in AIO_INITIAL_ONLY_PROFILE_STATUS_FIELDS:
        if visit_changed or normalized_synced_values.get(field_name) is None:
            fields_to_send[field_name] = 0

    return fields_to_send


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

    direct_conversion_config = {
        "channel_subscribe": (
            "AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID",
            AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID,
        ),
        "copy_hot_down": (
            "AIO_COPY_HOT_DOWN_CONVERSION_TYPE_UUID",
            AIO_COPY_HOT_DOWN_CONVERSION_TYPE_UUID,
        ),
        "vip_upgrade": (
            "AIO_VIP_UPGRADE_CONVERSION_TYPE_UUID",
            AIO_VIP_UPGRADE_CONVERSION_TYPE_UUID,
        ),
    }
    if normalized_event_slug in direct_conversion_config:
        env_name, default_uuid = direct_conversion_config[normalized_event_slug]
        conversion_type_uuid = _configured_uuid(env_name, default_uuid)
        normalized_currency = str(currency or "usd").strip().lower() or "usd"
        query = urlencode(
            {
                "arrived_revenue": normalize_aio_revenue(revenue),
                "currency": normalized_currency,
            }
        )
        return (
            f"{AIO_CONVERSION_BASE_URL}/{visit_uuid}/{conversion_type_uuid}"
            f"?{query}"
        )

    conversion_type_uuid = normalized_event_slug
    if normalized_event_slug == "start_chatterfy":
        conversion_type_uuid = _configured_uuid(
            "AIO_CHATTERFY_START_CONVERSION_TYPE_UUID",
            AIO_CHATTERFY_START_CONVERSION_TYPE_UUID,
        )
    elif normalized_event_slug == "start_bot_chatterfy":
        conversion_type_uuid = _configured_uuid(
            "AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID",
            AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID,
        )

    params = {
        "visit_uuid": visit_uuid,
        "conversion_type_uuid": conversion_type_uuid,
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


def build_aio_fields_trigger_url(
    aio_visit_uuid: str,
    fields: Mapping[str, object],
) -> str:
    visit_uuid = normalize_aio_visit_uuid(aio_visit_uuid)
    if not visit_uuid:
        raise ValueError("AIO visit UUID is invalid")

    normalized_fields = {}
    for field_name, field_value in dict(fields or {}).items():
        normalized_field_name = str(field_name or "").strip()
        if normalized_field_name not in AIO_USER_FIELD_NAMES:
            raise ValueError("AIO field name is invalid")
        normalized_fields[normalized_field_name] = str(
            field_value if field_value is not None else ""
        )
    if not normalized_fields:
        raise ValueError("At least one AIO field is required")

    return (
        f"{AIO_FIELD_TRIGGER_BASE_URL}/{visit_uuid}/"
        f"?{urlencode(normalized_fields)}"
    )


def build_aio_field_trigger_url(aio_visit_uuid: str, field_name: str, field_value: object) -> str:
    return build_aio_fields_trigger_url(
        aio_visit_uuid,
        {field_name: field_value},
    )

