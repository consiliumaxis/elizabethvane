from typing import Any


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
    return normalize_stream_indicator_key(indicator_key) in {"ATR", "RVOL", "RELATIVEVOLUME"}


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

    step = max(abs(current_price) * 0.0015, 0.0001)
    buy = direction == "BUY"
    sell = direction == "SELL"

    if key == "RSI":
        return 24.0 if buy else 76.0 if sell else 50.0
    if key == "MACD":
        base = max(abs(current_price) * 0.00012, 0.00001)
        macd = base if buy else -base if sell else 0.0
        signal_line = macd * 0.55 if direction != "NEUTRAL" else 0.0
        return {
            "macd": round(macd, 6),
            "signal": round(signal_line, 6),
            "hist": round(macd - signal_line, 6),
        }
    if key in {"STOCH", "STOCHASTIC", "STOCHRSI"}:
        if buy:
            return {"k": 18.0, "d": 14.0}
        if sell:
            return {"k": 82.0, "d": 86.0}
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
        return 31.2 if direction != "NEUTRAL" else 18.0
    if key == "DMI":
        # Display the signed +DI/-DI spread as one numeric value.
        return 16.0 if buy else -16.0 if sell else 0.0
    if key == "CCI":
        return -135.0 if buy else 135.0 if sell else 0.0
    if key in {"PSAR", "PARABOLICSAR", "SUPERTREND", "ICHIMOKU"}:
        value = current_price - step if buy else current_price + step if sell else current_price
        return round(value, 5)
    if key in {"PIVOTPOINT", "PIVOTPOINTS", "PIVOTPOINTSHL", "FIBONACCI", "FIBONACCIRETRACEMENT"}:
        value = current_price - (step * 2) if buy else current_price + (step * 2) if sell else current_price
        return round(value, 5)
    if key == "ATR":
        return round(max(abs(current_price) * 0.002, 0.0001), 5)
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
