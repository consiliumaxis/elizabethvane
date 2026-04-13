import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


ADV_PERIODS = {
    "5min": {
        "rsi": 9,
        "macd_fast": 5,
        "macd_slow": 13,
        "macd_signal": 1,
        "stoch_k": 5,
        "stoch_d": 3,
        "stoch_slow": 3,
        "bb": 20,
        "bb_sd": 2.0,
        "cci": 14,
        "adx": 10,
        "atr": 14,
        "st_p": 7,
        "st_m": 3.0,
        "fib_lookback": 100,
    },
    "15min": {
        "rsi": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "stoch_k": 9,
        "stoch_d": 3,
        "stoch_slow": 3,
        "bb": 20,
        "bb_sd": 2.0,
        "cci": 20,
        "adx": 14,
        "atr": 14,
        "st_p": 10,
        "st_m": 3.0,
        "fib_lookback": 75,
    },
    "30min": {
        "rsi": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "stoch_k": 14,
        "stoch_d": 3,
        "stoch_slow": 3,
        "bb": 20,
        "bb_sd": 2.0,
        "cci": 20,
        "adx": 14,
        "atr": 14,
        "st_p": 10,
        "st_m": 3.0,
        "fib_lookback": 50,
    },
    "1h": {
        "rsi": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "stoch_k": 14,
        "stoch_d": 3,
        "stoch_slow": 3,
        "bb": 20,
        "bb_sd": 2.0,
        "cci": 20,
        "adx": 14,
        "atr": 14,
        "st_p": 10,
        "st_m": 3.0,
        "fib_lookback": 35,
    },
    "4h": {
        "rsi": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "stoch_k": 14,
        "stoch_d": 3,
        "stoch_slow": 3,
        "bb": 20,
        "bb_sd": 2.0,
        "cci": 20,
        "adx": 14,
        "atr": 14,
        "st_p": 10,
        "st_m": 3.0,
        "fib_lookback": 70,
    },
    "1day": {
        "rsi": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "stoch_k": 14,
        "stoch_d": 3,
        "stoch_slow": 3,
        "bb": 20,
        "bb_sd": 2.0,
        "cci": 20,
        "adx": 14,
        "atr": 14,
        "st_p": 10,
        "st_m": 3.0,
        "fib_lookback": 120,
    },
}
ADV_PERIODS_DEFAULT = ADV_PERIODS["5min"]

RSI_THRESHOLDS = {
    "5min": {"ob": 75, "os": 25},
    "15min": {"ob": 70, "os": 30},
    "30min": {"ob": 70, "os": 30},
    "1h": {"ob": 70, "os": 30},
    "4h": {"ob": 70, "os": 30},
    "1day": {"ob": 70, "os": 30},
}
RSI_THRESHOLDS_DEFAULT = {"ob": 70, "os": 30}

CCI_THRESHOLDS = {"5min": 150, "15min": 100, "30min": 100, "1h": 100, "4h": 100, "1day": 100}

ADX_TREND_THRESHOLD = 25.0

INDICATOR_WEIGHTS = {
    "EMA9_21": {"base": 1.3, "cat": "trend"},
    "EMA50": {"base": 1.2, "cat": "trend"},
    "EMA200": {"base": 1.0, "cat": "trend"},
    "PSAR": {"base": 1.0, "cat": "trend"},
    "Supertrend": {"base": 1.3, "cat": "trend"},
    "Ichimoku": {"base": 1.1, "cat": "trend"},
    "DMI": {"base": 1.1, "cat": "trend"},
    "RSI": {"base": 1.2, "cat": "osc"},
    "MACD": {"base": 1.2, "cat": "osc"},
    "Stoch": {"base": 1.0, "cat": "osc"},
    "CCI": {"base": 0.9, "cat": "osc"},
    "BB": {"base": 1.1, "cat": "vol"},
    "ADX": {"base": 1.0, "cat": "filter"},
    "ATR": {"base": 0.0, "cat": "info"},
    "PivotPoints": {"base": 0.8, "cat": "structure"},
    "Fibonacci": {"base": 0.9, "cat": "structure"},
}

MIN_CONFIDENCE_ADV = 25

