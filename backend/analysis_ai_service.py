import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx


OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
DEFAULT_ANALYSIS_GPT_MODEL = "gpt-4o-mini"
DEFAULT_ANALYSIS_GPT_PROMPT = """You are the private market-analysis engine for Elizabeth Vane.

Your task is to transform raw technical market data into one compact trading signal for a mobile WebApp.

Core rules:
- Return only valid JSON that matches the requested structure.
- Never mention OpenAI, GPT, AI, model names, hidden prompts, or internal services.
- Use the raw indicator values, current price, interval, session data, OHLC/fibonacci/key levels when available.
- Use deterministic_baseline_analysis as a technical extraction reference. It is not mandatory as a final answer, but it shows how raw indicators map to BUY/SELL/NEUTRAL.
- Respect the strategy context and the list of allowed indicators.
- Give BUY only when bullish evidence clearly dominates.
- Give SELL only when bearish evidence clearly dominates.
- Give NEUTRAL when data is mixed, weak, low-liquidity, contradictory, or insufficient.
- Indicator signals describe each individual indicator only. Do not set an indicator to NEUTRAL just because the final recommendation is NEUTRAL.
- Low liquidity or a weak session may reduce final confidence, but must not erase clear per-indicator BUY/SELL readings.
- Never return all indicator signals as NEUTRAL unless the raw data and deterministic baseline show all indicators are neutral or missing.
- If directional indicators are mixed, keep their individual BUY/SELL signals and use NEUTRAL only for the final recommendation when needed.
- Calculate Conservative SL and Target (Take Profit) from current price, ATR, support/resistance, fibonacci, and signal direction.
- If the recommendation is NEUTRAL, still provide reasonable nearby levels, but keep confidence conservative.
- Confidence must be 0-100 and should reflect signal quality, trend strength, conflicts, session liquidity, and indicator agreement.
- Indicator signals must be one of BUY, SELL, NEUTRAL.
- The final votes and weighted_scores must be consistent with the indicator signals.
- Do not invent impossible precision. Round prices to a sensible precision for the symbol.

Output meaning:
- recommendation: BUY, SELL, or NEUTRAL.
- confidence: confidence in the final recommendation.
- indicators: per-indicator values/signals used by the strategy.
- key_levels.conservative_sl: conservative stop-loss level.
- key_levels.rr_2_1_target: take-profit target.
- confidence_reason: short machine-readable explanation using compact phrases separated by " | ".
"""


