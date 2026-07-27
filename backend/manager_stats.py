import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple


STAFF_ROLE_MANAGER = "manager"
STAFF_ROLE_ADMIN = "admin"
STAFF_ROLES = (STAFF_ROLE_MANAGER, STAFF_ROLE_ADMIN)
MANAGER_STATS_AUDIT_STATUSES = (
    "success",
    "not_found",
    "invalid_query",
    "denied",
    "private_chat_required",
)

_STATS_COMMAND_RE = re.compile(
    r"^/stats(?:@[A-Za-z0-9_]+)?(?:\s+(?P<target>\S+))?\s*$",
    re.IGNORECASE,
)
_TELEGRAM_USERNAME_RE = re.compile(r"^@[A-Za-z0-9_]{3,64}$")
_TELEGRAM_ID_RE = re.compile(r"^[1-9]\d{2,19}$")

_COUNTRY_NAMES_EN = {
    "AE": "United Arab Emirates",
    "AR": "Argentina",
    "AZ": "Azerbaijan",
    "BD": "Bangladesh",
    "BR": "Brazil",
    "BY": "Belarus",
    "CL": "Chile",
    "CN": "China",
    "CO": "Colombia",
    "DE": "Germany",
    "DZ": "Algeria",
    "EG": "Egypt",
    "ES": "Spain",
    "FR": "France",
    "GB": "United Kingdom",
    "GE": "Georgia",
    "GH": "Ghana",
    "ID": "Indonesia",
    "IN": "India",
    "IT": "Italy",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KZ": "Kazakhstan",
    "LK": "Sri Lanka",
    "MA": "Morocco",
    "MX": "Mexico",
    "MY": "Malaysia",
    "NG": "Nigeria",
    "NP": "Nepal",
    "PE": "Peru",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RU": "Russia",
    "SA": "Saudi Arabia",
    "TH": "Thailand",
    "TR": "Turkey",
    "UA": "Ukraine",
    "US": "United States",
    "UZ": "Uzbekistan",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "ZA": "South Africa",
}


def normalize_staff_role(value: Any, default: str = STAFF_ROLE_MANAGER) -> str:
    role = str(value or "").strip().lower()
    return role if role in STAFF_ROLES else default


def parse_stats_target(message_text: Any) -> Tuple[Optional[str], Optional[Any]]:
    match = _STATS_COMMAND_RE.fullmatch(str(message_text or "").strip())
    if not match:
        return None, None
    target = str(match.group("target") or "").strip()
    if _TELEGRAM_ID_RE.fullmatch(target):
        return "id", int(target)
    if _TELEGRAM_USERNAME_RE.fullmatch(target):
        return "username", target[1:].lower()
    return None, None


def calculate_winrate(wins: Any, losses: Any) -> Optional[float]:
    try:
        wins_count = max(0, int(wins or 0))
        losses_count = max(0, int(losses or 0))
    except (TypeError, ValueError):
        return None
    closed_count = wins_count + losses_count
    if closed_count <= 0:
        return None
    return round((wins_count / closed_count) * 100, 1)


def display_country(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Not specified"
    return _COUNTRY_NAMES_EN.get(raw.upper(), raw)


def _money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        amount = Decimal("0")
    return max(amount, Decimal("0")).quantize(Decimal("0.01"))


def _date_text(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%d.%m.%Y")
    except ValueError:
        return raw[:10]


def _trade_word(count: int) -> str:
    return "trade" if abs(int(count)) == 1 else "trades"


def format_manager_stats(summary: Dict[str, Any]) -> str:
    user_id = int(summary.get("user_id") or 0)
    username = str(summary.get("username") or "").strip().lstrip("@")
    first_name = str(summary.get("first_name") or "").strip()
    client_name = f"@{username}" if username else (first_name or "no username")

    deposit_amount = _money(summary.get("deposit_amount"))
    deposit_date = _date_text(summary.get("first_deposit_at"))
    if deposit_amount > 0:
        deposit_line = f"{deposit_amount:.2f} USD"
        if deposit_date:
            deposit_line += f" ({deposit_date})"
    else:
        deposit_line = "Not recorded"

    wins_total = int(summary.get("wins_total") or 0)
    losses_total = int(summary.get("losses_total") or 0)
    wins_7d = int(summary.get("wins_7d") or 0)
    losses_7d = int(summary.get("losses_7d") or 0)
    closed_total = wins_total + losses_total
    closed_7d = wins_7d + losses_7d
    winrate_total = calculate_winrate(wins_total, losses_total)
    winrate_7d = calculate_winrate(wins_7d, losses_7d)

    return "\n".join(
        [
            f"Client: {client_name} (ID {user_id})",
            f"Country: {display_country(summary.get('country'))}",
            f"Deposit: {deposit_line}",
            f"Total trades: {closed_total}",
            f"Winrate: {f'{winrate_total:.1f}%' if winrate_total is not None else '—'}",
            (
                f"Last 7 days: {closed_7d} {_trade_word(closed_7d)}, "
                f"winrate {f'{winrate_7d:.1f}%' if winrate_7d is not None else '—'}"
            ),
        ]
    )