MIN_CONFIDENCE_BY_INTERVAL = {
    "5min": 33,
    "15min": 30,
    "30min": 28,
    "1h": 26,
    "4h": 24,
    "1day": 24,
}

MIN_DIRECTIONAL_VOTES_BY_INTERVAL = {
    "5min": 4,
    "15min": 3,
    "30min": 3,
    "1h": 3,
    "4h": 3,
    "1day": 2,
}

MIN_WEIGHT_EDGE_BY_INTERVAL = {
    "5min": 0.8,
    "15min": 0.7,
    "30min": 0.6,
    "1h": 0.5,
    "4h": 0.45,
    "1day": 0.4,
}

ATR_LEVEL_MULTIPLIERS = {
    "5min": {"cons_sl": 0.45, "mod_sl": 0.7, "tp2": 0.75, "tp3": 1.1},
    "15min": {"cons_sl": 0.6, "mod_sl": 0.95, "tp2": 1.0, "tp3": 1.5},
    "30min": {"cons_sl": 0.9, "mod_sl": 1.3, "tp2": 1.6, "tp3": 2.2},
    "1h": {"cons_sl": 1.0, "mod_sl": 1.5, "tp2": 1.8, "tp3": 2.6},
    "4h": {"cons_sl": 1.2, "mod_sl": 1.8, "tp2": 2.2, "tp3": 3.2},
    "1day": {"cons_sl": 1.4, "mod_sl": 2.1, "tp2": 2.8, "tp3": 4.0},
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clean_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _normalize_interval(interval: str) -> str:
    m = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1day",
    }
    return m.get((interval or "").strip().lower(), (interval or "").strip().lower() or "5min")


def _clean_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper().replace(" ", "")
    if "/" in s:
        return s
    if "-" in s:
        return s.replace("-", "/")
    if len(s) == 6 and s.isalpha():
        return f"{s[:3]}/{s[3:]}"
    return s


def _get_adv_periods(interval: str) -> Dict[str, Any]:
    return ADV_PERIODS.get((interval or "").strip().lower(), ADV_PERIODS_DEFAULT)


def _get_rsi_thr(interval: str) -> Dict[str, int]:
    return RSI_THRESHOLDS.get((interval or "").strip().lower(), RSI_THRESHOLDS_DEFAULT)


def _get_cci_thr(interval: str) -> int:
    return CCI_THRESHOLDS.get((interval or "").strip().lower(), 100)


def _get_weight(name: str, adx_val: Optional[float]) -> float:
    info = INDICATOR_WEIGHTS.get(name, {"base": 1.0, "cat": "other"})
    w = info["base"]
    if w <= 0:
        return 0.0
    if adx_val is not None and adx_val > 0:
        trending = adx_val >= ADX_TREND_THRESHOLD
        cat = info["cat"]
        if trending:
            if cat == "trend":
                w *= 1.20
            elif cat == "osc":
                w *= 0.80
        else:
            if cat == "osc":
                w *= 1.15
            elif cat == "trend":
                w *= 0.85
    return w


