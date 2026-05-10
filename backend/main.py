import os
import asyncio
import aiomysql
import httpx
import json
import secrets
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BotCommand
from dotenv import load_dotenv
import uvicorn
import ai_service
import analysis_ai_service
from pydantic import BaseModel
from typing import Optional
from analysis_engine import compute_analysis_decision
try:
    from backend.telegram_auth import get_telegram_user
except ModuleNotFoundError:
    from telegram_auth import get_telegram_user
try:
    from backend.db_bootstrap import ensure_database_schema
except ModuleNotFoundError:
    from db_bootstrap import ensure_database_schema

load_dotenv()

def get_env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        print(f"[Config] Invalid {name}={raw!r}, fallback to {default}")
        return default
    if not (1 <= value <= 65535):
        print(f"[Config] {name} out of range ({value}), fallback to {default}")
        return default
    return value

API_HOST = (os.getenv("API_HOST") or "0.0.0.0").strip() or "0.0.0.0"
API_PORT = get_env_int("API_PORT", 8000)
ALLOWED_STRATEGY_TIMEFRAMES = ("1m", "3m", "5m", "10m", "15m", "30m", "1h", "4h", "1d")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "db": os.getenv("DB_NAME"),
    "autocommit": True
}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db_pool = None
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
menu_photo_file_id = (os.getenv("MENU_PHOTO_FILE_ID") or "").strip()
menu_file_id_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media", "menu.file_id")
if not menu_photo_file_id and os.path.exists(menu_file_id_path):
    try:
        with open(menu_file_id_path, "r", encoding="utf-8") as f:
            menu_photo_file_id = f.read().strip()
    except Exception:
        menu_photo_file_id = ""
admin_panel_token = (os.getenv("ADMIN_PANEL_TOKEN") or "").strip()
admin_token_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media", "admin.token")
if not admin_panel_token and os.path.exists(admin_token_file_path):
    try:
        with open(admin_token_file_path, "r", encoding="utf-8") as f:
            admin_panel_token = f.read().strip()
    except Exception:
        admin_panel_token = ""

analysis_queue = asyncio.Queue()
processing_ids = set() 
price_cache = {} 

COMMODITY_SYMBOLS = ["HG1", "W_1", "C_1", "S_1", "KC1", "CC1", "SB1", "CT1"]


def resolve_menu_photo_path() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "media", "menu.jpg"),
        os.path.join(base_dir, "media", "menu.png"),
        os.path.join(base_dir, "..", "backend", "media", "menu.jpg"),
        os.path.join(base_dir, "..", "backend", "media", "menu.png"),
        os.path.join("media", "menu.jpg"),
        os.path.join("media", "menu.png"),
        os.path.join("backend", "media", "menu.jpg"),
        os.path.join("backend", "media", "menu.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def get_admin_panel_token() -> str:
    global admin_panel_token
    if admin_panel_token:
        return admin_panel_token
    admin_panel_token = secrets.token_urlsafe(32)
    try:
        os.makedirs(os.path.dirname(admin_token_file_path), exist_ok=True)
        with open(admin_token_file_path, "w", encoding="utf-8") as f:
            f.write(admin_panel_token)
    except Exception:
        pass
    return admin_panel_token


def build_admin_webapp_url() -> str:
    base_url = ((os.getenv("WEB_APP_URL") or "").strip() or "").rstrip("/")
    token = get_admin_panel_token()
    if not base_url:
        return f"/admin/{token}"
    return f"{base_url}/admin/{token}"


async def is_admin_user(user_id: int) -> bool:
    if not db_pool:
        return False
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id
                FROM admin_users
                WHERE user_id = %s AND is_active = 1
                LIMIT 1
                """,
                (user_id,),
            )
            row = await cur.fetchone()
    return bool(row)


async def get_admin_user(
    user=Depends(get_telegram_user),
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
):
    expected = get_admin_panel_token()
    provided = (x_admin_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Admin token is invalid")
    if not await is_admin_user(int(user["user_id"])):
        raise HTTPException(status_code=403, detail="Admin access denied")
    return user


async def get_stream_settings_row():
    default_settings = {
        "is_enabled": 0,
        "scope": "all",
        "strategy_id": None,
        "forced_signal": "BUY",
        "levels_mode": "auto",
        "manual_conservative_sl": None,
        "manual_take_profit": None,
        "indicator_mode": "auto",
        "indicator_overrides": {},
        "message": "",
        "updated_at": None,
        "updated_by": None,
    }
    if not db_pool:
        return default_settings
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT
                    is_enabled,
                    scope,
                    strategy_id,
                    forced_signal,
                    levels_mode,
                    manual_conservative_sl,
                    manual_take_profit,
                    indicator_mode,
                    indicator_overrides,
                    message,
                    updated_at,
                    updated_by
                FROM admin_stream_settings
                WHERE id = 1
                LIMIT 1
                """
            )
            row = await cur.fetchone()
    if not row:
        return default_settings
    settings = {**default_settings, **row}
    settings["scope"] = str(settings.get("scope") or "all").strip().lower()
    if settings["scope"] not in ("all", "strategy"):
        settings["scope"] = "all"
    forced = str(settings.get("forced_signal") or "BUY").strip().upper()
    settings["forced_signal"] = forced if forced in ("BUY", "SELL") else "BUY"
    settings["is_enabled"] = 1 if int(settings.get("is_enabled") or 0) == 1 else 0
    levels_mode = str(settings.get("levels_mode") or "auto").strip().lower()
    settings["levels_mode"] = levels_mode if levels_mode in ("auto", "manual") else "auto"
    try:
        settings["manual_conservative_sl"] = (
            float(settings["manual_conservative_sl"]) if settings.get("manual_conservative_sl") is not None else None
        )
    except (TypeError, ValueError):
        settings["manual_conservative_sl"] = None
    try:
        settings["manual_take_profit"] = (
            float(settings["manual_take_profit"]) if settings.get("manual_take_profit") is not None else None
        )
    except (TypeError, ValueError):
        settings["manual_take_profit"] = None
    indicator_mode = str(settings.get("indicator_mode") or "auto").strip().lower()
    settings["indicator_mode"] = indicator_mode if indicator_mode in ("auto", "manual") else "auto"
    try:
        settings["strategy_id"] = int(settings["strategy_id"]) if settings.get("strategy_id") is not None else None
    except (TypeError, ValueError):
        settings["strategy_id"] = None
    overrides_raw = settings.get("indicator_overrides")
    if isinstance(overrides_raw, dict):
        parsed_overrides = overrides_raw
    elif isinstance(overrides_raw, str) and overrides_raw.strip():
        try:
            parsed_overrides = json.loads(overrides_raw)
        except Exception:
            parsed_overrides = {}
    else:
        parsed_overrides = {}
    if not isinstance(parsed_overrides, dict):
        parsed_overrides = {}
    normalized_overrides = {}
    for raw_key, raw_signal in parsed_overrides.items():
        key_norm = str(raw_key or "").strip().upper().replace(" ", "").replace("_", "").replace("-", "")
        if not key_norm:
            continue
        signal = str(raw_signal or "").strip().upper()
        if signal in ("BUY", "SELL", "NEUTRAL"):
            normalized_overrides[key_norm] = signal
    settings["indicator_overrides"] = normalized_overrides
    settings["message"] = str(settings.get("message") or "")
    return settings


async def resolve_stream_override(strategy_id: Optional[int]):
    settings = await get_stream_settings_row()
    if int(settings.get("is_enabled") or 0) != 1:
        return None
    scope = settings.get("scope") or "all"
    if scope == "all":
        return settings
    target_strategy_id = settings.get("strategy_id")
    if scope == "strategy" and target_strategy_id is not None and strategy_id is not None and int(target_strategy_id) == int(strategy_id):
        return settings
    return None


async def get_user_strategy_id(user_id: int) -> Optional[int]:
    if not db_pool:
        return None
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT strategy_id
                    FROM users
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = await cur.fetchone()
    except Exception:
        return None
    if not row:
        return None
    try:
        return int(row.get("strategy_id")) if row.get("strategy_id") is not None else None
    except (TypeError, ValueError):
        return None


