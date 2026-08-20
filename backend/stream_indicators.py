import math
from typing import Any, Dict, Iterable, Mapping


def normalize_stream_indicator_key(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )


def stream_indicator_is_neutral_only(indicator_key: Any) -> bool:
    """Indicators that measure volatility/activity but not trade direction."""
    return normalize_stream_indicator_key(indicator_key) in {
        "ADX",
        "ATR",
        "RVOL",
        "RELATIVEVOLUME",
    }


def _stream_indicator_priority(indicator_key: Any) -> int:
    """Keep trend evidence dominant and reserve oscillators for disagreement."""
    key = normalize_stream_indicator_key(indicator_key)
    if key.startswith("EMA") or key in {
        "MACD",
        "PSAR",
        "PARABOLICSAR",
        "DMI",
        "SUPERTREND",
        "ICHIMOKU",
        "VWAP",
        "WAP",
    }:
        return 0
    if key in {
        "PIVOTPOINT",
        "PIVOTPOINTS",
        "PIVOTPOINTSHL",
        "FIBONACCI",
        "FIBONACCIRETRACEMENT",
        "MOM",
        "MOMENTUM",
        "ROC",
        "OBV",
    }:
        return 1
    if key in {
        "RSI",
        "STOCH",
        "STOCHASTIC",
        "STOCHRSI",
        "BB",
        "BOLLINGERBAND",
        "BOLLINGERBANDS",
        "CCI",
        "MFI",
        "MONEYFLOWINDEX",
        "WILLR",
        "WILLIAMSR",
        "WILLIAMSPERCENTR",
    }:
        return 2
    return 3


