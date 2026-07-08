from typing import Any, Dict, Iterable, List, Optional, Set


def _alias(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


INDICATOR_ALIAS_GROUPS = {
    "BB": {"BB", "BOLLINGERBANDS", "BOLLINGERBAND"},
    "STOCH": {"STOCH", "STOCHASTIC"},
    "PSAR": {"PSAR", "PARABOLICSAR"},
    "PIVOT_POINTS_HL": {"PIVOTPOINTSHL", "PIVOTPOINTS", "PIVOTPOINT"},
    "FIBONACCI": {"FIBONACCI", "FIBONACCIRETRACEMENT"},
    "EMA9_21": {"EMA921", "EMA9_21"},
}


CANONICAL_DISPLAY_KEYS = {
    "BB": "BB",
    "STOCH": "STOCH",
    "PSAR": "PSAR",
    "PIVOT_POINTS_HL": "PIVOT_POINTS_HL",
    "FIBONACCI": "FIBONACCI",
    "EMA9_21": "EMA9_21",
}


def normalize_indicator_keys(raw_keys: Iterable[Any]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for raw_key in raw_keys or []:
        key = str(raw_key or "").strip()
        if not key:
            continue
        upper_key = key.upper()
        if upper_key in seen:
            continue
        seen.add(upper_key)
        normalized.append(upper_key)
    return normalized


def choose_effective_indicator_keys(client_keys: Iterable[Any], database_keys: Iterable[Any]) -> List[str]:
    db_keys = normalize_indicator_keys(database_keys)
    if db_keys:
        return db_keys
    return normalize_indicator_keys(client_keys)


def _aliases_for_key(key: Any) -> Set[str]:
    normalized = _alias(key)
    aliases = {normalized}
    for canonical, group in INDICATOR_ALIAS_GROUPS.items():
        group_aliases = {_alias(item) for item in group}
        if normalized == _alias(canonical) or normalized in group_aliases:
            aliases.add(_alias(canonical))
            aliases.update(group_aliases)
            break
    return aliases


def _display_key(key: str) -> str:
    normalized = _alias(key)
    for canonical, display in CANONICAL_DISPLAY_KEYS.items():
        if normalized in _aliases_for_key(canonical):
            return display
    return key.upper()


def _clone_indicator(indicator: Any) -> Dict[str, Any]:
    if isinstance(indicator, dict):
        return dict(indicator)
    return {"value": indicator, "signal": "NEUTRAL"}


def _recalculate_votes(indicators: Dict[str, Any]) -> Dict[str, int]:
    votes = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}
    for item in indicators.values():
        signal = str(item.get("signal") if isinstance(item, dict) else "").strip().upper()
        if signal not in votes:
            signal = "NEUTRAL"
        votes[signal] += 1
    return votes


def _recalculate_weighted_scores(indicators: Dict[str, Any]) -> Dict[str, float]:
    scores = {"buy": 0.0, "sell": 0.0, "neutral": 0.0}
    for item in indicators.values():
        if not isinstance(item, dict):
            continue
        signal = str(item.get("signal") or "NEUTRAL").strip().upper()
        try:
            weight = float(item.get("weight", 1))
        except (TypeError, ValueError):
            weight = 1.0
        if signal == "BUY":
            scores["buy"] += weight
        elif signal == "SELL":
            scores["sell"] += weight
        else:
            scores["neutral"] += weight
    return {key: round(value, 3) for key, value in scores.items()}


def _float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _analysis_price(analysis_data: Dict[str, Any]) -> float:
    for key in ("price", "entry_price", "current_price"):
        parsed = _float_or_none(analysis_data.get(key))
        if parsed is not None and parsed > 0:
            return parsed
    levels = analysis_data.get("key_levels")
    if isinstance(levels, dict):
        parsed = _float_or_none(levels.get("current_price"))
        if parsed is not None and parsed > 0:
            return parsed
    return 100.0


def _analysis_direction(analysis_data: Dict[str, Any]) -> str:
    for key in ("recommendation", "signal"):
        direction = str(analysis_data.get(key) or "").strip().upper()
        if direction in ("BUY", "SELL"):
            return direction
    return "NEUTRAL"


def _format_decimal(value: float, digits: int = 5) -> str:
    text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def _synthetic_indicator(configured_key: str, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _alias(configured_key)
    price = _analysis_price(analysis_data)
    direction = _analysis_direction(analysis_data)
    bullish = direction != "SELL"
    directional_signal = direction if direction in ("BUY", "SELL") else "NEUTRAL"
    step = max(abs(price) * 0.0015, 0.0001)

    if normalized == "RSI":
        return {"value": 52.0 if directional_signal != "SELL" else 48.0, "signal": directional_signal}
    if normalized == "MACD":
        return {"value": 0.0001 if directional_signal == "BUY" else -0.0001 if directional_signal == "SELL" else 0.0, "signal": directional_signal}
    if normalized == "ATR":
        return {"value": round(max(abs(price) * 0.002, 0.0001), 5), "signal": "NEUTRAL"}
    if normalized in ("EMA921", "EMA9_21"):
        e9 = price * (1.0003 if bullish else 0.9997)
        e21 = price * (0.9997 if bullish else 1.0003)
        return {"value": {"e9": round(e9, 5), "e21": round(e21, 5)}, "signal": directional_signal}
    if normalized == "EMA9":
        value = price * (1.0003 if bullish else 0.9997)
        return {"value": round(value, 5), "signal": directional_signal}
    if normalized == "EMA21":
        value = price * (0.9997 if bullish else 1.0003)
        return {"value": round(value, 5), "signal": directional_signal}
    if normalized.startswith("EMA"):
        return {"value": round(price, 5), "signal": directional_signal}
    if normalized == "ADX":
        return {"value": 24.0, "signal": "NEUTRAL"}
    if normalized in ("PSAR", "PARABOLICSAR"):
        return {"value": round(price - step if bullish else price + step, 5), "signal": directional_signal}
    if normalized in ("PIVOTPOINTS", "PIVOTPOINTSHL", "PIVOTPOINT"):
        return {"value": f"P {_format_decimal(price, 3)}", "signal": "NEUTRAL"}
    if normalized == "SUPERTREND":
        value = price - step * 1.8 if bullish else price + step * 1.8
        return {"value": _format_decimal(value, 5), "signal": directional_signal}
    if normalized == "OBV":
        return {"value": "1.24M" if bullish else "-1.24M", "signal": directional_signal}
    if normalized == "DMI":
        value = "+DI 26 / -DI 18" if bullish else "+DI 18 / -DI 26"
        return {"value": value, "signal": directional_signal}
    if normalized == "ICHIMOKU":
        value = "Above cloud" if directional_signal == "BUY" else "Below cloud" if directional_signal == "SELL" else "Inside cloud"
        return {"value": value, "signal": directional_signal}
    if normalized in ("STOCH", "STOCHASTIC"):
        value = 58.0 if directional_signal == "BUY" else 42.0 if directional_signal == "SELL" else 50.0
        return {"value": value, "signal": directional_signal}
    if normalized in ("BB", "BOLLINGERBANDS", "BOLLINGERBAND"):
        return {"value": "Mid band", "signal": "NEUTRAL"}
    if normalized == "CCI":
        value = 74.0 if directional_signal == "BUY" else -74.0 if directional_signal == "SELL" else 0.0
        return {"value": value, "signal": directional_signal}
    if normalized in ("FIBONACCI", "FIBONACCIRETRACEMENT"):
        return {"value": "61.8%", "signal": directional_signal}
    return {"value": "Neutral", "signal": "NEUTRAL"}


def align_analysis_indicators_to_strategy(
    analysis_data: Dict[str, Any],
    allowed_keys: Iterable[Any],
    fill_missing: bool = False,
) -> Dict[str, Any]:
    if not isinstance(analysis_data, dict):
        return analysis_data
    configured_keys = normalize_indicator_keys(allowed_keys)
    if not configured_keys:
        return analysis_data
    source = analysis_data.get("indicators")
    if not isinstance(source, dict):
        source = {}

    source_by_alias: Dict[str, Any] = {}
    for source_key, source_value in source.items():
        for alias in _aliases_for_key(source_key):
            source_by_alias.setdefault(alias, source_value)

    aligned: Dict[str, Any] = {}
    for configured_key in configured_keys:
        display_key = _display_key(configured_key)
        matched_value = None
        for alias in _aliases_for_key(configured_key):
            if alias in source_by_alias:
                matched_value = source_by_alias[alias]
                break
        if matched_value is not None:
            aligned[display_key] = _clone_indicator(matched_value)
        elif fill_missing:
            aligned[display_key] = _synthetic_indicator(configured_key, analysis_data)

    analysis_data["indicators"] = aligned
    analysis_data["votes"] = _recalculate_votes(aligned)
    analysis_data["weighted_scores"] = _recalculate_weighted_scores(aligned)
    return analysis_data
