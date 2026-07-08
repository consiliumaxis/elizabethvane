from decimal import Decimal, InvalidOperation
from typing import Any, Dict


ACCESS_POLICY_REGISTRATION = "registration"
ACCESS_POLICY_REGISTRATION_DEPOSIT = "registration_deposit"
ACCESS_POLICY_ALL = "all"
ACCESS_POLICIES = {
    ACCESS_POLICY_REGISTRATION,
    ACCESS_POLICY_REGISTRATION_DEPOSIT,
    ACCESS_POLICY_ALL,
}


def normalize_access_policy(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"registered", "after_registration"}:
        return ACCESS_POLICY_REGISTRATION
    if raw in {"deposit", "after_deposit", "registration_and_deposit", "registered_deposit"}:
        return ACCESS_POLICY_REGISTRATION_DEPOSIT
    if raw in {"open", "everyone", "public"}:
        return ACCESS_POLICY_ALL
    if raw in ACCESS_POLICIES:
        return raw
    return ACCESS_POLICY_REGISTRATION_DEPOSIT


def normalize_min_deposit(value: Any) -> Decimal:
    raw = str(value if value is not None else "").strip().replace(",", ".")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, ValueError):
        amount = Decimal("0")
    if amount < 0:
        amount = Decimal("0")
    return amount.quantize(Decimal("0.01"))


def system_policy_grants_signal_access(settings: Dict[str, Any], user_row: Dict[str, Any]) -> bool:
    policy = normalize_access_policy((settings or {}).get("policy"))
    if policy == ACCESS_POLICY_ALL:
        return True

    registered = int((user_row or {}).get("pocket_registered") or 0) == 1
    if policy == ACCESS_POLICY_REGISTRATION:
        return registered

    deposited = int((user_row or {}).get("pocket_deposited") or 0) == 1
    deposit_amount = normalize_min_deposit((user_row or {}).get("pocket_deposit_amount"))
    min_deposit = normalize_min_deposit((settings or {}).get("min_deposit_amount"))
    return registered and deposited and deposit_amount >= min_deposit