async def get_admin_analysis_settings() -> dict:
    default_settings = {
        "engine": "backend",
        "gpt_api_key": "",
        "gpt_model": analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL,
        "gpt_prompt": analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT,
        "gpt_key_configured": 0,
        "updated_at": None,
        "updated_by": None,
    }
    if not db_pool:
        return default_settings
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT engine, gpt_api_key, gpt_model, gpt_prompt, updated_at, updated_by
                    FROM admin_analysis_settings
                    WHERE id = 1
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
    except Exception as e:
        print(f"Admin analysis settings fallback: {e}")
        return default_settings
    if not row:
        return default_settings
    engine = str(row.get("engine") or "backend").strip().lower()
    if engine not in ("backend", "gpt"):
        engine = "backend"
    return {
        "engine": engine,
        "gpt_api_key": str(row.get("gpt_api_key") or "").strip(),
        "gpt_model": str(row.get("gpt_model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL).strip()
        or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL,
        "gpt_prompt": str(row.get("gpt_prompt") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT).strip()
        or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT,
        "gpt_key_configured": 1 if str(row.get("gpt_api_key") or "").strip() else 0,
        "updated_at": row.get("updated_at"),
        "updated_by": row.get("updated_by"),
    }


async def get_strategy_context(strategy_id: Optional[int]) -> dict:
    if not db_pool or strategy_id is None:
        return {}
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT
                        p.id,
                        p.name,
                        p.icon,
                        p.allowed_timeframes,
                        GROUP_CONCAT(i.name ORDER BY i.id SEPARATOR ', ') AS indicators_list,
                        GROUP_CONCAT(i.`key` ORDER BY i.id SEPARATOR ',') AS indicator_keys
                    FROM presets p
                    LEFT JOIN preset_indicators pi ON pi.preset_id = p.id
                    LEFT JOIN indicators i ON i.id = pi.indicator_id
                    WHERE p.id = %s
                    GROUP BY p.id
                    LIMIT 1
                    """,
                    (int(strategy_id),),
                )
                row = await cur.fetchone()
    except Exception as e:
        print(f"Strategy context fallback: {e}")
        return {}
    return row or {}


def normalize_allowed_timeframes(raw_value) -> str:
    if isinstance(raw_value, list):
        candidates = [str(item or "").strip() for item in raw_value]
    else:
        candidates = [part.strip() for part in str(raw_value or "").split(",")]
    seen = set()
    normalized = []
    for timeframe in candidates:
        if timeframe in ALLOWED_STRATEGY_TIMEFRAMES and timeframe not in seen:
            seen.add(timeframe)
            normalized.append(timeframe)
    if not normalized:
        normalized = ["5m", "15m", "30m", "1h", "4h", "1d"]
    return ",".join(normalized)


def ensure_analysis_key_levels(analysis_data: dict, preferred_signal: Optional[str] = None) -> dict:
    if not isinstance(analysis_data, dict):
        return analysis_data

    def to_float_or_none(value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    key_levels = analysis_data.get("key_levels")
    if not isinstance(key_levels, dict):
        key_levels = {}
    indicators = analysis_data.get("indicators")
    if not isinstance(indicators, dict):
        indicators = {}

    current_price = to_float_or_none(analysis_data.get("price"))
    if current_price is None:
        current_price = to_float_or_none(key_levels.get("current_price"))
    if current_price is None:
        analysis_data["key_levels"] = key_levels
        return analysis_data
    key_levels["current_price"] = round(current_price, 5)

    current_signal = str(preferred_signal or analysis_data.get("recommendation") or "").strip().upper()
    if current_signal not in ("BUY", "SELL", "NEUTRAL"):
        current_signal = "NEUTRAL"

    sl_value = to_float_or_none(key_levels.get("conservative_sl"))
    tp_value = to_float_or_none(key_levels.get("rr_2_1_target"))
    support_level = to_float_or_none(key_levels.get("nearest_support"))
    resistance_level = to_float_or_none(key_levels.get("nearest_resistance"))

    atr_value = to_float_or_none(key_levels.get("atr_14"))
    if atr_value is None:
        atr_indicator = indicators.get("ATR")
        if isinstance(atr_indicator, dict):
            atr_source = atr_indicator.get("value")
            if isinstance(atr_source, dict):
                atr_source = atr_source.get("atr")
            atr_value = to_float_or_none(atr_source)
        elif isinstance(atr_indicator, (int, float, str)):
            atr_value = to_float_or_none(atr_indicator)

    abs_price = abs(current_price)
    atr_abs = abs(float(atr_value)) if atr_value is not None else 0.0
    sl_step = max(atr_abs * 1.25, abs_price * 0.0008, 0.0001)
    tp_step = max(atr_abs * 2.0, abs_price * 0.0016, 0.0002)

    support_ok = support_level is not None and support_level < current_price
    resistance_ok = resistance_level is not None and resistance_level > current_price

    if sl_value is None:
        if current_signal == "BUY":
            sl_value = support_level if support_ok else current_price - sl_step
        elif current_signal == "SELL":
            sl_value = resistance_level if resistance_ok else current_price + sl_step
        else:
            sl_value = support_level if support_ok else current_price - sl_step
        key_levels["conservative_sl"] = round(sl_value, 5)

    if tp_value is None:
        if current_signal == "BUY":
            tp_value = resistance_level if resistance_ok else current_price + tp_step
        elif current_signal == "SELL":
            tp_value = support_level if support_ok else current_price - tp_step
        else:
            tp_value = resistance_level if resistance_ok else current_price + tp_step
        key_levels["rr_2_1_target"] = round(tp_value, 5)

    analysis_data["key_levels"] = key_levels
    return analysis_data


def apply_stream_override_to_analysis(analysis_data: dict, stream_settings: dict) -> dict:
    if not isinstance(analysis_data, dict):
        return analysis_data
    forced_signal = str(stream_settings.get("forced_signal") or "").upper()
    if forced_signal not in ("BUY", "SELL"):
        return analysis_data

    def normalize_alias(value: str) -> str:
        return str(value or "").strip().upper().replace(" ", "").replace("_", "").replace("-", "")

    alias_map = {
        "RSI": ["RSI"],
        "MACD": ["MACD"],
        "STOCH": ["STOCH", "STOCHASTIC"],
        "BB": ["BB", "BOLLINGERBANDS", "BOLLINGERBAND"],
        "EMA9_21": ["EMA9", "EMA21", "EMA921"],
        "EMA50": ["EMA50"],
        "EMA200": ["EMA200"],
        "ADX": ["ADX"],
        "CCI": ["CCI"],
        "PSAR": ["PSAR", "PARABOLICSAR"],
        "DMI": ["DMI"],
        "SUPERTREND": ["SUPERTREND"],
        "ICHIMOKU": ["ICHIMOKU"],
        "PIVOTPOINTS": ["PIVOTPOINTS", "PIVOTPOINTSHL"],
        "ATR": ["ATR"],
        "FIBONACCI": ["FIBONACCI"],
    }

    def aliases_for_indicator(indicator_name: str):
        base = normalize_alias(indicator_name)
        aliases = {base}
        for map_key, candidates in alias_map.items():
            if base == normalize_alias(map_key):
                aliases.update(normalize_alias(item) for item in candidates)
                return aliases
        return aliases

    stream_scope = str(stream_settings.get("scope") or "all").strip().lower()
    indicator_mode = str(stream_settings.get("indicator_mode") or "auto").strip().lower()
    manual_overrides = stream_settings.get("indicator_overrides") or {}
    if not isinstance(manual_overrides, dict):
        manual_overrides = {}
    if indicator_mode != "manual" or stream_scope != "strategy":
        manual_overrides = {}

    indicators = analysis_data.get("indicators")
    votes = {"BUY": 0, "SELL": 0, "NEUTRAL": 0}
    weighted_scores = {"buy": 0.0, "sell": 0.0, "neutral": 0.0}

    if isinstance(indicators, dict):
        indicator_keys = list(indicators.keys())
        indicator_count = len(indicator_keys)

        locked_signals = {}
        for indicator_key in indicator_keys:
            for alias in aliases_for_indicator(indicator_key):
                manual_signal = str(manual_overrides.get(alias) or "").strip().upper()
                if manual_signal in ("BUY", "SELL", "NEUTRAL"):
                    locked_signals[indicator_key] = manual_signal
                    break

        opposite_signal = "SELL" if forced_signal == "BUY" else "BUY"
        forced_locked = sum(1 for signal in locked_signals.values() if signal == forced_signal)
        remaining_keys = [key for key in indicator_keys if key not in locked_signals]
        remaining_count = len(remaining_keys)

        if indicator_count <= 1:
            target_forced = indicator_count
        else:
            required_majority = (indicator_count // 2) + 1
            min_target = max(required_majority, int(indicator_count * 0.56))
            max_target = max(min_target, int(indicator_count * 0.78))
            max_possible_forced = forced_locked + remaining_count
            if max_possible_forced <= min_target:
                target_forced = max_possible_forced
            else:
                target_forced = random.randint(min_target, min(max_target, max_possible_forced))

        forced_from_remaining = max(0, target_forced - forced_locked)
        forced_from_remaining = min(forced_from_remaining, remaining_count)
        non_majority_count = max(0, remaining_count - forced_from_remaining)
        neutral_count = 0
        opposite_count = 0
        if non_majority_count > 0:
            neutral_count = random.randint(0, non_majority_count)
            opposite_count = non_majority_count - neutral_count

            if non_majority_count >= 2 and opposite_count == 0:
                opposite_count = 1
                neutral_count = non_majority_count - opposite_count

        generated_signals = (
            [forced_signal] * forced_from_remaining
            + ["NEUTRAL"] * neutral_count
            + [opposite_signal] * opposite_count
        )
        random.shuffle(generated_signals)
        generated_by_key = {}
        for idx, indicator_key in enumerate(remaining_keys):
            generated_by_key[indicator_key] = generated_signals[idx] if idx < len(generated_signals) else forced_signal

        for indicator_key in indicator_keys:
            indicator_data = indicators.get(indicator_key)
            if isinstance(indicator_data, dict):
                signal = locked_signals.get(indicator_key) or generated_by_key.get(indicator_key) or forced_signal
                indicator_data["signal"] = signal
                votes[signal] = votes.get(signal, 0) + 1
    else:
        indicator_count = 0

    if indicator_count <= 0:
        votes[forced_signal] = 1
        indicator_count = 1

    weighted_scores["buy"] = float(votes["BUY"])
    weighted_scores["sell"] = float(votes["SELL"])
    weighted_scores["neutral"] = float(votes["NEUTRAL"])

    majority_share = (votes[forced_signal] / float(indicator_count)) if indicator_count else 1.0
    confidence = int(round(58 + majority_share * 28 + random.uniform(-3.5, 3.5)))
    confidence = max(55, min(92, confidence))

    analysis_data["recommendation"] = forced_signal
    analysis_data["votes"] = votes
    analysis_data["weighted_scores"] = weighted_scores
    analysis_data["confidence"] = confidence

    levels_mode = str(stream_settings.get("levels_mode") or "auto").strip().lower()
    key_levels = analysis_data.get("key_levels")
    if not isinstance(key_levels, dict):
        key_levels = {}

    price_raw = analysis_data.get("price", key_levels.get("current_price"))
    try:
        current_price = float(price_raw) if price_raw is not None else None
    except (TypeError, ValueError):
        current_price = None
    if current_price is not None:
        key_levels["current_price"] = round(current_price, 5)

    if levels_mode == "manual":
        raw_sl = stream_settings.get("manual_conservative_sl")
        raw_tp = stream_settings.get("manual_take_profit")
        try:
            manual_sl = float(raw_sl) if raw_sl is not None else None
        except (TypeError, ValueError):
            manual_sl = None
        try:
            manual_tp = float(raw_tp) if raw_tp is not None else None
        except (TypeError, ValueError):
            manual_tp = None
        if manual_sl is not None:
            key_levels["conservative_sl"] = round(manual_sl, 5)
        if manual_tp is not None:
            key_levels["rr_2_1_target"] = round(manual_tp, 5)

    sl_missing = key_levels.get("conservative_sl") in (None, "")
    tp_missing = key_levels.get("rr_2_1_target") in (None, "")
    if current_price is not None and (sl_missing or tp_missing):
        atr_value = None
        if isinstance(indicators, dict):
            atr_indicator = indicators.get("ATR")
            if isinstance(atr_indicator, dict):
                atr_source = atr_indicator.get("value")
                if isinstance(atr_source, dict):
                    atr_source = atr_source.get("atr")
                try:
                    atr_value = float(atr_source) if atr_source is not None else None
                except (TypeError, ValueError):
                    atr_value = None
            elif isinstance(atr_indicator, (int, float)):
                atr_value = float(atr_indicator)

        abs_price = abs(current_price)
        atr_abs = abs(float(atr_value)) if atr_value is not None else 0.0
        sl_step = max(atr_abs * 1.25, abs_price * 0.0008, 0.0001)
        tp_step = max(atr_abs * 2.0, abs_price * 0.0016, 0.0002)

        if forced_signal == "BUY":
            auto_sl = current_price - sl_step
            auto_tp = current_price + tp_step
        else:
            auto_sl = current_price + sl_step
            auto_tp = current_price - tp_step

        if sl_missing:
            key_levels["conservative_sl"] = round(auto_sl, 5)
        if tp_missing:
            key_levels["rr_2_1_target"] = round(auto_tp, 5)

    analysis_data["key_levels"] = key_levels

    analysis_data["confidence_reason"] = "admin_stream_override"
    analysis_data["stream_override"] = {
        "active": True,
        "scope": stream_settings.get("scope") or "all",
        "strategy_id": stream_settings.get("strategy_id"),
        "forced_signal": forced_signal,
        "levels_mode": levels_mode,
        "manual_conservative_sl": stream_settings.get("manual_conservative_sl"),
        "manual_take_profit": stream_settings.get("manual_take_profit"),
        "indicator_mode": stream_settings.get("indicator_mode") or "auto",
        "indicator_overrides": manual_overrides if manual_overrides else {},
        "message": stream_settings.get("message") or "",
    }
    return ensure_analysis_key_levels(analysis_data, preferred_signal=forced_signal)

@app.get("/api/support/links")
async def get_support_links():
    channel_url = (os.getenv("CHANNEL_URL") or "").strip()
    support_url = (os.getenv("SUPPORT_URL") or "").strip()
    return {
        "channel_url": channel_url,
        "support_url": support_url
    }

@app.get("/api/webapp/bot-info")
async def get_webapp_bot_info():
    bot_username = (os.getenv("BOT_USERNAME") or "").strip().lstrip("@")
    if not bot_username:
        try:
            me = await bot.get_me()
            bot_username = (me.username or "").strip()
        except Exception:
            bot_username = ""
    return {"bot_username": bot_username}


@app.get("/api/admin/me")
async def admin_me(admin=Depends(get_admin_user)):
    return {
        "status": "success",
        "user": {
            "user_id": int(admin["user_id"]),
            "username": admin.get("username") or "",
            "first_name": admin.get("first_name") or "",
        },
    }


@app.get("/api/admin/stats")
async def admin_stats(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    admin=Depends(get_admin_user),
):
    async def safe_count(cur, sql: str) -> int:
        try:
            await cur.execute(sql)
            return int((await cur.fetchone() or {}).get("cnt") or 0)
        except Exception:
            return 0

    from_dt = None
    to_dt = None
    if date_from:
        try:
            from_dt = datetime.strptime(date_from.strip(), "%Y-%m-%d")
        except Exception:
            from_dt = None
    if date_to:
        try:
            to_dt = datetime.strptime(date_to.strip(), "%Y-%m-%d")
        except Exception:
            to_dt = None
    if not to_dt:
        to_dt = datetime.utcnow()
    if not from_dt:
        from_dt = to_dt - timedelta(days=6)
    if from_dt > to_dt:
        from_dt, to_dt = to_dt, from_dt

    from_date = from_dt.strftime("%Y-%m-%d")
    to_date = to_dt.strftime("%Y-%m-%d")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            users_total = await safe_count(cur, "SELECT COUNT(*) AS cnt FROM users")
            admins_total = await safe_count(cur, "SELECT COUNT(*) AS cnt FROM admin_users WHERE is_active = 1")
            active_analyses = await safe_count(cur, "SELECT COUNT(*) AS cnt FROM user_analyses WHERE status = 'active'")
            chats_total = await safe_count(cur, "SELECT COUNT(*) AS cnt FROM ai_chats")

            mode_breakdown = {}
            try:
                await cur.execute(
                    """
                    SELECT mode, COUNT(*) AS cnt
                    FROM users
                    GROUP BY mode
                    """
                )
                modes_rows = await cur.fetchall()
                mode_breakdown = {row["mode"]: int(row["cnt"]) for row in (modes_rows or []) if row.get("mode")}
            except Exception:
                mode_breakdown = {}

            users_growth = []
            try:
                await cur.execute(
                    """
                    SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                    FROM users
                    WHERE DATE(created_at) BETWEEN %s AND %s
                    GROUP BY DATE(created_at)
                    ORDER BY d ASC
                    """,
                    (from_date, to_date),
                )
                growth_rows = await cur.fetchall()
                users_growth = [{"date": str(row["d"]), "count": int(row["cnt"])} for row in (growth_rows or [])]
            except Exception:
                users_growth = []

            users_by_day = []
            try:
                await cur.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM users
                    WHERE DATE(created_at) < %s
                    """,
                    (from_date,),
                )
                base_total = int((await cur.fetchone() or {}).get("cnt") or 0)

                await cur.execute(
                    """
                    SELECT DATE(created_at) AS d, COUNT(*) AS cnt
                    FROM users
                    WHERE DATE(created_at) BETWEEN %s AND %s
                    GROUP BY DATE(created_at)
                    ORDER BY d ASC
                    """,
                    (from_date, to_date),
                )
                daily_rows = await cur.fetchall()
                daily_map = {str(row["d"]): int(row["cnt"]) for row in (daily_rows or [])}

                day_cursor = from_dt.date()
                day_end = to_dt.date()
                running_total = base_total
                while day_cursor <= day_end:
                    day_iso = day_cursor.isoformat()
                    new_count = int(daily_map.get(day_iso, 0))
                    running_total += new_count
                    users_by_day.append(
                        {
                            "date": day_iso,
                            "new": new_count,
                            "total": running_total,
                        }
                    )
                    day_cursor += timedelta(days=1)
            except Exception:
                users_by_day = []

    return {
        "status": "success",
        "stats": {
            "users_total": users_total,
            "admins_total": admins_total,
            "active_analyses": active_analyses,
            "chats_total": chats_total,
            "mode_breakdown": mode_breakdown,
            "users_growth_7d": users_growth,
            "users_by_day": users_by_day,
            "users_growth_period": {
                "from": from_date,
                "to": to_date,
            },
        },
    }


@app.get("/api/admin/users")
async def admin_users(limit: int = 50, offset: int = 0, search: str = "", admin=Depends(get_admin_user)):
    limit = max(1, min(int(limit), 300))
    offset = max(0, int(offset))
    search = (search or "").strip()
    like = f"%{search}%"

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await cur.execute(
                    """
                    SELECT u.user_id, u.username, u.first_name, u.mode, u.lang, u.strategy_id, u.created_at,
                           p.name AS strategy_name,
                           CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
                           a.granted_at
                    FROM users u
                    LEFT JOIN presets p ON p.id = u.strategy_id
                    LEFT JOIN admin_users a ON a.user_id = u.user_id
                    WHERE (%s = '' OR CAST(u.user_id AS CHAR) LIKE %s OR COALESCE(u.username, '') LIKE %s OR COALESCE(u.first_name, '') LIKE %s)
                    ORDER BY u.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (search, like, like, like, limit, offset),
                )
                users_rows = await cur.fetchall()
            except Exception:
                await cur.execute(
                    """
                    SELECT u.user_id, u.username, u.first_name, u.mode, u.lang, u.strategy_id, NULL AS created_at,
                           p.name AS strategy_name,
                           CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
                           a.granted_at
                    FROM users u
                    LEFT JOIN presets p ON p.id = u.strategy_id
                    LEFT JOIN admin_users a ON a.user_id = u.user_id
                    WHERE (%s = '' OR CAST(u.user_id AS CHAR) LIKE %s OR COALESCE(u.username, '') LIKE %s OR COALESCE(u.first_name, '') LIKE %s)
                    ORDER BY u.user_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (search, like, like, like, limit, offset),
                )
                users_rows = await cur.fetchall()

            await cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM users u
                WHERE (%s = '' OR CAST(u.user_id AS CHAR) LIKE %s OR COALESCE(u.username, '') LIKE %s OR COALESCE(u.first_name, '') LIKE %s)
                """,
                (search, like, like, like),
            )
            total = int((await cur.fetchone() or {}).get("cnt") or 0)

    return {"status": "success", "users": users_rows or [], "total": total, "limit": limit, "offset": offset}


@app.get("/api/admin/admins")
async def admin_admins(admin=Depends(get_admin_user)):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT a.user_id, a.is_active, a.granted_at, a.granted_by,
                       u.username, u.first_name
                FROM admin_users a
                LEFT JOIN users u ON u.user_id = a.user_id
                WHERE a.is_active = 1
                ORDER BY a.granted_at DESC
                """
            )
            rows = await cur.fetchall()
    return {"status": "success", "admins": rows or []}