def _extract_indicators_container(payload: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("raw_indicators", "indicators_raw", "indicators"):
        val = payload.get(key)
        if isinstance(val, dict):
            return val
    return {}


def _ci_get(d: Dict[str, Any], *keys: str) -> Any:
    if not isinstance(d, dict):
        return None
    for k in keys:
        for dk, dv in d.items():
            if str(dk).upper() == str(k).upper():
                return dv
    return None


def _unwrap_indicator_value(v: Any) -> Any:
    if isinstance(v, dict) and "value" in v:
        return v.get("value")
    return v


def _extract_obj(payload: Dict[str, Any], indicators: Dict[str, Any], *names: str) -> Any:
    obj = _ci_get(indicators, *names)
    if obj is None:
        obj = _ci_get(payload, *names)
    return _unwrap_indicator_value(obj)


def _to_num_or_field(v: Any, *field_names: str) -> Optional[float]:
    if isinstance(v, dict):
        for f in field_names:
            fv = _clean_float(_ci_get(v, f))
            if fv is not None:
                return fv
        return None
    return _clean_float(v)


def _to_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return v
    return {}


def _parse_ohlc(payload: Dict[str, Any]) -> List[Dict[str, float]]:
    for key in ("ohlc", "ohlc_data", "candles", "time_series", "values"):
        seq = payload.get(key)
        if isinstance(seq, list):
            out = []
            for x in seq:
                if not isinstance(x, dict):
                    continue
                h = _clean_float(_ci_get(x, "high"))
                l = _clean_float(_ci_get(x, "low"))
                c = _clean_float(_ci_get(x, "close"))
                if h is not None and l is not None and c is not None:
                    out.append({"high": h, "low": l, "close": c})
            if out:
                return out
    return []


def _evaluate_rules(
    price: float,
    interval: str,
    *,
    rsi,
    macd,
    stoch,
    bbands,
    ema9,
    ema21,
    ema50,
    ema200,
    adx,
    cci,
    psar,
    plus_di,
    minus_di,
    supertrend,
    ichimoku,
    pivot_points,
    atr,
    allowed_indicators: List[str],
):
    allowed_upper = [a.upper() for a in (allowed_indicators or [])]
    w_buy = w_sell = w_neutral = 0.0
    votes = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}
    details: Dict[str, Any] = {}
    rsi_thr = _get_rsi_thr(interval)
    cci_thr = _get_cci_thr(interval)
    adx_val = _to_num_or_field(adx, "adx")

    backend_to_db_map = {
        "RSI": "RSI",
        "MACD": "MACD",
        "STOCH": "STOCH",
        "BB": "BB",
        "EMA9_21": ["EMA9", "EMA21"],
        "EMA50": "EMA50",
        "EMA200": "EMA200",
        "ADX": "ADX",
        "CCI": "CCI",
        "PSAR": "PSAR",
        "DMI": "DMI",
        "SUPERTREND": "SUPERTREND",
        "ICHIMOKU": "ICHIMOKU",
        "PIVOTPOINTS": ["PIVOT_POINTS_HL", "PIVOTPOINTS"],
        "ATR": "ATR",
    }

    def is_allowed(k: str) -> bool:
        if not allowed_upper:
            return True
        db_keys = backend_to_db_map.get(k.upper(), k.upper())
        if isinstance(db_keys, list):
            return any(dk in allowed_upper for dk in db_keys)
        return db_keys in allowed_upper

    def add(k: str, sig: str, val: Any):
        nonlocal w_buy, w_sell, w_neutral
        if isinstance(val, (int, float)) and float(val) == 0:
            return
        if isinstance(val, dict):
            has_non_zero = False
            for vv in val.values():
                fv = _clean_float(vv)
                if fv is not None and fv != 0:
                    has_non_zero = True
                    break
            if not has_non_zero and val:
                return
        if not is_allowed(k):
            return
        w = _get_weight(k, adx_val)
        details[k] = {"value": val, "signal": sig, "weight": round(w, 2)}
        votes[sig] += 1
        if sig == "BUY":
            w_buy += w
        elif sig == "SELL":
            w_sell += w
        else:
            w_neutral += w

    rsi_v = _to_num_or_field(rsi, "rsi")
    if rsi_v is not None:
        if rsi_v < rsi_thr["os"]:
            add("RSI", "BUY", rsi_v)
        elif rsi_v > rsi_thr["ob"]:
            add("RSI", "SELL", rsi_v)
        else:
            add("RSI", "NEUTRAL", rsi_v)

    m_v = _to_num_or_field(macd, "macd")
    s_v = _to_num_or_field(macd, "macd_signal", "signal")
    if m_v is not None and s_v is not None:
        hist = round(m_v - s_v, 6)
        if m_v > s_v:
            add("MACD", "BUY", {"macd": m_v, "signal": s_v, "hist": hist})
        elif m_v < s_v:
            add("MACD", "SELL", {"macd": m_v, "signal": s_v, "hist": hist})
        else:
            add("MACD", "NEUTRAL", {"macd": m_v, "signal": s_v, "hist": 0})

    k = _to_num_or_field(stoch, "slow_k", "k")
    d = _to_num_or_field(stoch, "slow_d", "d")
    if k is not None and d is not None:
        if k < 20 and k > d:
            add("Stoch", "BUY", {"k": k, "d": d})
        elif k > 80 and k < d:
            add("Stoch", "SELL", {"k": k, "d": d})
        else:
            add("Stoch", "NEUTRAL", {"k": k, "d": d})

    lb = _to_num_or_field(bbands, "lower_band", "lb")
    ub = _to_num_or_field(bbands, "upper_band", "ub")
    if lb is not None and ub is not None and ub > lb:
        pct_b = (price - lb) / (ub - lb)
        if pct_b <= 0.15:
            add("BB", "BUY", {"lb": lb, "ub": ub, "pct_b": round(pct_b, 3)})
        elif pct_b >= 0.85:
            add("BB", "SELL", {"lb": lb, "ub": ub, "pct_b": round(pct_b, 3)})
        else:
            add("BB", "NEUTRAL", {"lb": lb, "ub": ub, "pct_b": round(pct_b, 3)})

    e9 = _to_num_or_field(ema9, "ema", "value")
    e21 = _to_num_or_field(ema21, "ema", "value")
    if e9 is not None and e21 is not None:
        sig = "BUY" if e9 > e21 else ("SELL" if e9 < e21 else "NEUTRAL")
        add("EMA9_21", sig, {"e9": e9, "e21": e21})

    e50 = _to_num_or_field(ema50, "ema", "value")
    if e50 is not None:
        add("EMA50", "BUY" if price > e50 else "SELL", e50)

    e200 = _to_num_or_field(ema200, "ema", "value")
    if e200 is not None:
        add("EMA200", "BUY" if price > e200 else "SELL", e200)

    p_di = _to_num_or_field(plus_di, "plus_di")
    m_di = _to_num_or_field(minus_di, "minus_di")
    if adx_val is not None:
        if p_di is not None and m_di is not None:
            if adx_val >= ADX_TREND_THRESHOLD:
                sig = "BUY" if p_di > m_di else ("SELL" if p_di < m_di else "NEUTRAL")
                add("ADX", sig, adx_val)
                add("DMI", sig, {"plus_di": p_di, "minus_di": m_di, "adx": adx_val})
            else:
                add("ADX", "NEUTRAL", adx_val)
                add("DMI", "NEUTRAL", {"plus_di": p_di, "minus_di": m_di, "adx": adx_val})
        else:
            add("ADX", "NEUTRAL", adx_val)

    cci_v = _to_num_or_field(cci, "cci")
    if cci_v is not None:
        if cci_v < -cci_thr:
            add("CCI", "BUY", cci_v)
        elif cci_v > cci_thr:
            add("CCI", "SELL", cci_v)
        else:
            add("CCI", "NEUTRAL", cci_v)

    psar_v = _to_num_or_field(psar, "psar")
    if psar_v is not None:
        if adx_val is not None and adx_val >= ADX_TREND_THRESHOLD:
            add("PSAR", "BUY" if price > psar_v else "SELL", psar_v)
        else:
            add("PSAR", "NEUTRAL", psar_v)

    st_val = _to_num_or_field(supertrend, "supertrend")
    if st_val is not None:
        add("Supertrend", "BUY" if price > st_val else "SELL", st_val)

    ichi = _to_dict(ichimoku)
    sa = _to_num_or_field(ichi, "senkou_span_a")
    sb = _to_num_or_field(ichi, "senkou_span_b")
    if sa is not None and sb is not None:
        cloud_top, cloud_bot = max(sa, sb), min(sa, sb)
        if price > cloud_top:
            add("Ichimoku", "BUY", {"span_a": sa, "span_b": sb, "zone": "above"})
        elif price < cloud_bot:
            add("Ichimoku", "SELL", {"span_a": sa, "span_b": sb, "zone": "below"})
        else:
            add("Ichimoku", "NEUTRAL", {"span_a": sa, "span_b": sb, "zone": "inside"})

    pp_raw = _to_dict(pivot_points)
    if pp_raw and is_allowed("PivotPoints"):
        pp = _to_num_or_field(pp_raw, "pivot_point", "pp")
        s1 = _to_num_or_field(pp_raw, "s1")
        r1 = _to_num_or_field(pp_raw, "r1")
        if pp is not None:
            if s1 is not None and price <= s1:
                add("PivotPoints", "BUY", {**pp_raw, "_note": "at_S1_support"})
            elif r1 is not None and price >= r1:
                add("PivotPoints", "SELL", {**pp_raw, "_note": "at_R1_resistance"})
            elif price > pp:
                add("PivotPoints", "BUY", {**pp_raw, "_note": "above_PP"})
            elif price < pp:
                add("PivotPoints", "SELL", {**pp_raw, "_note": "below_PP"})
            else:
                add("PivotPoints", "NEUTRAL", pp_raw)

    atr_v = _to_num_or_field(atr, "atr")
    if atr_v is not None:
        add("ATR", "NEUTRAL", atr_v)

    return votes, details, w_buy, w_sell, w_neutral


