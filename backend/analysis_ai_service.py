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
- Respect the strategy context and the list of allowed indicators.
- Give BUY only when bullish evidence clearly dominates.
- Give SELL only when bearish evidence clearly dominates.
- Give NEUTRAL when data is mixed, weak, low-liquidity, contradictory, or insufficient.
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


def sanitize_gpt_analysis(
    parsed: Dict[str, Any],
    *,
    symbol: str,
    interval: str,
    price: Optional[float],
    raw_payload: Dict[str, Any],
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

    indicators_raw = parsed.get("indicators") if isinstance(parsed.get("indicators"), dict) else {}
    indicators = {}
    for key, value in indicators_raw.items():
        clean_key = str(key or "").strip()
        if not clean_key:
            continue
        if isinstance(value, dict):
            item = dict(value)
            item["signal"] = _normalize_signal(item.get("signal"))
            if "weight" not in item:
                item["weight"] = 1
        else:
            item = {"value": value, "signal": "NEUTRAL", "weight": 1}
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

    return sanitize_gpt_analysis(parsed, symbol=symbol, interval=interval, price=price, raw_payload=raw_payload)