@app.post("/api/admin/admins/grant")
async def admin_grant(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    if not target_user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    granted_by = int(admin["user_id"])
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (target_user_id,),
            )
            user_row = await cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")

        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO admin_users (user_id, is_active, granted_by)
                VALUES (%s, 1, %s)
                ON DUPLICATE KEY UPDATE
                    is_active = 1,
                    granted_by = VALUES(granted_by),
                    granted_at = CURRENT_TIMESTAMP
                """,
                (target_user_id, granted_by),
            )
    return {"status": "success", "user_id": target_user_id}


@app.post("/api/admin/admins/revoke")
async def admin_revoke(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    if not target_user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    current_admin_id = int(admin["user_id"])
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id
                FROM admin_users
                WHERE user_id = %s AND is_active = 1
                LIMIT 1
                """,
                (target_user_id,),
            )
            existing_admin = await cur.fetchone()
            if not existing_admin:
                raise HTTPException(status_code=404, detail="Admin not found")

            await cur.execute("SELECT COUNT(*) AS cnt FROM admin_users WHERE is_active = 1")
            active_count = int((await cur.fetchone() or {}).get("cnt") or 0)
            if target_user_id == current_admin_id and active_count <= 1:
                raise HTTPException(status_code=400, detail="Cannot revoke the last active admin")

        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE admin_users
                SET is_active = 0
                WHERE user_id = %s
                """,
                (target_user_id,),
            )
    return {"status": "success", "user_id": target_user_id}


@app.post("/api/admin/broadcast")
async def admin_broadcast(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Broadcast text is required")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id FROM users ORDER BY user_id ASC")
            users_rows = await cur.fetchall()

    sent = 0
    failed = 0
    failed_samples = []
    for row in users_rows or []:
        uid = int(row["user_id"])
        try:
            await bot.send_message(uid, text, disable_web_page_preview=True)
            sent += 1
            await asyncio.sleep(0.035)
        except Exception as e:
            failed += 1
            if len(failed_samples) < 20:
                failed_samples.append({"user_id": uid, "error": str(e)})

    return {
        "status": "success",
        "result": {
            "total": len(users_rows or []),
            "sent": sent,
            "failed": failed,
            "failed_samples": failed_samples,
        },
    }


@app.get("/api/admin/settings")
async def admin_settings(admin=Depends(get_admin_user)):
    stream_settings = await get_stream_settings_row()
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, system_prompt, model, updated_at FROM ai_settings WHERE id = 1")
            ai_settings = await cur.fetchone()
            await cur.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.icon,
                    p.is_system,
                    p.allowed_timeframes,
                    GROUP_CONCAT(i.name ORDER BY i.id SEPARATOR ', ') AS indicators_list,
                    GROUP_CONCAT(i.`key` ORDER BY i.id SEPARATOR ',') AS indicator_keys
                FROM presets p
                LEFT JOIN preset_indicators pi ON pi.preset_id = p.id
                LEFT JOIN indicators i ON i.id = pi.indicator_id
                GROUP BY p.id
                ORDER BY p.is_system DESC, p.id ASC
                """
            )
            stream_strategies = await cur.fetchall()
    if not ai_settings:
        ai_settings = {"id": 1, "system_prompt": "You are a helpful trading assistant.", "model": "gpt-4o-mini", "updated_at": None}
    return {
        "status": "success",
        "settings": {
            "ai": ai_settings,
            "streams": stream_settings,
            "stream_strategies": stream_strategies or [],
            "support": {
                "channel_url": (os.getenv("CHANNEL_URL") or "").strip(),
                "support_url": (os.getenv("SUPPORT_URL") or "").strip(),
            },
        },
    }