def _calculate_fibonacci_levels(ohlc_data: List[Dict[str, float]], lookback: int = 50) -> Dict[str, float]:
    recent = ohlc_data[:lookback]
    if not recent:
        return {}
    high = max(x["high"] for x in recent)
    low = min(x["low"] for x in recent)
    diff = high - low
    if diff <= 0:
        return {}
    return {
        "0": round(high, 5),
        "0.236": round(high - diff * 0.236, 5),
        "0.382": round(high - diff * 0.382, 5),
        "0.5": round(high - diff * 0.5, 5),
        "0.618": round(high - diff * 0.618, 5),
        "0.786": round(high - diff * 0.786, 5),
        "1": round(low, 5),
    }


def _fibonacci_signal(price: float, fib: Dict[str, float]) -> str:
    if not fib:
        return "NEUTRAL"
    l618 = fib.get("0.618")
    l786 = fib.get("0.786")
    top = fib.get("0")
    if l618 is not None and l786 is not None and l786 <= price <= l618:
        return "BUY"
    if l618 is not None and price < l618:
        return "BUY"
    if top is not None and price >= top:
        return "SELL"
    return "NEUTRAL"


def _calculate_key_levels(
    ohlc_data: List[Dict[str, float]],
    current_price: float,
    atr: float,
    signal: str,
    interval: str,
) -> Dict[str, Any]:
    recent = ohlc_data[:10]
    if not recent:
        return {}
    res = max(x["high"] for x in recent)
    sup = min(x["low"] for x in recent)
    m = ATR_LEVEL_MULTIPLIERS.get(interval, ATR_LEVEL_MULTIPLIERS["15min"])
    atr = max(float(atr), 1e-6)
    support_buffer = 0.25 * atr
    resistance_buffer = 0.25 * atr

    if signal == "BUY":
        cons_sl = current_price - m["cons_sl"] * atr
        mod_sl = current_price - m["mod_sl"] * atr
        if sup < current_price:
            cons_sl = max(cons_sl, sup - support_buffer)
            mod_sl = max(mod_sl, sup - 2 * support_buffer)

        tp2 = current_price + m["tp2"] * atr
        tp3 = current_price + m["tp3"] * atr
        if res > current_price:
            tp2 = min(tp2, res + resistance_buffer)
            tp3 = min(tp3, res + 2 * resistance_buffer)
    elif signal == "SELL":
        cons_sl = current_price + m["cons_sl"] * atr
        mod_sl = current_price + m["mod_sl"] * atr
        if res > current_price:
            cons_sl = min(cons_sl, res + resistance_buffer)
            mod_sl = min(mod_sl, res + 2 * resistance_buffer)

        tp2 = current_price - m["tp2"] * atr
        tp3 = current_price - m["tp3"] * atr
        if sup < current_price:
            tp2 = max(tp2, sup - support_buffer)
            tp3 = max(tp3, sup - 2 * support_buffer)
    else:
        cons_sl = mod_sl = tp2 = tp3 = None

    return {
        "current_price": round(current_price, 5),
        "nearest_support": round(sup, 5),
        "nearest_resistance": round(res, 5),
        "atr_14": round(atr, 5),
        "conservative_sl": round(cons_sl, 5) if cons_sl is not None else None,
        "moderate_sl": round(mod_sl, 5) if mod_sl is not None else None,
        "rr_2_1_target": round(tp2, 5) if tp2 is not None else None,
        "rr_3_1_target": round(tp3, 5) if tp3 is not None else None,
    }


