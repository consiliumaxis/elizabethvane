from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, Iterable, Mapping


DEFAULT_MIN_DEPOSIT = Decimal("10.00")
DEFAULT_VIP_DEPOSIT = Decimal("30.00")
DEFAULT_COPY_DEPOSIT = Decimal("50.00")

# Starter directory for the GEO selector. Administrators can change every
# threshold and add custom ISO alpha-2 countries later.
POPULAR_DEPOSIT_COUNTRIES = (
    ("US", "United States"),
    ("GB", "United Kingdom"),
    ("UA", "Ukraine"),
    ("RU", "Russia"),
    ("KZ", "Kazakhstan"),
    ("IN", "India"),
    ("BR", "Brazil"),
    ("MX", "Mexico"),
    ("AR", "Argentina"),
    ("CO", "Colombia"),
    ("CL", "Chile"),
    ("PE", "Peru"),
    ("DE", "Germany"),
    ("FR", "France"),
    ("ES", "Spain"),
    ("IT", "Italy"),
    ("PT", "Portugal"),
    ("PL", "Poland"),
    ("RO", "Romania"),
    ("CZ", "Czechia"),
    ("TR", "Türkiye"),
    ("AE", "United Arab Emirates"),
    ("SA", "Saudi Arabia"),
    ("ZA", "South Africa"),
    ("NG", "Nigeria"),
    ("ID", "Indonesia"),
    ("MY", "Malaysia"),
    ("TH", "Thailand"),
    ("VN", "Vietnam"),
    ("PH", "Philippines"),
    ("BD", "Bangladesh"),
    ("PK", "Pakistan"),
)

COUNTRY_CODE_ALIASES = {"UK": "GB"}


def normalize_country_code(value: Any) -> str:
    code = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        return ""
    return COUNTRY_CODE_ALIASES.get(code, code)


def normalize_country_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())
    if not name or len(name) > 100:
        raise ValueError("Country name must contain 1-100 characters")
    return name


def normalize_deposit_amount(value: Any) -> Decimal:
    raw = str(value if value is not None else "").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        raise ValueError("Deposit threshold must be a number")
    if not amount.is_finite() or amount < 0:
        raise ValueError("Deposit threshold cannot be negative")
    return amount.quantize(Decimal("0.01"))


def normalize_deposit_thresholds(
    min_deposit: Any,
    vip_deposit: Any,
    copy_deposit: Any,
) -> Dict[str, Decimal]:
    minimum = normalize_deposit_amount(min_deposit)
    vip = normalize_deposit_amount(vip_deposit)
    copy = normalize_deposit_amount(copy_deposit)
    if vip < minimum:
        raise ValueError("VIP threshold cannot be lower than the minimum deposit")
    if copy < vip:
        raise ValueError("Copy threshold cannot be lower than the VIP threshold")
    return {
        "min_deposit_amount": minimum,
        "vip_deposit_amount": vip,
        "copy_deposit_amount": copy,
    }


def serialize_deposit_thresholds(values: Mapping[str, Any]) -> Dict[str, str]:
    normalized = normalize_deposit_thresholds(
        values.get("min_deposit_amount", DEFAULT_MIN_DEPOSIT),
        values.get("vip_deposit_amount", DEFAULT_VIP_DEPOSIT),
        values.get("copy_deposit_amount", DEFAULT_COPY_DEPOSIT),
    )
    return {key: str(value) for key, value in normalized.items()}


def normalize_country_rule(
    value: Mapping[str, Any],
    *,
    is_custom: bool | None = None,
) -> Dict[str, Any]:
    country_code = normalize_country_code(value.get("country_code"))
    if not country_code:
        raise ValueError("Country code must be ISO alpha-2")
    thresholds = normalize_deposit_thresholds(
        value.get("min_deposit_amount"),
        value.get("vip_deposit_amount"),
        value.get("copy_deposit_amount"),
    )
    return {
        "country_code": country_code,
        "country_name": normalize_country_name(value.get("country_name")),
        **thresholds,
        "is_custom": bool(value.get("is_custom")) if is_custom is None else bool(is_custom),
    }


def resolve_deposit_thresholds(
    defaults: Mapping[str, Any],
    country_rules: Iterable[Mapping[str, Any]],
    aio_country_code: Any,
) -> Dict[str, Any]:
    fallback = serialize_deposit_thresholds(defaults)
    requested_code = normalize_country_code(aio_country_code)
    for raw_rule in country_rules or ():
        if not requested_code or normalize_country_code(raw_rule.get("country_code")) != requested_code:
            continue
        rule = normalize_country_rule(raw_rule)
        return {
            "country_code": requested_code,
            "country_name": rule["country_name"],
            "source": "country",
            **serialize_deposit_thresholds(rule),
        }
    return {
        "country_code": requested_code,
        "country_name": "",
        "source": "default",
        **fallback,
    }


def calculate_deposit_access(
    thresholds: Mapping[str, Any],
    deposit_amount: Any,
    *,
    registered: Any = False,
    deposited: Any = False,
) -> Dict[str, Any]:
    normalized = serialize_deposit_thresholds(thresholds)
    try:
        total = normalize_deposit_amount(deposit_amount)
    except ValueError:
        total = Decimal("0.00")
    confirmed = bool(int(registered or 0)) and bool(int(deposited or 0))
    minimum = Decimal(normalized["min_deposit_amount"])
    vip = Decimal(normalized["vip_deposit_amount"])
    copy = Decimal(normalized["copy_deposit_amount"])
    return {
        **normalized,
        "deposit_amount": str(total),
        "deposit_access": 1 if confirmed and total >= minimum else 0,
        "vip_access": 1 if confirmed and total >= vip else 0,
        "copy_access": 1 if confirmed and total >= copy else 0,
        "shortage": str(max(Decimal("0.00"), minimum - total)),
        "vip_shortage": str(max(Decimal("0.00"), vip - total)),
        "copy_shortage": str(max(Decimal("0.00"), copy - total)),
    }