@app.post("/api/admin/settings")
async def admin_settings_update(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    ai_data = data.get("ai") or {}
    streams_data = data.get("streams") or {}
    system_prompt = (ai_data.get("system_prompt") or "").strip()
    model = (ai_data.get("model") or "").strip()

    if not system_prompt:
        raise HTTPException(status_code=400, detail="system_prompt is required")
    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO ai_settings (id, system_prompt, model)
                VALUES (1, %s, %s)
                ON DUPLICATE KEY UPDATE
                    system_prompt = VALUES(system_prompt),
                    model = VALUES(model)
                """,
                (system_prompt, model),
            )
            if isinstance(streams_data, dict) and streams_data:
                is_enabled = 1 if bool(streams_data.get("is_enabled")) else 0
                scope = str(streams_data.get("scope") or "all").strip().lower()
                if scope not in ("all", "strategy"):
                    scope = "all"

                strategy_id = streams_data.get("strategy_id")
                try:
                    strategy_id = int(strategy_id) if strategy_id is not None and str(strategy_id).strip() else None
                except (TypeError, ValueError):
                    strategy_id = None
                if is_enabled == 1 and scope == "strategy" and strategy_id is None:
                    raise HTTPException(status_code=400, detail="strategy_id is required when stream scope is strategy")

                forced_signal = str(streams_data.get("forced_signal") or "BUY").strip().upper()
                if forced_signal not in ("BUY", "SELL"):
                    forced_signal = "BUY"
                message = str(streams_data.get("message") or "").strip()[:1000]
                levels_mode = str(streams_data.get("levels_mode") or "auto").strip().lower()
                if levels_mode not in ("auto", "manual"):
                    levels_mode = "auto"

                raw_sl = streams_data.get("manual_conservative_sl")
                raw_tp = streams_data.get("manual_take_profit")
                try:
                    manual_conservative_sl = float(raw_sl) if raw_sl is not None and str(raw_sl).strip() else None
                except (TypeError, ValueError):
                    manual_conservative_sl = None
                try:
                    manual_take_profit = float(raw_tp) if raw_tp is not None and str(raw_tp).strip() else None
                except (TypeError, ValueError):
                    manual_take_profit = None
                if levels_mode == "manual" and (manual_conservative_sl is None or manual_take_profit is None):
                    raise HTTPException(status_code=400, detail="manual levels require conservative_sl and take_profit")

                indicator_mode = str(streams_data.get("indicator_mode") or "auto").strip().lower()
                if indicator_mode not in ("auto", "manual"):
                    indicator_mode = "auto"

                raw_indicator_overrides = streams_data.get("indicator_overrides")
                indicator_overrides = {}
                if isinstance(raw_indicator_overrides, dict):
                    for raw_key, raw_signal in raw_indicator_overrides.items():
                        key_norm = str(raw_key or "").strip().upper().replace(" ", "").replace("_", "").replace("-", "")
                        if not key_norm:
                            continue
                        signal = str(raw_signal or "").strip().upper()
                        if signal in ("BUY", "SELL", "NEUTRAL"):
                            indicator_overrides[key_norm] = signal
                if scope != "strategy" or indicator_mode != "manual":
                    indicator_overrides = {}
                indicator_overrides_json = json.dumps(indicator_overrides, ensure_ascii=False)
                updated_by = int(admin["user_id"])

                await cur.execute(
                    """
                    INSERT INTO admin_stream_settings (
                        id,
                        is_enabled,
                        scope,
                        strategy_id,
                        forced_signal,
                        levels_mode,
                        manual_conservative_sl,
                        manual_take_profit,
                        indicator_mode,
                        indicator_overrides,
                        message,
                        updated_by
                    )
                    VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        is_enabled = VALUES(is_enabled),
                        scope = VALUES(scope),
                        strategy_id = VALUES(strategy_id),
                        forced_signal = VALUES(forced_signal),
                        levels_mode = VALUES(levels_mode),
                        manual_conservative_sl = VALUES(manual_conservative_sl),
                        manual_take_profit = VALUES(manual_take_profit),
                        indicator_mode = VALUES(indicator_mode),
                        indicator_overrides = VALUES(indicator_overrides),
                        message = VALUES(message),
                        updated_by = VALUES(updated_by)
                    """,
                    (
                        is_enabled,
                        scope,
                        strategy_id,
                        forced_signal,
                        levels_mode,
                        manual_conservative_sl,
                        manual_take_profit,
                        indicator_mode,
                        indicator_overrides_json,
                        message,
                        updated_by,
                    ),
                )
    return {"status": "success"}


@app.get("/api/admin/strategies")
async def admin_strategies(admin=Depends(get_admin_user)):
    analysis_settings = await get_admin_analysis_settings()
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT p.id, p.name, p.icon, p.is_system, p.allowed_timeframes, p.public_winrate,
                       (
                           SELECT GROUP_CONCAT(i.name ORDER BY i.name SEPARATOR ', ')
                           FROM preset_indicators pi
                           JOIN indicators i ON i.id = pi.indicator_id
                           WHERE pi.preset_id = p.id
                       ) AS indicators_list,
                       (
                           SELECT GROUP_CONCAT(i.id ORDER BY i.id SEPARATOR ',')
                           FROM preset_indicators pi
                           JOIN indicators i ON i.id = pi.indicator_id
                           WHERE pi.preset_id = p.id
                       ) AS indicator_ids,
                       (
                           SELECT COUNT(*)
                           FROM users u
                           WHERE u.strategy_id = p.id
                       ) AS users_count,
                       (
                           SELECT COUNT(*)
                           FROM user_analyses ua
                           WHERE ua.strategy_id = p.id
                       ) AS signals_count,
                       (
                           SELECT COUNT(*)
                           FROM user_analyses ua
                           WHERE ua.strategy_id = p.id AND ua.status = 'success'
                       ) AS wins_count,
                       (
                           SELECT COUNT(*)
                           FROM user_analyses ua
                           WHERE ua.strategy_id = p.id AND ua.status IN ('success', 'fail')
                       ) AS closed_signals
                FROM presets p
                ORDER BY p.is_system DESC, p.id ASC
                """
            )
            rows = await cur.fetchall()
            await cur.execute("SELECT id, name, `key` FROM indicators ORDER BY name ASC")
            indicators = await cur.fetchall()

    normalized_rows = []
    for row in rows or []:
        users_count = int(row.get("users_count") or 0)
        signals_count = int(row.get("signals_count") or 0)
        wins_count = int(row.get("wins_count") or 0)
        closed_signals = int(row.get("closed_signals") or 0)
        winrate = 0.0 if closed_signals <= 0 else round((wins_count / closed_signals) * 100, 2)
        raw_public_winrate = row.get("public_winrate")
        try:
            public_winrate = float(raw_public_winrate) if raw_public_winrate is not None else None
        except (TypeError, ValueError):
            public_winrate = None

        row["users_count"] = users_count
        row["usage_count"] = users_count
        row["signals_count"] = signals_count
        row["wins_count"] = wins_count
        row["closed_signals"] = closed_signals
        row["winrate"] = winrate
        row["public_winrate"] = public_winrate
        normalized_rows.append(row)

    system_count = sum(1 for row in normalized_rows if int(row.get("is_system") or 0) == 1)
    user_count = sum(1 for row in normalized_rows if int(row.get("is_system") or 0) != 1)

    return {
        "status": "success",
        "strategies": normalized_rows,
        "indicators": indicators or [],
        "analysis_settings": {
            "engine": analysis_settings.get("engine") or "backend",
            "gpt_model": analysis_settings.get("gpt_model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL,
            "gpt_prompt": analysis_settings.get("gpt_prompt") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT,
            "gpt_key_configured": int(analysis_settings.get("gpt_key_configured") or 0),
            "updated_at": analysis_settings.get("updated_at"),
            "updated_by": analysis_settings.get("updated_by"),
        },
        "summary": {
            "total_count": len(normalized_rows),
            "system_count": system_count,
            "user_count": user_count,
        },
    }


@app.post("/api/admin/strategies/validate-gpt-key")
async def admin_strategies_validate_gpt_key(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    api_key = (data.get("api_key") or "").strip()
    model = (data.get("model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL).strip()
    result = await analysis_ai_service.validate_openai_api_key(api_key, model=model)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "OpenAI key is invalid")
    return {"status": "success", "warning": result.get("warning")}


@app.post("/api/admin/analysis-settings")
async def admin_analysis_settings_update(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    engine = str(data.get("engine") or "backend").strip().lower()
    if engine not in ("backend", "gpt"):
        engine = "backend"
    gpt_model = (data.get("gpt_model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL).strip()
    gpt_prompt = (data.get("gpt_prompt") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT).strip()
    gpt_api_key = (data.get("gpt_api_key") or "").strip()
    if not gpt_model:
        gpt_model = analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL
    if not gpt_prompt:
        gpt_prompt = analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT

    current_settings = await get_admin_analysis_settings()
    stored_gpt_api_key = current_settings.get("gpt_api_key") or ""
    if gpt_api_key:
        validation = await analysis_ai_service.validate_openai_api_key(gpt_api_key, model=gpt_model)
        if not validation.get("ok"):
            raise HTTPException(status_code=400, detail=validation.get("error") or "OpenAI key is invalid")
        stored_gpt_api_key = gpt_api_key
    if engine == "gpt" and not stored_gpt_api_key:
        raise HTTPException(status_code=400, detail="OpenAI key is required for GPT analysis")

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO admin_analysis_settings (
                    id,
                    engine,
                    gpt_api_key,
                    gpt_model,
                    gpt_prompt,
                    updated_by
                )
                VALUES (1, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    engine = VALUES(engine),
                    gpt_api_key = VALUES(gpt_api_key),
                    gpt_model = VALUES(gpt_model),
                    gpt_prompt = VALUES(gpt_prompt),
                    updated_by = VALUES(updated_by)
                """,
                (
                    engine,
                    stored_gpt_api_key or None,
                    gpt_model,
                    gpt_prompt,
                    int(admin["user_id"]),
                ),
            )
    return {"status": "success"}


@app.post("/api/admin/strategies/update")
async def admin_strategies_update(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    strategy_id = int(data.get("id") or 0)
    if not strategy_id:
        raise HTTPException(status_code=400, detail="Strategy id is required")

    name = (data.get("name") or "").strip()
    icon = (data.get("icon") or "⚡").strip()[:32]
    allowed_timeframes = normalize_allowed_timeframes(data.get("allowed_timeframes"))
    is_system = 1 if bool(data.get("is_system")) else 0
    indicators = data.get("indicators")
    raw_public_winrate = data.get("public_winrate")
    if not name:
        raise HTTPException(status_code=400, detail="Strategy name is required")
    if raw_public_winrate is None or (isinstance(raw_public_winrate, str) and not raw_public_winrate.strip()):
        public_winrate = None
    else:
        try:
            public_winrate = round(float(raw_public_winrate), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="public_winrate must be a number")
        if public_winrate < 0 or public_winrate > 100:
            raise HTTPException(status_code=400, detail="public_winrate must be between 0 and 100")

    indicator_ids = []
    if isinstance(indicators, list):
        seen = set()
        for raw_id in indicators:
            try:
                ind_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if ind_id <= 0 or ind_id in seen:
                continue
            seen.add(ind_id)
            indicator_ids.append(ind_id)

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT is_system
                FROM presets
                WHERE id = %s
                LIMIT 1
                """,
                (strategy_id,),
            )
            current_row = await cur.fetchone()
            if not current_row:
                raise HTTPException(status_code=404, detail="Strategy not found")

            current_is_system = int(current_row[0] or 0)
            if current_is_system == 0 and is_system == 1:
                raise HTTPException(status_code=400, detail="User strategy cannot be converted to system strategy")
            if current_is_system == 0:
                is_system = 0

            await cur.execute(
                """
                UPDATE presets
                SET name = %s,
                    icon = %s,
                    allowed_timeframes = %s,
                    public_winrate = %s,
                    is_system = %s
                WHERE id = %s
                """,
                (name, icon, allowed_timeframes, public_winrate, is_system, strategy_id),
            )

            if isinstance(indicators, list):
                valid_ids = []
                if indicator_ids:
                    placeholders = ", ".join(["%s"] * len(indicator_ids))
                    await cur.execute(f"SELECT id FROM indicators WHERE id IN ({placeholders})", tuple(indicator_ids))
                    rows = await cur.fetchall()
                    allowed = {int(row[0]) for row in (rows or [])}
                    valid_ids = [ind_id for ind_id in indicator_ids if ind_id in allowed]

                await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (strategy_id,))
                if valid_ids:
                    await cur.executemany(
                        "INSERT INTO preset_indicators (preset_id, indicator_id) VALUES (%s, %s)",
                        [(strategy_id, ind_id) for ind_id in valid_ids],
                    )
    return {"status": "success"}


@app.post("/api/admin/strategies/delete")
async def admin_strategies_delete(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    strategy_id = int(data.get("id") or 0)
    if not strategy_id:
        raise HTTPException(status_code=400, detail="Strategy id is required")
    if strategy_id == 1:
        raise HTTPException(status_code=400, detail="Default strategy cannot be deleted")

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (strategy_id,))
            await cur.execute("DELETE FROM user_presets WHERE preset_id = %s", (strategy_id,))
            await cur.execute("DELETE FROM strategy_analysis_settings WHERE strategy_id = %s", (strategy_id,))
            await cur.execute("DELETE FROM presets WHERE id = %s", (strategy_id,))
            await cur.execute("UPDATE users SET strategy_id = 1 WHERE strategy_id = %s", (strategy_id,))
    return {"status": "success"}

def parse_timeframe_mins(tf: str) -> int:
    if not tf: return 5
    tf = tf.lower()
    try:
        if tf.endswith('m'): return int(tf[:-1])
        if tf.endswith('min'): return int(tf[:-3])
        if tf.endswith('h'): return int(tf[:-1]) * 60
        if tf.endswith('hour'): return int(tf[:-4]) * 60
        if tf.endswith('d'): return int(tf[:-1]) * 1440
        if tf.endswith('day'): return int(tf[:-3]) * 1440
    except:
        pass
    return 5

async def get_price_for_symbol(client: httpx.AsyncClient, symbol: str, token: str) -> Optional[float]:
    clean_sym = symbol.replace("/", "").replace("-", "").strip().upper()
    now = asyncio.get_event_loop().time()
    
    if clean_sym in price_cache and price_cache[clean_sym]["expires"] > now:
        return price_cache[clean_sym]["price"]
        
    url = f"https://api.devsbite.com/price/{clean_sym}"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    
    try:
        resp = await client.get(url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("price")
            if price is not None:
                price = float(price)
                price_cache[clean_sym] = {"price": price, "expires": now + 30}
                return price
    except Exception as e:
        print(f"[Worker] Failed to fetch price for {clean_sym} via proxy: {e}")
        
    if clean_sym in COMMODITY_SYMBOLS:
        td_key = os.getenv("TD_API_KEY")
        if td_key:
            try:
                td_url = f"https://api.twelvedata.com/price?symbol={clean_sym}:COMMODITY&apikey={td_key}"
                resp = await client.get(td_url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    price = data.get("price") or data.get("close")
                    if price is not None:
                        price = float(price)
                        price_cache[clean_sym] = {"price": price, "expires": now + 30}
                        return price
            except Exception as e:
                print(f"[Worker] Failed to fetch TD price for {clean_sym}: {e}")

    return None

async def analysis_producer():
    print("[Worker] Producer started...")
    while True:
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute("""
                            SELECT id, pair, timeframe, created_at, raw_data 
                            FROM user_analyses 
                            WHERE status = 'active' AND created_at < NOW() - INTERVAL 5 MINUTE
                        """)
                        rows = await cur.fetchall()

                now = datetime.now()
                for row in rows:
                    a_id = row['id']
                    if a_id in processing_ids:
                        continue

                    created_at = row['created_at']
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace('Z', ''))
                        except:
                            continue

                    tf_mins = parse_timeframe_mins(row['timeframe'])
                    expiration_time = created_at + timedelta(minutes=tf_mins + 10)

                    if now >= expiration_time:
                        processing_ids.add(a_id)
                        await analysis_queue.put(row)

        except Exception as e:
            print(f"[Worker] Producer error: {e}")
            
        await asyncio.sleep(30)

async def analysis_consumer():
    print("[Worker] Consumer started...")
    token = os.getenv("DEVSBITE_TOKEN")
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                item = await analysis_queue.get()
                items_to_process = [item]
                
                while not analysis_queue.empty():
                    try:
                        items_to_process.append(analysis_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                        
                async with db_pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        for row in items_to_process:
                            a_id = row['id']
                            symbol = row['pair']
                            raw_data = row['raw_data']
                            
                            try:
                                raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                                orig_price = float(raw.get('price', 0))
                                rec = raw.get('recommendation')
                            except:
                                orig_price, rec = 0, None
                                
                            new_status = 'skipped'
                            
                            if orig_price > 0 and rec in ['BUY', 'SELL']:
                                current_price = await get_price_for_symbol(client, symbol, token)
                                
                                if current_price is not None:
                                    if rec == 'BUY':
                                        if current_price > orig_price: new_status = 'success'
                                        elif current_price < orig_price: new_status = 'fail'
                                    elif rec == 'SELL':
                                        if current_price < orig_price: new_status = 'success'
                                        elif current_price > orig_price: new_status = 'fail'
                            
                            await cur.execute("UPDATE user_analyses SET status = %s WHERE id = %s", (new_status, a_id))
                            
                            processing_ids.discard(a_id)
                            analysis_queue.task_done()
                            
            except Exception as e:
                print(f"[Worker] Consumer error: {e}")
                await asyncio.sleep(5)



@app.post("/api/user/profile")
async def get_profile(user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT u.user_id, u.lang, u.mode, u.username, u.first_name, u.avatar_url, 
                       u.strategy_id, p.name as strategy_name
                FROM users u
                LEFT JOIN presets p ON u.strategy_id = p.id
                WHERE u.user_id = %s
            """, (user_id,))
            user = await cur.fetchone()
    return user or {"error": "Not found"}

@app.get("/api/indicators")
async def get_indicators(user=Depends(get_telegram_user)):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, name, `key` FROM indicators")
            indicators = await cur.fetchall()
    return {"indicators": indicators}

@app.get("/api/strategies")
async def get_strategies(user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT p.id, p.name, p.is_system, p.icon, p.allowed_timeframes, p.public_winrate,
                       (
                           SELECT COUNT(*)
                           FROM user_analyses ua
                           WHERE ua.strategy_id = p.id AND ua.status = 'success'
                       ) AS wins_count,
                       (
                           SELECT COUNT(*)
                           FROM user_analyses ua
                           WHERE ua.strategy_id = p.id AND ua.status IN ('success', 'fail')
                       ) AS closed_signals,
                       GROUP_CONCAT(i.name SEPARATOR ', ') as indicators_list,
                       GROUP_CONCAT(i.id SEPARATOR ',') as indicator_ids,
                       GROUP_CONCAT(i.key SEPARATOR ',') as indicator_keys
                FROM presets p
                LEFT JOIN preset_indicators pi ON p.id = pi.preset_id
                LEFT JOIN indicators i ON pi.indicator_id = i.id
                LEFT JOIN user_presets up ON p.id = up.preset_id
                WHERE p.is_system = 1 OR up.user_id = %s
                GROUP BY p.id
            """, (user_id,))
            strategies = await cur.fetchall()
    for strategy in strategies or []:
        wins_count = int(strategy.get("wins_count") or 0)
        closed_signals = int(strategy.get("closed_signals") or 0)
        actual_winrate = round((wins_count / closed_signals) * 100, 2) if closed_signals > 0 else 0.0
        raw_public_winrate = strategy.get("public_winrate")
        try:
            public_winrate = float(raw_public_winrate) if raw_public_winrate is not None else None
        except (TypeError, ValueError):
            public_winrate = None
        display_winrate = public_winrate if public_winrate is not None else actual_winrate
        strategy["wins_count"] = wins_count
        strategy["closed_signals"] = closed_signals
        strategy["actual_winrate"] = actual_winrate
        strategy["public_winrate"] = public_winrate
        strategy["display_winrate"] = round(float(display_winrate), 2)
    return {"strategies": strategies}

@app.post("/api/user/strategy")
async def update_strategy(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    user_id = user["user_id"]
    strategy_id = data.get("strategy_id")
    
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE users SET strategy_id = %s WHERE user_id = %s", (strategy_id, user_id))
    return {"status": "success", "strategy_id": strategy_id}

@app.post("/api/user/strategy/manage")
async def manage_custom_strategy(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    action = data.get("action") 
    user_id = user["user_id"]
    
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            if action == "create":
                name = data.get("name")
                icon = data.get("icon", "\u26A1")
                indicators = data.get("indicators", [])
                
                await cur.execute("INSERT INTO presets (name, is_system, icon) VALUES (%s, 0, %s)", (name, icon))
                preset_id = cur.lastrowid
                
                await cur.execute("INSERT INTO user_presets (user_id, preset_id) VALUES (%s, %s)", (user_id, preset_id))
                
                for ind_id in indicators:
                    await cur.execute("INSERT INTO preset_indicators (preset_id, indicator_id) VALUES (%s, %s)", (preset_id, ind_id))
                
                await cur.execute("UPDATE users SET strategy_id = %s WHERE user_id = %s", (preset_id, user_id))
                return {"status": "success", "strategy_id": preset_id}

            elif action == "update":
                preset_id = data.get("preset_id")
                name = data.get("name")
                icon = data.get("icon", "\u26A1")
                indicators = data.get("indicators", [])
                
                await cur.execute("UPDATE presets SET name = %s, icon = %s WHERE id = %s AND is_system = 0", (name, icon, preset_id))
                
                await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (preset_id,))
                for ind_id in indicators:
                    await cur.execute("INSERT INTO preset_indicators (preset_id, indicator_id) VALUES (%s, %s)", (preset_id, ind_id))
                return {"status": "success"}

            elif action == "delete":
                preset_id = data.get("preset_id")
                await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (preset_id,))
                await cur.execute("DELETE FROM user_presets WHERE preset_id = %s AND user_id = %s", (preset_id, user_id))
                await cur.execute("DELETE FROM presets WHERE id = %s AND is_system = 0", (preset_id,))
                
                await cur.execute("""
                    UPDATE users 
                    SET strategy_id = 1 
                    WHERE user_id = %s AND strategy_id = %s
                """, (user_id, preset_id))
                return {"status": "success"}

    return {"error": "Invalid action"}

@app.post("/api/user/sync")
async def sync_user(user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    username = user.get("username") or ""
    first_name = user.get("first_name") or ""
    avatar_url = user.get("photo_url") or ""
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO users (user_id, username, first_name, avatar_url, lang, mode)
                VALUES (%s, %s, %s, %s, 'ru', 'forex')
                ON DUPLICATE KEY UPDATE 
                    username = VALUES(username),
                    first_name = VALUES(first_name),
                    avatar_url = VALUES(avatar_url)
            """, (user_id, username, first_name, avatar_url))
    return {"status": "success"}
    
@app.post("/api/user/mode")
async def update_mode(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    user_id = user["user_id"]
    new_mode = data.get("mode")
    
    if user_id and new_mode:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE users SET mode = %s WHERE user_id = %s", (new_mode, user_id))
        return {"status": "success", "mode": new_mode}
    return {"error": "Invalid data"}

@app.get("/api/pairs/forex")
async def get_forex_pairs(user=Depends(get_telegram_user)):
    token = os.getenv("DEVSBITE_TOKEN")
    url = "https://api.devsbite.com/pairs/forex?min_payout=34"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if "pairs" in data:
                data["pairs"] = sorted(data["pairs"], key=lambda x: x["payout"], reverse=True)
            return data
        except Exception as e:
            return {"error": str(e), "pairs": []}
            
@app.get("/api/pairs/commodity")
async def get_commodity_pairs(user=Depends(get_telegram_user)):
    token = os.getenv("DEVSBITE_TOKEN")
    url = "https://api.devsbite.com/pairs/commodity"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Commodity API Error: {e}")
            return [] 

@app.get("/api/pairs/indices")
async def get_indices_pairs(user=Depends(get_telegram_user)):
    token = os.getenv("DEVSBITE_TOKEN")
    url = "https://api.devsbite.com/pairs/indices"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Indices API Error: {e}")
            return []
            
@app.get("/api/analysis/active")
async def get_active_analyses(user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT a.id, a.pair, a.timeframe, a.strategy_id, a.raw_data, a.news_data, a.created_at, p.name as strategy_name
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.user_id = %s AND a.status = 'active'
                ORDER BY a.created_at DESC
            """, (user_id,))
            analyses = await cur.fetchall()
            
            for a in analyses:
                if isinstance(a['raw_data'], str):
                    a['raw_data'] = json.loads(a['raw_data'])
                if a.get('news_data') and isinstance(a['news_data'], str):
                    a['news_data'] = json.loads(a['news_data'])
                    
    return {"analyses": analyses}

@app.get("/api/analysis/history")
async def get_analysis_history(
    strategy_id: Optional[int] = Query(default=None),
    user=Depends(get_telegram_user),
):
    user_id = int(user["user_id"])
    strategy_filter = int(strategy_id) if strategy_id is not None and int(strategy_id) > 0 else None
    where_clause = "a.user_id = %s AND a.status != 'active'"
    params = [user_id]
    if strategy_filter is not None:
        where_clause += " AND a.strategy_id = %s"
        params.append(strategy_filter)

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(f"""
                SELECT a.id, a.pair, a.timeframe, a.status, a.created_at, a.strategy_id, p.name as strategy_name, p.public_winrate
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE {where_clause}
                ORDER BY a.created_at DESC
            """, tuple(params))
            history = await cur.fetchall()

    success_count = sum(1 for item in history if item['status'] == 'success')
    fail_count = sum(1 for item in history if item['status'] == 'fail')
    skipped_count = sum(1 for item in history if item['status'] == 'skipped')
    closed_total = success_count + fail_count
    winrate = round((success_count / closed_total) * 100, 2) if closed_total > 0 else 0.0

    return {
        "history": history,
        "stats": {
            "success": success_count,
            "fail": fail_count,
            "skipped": skipped_count,
            "total": len(history),
            "closed_total": closed_total,
            "winrate": winrate,
        },
        "applied_filter": {
            "strategy_id": strategy_filter,
        },
    }

async def fetch_news_data():
    token = os.getenv("FINNHUB_TOKEN")
    url = f"https://finnhub.io/api/v1/calendar/economic?token={token}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            if response.status_code != 200:
                return {"economicCalendar": []}
            raw_data = response.json()
    except Exception as e:
        print(f"News API Error: {e}")
        return {"economicCalendar": []}

    events = raw_data.get("economicCalendar", [])
    if not events:
        return {"economicCalendar": []}

    country_to_currency = {
        "US": "USD", "GB": "GBP", "CA": "CAD", "AU": "AUD", "NZ": "NZD",
        "JP": "JPY", "CH": "CHF", "CN": "CNY", "RU": "RUB", "TR": "TRY",
        "ZA": "ZAR", "MX": "MXN", "BR": "BRL", "IN": "INR", "KR": "KRW",
        "EU": "EUR", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR"
    }

    symbol_to_currency_map = {
        "XAU": "USD", "XAG": "USD", "XPT": "USD", "XPD": "USD",
        "WTI": "USD", "BRENT": "USD", "XBR": "USD", "NG": "USD"
    }

    now = datetime.utcnow()
    filtered_events = []

    for event in events:
        try:
            event_time = datetime.strptime(event["time"], "%Y-%m-%d %H:%M:%S")
            
            if event_time.date() == now.date() and event_time > (now - timedelta(hours=2)):
                country = event.get("country", "").strip().upper()
                currency = country_to_currency.get(country, "ALL")
                
                event["currency"] = currency
                filtered_events.append(event)
        except:
            continue

    return {"economicCalendar": filtered_events}

@app.get("/api/news")
async def get_news(user=Depends(get_telegram_user)):
    return await fetch_news_data()
    
@app.post("/api/analysis/forex")
async def create_forex_analysis(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    user_id = int(user["user_id"])
    pair = data.get("pair")
    interval_raw = data.get("exp")
    strategy_id = data.get("strategy_id")
    try:
        strategy_id_int = int(strategy_id) if strategy_id is not None and str(strategy_id).strip() else None
    except (TypeError, ValueError):
        strategy_id_int = None
    if strategy_id_int is None:
        strategy_id_int = await get_user_strategy_id(user_id)
    allowed_indicators = data.get("allowed_indicators", [])
    exchange = data.get("exchange")

    interval_map = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1h": "1h",
        "4h": "4h",
        "1d": "1day",
    }
    interval = interval_map.get(interval_raw, "5min")

    demo_symbol_map = {
        "SPX": "SPX",
        "NDX": "NDX",
        "DJI": "DJI",
        "DAX": "GDAXI",
        "UK100": "FTSE",
        "NI225": "N225",
    }
    formatted_pair = demo_symbol_map.get(pair)
    if not formatted_pair:
        compact = (pair or "").upper().replace("/", "").replace(" ", "")
        if len(compact) == 6 and compact.isalpha():
            formatted_pair = f"{compact[:3]}/{compact[3:]}"
        else:
            formatted_pair = (pair or "").strip()

    token = os.getenv("DEVSBITE_TOKEN")
    url = (os.getenv("ANALYSIS_GATEWAY_URL") or "https://api.devsbite.com/analysis/advanced").strip()
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["X-Client-Token"] = token

    payload = {
        "symbol": formatted_pair,
        "interval": interval,
        "allowed_indicators": allowed_indicators,
        "exchange": exchange,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            resp.raise_for_status()
            upstream_data = resp.json()

            baseline_analysis_data = compute_analysis_decision(
                upstream_data,
                symbol=formatted_pair,
                interval=interval,
                allowed_indicators=allowed_indicators,
            )
            analysis_settings = await get_admin_analysis_settings()
            if analysis_settings.get("engine") == "gpt":
                if not analysis_settings.get("gpt_api_key"):
                    print("GPT analysis is not configured")
                    return {"error": "Analysis is temporarily unavailable. Please try again later."}
                strategy_context = await get_strategy_context(strategy_id_int)
                try:
                    analysis_data = await analysis_ai_service.generate_gpt_analysis(
                        api_key=analysis_settings.get("gpt_api_key") or "",
                        model=analysis_settings.get("gpt_model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL,
                        prompt=analysis_settings.get("gpt_prompt") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT,
                        raw_payload=upstream_data,
                        symbol=formatted_pair,
                        interval=interval,
                        allowed_indicators=allowed_indicators,
                        strategy=strategy_context,
                        baseline_analysis=baseline_analysis_data,
                    )
                except Exception as e:
                    print(f"GPT analysis error: {e}")
                    return {"error": "Analysis is temporarily unavailable. Please try again later."}
            else:
                analysis_data = baseline_analysis_data
            analysis_data = ensure_analysis_key_levels(analysis_data, preferred_signal=analysis_data.get("recommendation"))
            stream_override = await resolve_stream_override(strategy_id_int)
            if stream_override:
                analysis_data = apply_stream_override_to_analysis(analysis_data, stream_override)
            analysis_data = ensure_analysis_key_levels(analysis_data, preferred_signal=analysis_data.get("recommendation"))
            news_data = await fetch_news_data()
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            print(f"ANALYSIS GATEWAY ERROR [{e.response.status_code}]: {error_text} (Payload: {payload})")
            return {"error": f"API Error: {error_text}"}
        except ValueError as e:
            return {"error": f"Analysis parse error: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_analyses (user_id, pair, timeframe, strategy_id, raw_data, news_data, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'active')
                """,
                (user_id, pair, interval_raw, strategy_id_int, json.dumps(analysis_data), json.dumps(news_data)),
            )
            analysis_id = cur.lastrowid

    return {"status": "success", "analysis_id": analysis_id, "data": analysis_data, "news_data": news_data}
@app.post("/api/analysis/status")
async def update_analysis_status(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    analysis_id = data.get("analysis_id")
    status = data.get("status") 
    user_id = user["user_id"]

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                UPDATE user_analyses 
                SET status = %s 
                WHERE id = %s AND user_id = %s
            """, (status, analysis_id, user_id))
    return {"status": "success"}
    
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    global menu_photo_file_id
    user_name = message.from_user.first_name or message.from_user.username or "Trader"
    user_id = int(message.from_user.id)

    welcome_text = (
        f"Welcome, {user_name}!\n\n"
        f"<b>Elizabeth Vane</b> | <code>Private Trading Analytics</code>\n\n"
        f"A professional analytical space for those who value precision. "
        f"We've combined advanced technical analysis methods with the convenience of a Web App.\n\n"
        f"<i>Your market edge begins here.</i>"
    )

    keyboard_rows = [
        [
            InlineKeyboardButton(
                text="Open Elizabeth Vane",
                web_app=WebAppInfo(url=os.getenv("WEB_APP_URL"))
            )
        ]
    ]
    if await is_admin_user(user_id):
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="Admin Center",
                    web_app=WebAppInfo(url=build_admin_webapp_url())
                )
            ]
        )
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

    if menu_photo_file_id:
        await message.answer_photo(
            photo=menu_photo_file_id,
            caption=welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    photo_path = resolve_menu_photo_path()
    sent_message = await message.answer_photo(
        photo=FSInputFile(photo_path),
        caption=welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    if sent_message and sent_message.photo:
        menu_photo_file_id = sent_message.photo[-1].file_id
        try:
            with open(menu_file_id_path, "w", encoding="utf-8") as f:
                f.write(menu_photo_file_id)
        except Exception:
            pass

class AIChatRequest(BaseModel):
    user_id: Optional[int] = None
    text: Optional[str] = None
    chat_id: Optional[int] = None

async def get_or_create_active_chat_for_user(user_id: int):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT id, title
                FROM ai_chats 
                WHERE user_id = %s AND status = 'active' 
                AND updated_at >= NOW() - INTERVAL 24 HOUR
                ORDER BY updated_at DESC LIMIT 1
            """, (user_id,))
            chat = await cur.fetchone()

            if not chat:
                await cur.execute("UPDATE ai_chats SET status = 'archived' WHERE user_id = %s AND status = 'active'", (user_id,))
                await cur.execute("INSERT INTO ai_chats (user_id) VALUES (%s)", (user_id,))
                chat_id = cur.lastrowid
                return {"status": "success", "chat_id": chat_id, "title": "New Chat", "messages": []}

            await cur.execute("SELECT id, role, content, created_at as timestamp FROM ai_messages WHERE chat_id = %s ORDER BY id ASC", (chat['id'],))
            messages = await cur.fetchall()
            
            return {"status": "success", "chat_id": chat['id'], "title": chat['title'], "messages": messages}

@app.post("/api/ai/chat/active")
async def get_or_create_active_chat(request: AIChatRequest, user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    return await get_or_create_active_chat_for_user(user_id)

@app.post("/api/ai/chat/send")
async def send_chat_message(request: AIChatRequest, user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    if not request.text or not request.chat_id:
        return {"error": "text and chat_id are required"}
    result = await ai_service.process_user_message(db_pool, user_id, request.chat_id, request.text)
    if result.get("status") != "success":
        raise HTTPException(status_code=502, detail=result.get("error") or "AI provider request failed")
    return result

@app.post("/api/ai/chat/history")
async def get_chat_history(request: AIChatRequest, user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT id, title, status, updated_at 
                FROM ai_chats 
                WHERE user_id = %s 
                ORDER BY updated_at DESC 
                LIMIT 10
            """, (user_id,))
            chats = await cur.fetchall()
    return {"status": "success", "chats": chats}

@app.post("/api/ai/chat/load")
async def load_historical_chat(request: AIChatRequest, user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    if not request.chat_id:
        return {"error": "chat_id is required"}
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE ai_chats SET status = 'archived' WHERE user_id = %s AND status = 'active'", (user_id,))
            await cur.execute("UPDATE ai_chats SET status = 'active', updated_at = NOW() WHERE id = %s AND user_id = %s", (request.chat_id, user_id))
    return await get_or_create_active_chat_for_user(user_id)

@app.post("/api/ai/chat/new")
async def create_new_chat(request: AIChatRequest, user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE ai_chats SET status = 'archived' WHERE user_id = %s AND status = 'active'", (user_id,))
            await cur.execute("INSERT INTO ai_chats (user_id) VALUES (%s)", (user_id,))
            chat_id = cur.lastrowid
    return {"status": "success", "chat_id": chat_id, "title": "New Chat", "messages": []}
    
async def start_bot():
    try:
        await bot.set_my_commands(
            [
                BotCommand(
                    command="start",
                    description="Open main menu",
                )
            ]
        )
    except Exception as e:
        print(f"[Bot] set_my_commands error: {e}")
    await dp.start_polling(bot)

async def start_api():
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT)
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    global db_pool
    db_pool = await aiomysql.create_pool(**DB_CONFIG)
    await ensure_database_schema(db_pool)
    
    await asyncio.gather(
        start_bot(), 
        start_api(),
        analysis_producer(),
        analysis_consumer()
    )

if __name__ == "__main__":
    async def main_wrapper():
        try:
            await main()
        except KeyboardInterrupt:
            pass
    asyncio.run(main_wrapper())

