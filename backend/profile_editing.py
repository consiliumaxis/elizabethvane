import re
from typing import Any


PROFILE_NAME_MAX_LENGTH = 80
PROFILE_TRADER_ID_MAX_LENGTH = 64
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_profile_name(value: Any) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if not normalized:
        raise ValueError("Name cannot be empty")
    if _CONTROL_CHARACTERS.search(normalized):
        raise ValueError("Name contains unsupported characters")
    if len(normalized) > PROFILE_NAME_MAX_LENGTH:
        raise ValueError(f"Name must be no longer than {PROFILE_NAME_MAX_LENGTH} characters")
    return normalized


def normalize_profile_trader_id(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("Trader ID cannot be empty")
    if _CONTROL_CHARACTERS.search(normalized):
        raise ValueError("Trader ID contains unsupported characters")
    if len(normalized) > PROFILE_TRADER_ID_MAX_LENGTH:
        raise ValueError(
            f"Trader ID must be no longer than {PROFILE_TRADER_ID_MAX_LENGTH} characters"
        )
    return normalized


def effective_profile_name(
    profile_name: Any,
    telegram_first_name: Any,
    telegram_username: Any = "",
) -> str:
    return (
        str(profile_name or "").strip()
        or str(telegram_first_name or "").strip()
        or str(telegram_username or "").strip().lstrip("@")
    )


def effective_profile_trader_id(manual_trader_id: Any, pocket_trader_id: Any) -> str:
    return str(manual_trader_id or "").strip() or str(pocket_trader_id or "").strip()


def has_manual_profile_trader_id(value: Any) -> bool:
    return bool(str(value or "").strip())