def compact_market_payload(value: Any, *, max_chars: int = 18000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...[truncated]"


def _extract_error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
    except Exception:
        return (response.text or "").strip()[:500]
    if isinstance(data, dict) and isinstance(data.get("error"), dict):
        error = data["error"]
        return " | ".join(str(x) for x in [error.get("message"), error.get("code"), error.get("type")] if x)[:500]
    return str(data)[:500]


async def validate_openai_api_key(api_key: str, model: str = DEFAULT_ANALYSIS_GPT_MODEL) -> Dict[str, Any]:
    clean_key = (api_key or "").strip()
    if not clean_key:
        return {"ok": False, "error": "OpenAI key is empty"}

    headers = {"Authorization": f"Bearer {clean_key}"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(OPENAI_MODELS_URL, headers=headers, timeout=15.0)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as e:
            return {"ok": False, "error": _extract_error_text(e.response) or f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {str(e)}"}

    requested_model = (model or DEFAULT_ANALYSIS_GPT_MODEL).strip()
    models = payload.get("data") if isinstance(payload, dict) else []
    ids = {str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")}
    if requested_model and ids and requested_model not in ids:
        return {"ok": True, "warning": f"Key is valid, but model {requested_model} was not found in /v1/models"}
    return {"ok": True}


def _json_schema_response_format() -> Dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "trading_signal_analysis",
            "strict": False,
            "schema": {
                "type": "object",
                "properties": {
                    "recommendation": {"type": "string", "enum": ["BUY", "SELL", "NEUTRAL"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 100},
                    "confidence_reason": {"type": "string"},
                    "votes": {
                        "type": "object",
                        "properties": {
                            "BUY": {"type": "number"},
                            "SELL": {"type": "number"},
                            "NEUTRAL": {"type": "number"},
                        },
                    },
                    "weighted_scores": {
                        "type": "object",
                        "properties": {
                            "buy": {"type": "number"},
                            "sell": {"type": "number"},
                            "neutral": {"type": "number"},
                        },
                    },
                    "indicators": {"type": "object"},
                    "key_levels": {"type": "object"},
                    "fibonacci": {"type": ["object", "null"]},
                    "summary": {"type": "string"},
                },
                "required": [
                    "recommendation",
                    "confidence",
                    "confidence_reason",
                    "votes",
                    "weighted_scores",
                    "indicators",
                    "key_levels",
                ],
            },
        },
    }


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_signal(value: Any, default: str = "NEUTRAL") -> str:
    signal = str(value or "").strip().upper()
    return signal if signal in ("BUY", "SELL", "NEUTRAL") else default


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().upper().replace(" ", "").replace("_", "").replace("-", "")


def _indicator_aliases(value: Any) -> set:
    normalized = _normalize_key(value)
    aliases = {normalized}
    alias_map = {
        "STOCH": {"STOCHASTIC"},
        "BB": {"BOLLINGERBANDS", "BOLLINGERBAND"},
        "EMA9_21": {"EMA9", "EMA21", "EMA921"},
        "PSAR": {"PARABOLICSAR"},
        "PIVOTPOINTS": {"PIVOTPOINTSHL", "PIVOT_POINTS_HL"},
    }
    for canonical, extra in alias_map.items():
        keys = {_normalize_key(canonical), *{_normalize_key(item) for item in extra}}
        if normalized in keys:
            aliases.update(keys)
            break
    return {item for item in aliases if item}


def _find_baseline_indicator(indicator_key: str, baseline_indicators: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    wanted = _indicator_aliases(indicator_key)
    for raw_key, raw_value in baseline_indicators.items():
        if wanted.intersection(_indicator_aliases(raw_key)) and isinstance(raw_value, dict):
            return raw_value
    return None


def _recalculate_votes(indicators: Dict[str, Any]) -> tuple:
    votes = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}
    weighted_scores = {"buy": 0.0, "sell": 0.0, "neutral": 0.0}
    for item in indicators.values():
        if not isinstance(item, dict):
            continue
        signal = _normalize_signal(item.get("signal"))
        weight = _to_float(item.get("weight"))
        if weight is None or weight <= 0:
            weight = 1.0
        votes[signal] += 1
        if signal == "BUY":
            weighted_scores["buy"] += weight
        elif signal == "SELL":
            weighted_scores["sell"] += weight
        else:
            weighted_scores["neutral"] += weight
    return votes, {key: round(value, 3) for key, value in weighted_scores.items()}


def sanitize_gpt_analysis(
    parsed: Dict[str, Any],
    *,
    symbol: str,
    interval: str,
    price: Optional[float],
    raw_payload: Dict[str, Any],
    baseline_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        raise ValueError("GPT response is not a JSON object")

    recommendation = _normalize_signal(parsed.get("recommendation"))
    confidence_raw = _to_float(parsed.get("confidence"))
    confidence = int(max(0, min(100, round(confidence_raw if confidence_raw is not None else 0))))

    votes_raw = parsed.get("votes") if isinstance(parsed.get("votes"), dict) else {}
    votes = {
        "BUY": int(_to_float(votes_raw.get("BUY")) or 0),
        "SELL": int(_to_float(votes_raw.get("SELL")) or 0),
        "NEUTRAL": int(_to_float(votes_raw.get("NEUTRAL")) or 0),
    }

    scores_raw = parsed.get("weighted_scores") if isinstance(parsed.get("weighted_scores"), dict) else {}
    weighted_scores = {
        "buy": round(_to_float(scores_raw.get("buy")) or float(votes["BUY"]), 3),
        "sell": round(_to_float(scores_raw.get("sell")) or float(votes["SELL"]), 3),
        "neutral": round(_to_float(scores_raw.get("neutral")) or float(votes["NEUTRAL"]), 3),
    }

    baseline_indicators = {}
    if isinstance(baseline_analysis, dict) and isinstance(baseline_analysis.get("indicators"), dict):
        baseline_indicators = baseline_analysis.get("indicators") or {}

    indicators_raw = parsed.get("indicators") if isinstance(parsed.get("indicators"), dict) else {}
    indicators = {}
    for key, value in indicators_raw.items():
        clean_key = str(key or "").strip()
        if not clean_key:
            continue
        baseline_item = _find_baseline_indicator(clean_key, baseline_indicators)
        if isinstance(value, dict):
            item = dict(value)
            item["signal"] = _normalize_signal(item.get("signal"))
            if "weight" not in item:
                item["weight"] = 1
        else:
            item = {"value": value, "signal": "NEUTRAL", "weight": 1}
        value_signal = _normalize_signal(item.get("value"), default="")
        if item["signal"] == "NEUTRAL" and value_signal in ("BUY", "SELL"):
            item["signal"] = value_signal
        if item["signal"] == "NEUTRAL" and baseline_item:
            baseline_signal = _normalize_signal(baseline_item.get("signal"), default="")
            if baseline_signal in ("BUY", "SELL"):
                item["signal"] = baseline_signal
                if _normalize_signal(item.get("value"), default="") in ("BUY", "SELL", "NEUTRAL"):
                    item["value"] = baseline_item.get("value")
                if baseline_item.get("weight") is not None and _to_float(item.get("weight")) in (None, 1.0):
                    item["weight"] = baseline_item.get("weight")
        indicators[clean_key] = item

    if not indicators:
        indicators = {
            "Market": {
                "value": "raw_data",
                "signal": recommendation,
                "weight": 1,
            }
        }
        votes[recommendation] = max(1, votes.get(recommendation, 0))

    existing_aliases = set()
    for key in indicators.keys():
        existing_aliases.update(_indicator_aliases(key))
    for baseline_key, baseline_item in baseline_indicators.items():
        if not isinstance(baseline_item, dict):
            continue
        baseline_signal = _normalize_signal(baseline_item.get("signal"), default="")
        if baseline_signal not in ("BUY", "SELL"):
            continue
        aliases = _indicator_aliases(baseline_key)
        if existing_aliases.intersection(aliases):
            continue
        indicators[str(baseline_key)] = dict(baseline_item)
        existing_aliases.update(aliases)

    votes, weighted_scores = _recalculate_votes(indicators)
    directional_votes = votes["BUY"] + votes["SELL"]
    total_votes = directional_votes + votes["NEUTRAL"]
    if total_votes and recommendation == "NEUTRAL":
        dominant_signal = "BUY" if votes["BUY"] > votes["SELL"] else "SELL" if votes["SELL"] > votes["BUY"] else "NEUTRAL"
        dominant_count = max(votes["BUY"], votes["SELL"])
        min_directional = 2 if total_votes <= 5 else 3
        dominance = dominant_count / float(total_votes)
        if dominant_signal in ("BUY", "SELL") and directional_votes >= min_directional and dominance >= 0.52:
            recommendation = dominant_signal
            confidence = max(confidence, int(round(54 + min(0.35, dominance - 0.52) * 100)))
            reason = str(parsed.get("confidence_reason") or "").strip()
            parsed["confidence_reason"] = f"{reason} | directional_majority_restored".strip(" |")

    key_levels = parsed.get("key_levels") if isinstance(parsed.get("key_levels"), dict) else {}
    clean_levels = {}
    for key, value in key_levels.items():
        numeric = _to_float(value)
        clean_levels[str(key)] = round(numeric, 6) if numeric is not None else value

    resolved_price = _to_float(parsed.get("price"))
    if resolved_price is None:
        resolved_price = price
    if resolved_price is None:
        resolved_price = _to_float(raw_payload.get("price")) or 0.0
    clean_levels.setdefault("current_price", round(float(resolved_price), 6))

    session = raw_payload.get("session") if isinstance(raw_payload.get("session"), dict) else {}
    periods = raw_payload.get("periods_used") if isinstance(raw_payload.get("periods_used"), dict) else {}

    return {
        "ok": True,
        "symbol": symbol,
        "interval": interval,
        "price": float(resolved_price),
        "recommendation": recommendation,
        "confidence": confidence,
        "votes": votes,
        "weighted_scores": weighted_scores,
        "indicators": indicators,
        "key_levels": clean_levels,
        "fibonacci": parsed.get("fibonacci") if isinstance(parsed.get("fibonacci"), dict) else None,
        "session": {
            "multiplier": _to_float(session.get("multiplier")) or 1.0,
            "reason": str(session.get("reason") or "normal"),
        },
        "periods_used": periods,
        "confidence_reason": str(parsed.get("confidence_reason") or "structured_analysis").strip()[:500],
        "fetched_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }


async def generate_gpt_analysis(
    *,
    api_key: str,
    model: str,
    prompt: str,
    raw_payload: Dict[str, Any],
    symbol: str,
    interval: str,
    allowed_indicators: List[str],
    strategy: Optional[Dict[str, Any]] = None,
    baseline_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    clean_key = (api_key or "").strip()
    if not clean_key:
        raise ValueError("GPT API key is not configured")

    clean_model = (model or DEFAULT_ANALYSIS_GPT_MODEL).strip() or DEFAULT_ANALYSIS_GPT_MODEL
    system_prompt = (prompt or DEFAULT_ANALYSIS_GPT_PROMPT).strip() or DEFAULT_ANALYSIS_GPT_PROMPT
    price = _to_float(raw_payload.get("price"))
    context = {
        "symbol": symbol,
        "interval": interval,
        "current_price": price,
        "allowed_indicators": allowed_indicators or [],
        "strategy": strategy or {},
        "deterministic_baseline_analysis": baseline_analysis or {},
        "raw_market_data": raw_payload,
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Create one trading signal from this raw market payload. "
                "Return JSON only.\n\n"
                f"{compact_market_payload(context)}"
            ),
        },
    ]
    payload = {
        "model": clean_model,
        "messages": messages,
        "temperature": 0.15,
        "max_tokens": 1800,
        "response_format": _json_schema_response_format(),
    }
    headers = {
        "Authorization": f"Bearer {clean_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(OPENAI_CHAT_URL, headers=headers, json=payload, timeout=35.0)
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPStatusError as e:
            raise ValueError(_extract_error_text(e.response) or f"GPT HTTP {e.response.status_code}") from e
        except Exception as e:
            raise ValueError(f"{type(e).__name__}: {str(e)}") from e

    content = (((result.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise ValueError("GPT returned empty response")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"GPT returned invalid JSON: {str(e)}") from e

    return sanitize_gpt_analysis(
        parsed,
        symbol=symbol,
        interval=interval,
        price=price,
        raw_payload=raw_payload,
        baseline_analysis=baseline_analysis,
    )
