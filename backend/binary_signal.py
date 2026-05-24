from typing import Any, Dict, Optional


DIRECTIONAL_SIGNALS = {"BUY", "SELL"}


def _direction(value: Any) -> Optional[str]:
    normalized = str(value or "").strip().upper()
    return normalized if normalized in DIRECTIONAL_SIGNALS else None


def _numeric(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
        return parsed
    except (TypeError, ValueError):
        return None


def _weighted_direction(analysis_data: Dict[str, Any]) -> Optional[str]:
    scores = analysis_data.get("weighted_scores")
    if not isinstance(scores, dict):
        return None
    buy_score = _numeric(scores.get("buy") or scores.get("BUY")) or 0.0
    sell_score = _numeric(scores.get("sell") or scores.get("SELL")) or 0.0
    if buy_score > sell_score:
        return "BUY"
    if sell_score > buy_score:
        return "SELL"
    return None


def _stable_tiebreak_direction(analysis_data: Dict[str, Any]) -> str:
    source = "|".join(
        str(analysis_data.get(key) or "")
        for key in ("symbol", "interval", "price", "entry_price", "fetched_at")
    )
    checksum = sum((index + 1) * ord(char) for index, char in enumerate(source))
    return "BUY" if checksum % 2 else "SELL"


def _normalize_indicator_votes(indicators: Dict[str, Any]) -> Dict[str, int]:
    votes = {"BUY": 0, "SELL": 0}
    for item in indicators.values():
        if not isinstance(item, dict):
            continue
        signal = _direction(item.get("signal"))
        value_signal = _direction(item.get("value"))
        if signal is None and value_signal is not None:
            signal = value_signal
            item["signal"] = value_signal
        if signal in votes:
            votes[signal] += 1
    return votes


def _stored_vote_direction(analysis_data: Dict[str, Any]) -> Optional[str]:
    votes = analysis_data.get("votes")
    if not isinstance(votes, dict):
        return None
    buy_votes = int(_numeric(votes.get("BUY") or votes.get("buy")) or 0)
    sell_votes = int(_numeric(votes.get("SELL") or votes.get("sell")) or 0)
    if buy_votes > sell_votes:
        return "BUY"
    if sell_votes > buy_votes:
        return "SELL"
    return None


def enforce_binary_signal(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    indicators = analysis_data.get("indicators")
    if not isinstance(indicators, dict):
        return analysis_data

    recommendation = _direction(analysis_data.get("recommendation") or analysis_data.get("signal"))
    indicator_votes = _normalize_indicator_votes(indicators)
    if recommendation:
        return analysis_data

    forced_signal: Optional[str] = None
    if indicator_votes["BUY"] > indicator_votes["SELL"]:
        forced_signal = "BUY"
    elif indicator_votes["SELL"] > indicator_votes["BUY"]:
        forced_signal = "SELL"
    else:
        forced_signal = _stored_vote_direction(analysis_data) or _weighted_direction(analysis_data)

    if forced_signal is None and (indicator_votes["BUY"] + indicator_votes["SELL"]) > 0:
        forced_signal = _stable_tiebreak_direction(analysis_data)

    if forced_signal:
        analysis_data["recommendation"] = forced_signal
        analysis_data["signal"] = forced_signal
        existing_reason = str(analysis_data.get("confidence_reason") or "").strip()
        reason = "binary_direction_restored"
        analysis_data["confidence_reason"] = f"{existing_reason} | {reason}" if existing_reason else reason

    return analysis_data