def _calc_recent_tr(ohlc_data: List[Dict[str, float]], max_bars: int = 50) -> List[float]:
    if len(ohlc_data) < 2:
        return []
    limit = min(len(ohlc_data) - 1, max_bars)
    trs: List[float] = []
    for i in range(limit):
        cur = ohlc_data[i]
        prev_close = ohlc_data[i + 1]["close"]
        h = cur["high"]
        l = cur["low"]
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        if tr > 0:
            trs.append(tr)
    return trs


def _compute_confidence(
    w_buy: float,
    w_sell: float,
    w_neutral: float,
    adx_val: Optional[float],
    session_mult: float,
    atr_val: Optional[float],
    atr_avg: Optional[float],
    votes: Optional[Dict[str, int]] = None,
) -> Tuple[int, str]:
    total_w = w_buy + w_sell + w_neutral
    if total_w <= 0:
        return 0, "no_votes"

    dominance = (max(w_buy, w_sell) - min(w_buy, w_sell)) / total_w
    dir_ratio = (w_buy + w_sell) / total_w
    raw_conf = dominance * dir_ratio * 100.0
    reasons: List[str] = []

    if adx_val is not None and adx_val < ADX_TREND_THRESHOLD:
        r = max(0.3, adx_val / ADX_TREND_THRESHOLD)
        raw_conf *= r
        reasons.append(f"adx_flat={adx_val:.1f}")

    if w_buy > 0 and w_sell > 0:
        conflict_ratio = min(w_buy, w_sell) / max(w_buy, w_sell)
        raw_conf *= (1.0 - 0.45 * conflict_ratio)
        if conflict_ratio > 0.25:
            reasons.append(f"signal_conflict={conflict_ratio:.2f}")

    if votes:
        directional_votes = votes.get("BUY", 0) + votes.get("SELL", 0)
        if directional_votes > 0:
            vote_balance = abs(votes.get("BUY", 0) - votes.get("SELL", 0)) / directional_votes
            raw_conf *= (0.65 + 0.35 * vote_balance)
            if vote_balance < 0.34:
                reasons.append(f"vote_split={vote_balance:.2f}")

    if atr_val is not None and atr_avg is not None and atr_avg > 0:
        r = atr_val / atr_avg
        if r < 0.5:
            raw_conf *= max(0.4, r)
            reasons.append(f"low_atr={r:.2f}")

    raw_conf *= session_mult
    if session_mult < 1.0:
        reasons.append(f"session={session_mult:.2f}")

    return max(0, min(100, int(round(raw_conf)))), " | ".join(reasons) if reasons else "normal"


