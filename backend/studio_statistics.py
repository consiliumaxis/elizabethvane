import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple


MAX_STUDIO_RANGE_DAYS = 3660


def parse_iso_date(value: Any, field_name: str = "date") -> date:
    raw = str(value or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format") from exc


def normalize_date_range(
    date_from: Any = None,
    date_to: Any = None,
    *,
    today: Optional[date] = None,
) -> Tuple[date, date]:
    end = parse_iso_date(date_to, "date_to") if date_to else (today or date.today())
    start = parse_iso_date(date_from, "date_from") if date_from else end - timedelta(days=6)
    if start > end:
        start, end = end, start
    if (end - start).days + 1 > MAX_STUDIO_RANGE_DAYS:
        raise ValueError(f"Date range cannot exceed {MAX_STUDIO_RANGE_DAYS} days")
    return start, end


def normalize_nonnegative_int(value: Any, field_name: str) -> int:
    try:
        normalized = int(str(value if value is not None else "0").strip() or "0")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return normalized


def normalize_nonnegative_decimal(value: Any, field_name: str = "volume") -> Decimal:
    raw = str(value if value is not None else "0").strip().replace(",", ".") or "0"
    try:
        normalized = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if normalized < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return normalized.quantize(Decimal("0.01"))


def normalize_strategy_winrates(value: Any) -> List[Dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for item in rows[:200]:
        if not isinstance(item, dict):
            continue
        try:
            strategy_id = int(item.get("strategy_id") or 0)
        except (TypeError, ValueError):
            strategy_id = 0
        strategy_name = str(item.get("strategy_name") or "").strip()[:255]
        key = str(strategy_id) if strategy_id > 0 else strategy_name.lower()
        if not key or key in seen:
            continue
        raw_winrate = item.get("winrate")
        if raw_winrate in (None, ""):
            continue
        try:
            winrate = round(float(str(raw_winrate).replace(",", ".")), 2)
        except (TypeError, ValueError) as exc:
            raise ValueError("Strategy winrate must be a number") from exc
        if winrate < 0 or winrate > 100:
            raise ValueError("Strategy winrate must be between 0 and 100")
        seen.add(key)
        normalized.append(
            {
                "strategy_id": strategy_id or None,
                "strategy_name": strategy_name or f"Strategy {strategy_id}",
                "winrate": winrate,
            }
        )
    return normalized


def decode_strategy_winrates(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            value = []
    return normalize_strategy_winrates(value)


def normalize_daily_stat(payload: Dict[str, Any]) -> Dict[str, Any]:
    stat_date = parse_iso_date(payload.get("date"), "date")
    total_users_raw = payload.get("total_users")
    total_users = (
        None
        if total_users_raw in (None, "")
        else normalize_nonnegative_int(total_users_raw, "total_users")
    )
    return {
        "date": stat_date,
        "new_users": normalize_nonnegative_int(payload.get("new_users"), "new_users"),
        "total_users": total_users,
        "deals": normalize_nonnegative_int(payload.get("deals"), "deals"),
        "volume": normalize_nonnegative_decimal(payload.get("volume"), "volume"),
        "strategy_winrates": normalize_strategy_winrates(payload.get("strategy_winrates")),
    }


def aggregate_studio_statistics(
    rows: Iterable[Dict[str, Any]],
    *,
    cumulative_total_users: Optional[int] = None,
) -> Dict[str, Any]:
    normalized_rows = list(rows or [])
    new_users = 0
    deals = 0
    volume = Decimal("0.00")
    latest_total_users = None
    latest_total_date = None
    strategy_values: Dict[str, Dict[str, Any]] = {}

    for row in normalized_rows:
        new_users += normalize_nonnegative_int(row.get("new_users"), "new_users")
        deals += normalize_nonnegative_int(row.get("deals"), "deals")
        volume += normalize_nonnegative_decimal(row.get("volume"), "volume")

        row_date = row.get("stat_date") or row.get("date")
        total_users = row.get("total_users")
        if total_users not in (None, ""):
            parsed_total = normalize_nonnegative_int(total_users, "total_users")
            if latest_total_date is None or str(row_date) >= str(latest_total_date):
                latest_total_date = row_date
                latest_total_users = parsed_total

        for item in decode_strategy_winrates(row.get("strategy_winrates")):
            key = (
                f"id:{item['strategy_id']}"
                if item.get("strategy_id")
                else f"name:{item['strategy_name'].lower()}"
            )
            bucket = strategy_values.setdefault(
                key,
                {
                    "strategy_id": item.get("strategy_id"),
                    "strategy_name": item["strategy_name"],
                    "sum": 0.0,
                    "days": 0,
                },
            )
            bucket["sum"] += float(item["winrate"])
            bucket["days"] += 1
            if item.get("strategy_name"):
                bucket["strategy_name"] = item["strategy_name"]

    if latest_total_users is None:
        latest_total_users = max(0, int(cumulative_total_users or new_users))

    strategies = [
        {
            "strategy_id": item["strategy_id"],
            "strategy_name": item["strategy_name"],
            "winrate": round(item["sum"] / item["days"], 2),
            "days": item["days"],
        }
        for item in strategy_values.values()
        if item["days"] > 0
    ]
    strategies.sort(key=lambda item: (-float(item["winrate"]), item["strategy_name"].lower()))

    return {
        "new_users": new_users,
        "total_users": latest_total_users,
        "deals": deals,
        "volume": f"{volume.quantize(Decimal('0.01')):.2f}",
        "strategy_winrates": strategies,
        "days_with_data": len(normalized_rows),
    }