def distribute_stream_indicator_signals(
    indicator_keys: Iterable[Any],
    forced_signal: str,
    locked_signals: Mapping[Any, Any] | None = None,
) -> Dict[Any, str]:
    """Build one stable, coherent indicator distribution for a stream signal.

    The previous implementation randomly changed indicator directions on every
    request.  Stream recordings need repeatable numbers, so the allocation is
    now deterministic: trend indicators support the final signal first,
    volatility/strength-only indicators stay neutral, and at most one remaining
    oscillator is used as realistic disagreement.
    """
    direction = str(forced_signal or "").strip().upper()
    if direction not in {"BUY", "SELL"}:
        return {}
    opposite = "SELL" if direction == "BUY" else "BUY"
    keys = list(dict.fromkeys(indicator_keys or []))
    resolved: Dict[Any, str] = {}

    for key, raw_signal in dict(locked_signals or {}).items():
        signal = str(raw_signal or "").strip().upper()
        if key in keys and signal in {"BUY", "SELL", "NEUTRAL"}:
            resolved[key] = signal
    for key in keys:
        if key not in resolved and stream_indicator_is_neutral_only(key):
            resolved[key] = "NEUTRAL"

    remaining = [key for key in keys if key not in resolved]
    forced_locked = sum(1 for signal in resolved.values() if signal == direction)
    required_majority = (len(keys) // 2) + 1 if keys else 0
    target_forced = max(required_majority, int(math.ceil(len(keys) * 0.60)))
    forced_needed = min(len(remaining), max(0, target_forced - forced_locked))

    ordered = sorted(
        enumerate(remaining),
        key=lambda item: (_stream_indicator_priority(item[1]), item[0]),
    )
    forced_keys = {key for _, key in ordered[:forced_needed]}
    for key in remaining:
        if key in forced_keys:
            resolved[key] = direction

    undecided = [key for key in remaining if key not in forced_keys]
    if undecided and len(keys) >= 3:
        opposite_key = sorted(
            enumerate(undecided),
            key=lambda item: (-_stream_indicator_priority(item[1]), item[0]),
        )[0][1]
        resolved[opposite_key] = opposite
    for key in undecided:
        resolved.setdefault(key, "NEUTRAL")
    return resolved


def coherent_stream_indicator_value(indicator_key: Any, signal: str, price: Any) -> Any:
    """Build a plausible value whose trading meaning agrees with the displayed signal.

    Stream mode is a deterministic presentation fallback and does not call GPT.  Values
    therefore need to be generated from the same rules used by the regular analysis
    engine instead of being left over from a different, randomly assigned signal.
    """
    key = normalize_stream_indicator_key(indicator_key)
    direction = str(signal or "NEUTRAL").strip().upper()
    if direction not in {"BUY", "SELL"}:
        direction = "NEUTRAL"
    try:
        current_price = float(price)
        if current_price <= 0:
            raise ValueError
    except (TypeError, ValueError):
        current_price = 100.0

    seed_text = f"{key}|{direction}|{current_price:.8f}"
    variation = (sum((index + 1) * ord(char) for index, char in enumerate(seed_text)) % 1000) / 1000.0
    step = max(abs(current_price) * (0.0008 + (variation * 0.0012)), 0.00001)
    buy = direction == "BUY"
    sell = direction == "SELL"

    if key == "RSI":
        return round(56.0 + (variation * 12.0), 2) if buy else round(44.0 - (variation * 12.0), 2) if sell else 50.0
    if key == "MACD":
        base = max(abs(current_price) * (0.00008 + (variation * 0.00008)), 0.00001)
        macd = base if buy else -base if sell else 0.0
        signal_line = macd * 0.55 if direction != "NEUTRAL" else 0.0
        return {
            "macd": round(macd, 5),
            "signal": round(signal_line, 5),
            "hist": round(macd - signal_line, 5),
        }
    if key in {"STOCH", "STOCHASTIC", "STOCHRSI"}:
        if buy:
            k_value = 56.0 + (variation * 18.0)
            return {"k": round(k_value, 2), "d": round(k_value - 5.0, 2)}
        if sell:
            k_value = 44.0 - (variation * 18.0)
            return {"k": round(k_value, 2), "d": round(k_value + 5.0, 2)}
        return {"k": 50.0, "d": 50.0}
    if key in {"BB", "BOLLINGERBAND", "BOLLINGERBANDS"}:
        # Bollinger %B: <= .15 is BUY, >= .85 is SELL in the main engine.
        return 0.12 if buy else 0.88 if sell else 0.5
    if key in {"EMA921", "EMA9/21"}:
        if buy:
            return {"e9": round(current_price + step, 5), "e21": round(current_price - step, 5)}
        if sell:
            return {"e9": round(current_price - step, 5), "e21": round(current_price + step, 5)}
        return {"e9": round(current_price, 5), "e21": round(current_price, 5)}
    if key.startswith("EMA") or key in {"VWAP", "WAP"}:
        # Price above the average is BUY; price below it is SELL.
        value = current_price - step if buy else current_price + step if sell else current_price
        return round(value, 5)
    if key == "ADX":
        # ADX is strength; the direction is supplied by DMI in the engine.
        return round(27.0 + (variation * 12.0), 2) if direction != "NEUTRAL" else round(15.0 + (variation * 7.0), 2)
    if key == "DMI":
        dominant = round(25.0 + (variation * 8.0), 2)
        secondary = round(13.0 + (variation * 7.0), 2)
        strength = round(27.0 + (variation * 12.0), 2)
        if buy:
            return {"plus_di": dominant, "minus_di": secondary, "adx": strength}
        if sell:
            return {"plus_di": secondary, "minus_di": dominant, "adx": strength}
        return {"plus_di": 20.0, "minus_di": 20.0, "adx": round(15.0 + (variation * 7.0), 2)}
    if key == "CCI":
        value = round(60.0 + (variation * 90.0), 2)
        return value if buy else -value if sell else 0.0
    if key in {"PSAR", "PARABOLICSAR", "SUPERTREND", "ICHIMOKU"}:
        value = current_price - step if buy else current_price + step if sell else current_price
        return round(value, 5)
    if key in {"PIVOTPOINT", "PIVOTPOINTS", "PIVOTPOINTSHL", "FIBONACCI", "FIBONACCIRETRACEMENT"}:
        value = current_price - (step * 2) if buy else current_price + (step * 2) if sell else current_price
        return round(value, 5)
    if key == "ATR":
        return round(max(abs(current_price) * (0.0012 + (variation * 0.0012)), 0.00001), 5)
    if key in {"MFI", "MONEYFLOWINDEX"}:
        return 18.0 if buy else 82.0 if sell else 50.0
    if key in {"WILLR", "WILLIAMSR", "WILLIAMSPERCENTR"}:
        return -85.0 if buy else -15.0 if sell else -50.0
    if key in {"MOM", "MOMENTUM", "ROC", "OBV", "AD", "ADOSC", "ACCUMULATIONDISTRIBUTION"}:
        return 16.0 if buy else -16.0 if sell else 0.0
    if key in {"RVOL", "RELATIVEVOLUME"}:
        return 1.2

    # Unknown configured indicators still receive a numeric, stable value rather
    # than the misleading text "Neutral" paired with BUY/SELL.
    value = current_price - step if buy else current_price + step if sell else current_price
    return round(value, 5)