def compute_analysis_decision(
    raw_payload: Dict[str, Any],
    *,
    symbol: str,
    interval: str,
    allowed_indicators: Optional[List[str]] = None,
) -> Dict[str, Any]:
    allowed_indicators = allowed_indicators or []
    sym = _clean_symbol(symbol)
    interval_norm = _normalize_interval(interval)
    periods = raw_payload.get("periods_used") or _get_adv_periods(interval_norm)

    price_val = _clean_float(raw_payload.get("price"))
    if price_val is None:
        raise ValueError("price not found in raw payload")

    session = raw_payload.get("session") if isinstance(raw_payload.get("session"), dict) else {}
    sess_mult = _clean_float(session.get("multiplier")) or 1.0
    sess_reason = str(session.get("reason") or "normal")

    indicators = _extract_indicators_container(raw_payload)

    data_map = {
        "rsi": {"rsi": _to_num_or_field(_extract_obj(raw_payload, indicators, "RSI", "rsi"), "rsi")},
        "macd": {
            "macd": _to_num_or_field(_extract_obj(raw_payload, indicators, "MACD", "macd"), "macd"),
            "macd_signal": _to_num_or_field(_extract_obj(raw_payload, indicators, "MACD", "macd"), "macd_signal", "signal"),
        },
        "stoch": {
            "slow_k": _to_num_or_field(_extract_obj(raw_payload, indicators, "STOCH", "Stoch", "stoch"), "slow_k", "k"),
            "slow_d": _to_num_or_field(_extract_obj(raw_payload, indicators, "STOCH", "Stoch", "stoch"), "slow_d", "d"),
        },
        "bbands": {
            "lower_band": _to_num_or_field(_extract_obj(raw_payload, indicators, "BB", "bbands"), "lower_band", "lb"),
            "upper_band": _to_num_or_field(_extract_obj(raw_payload, indicators, "BB", "bbands"), "upper_band", "ub"),
        },
        "ema9": {"ema": _to_num_or_field(_extract_obj(raw_payload, indicators, "EMA9", "ema9"), "ema", "value")},
        "ema21": {"ema": _to_num_or_field(_extract_obj(raw_payload, indicators, "EMA21", "ema21"), "ema", "value")},
        "ema50": {"ema": _to_num_or_field(_extract_obj(raw_payload, indicators, "EMA50", "ema50"), "ema", "value")},
        "ema200": {"ema": _to_num_or_field(_extract_obj(raw_payload, indicators, "EMA200", "ema200"), "ema", "value")},
        "adx": {"adx": _to_num_or_field(_extract_obj(raw_payload, indicators, "ADX", "adx"), "adx")},
        "cci": {"cci": _to_num_or_field(_extract_obj(raw_payload, indicators, "CCI", "cci"), "cci")},
        "psar": {"psar": _to_num_or_field(_extract_obj(raw_payload, indicators, "PSAR", "psar"), "psar")},
        "plus_di": {"plus_di": _to_num_or_field(_extract_obj(raw_payload, indicators, "PLUS_DI", "plus_di"), "plus_di")},
        "minus_di": {"minus_di": _to_num_or_field(_extract_obj(raw_payload, indicators, "MINUS_DI", "minus_di"), "minus_di")},
        "supertrend": {"supertrend": _to_num_or_field(_extract_obj(raw_payload, indicators, "SUPERTREND", "supertrend"), "supertrend")},
        "ichimoku": _to_dict(_extract_obj(raw_payload, indicators, "ICHIMOKU", "ichimoku")),
        "pivot_points": _to_dict(_extract_obj(raw_payload, indicators, "PIVOTPOINTS", "PIVOT_POINTS_HL", "pivot_points")),
        "atr": {"atr": _to_num_or_field(_extract_obj(raw_payload, indicators, "ATR", "atr"), "atr")},
    }

    votes, details, w_buy, w_sell, w_neutral = _evaluate_rules(
        price_val,
        interval_norm,
        **data_map,
        allowed_indicators=allowed_indicators,
    )

    ohlc_data = _parse_ohlc(raw_payload)
    atr_raw = data_map["atr"].get("atr") or 0.001

    atr_avg = None
    if len(ohlc_data) >= 14:
        trs = _calc_recent_tr(ohlc_data, max_bars=50)
        if trs:
            atr_avg = sum(trs) / len(trs)

    fib_levels = {}
    if ohlc_data:
        fib_levels = _calculate_fibonacci_levels(ohlc_data, lookback=periods.get("fib_lookback", 50))
        fib_signal = _fibonacci_signal(price_val, fib_levels)
        allowed_upper = [a.upper() for a in allowed_indicators]
        is_fib_allowed = not allowed_upper or "FIBONACCI" in allowed_upper
        if is_fib_allowed and fib_levels:
            fib_w = _get_weight("Fibonacci", data_map["adx"].get("adx"))
            if interval_norm in ("5min", "15min"):
                fib_w *= 0.75
            details["Fibonacci"] = {"value": fib_levels, "signal": fib_signal, "weight": round(fib_w, 2)}
            votes[fib_signal] += 1
            if fib_signal == "BUY":
                w_buy += fib_w
            elif fib_signal == "SELL":
                w_sell += fib_w
            else:
                w_neutral += fib_w

    min_edge = MIN_WEIGHT_EDGE_BY_INTERVAL.get(interval_norm, 0.5)
    min_dir_votes = MIN_DIRECTIONAL_VOTES_BY_INTERVAL.get(interval_norm, 3)
    directional_votes = votes["BUY"] + votes["SELL"]

    final_sig = "NEUTRAL"
    if w_buy > w_sell and (w_buy - w_sell) > min_edge:
        final_sig = "BUY"
    elif w_sell > w_buy and (w_sell - w_buy) > min_edge:
        final_sig = "SELL"
    elif votes["BUY"] == votes["SELL"] and votes["BUY"] > 0 and data_map["ema200"].get("ema") is not None:
        final_sig = "BUY" if price_val > float(data_map["ema200"]["ema"]) else "SELL"

    votes_block_reason = ""
    if directional_votes < min_dir_votes and final_sig != "NEUTRAL":
        final_sig = "NEUTRAL"
        votes_block_reason = f"low_directional_votes={directional_votes}/{min_dir_votes}"

    microtrend_reason = ""
    adx_now = data_map["adx"].get("adx")
    apply_microtrend_filter = (
        interval_norm in ("5min", "15min")
        and final_sig in ("BUY", "SELL")
        and (adx_now is None or adx_now < ADX_TREND_THRESHOLD)
    )
    if apply_microtrend_filter:
        trend_checks = 0
        trend_passed = 0

        e9 = data_map["ema9"].get("ema")
        e21 = data_map["ema21"].get("ema")
        if e9 is not None and e21 is not None:
            trend_checks += 1
            if (final_sig == "BUY" and e9 > e21) or (final_sig == "SELL" and e9 < e21):
                trend_passed += 1

        e50 = data_map["ema50"].get("ema")
        if e50 is not None:
            trend_checks += 1
            if (final_sig == "BUY" and price_val > e50) or (final_sig == "SELL" and price_val < e50):
                trend_passed += 1

        st_val = data_map["supertrend"].get("supertrend")
        if st_val is not None:
            trend_checks += 1
            if (final_sig == "BUY" and price_val > st_val) or (final_sig == "SELL" and price_val < st_val):
                trend_passed += 1

        required = 2 if trend_checks >= 3 else (1 if trend_checks > 0 else 0)
        if required and trend_passed < required:
            final_sig = "NEUTRAL"
            microtrend_reason = f"microtrend_filter={trend_passed}/{required}"

    if final_sig in ("BUY", "SELL"):
        levels_dir = final_sig
    elif w_buy > w_sell:
        levels_dir = "BUY"
    elif w_sell > w_buy:
        levels_dir = "SELL"
    elif votes["BUY"] > votes["SELL"]:
        levels_dir = "BUY"
    elif votes["SELL"] > votes["BUY"]:
        levels_dir = "SELL"
    else:
        levels_dir = "NEUTRAL"

    key_levels = _calculate_key_levels(ohlc_data, price_val, atr_raw, levels_dir, interval_norm) if ohlc_data else {}

    confidence, conf_reason = _compute_confidence(
        w_buy,
        w_sell,
        w_neutral,
        data_map["adx"].get("adx"),
        sess_mult,
        atr_raw,
        atr_avg,
        votes,
    )
    min_conf = MIN_CONFIDENCE_BY_INTERVAL.get(interval_norm, MIN_CONFIDENCE_ADV)
    if confidence < min_conf and final_sig != "NEUTRAL":
        final_sig = "NEUTRAL"
        conf_reason += f" | below_min_confidence={min_conf}"
    if votes_block_reason:
        conf_reason = f"{conf_reason} | {votes_block_reason}" if conf_reason else votes_block_reason
    if microtrend_reason:
        conf_reason = f"{conf_reason} | {microtrend_reason}" if conf_reason else microtrend_reason

    return {
        "ok": True,
        "symbol": sym,
        "interval": interval_norm,
        "price": price_val,
        "recommendation": final_sig,
        "confidence": confidence,
        "votes": votes,
        "weighted_scores": {"buy": round(w_buy, 3), "sell": round(w_sell, 3), "neutral": round(w_neutral, 3)},
        "indicators": details,
        "key_levels": key_levels,
        "fibonacci": fib_levels or None,
        "session": {"multiplier": sess_mult, "reason": sess_reason},
        "periods_used": periods,
        "confidence_reason": conf_reason,
        "fetched_at": utc_iso(),
    }
