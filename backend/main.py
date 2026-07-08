import os
import asyncio
import aiomysql
import httpx
import json
import secrets
import random
from datetime import datetime, timedelta
from urllib.parse import parse_qs
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
from typing import Optional, Any, Dict, List
from analysis_engine import compute_analysis_decision
try:
    from backend.analysis_runtime import fallback_to_baseline_analysis
except ModuleNotFoundError:
    from analysis_runtime import fallback_to_baseline_analysis
try:
    from backend.telegram_auth import get_telegram_user
except ModuleNotFoundError:
    from telegram_auth import get_telegram_user
try:
    from backend.db_bootstrap import ensure_database_schema
except ModuleNotFoundError:
    from db_bootstrap import ensure_database_schema
try:
    from backend.stream_matching import stream_requested_asset_matches
except ModuleNotFoundError:
    from stream_matching import stream_requested_asset_matches
try:
    from backend.binary_signal import enforce_binary_signal as normalize_binary_signal
except ModuleNotFoundError:
    from binary_signal import enforce_binary_signal as normalize_binary_signal
try:
    from backend.market_symbol_mapping import (
        get_custom_forex_currency_assets,
        get_custom_forex_index_assets,
        get_forex_stock_assets,
        get_twelvedata_symbol_candidates,
        has_explicit_twelvedata_mapping,
        merge_custom_market_assets,
    )
except ModuleNotFoundError:
    from market_symbol_mapping import (
        get_custom_forex_currency_assets,
        get_custom_forex_index_assets,
        get_forex_stock_assets,
        get_twelvedata_symbol_candidates,
        has_explicit_twelvedata_mapping,
        merge_custom_market_assets,
    )
try:
    from backend.pocket_api import (
        POCKET_DEPOSIT_EVENT,
        POCKET_FTD_EVENT,
        POCKET_REGISTRATION_EVENT,
        POCKET_USER_INFO_ENDPOINT_TEMPLATE,
        build_pocket_user_info_url,
        mask_secret,
        normalize_pocket_postback_payload,
    )
except ModuleNotFoundError:
    from pocket_api import (
        POCKET_DEPOSIT_EVENT,
        POCKET_FTD_EVENT,
        POCKET_REGISTRATION_EVENT,
        POCKET_USER_INFO_ENDPOINT_TEMPLATE,
        build_pocket_user_info_url,
        mask_secret,
        normalize_pocket_postback_payload,
    )
try:
    from backend.aio_tracking import (
        build_aio_pocket_deposit_conversion_url,
        build_aio_pocket_ftd_conversion_url,
        build_aio_pocket_registration_conversion_url,
        extract_aio_visit_uuid_from_start_text,
        normalize_aio_revenue,
        normalize_aio_visit_uuid,
    )
except ModuleNotFoundError:
    from aio_tracking import (
        build_aio_pocket_deposit_conversion_url,
        build_aio_pocket_ftd_conversion_url,
        build_aio_pocket_registration_conversion_url,
        extract_aio_visit_uuid_from_start_text,
        normalize_aio_revenue,
        normalize_aio_visit_uuid,
    )
try:
    from backend.chatterfy_pocket import CHATTERFY_POCKET_EVENT_SLUGS, build_chatterfy_pocket_postback_url
except ModuleNotFoundError:
    from chatterfy_pocket import CHATTERFY_POCKET_EVENT_SLUGS, build_chatterfy_pocket_postback_url

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
DEVSBITE_API_BASE_URL = (os.getenv("DEVSBITE_API_BASE_URL") or "https://api.devsbite.com").strip().rstrip("/")
DEVSBITE_MIN_PAYOUT = int((os.getenv("DEVSBITE_MIN_PAYOUT") or "34").strip() or "34")
DEVSBITE_EXPIRATIONS_URL = (os.getenv("DEVSBITE_EXPIRATIONS_URL") or "").strip()
DEVSBITE_CLIENT_TOKEN = (os.getenv("DEVSBITE_CLIENT_TOKEN") or os.getenv("DEVSBITE_TOKEN") or "").strip()
BINARY_EXPIRATION_OPTIONS = (os.getenv("BINARY_EXPIRATION_OPTIONS") or "5s,15s,1m,3m,5m,15m,1h").strip()
MARKET_KIND_CONFIG = {
    "forex": {"title": "Forex", "path": "forex"},
    "otc": {"title": "OTC", "path": "otc"},
    "commodities": {"title": "Commodities", "path": "otc/commodities"},
    "stocks": {"title": "Stocks", "path": "otc/stocks"},
    "crypto": {"title": "Crypto", "path": "otc/crypto"},
}
MARKET_KIND_ALIASES = {
    "metal": "commodities",
    "metals": "commodities",
    "commodity": "commodities",
    "commodities": "commodities",
    "stock": "stocks",
    "stocks": "stocks",
    "crypto": "crypto",
    "crypta": "crypto",
}

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "db": os.getenv("DB_NAME"),
    "autocommit": True
}
POCKET_POSTBACK_SECRET = (os.getenv("POCKET_POSTBACK_SECRET") or "").strip()

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
    if not await is_admin_user(int(user["user_id"])):
        raise HTTPException(status_code=403, detail="Admin access denied")

    expected = get_admin_panel_token()
    provided = (x_admin_token or "").strip()
    if provided and secrets.compare_digest(provided, expected):
        return user

    # Telegram WebApp initData already proves the user identity; keep old
    # admin buttons working even if their URL token was rotated by a deploy.
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
        "emulation_analysis_type": "forex",
        "emulation_market": "",
        "emulation_symbol": "",
        "emulation_price": None,
        "emulation_strategy_id": None,
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
                    emulation_analysis_type,
                    emulation_market,
                    emulation_symbol,
                    emulation_price,
                    emulation_strategy_id,
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
    for raw_key, raw_entry in parsed_overrides.items():
        key_norm = str(raw_key or "").strip().upper().replace(" ", "").replace("_", "").replace("-", "")
        if not key_norm:
            continue
        if isinstance(raw_entry, dict):
            signal = str(raw_entry.get("signal") or "AUTO").strip().upper()
            value = str(raw_entry.get("value") or "").strip()
        else:
            signal = str(raw_entry or "").strip().upper()
            value = ""
        entry = {}
        if signal in ("BUY", "SELL", "NEUTRAL"):
            entry["signal"] = signal
        if value:
            entry["value"] = value[:64]
        if entry:
            normalized_overrides[key_norm] = entry
    settings["indicator_overrides"] = normalized_overrides
    settings["message"] = str(settings.get("message") or "")
    emulation_analysis_type = str(settings.get("emulation_analysis_type") or "forex").strip().lower()
    settings["emulation_analysis_type"] = emulation_analysis_type if emulation_analysis_type in ("forex", "binary") else "forex"
    if settings["emulation_analysis_type"] == "binary":
        settings["emulation_market"] = normalize_market_kind(settings.get("emulation_market") or "") if settings.get("emulation_market") else ""
    else:
        settings["emulation_market"] = normalize_forex_stream_market(settings.get("emulation_market") or "") if settings.get("emulation_market") else "currencies"
    settings["emulation_symbol"] = str(settings.get("emulation_symbol") or "").strip()
    try:
        settings["emulation_price"] = float(settings["emulation_price"]) if settings.get("emulation_price") is not None else None
    except (TypeError, ValueError):
        settings["emulation_price"] = None
    if settings.get("emulation_price") is not None and settings["emulation_price"] <= 0:
        settings["emulation_price"] = None
    try:
        settings["emulation_strategy_id"] = (
            int(settings["emulation_strategy_id"]) if settings.get("emulation_strategy_id") is not None else None
        )
    except (TypeError, ValueError):
        settings["emulation_strategy_id"] = None
    return settings


async def resolve_stream_override(
    strategy_id: Optional[int],
    analysis_type: str = "forex",
    requested_symbol: str = "",
    requested_market: str = "",
):
    settings = await get_stream_settings_row()
    if int(settings.get("is_enabled") or 0) != 1:
        return None
    target_analysis_type = str(settings.get("emulation_analysis_type") or "forex").strip().lower()
    current_analysis_type = str(analysis_type or "forex").strip().lower()
    if target_analysis_type in ("forex", "binary") and target_analysis_type != current_analysis_type:
        return None
    if not stream_requested_asset_matches(settings, current_analysis_type, requested_symbol, requested_market):
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


FOREX_STREAM_MARKETS = {
    "currencies": {"title": "Currencies"},
    "indices": {"title": "Indices"},
    "commodities": {"title": "Commodities"},
    "stocks": {"title": "Stocks"},
}

FOREX_STREAM_MARKET_ALIASES = {
    "currency": "currencies",
    "currencies": "currencies",
    "forex": "currencies",
    "indices": "indices",
    "index": "indices",
    "commodity": "commodities",
    "commodities": "commodities",
    "metal": "commodities",
    "metals": "commodities",
    "stock": "stocks",
    "stocks": "stocks",
}


def normalize_forex_stream_market(value: str) -> str:
    raw = str(value or "").strip().lower()
    return FOREX_STREAM_MARKET_ALIASES.get(raw, "currencies")


def normalize_forex_stream_assets(market: str, payload: Any) -> List[Dict[str, Any]]:
    rows = extract_market_rows(payload)
    normalized = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        pair = (
            row.get("apiVal")
            or row.get("symbol")
            or row.get("asset")
            or row.get("pair")
            or row.get("ticker")
            or row.get("name")
        )
        pair = str(pair or "").strip()
        if not pair:
            continue
        key = pair.upper()
        if key in seen:
            continue
        seen.add(key)
        label = str(row.get("name") or row.get("label") or row.get("display_name") or pair).strip()
        item = {"pair": pair, "apiVal": pair, "symbol": pair, "name": label, "label": label, "market": market}
        if row.get("icon"):
            item["icon"] = row.get("icon")
        if row.get("country"):
            item["country"] = row.get("country")
        if row.get("exchange"):
            item["exchange"] = row.get("exchange")
        normalized.append(item)
    return sorted(normalized, key=lambda item: item.get("label") or item.get("pair") or "")


async def fetch_devsbite_json(path: str) -> Any:
    token = os.getenv("DEVSBITE_TOKEN")
    if not token:
        return []
    headers = {"accept": "application/json", "X-Client-Token": token, "Cache-Control": "no-cache"}
    url = f"{DEVSBITE_API_BASE_URL}/{path.lstrip('/')}"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=12.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Devsbite asset API Error [{path}]: {e}")
            return []


async def get_forex_stream_options_payload(market: str) -> Dict[str, Any]:
    forex_market = normalize_forex_stream_market(market)
    if forex_market == "currencies":
        binary_payload = await get_market_options_payload("forex", DEVSBITE_MIN_PAYOUT)
        pairs = [{"pair": item.get("pair"), "label": item.get("pair"), "market": forex_market} for item in binary_payload.get("pairs") or [] if item.get("pair")]
        pairs = merge_custom_market_assets(pairs, get_custom_forex_currency_assets())
    elif forex_market == "indices":
        pairs = normalize_forex_stream_assets(forex_market, await fetch_devsbite_json("pairs/indices"))
        pairs = merge_custom_market_assets(pairs, get_custom_forex_index_assets())
    elif forex_market == "commodities":
        pairs = normalize_forex_stream_assets(forex_market, await fetch_devsbite_json("pairs/commodity"))
    else:
        pairs = get_forex_stock_assets()
    return {
        "analysis_type": "forex",
        "kind": forex_market,
        "market_title": FOREX_STREAM_MARKETS[forex_market]["title"],
        "available_markets": [{"key": key, "title": value["title"]} for key, value in FOREX_STREAM_MARKETS.items()],
        "pairs": pairs,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


async def get_stream_asset_options_payload(analysis_type: str, market: str, min_payout: int) -> Dict[str, Any]:
    normalized_type = str(analysis_type or "forex").strip().lower()
    if normalized_type == "binary":
        payload = await get_market_options_payload(market or "forex", min_payout)
        payload["analysis_type"] = "binary"
        return payload
    return await get_forex_stream_options_payload(market or "currencies")


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

    emulation_symbol = str(stream_settings.get("emulation_symbol") or "").strip()
    emulation_market = str(stream_settings.get("emulation_market") or "").strip()
    emulation_price = None
    try:
        raw_emulation_price = stream_settings.get("emulation_price")
        emulation_price = float(raw_emulation_price) if raw_emulation_price is not None else None
    except (TypeError, ValueError):
        emulation_price = None
    if emulation_price is not None and emulation_price > 0:
        analysis_data["price"] = float(emulation_price)
        analysis_data["entry_price"] = float(emulation_price)
    emulation_analysis_type = str(stream_settings.get("emulation_analysis_type") or "forex").strip().lower()

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
                raw_override = manual_overrides.get(alias)
                manual_signal = (
                    str(raw_override.get("signal") or "").strip().upper()
                    if isinstance(raw_override, dict)
                    else str(raw_override or "").strip().upper()
                )
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
                for alias in aliases_for_indicator(indicator_key):
                    raw_override = manual_overrides.get(alias)
                    if isinstance(raw_override, dict):
                        manual_value = str(raw_override.get("value") or "").strip()
                        if manual_value:
                            indicator_data["value"] = manual_value
                            break
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
        "emulation_analysis_type": emulation_analysis_type if emulation_analysis_type in ("forex", "binary") else "forex",
        "emulation_market": (
            normalize_market_kind(emulation_market)
            if emulation_analysis_type == "binary" and emulation_market
            else normalize_forex_stream_market(emulation_market) if emulation_market else ""
        ),
        "emulation_symbol": emulation_symbol,
        "emulation_price": emulation_price if emulation_price is not None and emulation_price > 0 else None,
        "emulation_strategy_id": stream_settings.get("emulation_strategy_id"),
    }
    return ensure_analysis_key_levels(analysis_data, preferred_signal=forced_signal)


def get_stream_fallback_price(symbol: str, stream_settings: dict) -> float:
    try:
        price = float(stream_settings.get("emulation_price"))
        if price > 0:
            return price
    except (TypeError, ValueError):
        pass

    key = "".join(ch for ch in str(symbol or "").upper() if ch.isalnum())
    defaults = {
        "AUDUSD": 0.65,
        "SP500": 5500.0,
        "SPX": 5500.0,
        "US500": 5500.0,
        "DAX": 18000.0,
        "GER40": 18000.0,
        "NIKKEI": 39000.0,
        "NIKKEI225": 39000.0,
        "NI225": 39000.0,
    }
    return defaults.get(key, 100.0)


def build_stream_local_analysis(
    symbol: str,
    interval: str,
    allowed_indicators: List[Any],
    stream_settings: dict,
    analysis_type: str = "forex",
    market_kind: str = "",
) -> dict:
    price = get_stream_fallback_price(symbol, stream_settings)
    indicator_keys: List[str] = []
    for item in allowed_indicators if isinstance(allowed_indicators, list) else []:
        if isinstance(item, dict):
            key = str(item.get("key") or item.get("name") or "").strip()
        else:
            key = str(item or "").strip()
        if key and key not in indicator_keys:
            indicator_keys.append(key)
    if not indicator_keys:
        indicator_keys = ["RSI", "MACD", "EMA50", "EMA200", "ADX", "DMI", "ATR", "ICHIMOKU"]

    def indicator_value(key: str):
        normalized = str(key or "").upper().replace(" ", "").replace("-", "").replace("_", "")
        direction = str(stream_settings.get("forced_signal") or "BUY").upper()
        bullish = direction != "SELL"
        price_step = max(abs(price) * 0.0015, 0.0001)

        def fmt(value: float, digits: int = 3) -> str:
            return f"{float(value):.{digits}f}"

        if normalized == "RSI":
            return 52.0
        if normalized == "MACD":
            return 0.0
        if normalized in ("ATR",):
            return round(max(abs(price) * 0.002, 0.0001), 5)
        if normalized in ("EMA921", "EMA9", "EMA21"):
            return {"e9": round(price * 1.0003, 5), "e21": round(price * 0.9997, 5)}
        if normalized.startswith("EMA"):
            return round(price, 5)
        if normalized == "ADX":
            return 24.0
        if normalized in ("PSAR", "PARABOLICSAR"):
            return round(price - price_step if bullish else price + price_step, 5)
        if normalized in ("PIVOTPOINTS", "PIVOTPOINTSHL", "PIVOTPOINT"):
            return f"P {fmt(price)}"
        if normalized == "SUPERTREND":
            return fmt(price - price_step * 1.8 if bullish else price + price_step * 1.8)
        if normalized == "OBV":
            return "1.24M" if bullish else "-1.24M"
        if normalized == "DMI":
            return "+DI 26 / -DI 18" if bullish else "+DI 18 / -DI 26"
        if normalized == "ICHIMOKU":
            return "Above cloud" if bullish else "Below cloud"
        if normalized in ("STOCH", "STOCHASTIC"):
            return 58.0 if bullish else 42.0
        if normalized in ("BB", "BOLLINGERBANDS", "BOLLINGERBAND"):
            return "Mid band"
        if normalized == "CCI":
            return 74.0 if bullish else -74.0
        if normalized == "FIBONACCI":
            return "61.8%"
        return "Neutral"

    indicators = {
        key: {"value": indicator_value(key), "signal": "NEUTRAL"}
        for key in indicator_keys
    }
    step = max(abs(price) * 0.005, 0.0005)
    analysis_data = {
        "symbol": str(symbol or "").strip(),
        "interval": interval,
        "analysis_type": analysis_type,
        "market_kind": market_kind,
        "price": float(price),
        "entry_price": float(price),
        "recommendation": "NEUTRAL",
        "signal": "NEUTRAL",
        "confidence": 60,
        "indicators": indicators,
        "votes": {"BUY": 0, "SELL": 0, "NEUTRAL": len(indicators) or 1},
        "weighted_scores": {"buy": 0.0, "sell": 0.0, "neutral": float(len(indicators) or 1)},
        "key_levels": {
            "current_price": round(price, 5),
            "nearest_support": round(price - step, 5),
            "nearest_resistance": round(price + step, 5),
        },
        "source": "admin_stream_local",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }
    return apply_stream_override_to_analysis(analysis_data, stream_settings)

async def get_support_links_row():
    fallback = {
        "channel_url": (os.getenv("CHANNEL_URL") or "").strip(),
        "support_url": (os.getenv("SUPPORT_URL") or "").strip(),
    }
    if not db_pool:
        return fallback
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT channel_url, support_url
                    FROM admin_support_links
                    WHERE id = 1
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
    except Exception as e:
        print(f"Support links fallback: {e}")
        return fallback
    if not row:
        return fallback
    return {
        "channel_url": (row.get("channel_url") or fallback["channel_url"] or "").strip(),
        "support_url": (row.get("support_url") or fallback["support_url"] or "").strip(),
    }


async def get_pocket_api_settings_row(include_token: bool = False):
    fallback = {
        "partner_id": "",
        "api_token": "" if include_token else None,
        "api_token_masked": "",
        "api_token_configured": 0,
        "endpoint_template": POCKET_USER_INFO_ENDPOINT_TEMPLATE,
        "updated_at": None,
        "updated_by": None,
    }
    if not db_pool:
        return fallback
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT partner_id, api_token, updated_at, updated_by
                    FROM admin_pocket_api_settings
                    WHERE id = 1
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
    except Exception as e:
        print(f"Pocket API settings fallback: {e}")
        return fallback
    if not row:
        return fallback
    token = str(row.get("api_token") or "").strip()
    settings = {
        "partner_id": str(row.get("partner_id") or "").strip(),
        "api_token_masked": mask_secret(token),
        "api_token_configured": 1 if token else 0,
        "endpoint_template": fallback["endpoint_template"],
        "updated_at": row.get("updated_at"),
        "updated_by": row.get("updated_by"),
    }
    if include_token:
        settings["api_token"] = token
    return settings


def truthy_db(value) -> int:
    try:
        return 1 if int(value or 0) == 1 else 0
    except (TypeError, ValueError):
        return 0


def extract_pocket_balance(payload: Any) -> Optional[float]:
    if not isinstance(payload, dict):
        return None
    for key in ("real_balance", "balance", "total_balance"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return None


async def fetch_pocket_user_info(trader_id: str, partner_id: str, api_token: str) -> Dict[str, Any]:
    url = build_pocket_user_info_url(trader_id, partner_id, api_token)
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=12.0)
        response.raise_for_status()
        return response.json()


async def sync_pocket_balance_for_user(user_row: Dict[str, Any], pocket_settings: Dict[str, Any]) -> bool:
    user_id = int(user_row.get("user_id") or 0)
    trader_id = str(user_row.get("trader_id") or "").strip()
    partner_id = str(pocket_settings.get("partner_id") or "").strip()
    api_token = str(pocket_settings.get("api_token") or "").strip()
    if not user_id or not trader_id or not partner_id or not api_token:
        return False
    try:
        payload = await fetch_pocket_user_info(trader_id, partner_id, api_token)
        balance = extract_pocket_balance(payload)
        if balance is None:
            raise ValueError("Pocket response does not contain balance")
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE users
                    SET balance = %s,
                        balance_synced_at = NOW(),
                        balance_sync_error = NULL
                    WHERE user_id = %s
                    """,
                    (balance, user_id),
                )
        return True
    except Exception as e:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE users
                    SET balance_synced_at = NOW(),
                        balance_sync_error = %s
                    WHERE user_id = %s
                    """,
                    (str(e)[:1000], user_id),
                )
        return False


async def pocket_balance_sync_worker():
    while True:
        try:
            await asyncio.sleep(300)
            if not db_pool:
                continue
            pocket_settings = await get_pocket_api_settings_row(include_token=True)
            if not pocket_settings.get("partner_id") or not pocket_settings.get("api_token"):
                continue
            async with db_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT user_id, trader_id
                        FROM users
                        WHERE balance_sync_enabled = 1
                          AND trader_id IS NOT NULL
                          AND TRIM(trader_id) != ''
                        ORDER BY COALESCE(balance_synced_at, '1970-01-01') ASC, user_id ASC
                        """
                    )
                    users_rows = await cur.fetchall()
            for user_row in users_rows or []:
                await sync_pocket_balance_for_user(user_row, pocket_settings)
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[PocketSync] Worker error: {e}")


async def read_postback_payload(request: Request) -> Dict[str, Any]:
    payload = dict(request.query_params)
    body = await request.body()
    if not body:
        return payload

    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body_payload = json.loads(body.decode("utf-8"))
            if isinstance(body_payload, dict):
                payload.update(body_payload)
        except Exception:
            pass
        return payload

    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        payload.update({key: values[-1] if values else "" for key, values in parsed.items()})
    except Exception:
        pass
    return payload


def get_pocket_postback_secret() -> str:
    return (os.getenv("POCKET_POSTBACK_SECRET") or POCKET_POSTBACK_SECRET or "").strip()


def normalize_deposit_amount(value: Any) -> float:
    try:
        amount = float(str(value or "0").replace(",", "."))
    except (TypeError, ValueError):
        amount = 0.0
    return round(max(amount, 0.0), 2)


async def insert_pocket_postback_log(
    normalized: Dict[str, Any],
    raw_payload: Dict[str, Any],
    status: str,
    reason: Optional[str],
    user_id: Optional[int],
    source_ip: str,
) -> int:
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT IGNORE INTO pocket_postback_events (
                    event_slug, unique_key, user_id, click_id, trader_id, deposit_amount,
                    site_id, cid, sub_id1, sub_id2, raw_payload, status, reason, source_ip
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    normalized.get("event_slug") or "unknown",
                    normalized.get("unique_key") or "unknown",
                    user_id,
                    normalized.get("click_id") or None,
                    normalized.get("trader_id") or None,
                    normalized.get("deposit_amount") or "0.00",
                    normalized.get("site_id") or None,
                    normalized.get("cid") or None,
                    normalized.get("sub_id1") or None,
                    normalized.get("sub_id2") or None,
                    json.dumps(raw_payload, ensure_ascii=False, default=str),
                    status,
                    reason,
                    source_ip,
                ),
            )
            return int(cur.lastrowid)


async def update_pocket_chatterfy_delivery(log_id: int, result: Dict[str, Any]) -> None:
    if not log_id or not db_pool:
        return
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE pocket_postback_events
                SET chatterfy_request_url = %s,
                    chatterfy_status = %s,
                    chatterfy_response_status = %s,
                    chatterfy_response_body = %s,
                    chatterfy_error = %s,
                    chatterfy_sent_at = NOW()
                WHERE id = %s
                """,
                (
                    result.get("url"),
                    result.get("status"),
                    result.get("response_status"),
                    result.get("response_body"),
                    result.get("error") or result.get("reason"),
                    log_id,
                ),
            )


async def send_chatterfy_pocket_postback(
    *,
    log_id: int,
    event_slug: str,
    clickid: str,
    trader_id: str,
    trader_aio_id: str,
    tgid: int,
    revenue: str = "",
    unique_key: str = "",
) -> Dict[str, Any]:
    event_slug = str(event_slug or "").strip()
    clickid = str(clickid or "").strip()
    trader_id = str(trader_id or "").strip()
    trader_aio_id = normalize_aio_visit_uuid(trader_aio_id) or ""
    if event_slug not in CHATTERFY_POCKET_EVENT_SLUGS:
        result = {"status": "skipped", "reason": "unsupported_chatterfy_event"}
        await update_pocket_chatterfy_delivery(log_id, result)
        return result
    if not clickid:
        result = {"status": "skipped", "reason": "missing_chatterfy_clickid"}
        await update_pocket_chatterfy_delivery(log_id, result)
        return result
    try:
        request_url = build_chatterfy_pocket_postback_url(
            event_slug=event_slug,
            clickid=clickid,
            trader_id=trader_id,
            trader_aio_id=trader_aio_id,
            tgid=tgid,
            revenue=revenue,
            unique_key=unique_key,
        )
    except ValueError as exc:
        result = {"status": "skipped", "reason": str(exc)}
        await update_pocket_chatterfy_delivery(log_id, result)
        return result

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(request_url)
        response_body = response.text[:4000]
        result = {
            "url": request_url,
            "status": "sent" if response.status_code < 400 else "failed",
            "response_status": response.status_code,
            "response_body": response_body,
        }
        if response.status_code >= 400:
            result["error"] = f"Chatterfy returned HTTP {response.status_code}"
    except Exception as exc:
        result = {"url": request_url, "status": "failed", "error": str(exc)[:4000]}
    await update_pocket_chatterfy_delivery(log_id, result)
    return result


async def send_aio_pocket_conversion(
    user_id: int,
    event_slug: str,
    trader_id: str,
    unique_key: str,
    revenue: object = None,
) -> Dict[str, Any]:
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}

    normalized_unique_key = str(unique_key or f"{event_slug}:{user_id}:{trader_id}").strip()[:128]
    normalized_trader_id = str(trader_id or "").strip()
    if event_slug == POCKET_REGISTRATION_EVENT:
        aio_event_slug = "pocket_registration"
    elif event_slug == POCKET_FTD_EVENT:
        aio_event_slug = "pocket_ftd"
    elif event_slug == POCKET_DEPOSIT_EVENT:
        aio_event_slug = "pocket_deposit"
    else:
        return {"status": "skipped", "reason": "unsupported_pocket_event"}

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT aio_visit_uuid FROM users WHERE user_id = %s LIMIT 1", (user_id,))
            user_row = await cur.fetchone()
            aio_visit_uuid = normalize_aio_visit_uuid((user_row or {}).get("aio_visit_uuid"))
            if not aio_visit_uuid:
                return {"status": "skipped", "reason": "missing_aio_visit_uuid"}

            try:
                if event_slug == POCKET_REGISTRATION_EVENT:
                    request_url = build_aio_pocket_registration_conversion_url(aio_visit_uuid, user_id, normalized_trader_id)
                elif event_slug == POCKET_FTD_EVENT:
                    request_url = build_aio_pocket_ftd_conversion_url(aio_visit_uuid, revenue, user_id, normalized_trader_id)
                else:
                    request_url = build_aio_pocket_deposit_conversion_url(aio_visit_uuid, revenue, user_id, normalized_trader_id)
            except ValueError as exc:
                return {"status": "skipped", "reason": str(exc)}

            await cur.execute(
                """
                INSERT IGNORE INTO aio_postback_events (
                    user_id, aio_visit_uuid, event_slug, unique_key, revenue, request_url, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                """,
                (user_id, aio_visit_uuid, aio_event_slug, normalized_unique_key, normalize_aio_revenue(revenue), request_url),
            )
            if cur.rowcount == 0:
                return {"status": "skipped", "reason": "duplicate"}
            event_id = cur.lastrowid

    response_status = None
    response_body = ""
    error_text = None
    final_status = "sent"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(request_url)
        response_status = response.status_code
        response_body = response.text[:4000]
        if response.status_code >= 400:
            final_status = "failed"
            error_text = f"AIO returned HTTP {response.status_code}"
    except Exception as exc:
        final_status = "failed"
        error_text = str(exc)[:4000]

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE aio_postback_events
                SET status = %s,
                    response_status = %s,
                    response_body = %s,
                    error = %s,
                    sent_at = NOW()
                WHERE id = %s
                """,
                (final_status, response_status, response_body, error_text, event_id),
            )
    return {"status": final_status, "event_id": event_id, "response_status": response_status, "error": error_text}


@app.api_route("/api/integrations/pocket/postback", methods=["GET", "POST"])
async def pocket_postback(request: Request):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    expected_secret = get_pocket_postback_secret()
    if not expected_secret:
        raise HTTPException(status_code=503, detail="Pocket postback secret is not configured")

    payload = await read_postback_payload(request)
    provided_secret = str(payload.get("secret") or request.headers.get("X-Pocket-Secret") or "").strip()
    if not provided_secret or not secrets.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=403, detail="Invalid postback secret")

    normalized = normalize_pocket_postback_payload(payload)
    source_ip = request.client.host if request.client else ""
    event_slug = normalized.get("event_slug")
    telegram_id = normalized.get("telegram_id")
    click_id = normalized.get("click_id") or ""
    trader_id = normalized.get("trader_id") or ""
    site_id = normalized.get("site_id") or ""
    cid = normalized.get("cid") or ""
    sub_id1 = normalized.get("sub_id1") or ""
    sub_id2 = normalized.get("sub_id2") or ""
    deposit_amount = normalize_deposit_amount(normalized.get("deposit_amount"))

    if event_slug not in {POCKET_REGISTRATION_EVENT, POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT}:
        log_id = await insert_pocket_postback_log(normalized, payload, "skipped", "unsupported_event", telegram_id, source_ip)
        return {"status": "skipped", "reason": "unsupported_event", "log_id": log_id}

    if not telegram_id:
        log_id = await insert_pocket_postback_log(normalized, payload, "skipped", "missing_click_id", None, source_ip)
        return {"status": "skipped", "reason": "missing_click_id", "log_id": log_id}

    if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT} and deposit_amount <= 0:
        log_id = await insert_pocket_postback_log(normalized, payload, "skipped", "invalid_deposit_amount", telegram_id, source_ip)
        return {"status": "skipped", "reason": "invalid_deposit_amount", "log_id": log_id}

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id, aio_visit_uuid FROM users WHERE user_id = %s LIMIT 1", (telegram_id,))
            user_row = await cur.fetchone()
            if not user_row:
                log_id = await insert_pocket_postback_log(normalized, payload, "skipped", "user_not_found", telegram_id, source_ip)
                return {"status": "skipped", "reason": "user_not_found", "log_id": log_id}

            if event_slug == POCKET_REGISTRATION_EVENT:
                await cur.execute(
                    """
                    UPDATE users
                    SET trader_id = CASE WHEN %s <> '' THEN %s ELSE trader_id END,
                        pocket_click_id = CASE WHEN %s <> '' THEN %s ELSE pocket_click_id END,
                        pocket_site_id = CASE WHEN %s <> '' THEN %s ELSE pocket_site_id END,
                        pocket_cid = CASE WHEN %s <> '' THEN %s ELSE pocket_cid END,
                        pocket_sub_id1 = CASE WHEN %s <> '' THEN %s ELSE pocket_sub_id1 END,
                        pocket_sub_id2 = CASE WHEN %s <> '' THEN %s ELSE pocket_sub_id2 END,
                        pocket_registered = 1,
                        pocket_registered_at = COALESCE(pocket_registered_at, DATE_FORMAT(NOW(), '%%Y-%%m-%%dT%%H:%%i:%%sZ')),
                        pocket_checked_at = NOW()
                    WHERE user_id = %s
                    """,
                    (
                        trader_id, trader_id, click_id, click_id, site_id, site_id, cid, cid,
                        sub_id1, sub_id1, sub_id2, sub_id2, telegram_id,
                    ),
                )
            else:
                await cur.execute(
                    """
                    UPDATE users
                    SET trader_id = CASE WHEN %s <> '' THEN %s ELSE trader_id END,
                        pocket_click_id = CASE WHEN %s <> '' THEN %s ELSE pocket_click_id END,
                        pocket_site_id = CASE WHEN %s <> '' THEN %s ELSE pocket_site_id END,
                        pocket_cid = CASE WHEN %s <> '' THEN %s ELSE pocket_cid END,
                        pocket_sub_id1 = CASE WHEN %s <> '' THEN %s ELSE pocket_sub_id1 END,
                        pocket_sub_id2 = CASE WHEN %s <> '' THEN %s ELSE pocket_sub_id2 END,
                        pocket_registered = 1,
                        pocket_registered_at = COALESCE(pocket_registered_at, DATE_FORMAT(NOW(), '%%Y-%%m-%%dT%%H:%%i:%%sZ')),
                        pocket_deposited = 1,
                        pocket_deposit_amount = COALESCE(pocket_deposit_amount, 0) + %s,
                        pocket_checked_at = NOW()
                    WHERE user_id = %s
                    """,
                    (
                        trader_id, trader_id, click_id, click_id, site_id, site_id, cid, cid,
                        sub_id1, sub_id1, sub_id2, sub_id2, f"{deposit_amount:.2f}", telegram_id,
                    ),
                )
            await cur.execute(
                """
                SELECT COALESCE(pocket_deposit_amount, 0) AS pocket_deposit_amount
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (telegram_id,),
            )
            updated_user_row = await cur.fetchone()

    status = "registered" if event_slug == POCKET_REGISTRATION_EVENT else "deposited"
    log_id = await insert_pocket_postback_log(normalized, payload, status, None, telegram_id, source_ip)
    total_deposit_amount = normalize_deposit_amount((updated_user_row or {}).get("pocket_deposit_amount"))
    aio_result = await send_aio_pocket_conversion(
        user_id=int(telegram_id),
        event_slug=event_slug,
        unique_key=normalized.get("unique_key") or event_slug,
        trader_id=trader_id,
        revenue=f"{deposit_amount:.2f}" if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT} else "",
    )
    chatterfy_result = await send_chatterfy_pocket_postback(
        log_id=log_id,
        event_slug=event_slug,
        clickid=sub_id2,
        trader_id=trader_id,
        trader_aio_id=(user_row or {}).get("aio_visit_uuid") or "",
        tgid=int(telegram_id),
        revenue=f"{deposit_amount:.2f}" if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT} else "",
        unique_key=normalized.get("unique_key") or event_slug,
    )
    return {
        "status": status,
        "log_id": log_id,
        "user_id": telegram_id,
        "event": event_slug,
        "trader_id": trader_id or None,
        "deposit_amount": f"{deposit_amount:.2f}" if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT} else None,
        "total_deposit_amount": f"{total_deposit_amount:.2f}" if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT} else None,
        "site_id": site_id or None,
        "cid": cid or None,
        "sub_id1": sub_id1 or None,
        "sub_id2": sub_id2 or None,
        "aio": aio_result,
        "chatterfy": chatterfy_result,
    }


def normalize_access_payload(value) -> int:
    return 1 if bool(value) else 0


async def fetch_admin_user_row(cur, user_id: int) -> Optional[Dict[str, Any]]:
    await cur.execute(
        """
        SELECT u.user_id, u.username, u.first_name, u.avatar_url, u.mode, u.lang, u.strategy_id,
               u.trader_id, COALESCE(u.balance, 0) AS balance,
               COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
               u.balance_synced_at, u.balance_sync_error,
               COALESCE(fx.is_enabled, 1) AS forex_access,
               COALESCE(bin.is_enabled, 1) AS binary_access,
               COALESCE(u.is_blocked, 0) AS is_blocked, u.blocked_at, u.blocked_by, u.created_at,
               p.name AS strategy_name,
               CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
               a.granted_at
        FROM users u
        LEFT JOIN presets p ON p.id = u.strategy_id
        LEFT JOIN admin_users a ON a.user_id = u.user_id
        LEFT JOIN user_mode_access fx ON fx.user_id = u.user_id AND fx.mode = 'forex'
        LEFT JOIN user_mode_access bin ON bin.user_id = u.user_id AND bin.mode = 'binary'
        WHERE u.user_id = %s
        LIMIT 1
        """,
        (user_id,),
    )
    return await cur.fetchone()


@app.get("/api/support/links")
async def get_support_links():
    links = await get_support_links_row()
    channel_url = links["channel_url"]
    support_url = links["support_url"]
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
                    SELECT u.user_id, u.username, u.first_name, u.avatar_url, u.mode, u.lang, u.strategy_id,
                           u.trader_id, COALESCE(u.balance, 0) AS balance,
                           COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
                           u.balance_synced_at, u.balance_sync_error,
                           COALESCE(fx.is_enabled, 1) AS forex_access,
                           COALESCE(bin.is_enabled, 1) AS binary_access,
                           COALESCE(u.is_blocked, 0) AS is_blocked, u.blocked_at, u.blocked_by, u.created_at,
                           p.name AS strategy_name,
                           CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
                           a.granted_at
                    FROM users u
                    LEFT JOIN presets p ON p.id = u.strategy_id
                    LEFT JOIN admin_users a ON a.user_id = u.user_id
                    LEFT JOIN user_mode_access fx ON fx.user_id = u.user_id AND fx.mode = 'forex'
                    LEFT JOIN user_mode_access bin ON bin.user_id = u.user_id AND bin.mode = 'binary'
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
                    SELECT u.user_id, u.username, u.first_name, u.avatar_url, u.mode, u.lang, u.strategy_id,
                           NULL AS trader_id, 0 AS balance,
                           0 AS balance_sync_enabled, NULL AS balance_synced_at, NULL AS balance_sync_error,
                           1 AS forex_access, 1 AS binary_access,
                           0 AS is_blocked, NULL AS blocked_at, NULL AS blocked_by, NULL AS created_at,
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


@app.post("/api/admin/users/block")
async def admin_block_user(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    is_blocked = 1 if bool(data.get("is_blocked")) else 0
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")
    if target_user_id == int(admin.get("user_id") or 0) and is_blocked:
        raise HTTPException(status_code=400, detail="You cannot block yourself")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id FROM users WHERE user_id = %s LIMIT 1", (target_user_id,))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
            await cur.execute(
                """
                UPDATE users
                SET is_blocked = %s,
                    blocked_by = CASE WHEN %s = 1 THEN %s ELSE NULL END,
                    blocked_at = CASE WHEN %s = 1 THEN NOW() ELSE NULL END
                WHERE user_id = %s
                """,
                (is_blocked, is_blocked, int(admin.get("user_id") or 0), is_blocked, target_user_id),
            )
            row = await fetch_admin_user_row(cur, target_user_id)
    return {"status": "success", "user": row}


@app.post("/api/admin/users/access")
async def admin_update_user_access(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")

    forex_access = normalize_access_payload(data.get("forex_access"))
    binary_access = normalize_access_payload(data.get("binary_access"))
    updated_by = int(admin.get("user_id") or 0)

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id, mode FROM users WHERE user_id = %s LIMIT 1", (target_user_id,))
            user_row = await cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")

            await cur.executemany(
                """
                INSERT INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    is_enabled = VALUES(is_enabled),
                    updated_by = VALUES(updated_by)
                """,
                [
                    (target_user_id, "forex", forex_access, updated_by),
                    (target_user_id, "binary", binary_access, updated_by),
                ],
            )

            current_mode = str(user_row.get("mode") or "forex").lower()
            if current_mode == "forex" and forex_access != 1 and binary_access == 1:
                await cur.execute("UPDATE users SET mode = 'binary' WHERE user_id = %s", (target_user_id,))
            elif current_mode == "binary" and binary_access != 1 and forex_access == 1:
                await cur.execute("UPDATE users SET mode = 'forex' WHERE user_id = %s", (target_user_id,))

            row = await fetch_admin_user_row(cur, target_user_id)
    return {"status": "success", "user": row}


@app.post("/api/admin/users/balance")
async def admin_update_user_balance(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")
    try:
        balance = round(float(data.get("balance")), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Balance must be a number")
    if balance < 0:
        raise HTTPException(status_code=400, detail="Balance cannot be negative")

    sync_enabled = 1 if bool(data.get("balance_sync_enabled")) else 0
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id, trader_id FROM users WHERE user_id = %s LIMIT 1", (target_user_id,))
            user_row = await cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")
            if sync_enabled == 1 and not str(user_row.get("trader_id") or "").strip():
                raise HTTPException(status_code=400, detail="Trader ID is required for balance sync")
            await cur.execute(
                """
                UPDATE users
                SET balance = %s,
                    balance_sync_enabled = %s,
                    balance_sync_error = CASE WHEN %s = 0 THEN NULL ELSE balance_sync_error END
                WHERE user_id = %s
                """,
                (balance, sync_enabled, sync_enabled, target_user_id),
            )
            row = await fetch_admin_user_row(cur, target_user_id)
    return {"status": "success", "user": row}


@app.delete("/api/admin/users/{target_user_id}")
async def admin_delete_user(target_user_id: int, admin=Depends(get_admin_user)):
    target_user_id = int(target_user_id or 0)
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")
    if target_user_id == int(admin.get("user_id") or 0):
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id FROM users WHERE user_id = %s LIMIT 1", (target_user_id,))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            await cur.execute(
                """
                SELECT up.preset_id
                FROM user_presets up
                JOIN presets p ON p.id = up.preset_id
                WHERE up.user_id = %s AND p.is_system = 0
                """,
                (target_user_id,),
            )
            custom_preset_ids = [int(row["preset_id"]) for row in (await cur.fetchall() or [])]

            await cur.execute(
                "SELECT id FROM ai_chats WHERE user_id = %s",
                (target_user_id,),
            )
            chat_ids = [int(row["id"]) for row in (await cur.fetchall() or [])]

        async with conn.cursor() as cur:
            if chat_ids:
                placeholders = ",".join(["%s"] * len(chat_ids))
                await cur.execute(f"DELETE FROM ai_messages WHERE chat_id IN ({placeholders})", tuple(chat_ids))
            await cur.execute("DELETE FROM ai_chats WHERE user_id = %s", (target_user_id,))
            await cur.execute("DELETE FROM user_analyses WHERE user_id = %s", (target_user_id,))
            await cur.execute("DELETE FROM user_mode_access WHERE user_id = %s", (target_user_id,))
            await cur.execute("DELETE FROM admin_users WHERE user_id = %s", (target_user_id,))
            await cur.execute("DELETE FROM user_presets WHERE user_id = %s", (target_user_id,))
            if custom_preset_ids:
                placeholders = ",".join(["%s"] * len(custom_preset_ids))
                await cur.execute(f"DELETE FROM preset_indicators WHERE preset_id IN ({placeholders})", tuple(custom_preset_ids))
                await cur.execute(
                    f"DELETE FROM presets WHERE is_system = 0 AND id IN ({placeholders})",
                    tuple(custom_preset_ids),
                )
            await cur.execute("DELETE FROM users WHERE user_id = %s", (target_user_id,))
    return {"status": "success", "user_id": target_user_id}


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


@app.get("/api/admin/market-options")
async def admin_market_options(
    kind: str = Query(default="forex"),
    min_payout: int = Query(default=DEVSBITE_MIN_PAYOUT, ge=0, le=100),
    admin=Depends(get_admin_user),
):
    return await get_market_options_payload(kind, min_payout)


@app.get("/api/admin/stream-assets")
async def admin_stream_assets(
    analysis_type: str = Query(default="forex"),
    market: str = Query(default="currencies"),
    min_payout: int = Query(default=DEVSBITE_MIN_PAYOUT, ge=0, le=100),
    admin=Depends(get_admin_user),
):
    return await get_stream_asset_options_payload(analysis_type, market, min_payout)


@app.get("/api/admin/settings")
async def admin_settings(admin=Depends(get_admin_user)):
    stream_settings = await get_stream_settings_row()
    support_links = await get_support_links_row()
    pocket_settings = await get_pocket_api_settings_row()
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
            "support": support_links,
            "pocket_api": pocket_settings,
        },
    }


@app.post("/api/admin/settings")
async def admin_settings_update(request: Request, admin=Depends(get_admin_user)):
    data = await request.json()
    ai_data = data.get("ai") or {}
    streams_data = data.get("streams") or {}
    support_data = data.get("support") or {}
    pocket_data = data.get("pocket_api") or {}
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

                emulation_analysis_type = str(streams_data.get("emulation_analysis_type") or "forex").strip().lower()
                if emulation_analysis_type not in ("forex", "binary"):
                    emulation_analysis_type = "forex"
                emulation_market_raw = str(streams_data.get("emulation_market") or "").strip()
                if emulation_analysis_type == "binary":
                    emulation_market = normalize_market_kind(emulation_market_raw) if emulation_market_raw else ""
                else:
                    emulation_market = normalize_forex_stream_market(emulation_market_raw) if emulation_market_raw else "currencies"
                emulation_symbol = str(streams_data.get("emulation_symbol") or "").strip()[:128]
                raw_emulation_price = streams_data.get("emulation_price")
                try:
                    emulation_price = (
                        float(raw_emulation_price)
                        if raw_emulation_price is not None and str(raw_emulation_price).strip()
                        else None
                    )
                except (TypeError, ValueError):
                    emulation_price = None
                if emulation_price is not None and emulation_price <= 0:
                    raise HTTPException(status_code=400, detail="emulation_price must be greater than zero")
                emulation_strategy_id = streams_data.get("emulation_strategy_id", strategy_id)
                try:
                    emulation_strategy_id = (
                        int(emulation_strategy_id)
                        if emulation_strategy_id is not None and str(emulation_strategy_id).strip()
                        else strategy_id
                    )
                except (TypeError, ValueError):
                    emulation_strategy_id = strategy_id

                indicator_mode = str(streams_data.get("indicator_mode") or "auto").strip().lower()
                if indicator_mode not in ("auto", "manual"):
                    indicator_mode = "auto"

                raw_indicator_overrides = streams_data.get("indicator_overrides")
                indicator_overrides = {}
                if isinstance(raw_indicator_overrides, dict):
                    for raw_key, raw_entry in raw_indicator_overrides.items():
                        key_norm = str(raw_key or "").strip().upper().replace(" ", "").replace("_", "").replace("-", "")
                        if not key_norm:
                            continue
                        if isinstance(raw_entry, dict):
                            signal = str(raw_entry.get("signal") or "AUTO").strip().upper()
                            value = str(raw_entry.get("value") or "").strip()
                        else:
                            signal = str(raw_entry or "").strip().upper()
                            value = ""
                        entry = {}
                        if signal in ("BUY", "SELL", "NEUTRAL"):
                            entry["signal"] = signal
                        if value:
                            entry["value"] = value[:64]
                        if entry:
                            indicator_overrides[key_norm] = entry
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
                        emulation_analysis_type,
                        emulation_market,
                        emulation_symbol,
                        emulation_price,
                        emulation_strategy_id,
                        updated_by
                    )
                    VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        emulation_analysis_type = VALUES(emulation_analysis_type),
                        emulation_market = VALUES(emulation_market),
                        emulation_symbol = VALUES(emulation_symbol),
                        emulation_price = VALUES(emulation_price),
                        emulation_strategy_id = VALUES(emulation_strategy_id),
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
                        emulation_analysis_type,
                        emulation_market,
                        emulation_symbol,
                        emulation_price,
                        emulation_strategy_id,
                        updated_by,
                    ),
                )
            if isinstance(support_data, dict) and support_data:
                channel_url = str(support_data.get("channel_url") or "").strip()[:1000]
                support_url = str(support_data.get("support_url") or "").strip()[:1000]
                await cur.execute(
                    """
                    INSERT INTO admin_support_links (id, channel_url, support_url, updated_by)
                    VALUES (1, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        channel_url = VALUES(channel_url),
                        support_url = VALUES(support_url),
                        updated_by = VALUES(updated_by)
                    """,
                    (channel_url, support_url, int(admin["user_id"])),
                )
            if isinstance(pocket_data, dict) and pocket_data:
                partner_id = str(pocket_data.get("partner_id") or "").strip()[:64]
                api_token = str(pocket_data.get("api_token") or "").strip()
                clear_token = bool(pocket_data.get("clear_api_token"))
                if api_token:
                    await cur.execute(
                        """
                        INSERT INTO admin_pocket_api_settings (id, partner_id, api_token, updated_by)
                        VALUES (1, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            partner_id = VALUES(partner_id),
                            api_token = VALUES(api_token),
                            updated_by = VALUES(updated_by)
                        """,
                        (partner_id, api_token, int(admin["user_id"])),
                    )
                else:
                    await cur.execute(
                        """
                        INSERT INTO admin_pocket_api_settings (id, partner_id, api_token, updated_by)
                        VALUES (1, %s, NULL, %s)
                        ON DUPLICATE KEY UPDATE
                            partner_id = VALUES(partner_id),
                            api_token = CASE WHEN %s = 1 THEN NULL ELSE api_token END,
                            updated_by = VALUES(updated_by)
                        """,
                        (partner_id, int(admin["user_id"]), 1 if clear_token else 0),
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
    seconds = parse_timeframe_seconds(tf)
    return max(1, int((seconds + 59) // 60))

def parse_timeframe_seconds(tf: str) -> int:
    if not tf:
        return 5 * 60
    tf = str(tf).strip().lower()
    try:
        if tf.endswith('sec'): return max(1, int(tf[:-3]))
        if tf.endswith('s'): return max(1, int(tf[:-1]))
        if tf.endswith('min'): return max(1, int(tf[:-3]) * 60)
        if tf.endswith('m'): return max(1, int(tf[:-1]) * 60)
        if tf.endswith('hour'): return max(1, int(tf[:-4]) * 60 * 60)
        if tf.endswith('h'): return max(1, int(tf[:-1]) * 60 * 60)
        if tf.endswith('day'): return max(1, int(tf[:-3]) * 24 * 60 * 60)
        if tf.endswith('d'): return max(1, int(tf[:-1]) * 24 * 60 * 60)
    except:
        pass
    return 5 * 60

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

def extract_price_from_payload(payload: Any) -> Optional[float]:
    def as_float(value: Any) -> Optional[float]:
        try:
            price = float(value)
            return price if price > 0 else None
        except (TypeError, ValueError):
            return None

    def walk(node: Any) -> Optional[float]:
        if isinstance(node, dict):
            for key in ("price", "last", "last_price", "close", "value", "bid", "ask", "mid", "current_price"):
                price = as_float(node.get(key))
                if price:
                    return price
            for key in ("candles", "history", "points", "ticks", "quotes", "series", "values", "data", "result", "snapshot", "quote"):
                nested = node.get(key)
                price = walk(nested)
                if price:
                    return price
            for nested in node.values():
                if isinstance(nested, (dict, list)):
                    price = walk(nested)
                    if price:
                        return price
        elif isinstance(node, list):
            for item in reversed(node):
                if isinstance(item, (dict, list)):
                    price = walk(item)
                    if price:
                        return price
                else:
                    price = as_float(item)
                    if price and price < 100000000:
                        return price
        return None

    return walk(payload)

def normalize_binary_quote_symbol(symbol: str) -> str:
    return str(symbol or "").strip()

def build_binary_quote_symbol_candidates(symbol: str) -> List[str]:
    raw = normalize_binary_quote_symbol(symbol)
    if not raw:
        return []
    cleaned_key = "".join(ch for ch in raw.lower() if ch.isalnum())
    cleaned_key = cleaned_key.replace("otc", "").replace("spot", "")
    aliases = {
        "gas": ["Natural Gas OTC", "Natural Gas", "NG/USD", "NGUSD", "Gas OTC"],
        "naturalgas": ["Natural Gas OTC", "Natural Gas", "NG/USD", "NGUSD", "Gas OTC"],
        "cotton": ["Cotton OTC", "Cotton", "CT1", "COTN"],
        "sugar": ["SB1", "Sugar OTC", "Sugar"],
        "cocoa": ["CC1", "COCO", "Cocoa OTC", "Cocoa"],
        "coffee": ["KC1", "COFF", "Coffee OTC", "Coffee"],
        "soy": ["SOYB", "Soybean OTC", "Soybeans OTC", "Soybean", "Soybeans", "S_1"],
        "soya": ["SOYB", "Soybean OTC", "Soybeans OTC", "Soybean", "Soybeans", "S_1"],
        "soybean": ["SOYB", "Soybean OTC", "Soybeans OTC", "Soybean", "Soybeans", "S_1"],
        "soybeans": ["SOYB", "Soybean OTC", "Soybeans OTC", "Soybean", "Soybeans", "S_1"],
        "corn": ["CORN", "Corn OTC", "Corn", "C_1"],
        "maize": ["CORN", "Corn OTC", "Corn", "C_1"],
        "wheat": ["WEAT", "Wheat OTC", "Wheat", "W_1"],
    }
    candidates = [raw]
    candidates.extend(aliases.get(cleaned_key, []))
    if not raw.lower().endswith("otc"):
        candidates.append(f"{raw} OTC")
    candidates.extend([raw.title(), raw.upper()])
    unique = []
    seen = set()
    for item in candidates:
        item = str(item or "").strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def build_binary_quote_category_candidates(category: str) -> List[str]:
    market_kind = normalize_market_kind(category)
    candidates = [market_kind]
    if market_kind == "commodities":
        candidates.extend(["commodity", "otc"])
    unique = []
    seen = set()
    for item in candidates:
        key = str(item).lower()
        if item and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def normalize_twelvedata_interval(interval: str) -> str:
    raw = str(interval or "").strip().lower()
    mapping = {
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
        "1d": "1day",
    }
    if raw in mapping:
        return mapping[raw]
    if raw in ("1min", "5min", "15min", "30min", "45min", "1h", "2h", "4h", "8h", "1day", "1week", "1month"):
        return raw
    if raw.endswith("s"):
        return "1min"
    return "5min"

async def fetch_twelvedata_payload(symbol: str, interval: str, outputsize: int = 120) -> Dict[str, Any]:
    api_key = (os.getenv("TD_API_KEY") or os.getenv("TWELVEDATA_API_KEY") or "").strip()
    if not api_key:
        return {}
    candidates = get_twelvedata_symbol_candidates(symbol)
    if not candidates:
        return {}
    headers = {"accept": "application/json", "Cache-Control": "no-cache"}
    td_interval = normalize_twelvedata_interval(interval)
    async with httpx.AsyncClient() as client:
        last_payload: Dict[str, Any] = {}
        for td_symbol, exchange in candidates:
            params = {
                "symbol": td_symbol,
                "interval": td_interval,
                "outputsize": max(2, int(outputsize or 120)),
                "apikey": api_key,
            }
            if exchange:
                params["exchange"] = exchange
            try:
                response = await client.get("https://api.twelvedata.com/time_series", headers=headers, params=params, timeout=15.0)
                payload = response.json()
                if isinstance(payload, dict):
                    last_payload = payload
                values = payload.get("values") if isinstance(payload, dict) else None
                if response.status_code == 200 and isinstance(values, list) and values:
                    payload["values"] = list(reversed(values))
                    payload["_resolved_quote_symbol"] = td_symbol
                    payload["_resolved_quote_exchange"] = exchange or ""
                    payload["_quote_source"] = "twelvedata_time_series"
                    return payload
            except Exception:
                pass

            params = {"symbol": td_symbol, "apikey": api_key}
            if exchange:
                params["exchange"] = exchange
            try:
                response = await client.get("https://api.twelvedata.com/price", headers=headers, params=params, timeout=12.0)
                payload = response.json()
                if isinstance(payload, dict):
                    last_payload = payload
                price = extract_price_from_payload(payload)
                if response.status_code == 200 and price:
                    payload["_resolved_quote_symbol"] = td_symbol
                    payload["_resolved_quote_exchange"] = exchange or ""
                    payload["_quote_source"] = "twelvedata_price"
                    return payload
            except Exception:
                pass
        return last_payload if isinstance(last_payload, dict) else {}

def extract_quote_ohlc_rows(payload: Any) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []

    def as_float(value: Any) -> Optional[float]:
        try:
            parsed = float(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            return None

    def ci_get(node: Dict[str, Any], *keys: str) -> Any:
        for wanted in keys:
            for key, value in node.items():
                if str(key).lower() == wanted.lower():
                    return value
        return None

    def row_from_item(item: Any) -> Optional[Dict[str, float]]:
        if isinstance(item, dict):
            close = as_float(ci_get(item, "close", "price", "value", "last", "last_price", "bid", "ask", "current_price"))
            if close is None:
                return None
            open_price = as_float(ci_get(item, "open", "previous", "previous_close", "prev_close"))
            high = as_float(ci_get(item, "high")) or max(close, open_price or close)
            low = as_float(ci_get(item, "low")) or min(close, open_price or close)
            return {"high": high, "low": low, "close": close}
        if isinstance(item, (list, tuple)):
            nums = [as_float(value) for value in item]
            nums = [value for value in nums if value is not None]
            if not nums:
                return None
            if len(nums) >= 5 and nums[0] > 100000000:
                open_price, high, low, close = nums[1], nums[2], nums[3], nums[4]
            elif len(nums) >= 4:
                open_price, high, low, close = nums[-4], nums[-3], nums[-2], nums[-1]
            else:
                close = nums[-1]
                open_price = nums[-2] if len(nums) > 1 else close
                high = max(open_price, close)
                low = min(open_price, close)
            return {"high": max(high, low, close), "low": min(high, low, close), "close": close}
        return None

    def walk(node: Any) -> None:
        if rows:
            return
        if isinstance(node, list):
            parsed = [row_from_item(item) for item in node]
            rows.extend([item for item in parsed if item])
            return
        if not isinstance(node, dict):
            return
        for key in ("candles", "history", "points", "ticks", "quotes", "series", "data", "values", "result", "snapshot", "quote"):
            value = node.get(key)
            if isinstance(value, list):
                parsed = [row_from_item(item) for item in value]
                rows.extend([item for item in parsed if item])
                if rows:
                    return
            elif isinstance(value, dict):
                walk(value)
                if rows:
                    return
        direct_row = row_from_item(node)
        if direct_row:
            rows.append(direct_row)
            return
        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)
                if rows:
                    return

    walk(payload)
    return rows

def build_binary_quote_candles(payload: Any, price: float, symbol: str, interval: str) -> List[Dict[str, float]]:
    candles = extract_quote_ohlc_rows(payload)
    if len(candles) >= 2:
        return candles

    def find_number(node: Any, *keys: str) -> Optional[float]:
        if isinstance(node, dict):
            for wanted in keys:
                for key, value in node.items():
                    if str(key).lower() == wanted.lower():
                        try:
                            parsed = float(value)
                            if parsed > 0:
                                return parsed
                        except (TypeError, ValueError):
                            pass
            for value in node.values():
                if isinstance(value, (dict, list)):
                    found = find_number(value, *keys)
                    if found:
                        return found
        elif isinstance(node, list):
            for value in reversed(node):
                found = find_number(value, *keys)
                if found:
                    return found
        return None

    previous = find_number(payload, "open", "previous", "previous_close", "prev_close", "reference_price")
    if not previous:
        change = find_number(payload, "change", "price_change")
        if change and price > change:
            previous = price - change
    if not previous:
        change_pct = find_number(payload, "change_percent", "percent_change", "change_pct")
        if change_pct and change_pct > -99:
            previous = price / (1 + (change_pct / 100))
    if not previous:
        seed = sum((index + 1) * ord(char) for index, char in enumerate(f"{symbol}|{interval}"))
        direction = 1 if seed % 2 else -1
        magnitude = price * (0.0008 + ((seed % 9) * 0.00015))
        previous = max(price - (direction * magnitude), price * 0.0001)

    spread = max(abs(price - previous), price * 0.0006)
    first = {
        "high": max(previous, price) + spread * 0.35,
        "low": min(previous, price) - spread * 0.35,
        "close": previous,
    }
    second = {
        "high": max(previous, price) + spread * 0.2,
        "low": min(previous, price) - spread * 0.2,
        "close": price,
    }
    return [first, second]

def calculate_ema_values(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    ema = values[0]
    result = [ema]
    for value in values[1:]:
        ema = (value * alpha) + (ema * (1 - alpha))
        result.append(ema)
    return result

def calculate_binary_quote_indicators(candles: List[Dict[str, float]], price: float) -> Dict[str, Any]:
    closes = [float(item["close"]) for item in candles if item.get("close")]
    highs = [float(item["high"]) for item in candles if item.get("high")]
    lows = [float(item["low"]) for item in candles if item.get("low")]
    indicators: Dict[str, Any] = {}
    if len(closes) < 2:
        return indicators

    def last_ema(period: int) -> Optional[float]:
        source = closes[-max(period * 3, period):]
        if len(source) < 2:
            return None
        return calculate_ema_values(source, period)[-1]

    ema9 = last_ema(9)
    ema21 = last_ema(21)
    ema50 = last_ema(50) or (sum(closes[-50:]) / min(len(closes), 50))
    ema200 = last_ema(200) or (sum(closes) / len(closes))
    indicators["EMA9"] = {"ema": ema9 or price}
    indicators["EMA21"] = {"ema": ema21 or ema50}
    indicators["EMA50"] = {"ema": ema50}
    indicators["EMA200"] = {"ema": ema200}

    gains: List[float] = []
    losses: List[float] = []
    for current, previous in zip(closes[-15:], closes[-16:-1]):
        delta = current - previous
        gains.append(max(delta, 0))
        losses.append(abs(min(delta, 0)))
    if gains and losses:
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        rsi = 100.0 if avg_loss == 0 else 100 - (100 / (1 + (avg_gain / avg_loss)))
        indicators["RSI"] = {"rsi": rsi}

    macd_fast = calculate_ema_values(closes[-80:], 12)
    macd_slow = calculate_ema_values(closes[-80:], 26)
    if macd_fast and macd_slow:
        macd_line_series = [fast - slow for fast, slow in zip(macd_fast[-len(macd_slow):], macd_slow)]
        signal_series = calculate_ema_values(macd_line_series, 9)
        if macd_line_series and signal_series:
            indicators["MACD"] = {"macd": macd_line_series[-1], "macd_signal": signal_series[-1]}

    if len(highs) >= 14 and len(lows) >= 14 and len(closes) >= 14:
        recent_high = max(highs[-14:])
        recent_low = min(lows[-14:])
        if recent_high > recent_low:
            k = ((price - recent_low) / (recent_high - recent_low)) * 100
            prev_closes = closes[-17:-2] if len(closes) >= 17 else closes[:-1]
            d_values = []
            for idx in range(max(0, len(prev_closes) - 3), len(prev_closes)):
                window_high = max(highs[max(0, idx - 13):idx + 1] or [recent_high])
                window_low = min(lows[max(0, idx - 13):idx + 1] or [recent_low])
                close_value = prev_closes[idx] if idx < len(prev_closes) else price
                if window_high > window_low:
                    d_values.append(((close_value - window_low) / (window_high - window_low)) * 100)
            indicators["STOCH"] = {"slow_k": k, "slow_d": (sum(d_values) / len(d_values)) if d_values else k}

    if len(closes) >= 20:
        window = closes[-20:]
        middle = sum(window) / len(window)
        variance = sum((value - middle) ** 2 for value in window) / len(window)
        deviation = variance ** 0.5
        indicators["BB"] = {"lower_band": middle - 2 * deviation, "upper_band": middle + 2 * deviation}

    true_ranges = []
    for index in range(1, len(candles)):
        high = float(candles[index]["high"])
        low = float(candles[index]["low"])
        prev_close = float(candles[index - 1]["close"])
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    if true_ranges:
        indicators["ATR"] = {"atr": sum(true_ranges[-14:]) / min(len(true_ranges), 14)}

    return indicators

async def fetch_binary_quote_payload(
    category: str,
    symbol: str,
    history_seconds: int = 300,
    prefer_history: bool = False,
) -> Dict[str, Any]:
    token = DEVSBITE_CLIENT_TOKEN or os.getenv("DEVSBITE_TOKEN") or ""
    if not token:
        return {}
    market_kind = normalize_market_kind(category)
    symbol_candidates = build_binary_quote_symbol_candidates(symbol)
    category_candidates = build_binary_quote_category_candidates(market_kind)
    headers = {
        "accept": "application/json",
        "X-Client-Token": token,
        "Cache-Control": "no-cache",
    }
    async with httpx.AsyncClient() as client:
        async def request_price(params: Dict[str, str]) -> Dict[str, Any]:
            try:
                response = await client.get(f"{DEVSBITE_API_BASE_URL}/quotes/price", headers=headers, params=params, timeout=10.0)
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}

        async def request_history(params: Dict[str, str]) -> Dict[str, Any]:
            try:
                response = await client.get(
                    f"{DEVSBITE_API_BASE_URL}/quotes/quote",
                    headers=headers,
                    params={**params, "history_seconds": max(int(history_seconds or 300), 60)},
                    timeout=12.0,
                )
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else {}
            except Exception:
                return {}

        last_payload: Dict[str, Any] = {}
        for quote_category in category_candidates:
            for quote_symbol in symbol_candidates:
                params = {"category": quote_category, "symbol": quote_symbol}
                price_first = market_kind == "commodities" or not prefer_history
                first = await (request_price(params) if price_first else request_history(params))
                if first:
                    last_payload = first
                if first and (extract_price_from_payload(first) or extract_quote_ohlc_rows(first)):
                    first["_resolved_quote_category"] = quote_category
                    first["_resolved_quote_symbol"] = quote_symbol
                    return first
                second = await (request_history(params) if price_first else request_price(params))
                if second:
                    last_payload = second
                if second and (extract_price_from_payload(second) or extract_quote_ohlc_rows(second)):
                    second["_resolved_quote_category"] = quote_category
                    second["_resolved_quote_symbol"] = quote_symbol
                    return second
                legacy_price = await get_price_for_symbol(client, quote_symbol, token)
                if legacy_price and legacy_price > 0:
                    return {
                        "ok": True,
                        "price": float(legacy_price),
                        "symbol": symbol,
                        "_resolved_quote_category": quote_category,
                        "_resolved_quote_symbol": quote_symbol,
                        "_quote_source": "devsbite_price",
                    }
        td_payload = await fetch_twelvedata_payload(symbol, "1min", outputsize=160)
        if td_payload and (extract_price_from_payload(td_payload) or extract_quote_ohlc_rows(td_payload)):
            return td_payload
        return last_payload if isinstance(last_payload, dict) else {}

async def fetch_binary_quote_price(category: str, symbol: str) -> Optional[float]:
    payload = await fetch_binary_quote_payload(category, symbol, 300)
    price = extract_price_from_payload(payload)
    if price and price > 0:
        return price
    token = os.getenv("DEVSBITE_TOKEN") or ""
    async with httpx.AsyncClient() as client:
        return await get_price_for_symbol(client, symbol, token)

def binary_interval_for_analysis(expiration: str) -> str:
    seconds = parse_timeframe_seconds(expiration)
    if seconds >= 60 * 60:
        return "1h"
    if seconds >= 30 * 60:
        return "30min"
    if seconds >= 15 * 60:
        return "15min"
    return "5min"

def format_pair_for_advanced_analysis(pair: str) -> str:
    raw = str(pair or "").strip()
    compact = raw.upper().replace("/", "").replace("-", "").replace(" ", "")
    if len(compact) == 6 and compact.isalpha():
        return f"{compact[:3]}/{compact[3:]}"
    return raw

async def build_quote_based_binary_analysis(
    market_kind: str,
    pair: str,
    interval: str,
    allowed_indicators: List[str],
) -> Dict[str, Any]:
    history_seconds = max(300, min(parse_timeframe_seconds(interval) * 120, 86400))
    quote_payload = await fetch_binary_quote_payload(market_kind, pair, history_seconds, prefer_history=True)
    price = extract_price_from_payload(quote_payload)
    if not price:
        raise ValueError("Live price is unavailable")
    candles = build_binary_quote_candles(quote_payload, float(price), pair, interval)
    indicators = calculate_binary_quote_indicators(candles, float(price))
    raw_payload = {
        "ok": True,
        "symbol": pair,
        "interval": binary_interval_for_analysis(interval),
        "price": float(price),
        "indicators": indicators,
        "candles": candles,
        "session": {"multiplier": 1.0, "reason": f"quote_{market_kind}"},
        "quote_payload": quote_payload,
    }
    analysis_data = compute_analysis_decision(
        raw_payload,
        symbol=pair,
        interval=binary_interval_for_analysis(interval),
        allowed_indicators=allowed_indicators,
    )
    if (
        str(analysis_data.get("recommendation") or "").upper() == "NEUTRAL"
        and allowed_indicators
        and not analysis_data.get("indicators")
    ):
        analysis_data = compute_analysis_decision(
            raw_payload,
            symbol=pair,
            interval=binary_interval_for_analysis(interval),
            allowed_indicators=[],
        )
    analysis_data["quote_source"] = "devsbite_quotes"
    return analysis_data

async def build_twelvedata_based_analysis(
    pair: str,
    interval: str,
    allowed_indicators: List[str],
) -> Optional[tuple]:
    td_payload = await fetch_twelvedata_payload(pair, interval, outputsize=160)
    price = extract_price_from_payload(td_payload)
    if not price:
        return None
    candles = build_binary_quote_candles(td_payload, float(price), pair, interval)
    indicators = calculate_binary_quote_indicators(candles, float(price))
    raw_payload = {
        "ok": True,
        "symbol": pair,
        "interval": normalize_twelvedata_interval(interval),
        "price": float(price),
        "indicators": indicators,
        "candles": candles,
        "session": {"multiplier": 1.0, "reason": "twelvedata_fallback"},
        "quote_payload": td_payload,
    }
    analysis_data = compute_analysis_decision(
        raw_payload,
        symbol=pair,
        interval=normalize_twelvedata_interval(interval),
        allowed_indicators=allowed_indicators,
    )
    if (
        str(analysis_data.get("recommendation") or "").upper() == "NEUTRAL"
        and allowed_indicators
        and not analysis_data.get("indicators")
    ):
        analysis_data = compute_analysis_decision(
            raw_payload,
            symbol=pair,
            interval=normalize_twelvedata_interval(interval),
            allowed_indicators=[],
        )
    analysis_data["quote_source"] = "twelvedata"
    analysis_data["resolved_symbol"] = td_payload.get("_resolved_quote_symbol")
    analysis_data["resolved_exchange"] = td_payload.get("_resolved_quote_exchange")
    return raw_payload, analysis_data

def enforce_binary_signal(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_binary_signal(analysis_data)

def get_analysis_remaining_seconds(row: Dict[str, Any]) -> int:
    created_at = row.get("created_at")
    if not created_at:
        return 0
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "").replace("T", " "))
        except Exception:
            return 0
    seconds = parse_timeframe_seconds(row.get("timeframe"))
    if str(row.get("analysis_type") or "forex").lower() != "binary":
        seconds += 10 * 60
    return max(0, int(round((created_at + timedelta(seconds=seconds) - datetime.now()).total_seconds())))

def serialize_user_analysis(row: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(row or {})
    for key in ("raw_data", "news_data"):
        if isinstance(item.get(key), str):
            try:
                item[key] = json.loads(item[key])
            except Exception:
                item[key] = {}
    created_at = item.get("created_at")
    closed_at = item.get("closed_at")
    if hasattr(created_at, "isoformat"):
        item["created_at"] = created_at.isoformat()
    if hasattr(closed_at, "isoformat"):
        item["closed_at"] = closed_at.isoformat()
    item["remaining_seconds"] = get_analysis_remaining_seconds(row)
    return item

async def settle_user_analysis_row(row: Dict[str, Any]) -> Dict[str, Any]:
    analysis_id = int(row.get("id") or 0)
    if not analysis_id:
        raise HTTPException(status_code=400, detail="Analysis id is required")
    raw = row.get("raw_data")
    try:
        raw_data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except Exception:
        raw_data = {}
    try:
        entry_price = float(row.get("entry_price") or raw_data.get("price") or raw_data.get("entry_price") or 0)
    except (TypeError, ValueError):
        entry_price = 0.0
    recommendation = str(raw_data.get("recommendation") or raw_data.get("signal") or "").strip().upper()
    market_kind = row.get("market_kind") or raw_data.get("market_kind") or "forex"
    pair = row.get("pair") or raw_data.get("symbol") or ""
    exit_price = await fetch_binary_quote_price(market_kind, pair)
    status = "skipped"
    if entry_price > 0 and exit_price and exit_price > 0 and recommendation in ("BUY", "SELL"):
        if recommendation == "BUY":
            status = "success" if exit_price > entry_price else "fail" if exit_price < entry_price else "skipped"
        if recommendation == "SELL":
            status = "success" if exit_price < entry_price else "fail" if exit_price > entry_price else "skipped"
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                UPDATE user_analyses
                SET status = %s, exit_price = %s, closed_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (status, float(exit_price or 0), analysis_id, int(row.get("user_id") or 0)),
            )
            await cur.execute(
                """
                SELECT a.id, a.user_id, a.pair, a.timeframe, a.strategy_id, a.analysis_type,
                       a.market_kind, a.entry_price, a.exit_price, a.raw_data, a.news_data,
                       a.status, a.created_at, a.closed_at, p.name as strategy_name
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.id = %s
                LIMIT 1
                """,
                (analysis_id,),
            )
            updated = await cur.fetchone()
    return serialize_user_analysis(updated or row)

async def analysis_producer():
    print("[Worker] Producer started...")
    while True:
        try:
            if db_pool:
                async with db_pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute("""
                            SELECT id, user_id, pair, timeframe, analysis_type, market_kind,
                                   entry_price, created_at, raw_data
                            FROM user_analyses
                            WHERE status = 'active'
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

                    tf_seconds = parse_timeframe_seconds(row['timeframe'])
                    if str(row.get("analysis_type") or "forex").lower() != "binary":
                        tf_seconds += 10 * 60
                    expiration_time = created_at + timedelta(seconds=tf_seconds)

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
                            analysis_type = str(row.get("analysis_type") or "forex").lower()
                            
                            try:
                                raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                                orig_price = float(row.get("entry_price") or raw.get('price', 0) or raw.get("entry_price", 0))
                                rec = str(raw.get('recommendation') or raw.get("signal") or "").strip().upper()
                            except:
                                orig_price, rec = 0, None
                                
                            new_status = 'skipped'
                            current_price = None
                            
                            if orig_price > 0 and rec in ['BUY', 'SELL']:
                                if analysis_type == "binary":
                                    current_price = await fetch_binary_quote_price(row.get("market_kind") or raw.get("market_kind") or "forex", symbol)
                                else:
                                    current_price = await get_price_for_symbol(client, symbol, token)
                                
                                if current_price is not None:
                                    if rec == 'BUY':
                                        if current_price > orig_price: new_status = 'success'
                                        elif current_price < orig_price: new_status = 'fail'
                                    elif rec == 'SELL':
                                        if current_price < orig_price: new_status = 'success'
                                        elif current_price > orig_price: new_status = 'fail'
                            
                            await cur.execute(
                                "UPDATE user_analyses SET status = %s, exit_price = %s, closed_at = NOW() WHERE id = %s",
                                (new_status, float(current_price) if current_price is not None else None, a_id),
                            )
                            
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
                       u.strategy_id, u.trader_id, COALESCE(u.balance, 0) AS balance,
                       COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
                       u.balance_synced_at,
                       COALESCE(fx.is_enabled, 1) AS forex_access,
                       COALESCE(bin.is_enabled, 1) AS binary_access,
                       COALESCE(u.is_blocked, 0) AS is_blocked, u.blocked_at,
                       p.name as strategy_name,
                       CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin
                FROM users u
                LEFT JOIN presets p ON u.strategy_id = p.id
                LEFT JOIN admin_users a ON a.user_id = u.user_id
                LEFT JOIN user_mode_access fx ON fx.user_id = u.user_id AND fx.mode = 'forex'
                LEFT JOIN user_mode_access bin ON bin.user_id = u.user_id AND bin.mode = 'binary'
                WHERE u.user_id = %s
            """, (user_id,))
            user = await cur.fetchone()
    if user:
        user["admin_url"] = build_admin_webapp_url() if int(user.get("is_admin") or 0) == 1 else ""
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
                    avatar_url = COALESCE(NULLIF(VALUES(avatar_url), ''), avatar_url)
            """, (user_id, username, first_name, avatar_url))
            await cur.executemany(
                """
                INSERT IGNORE INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                VALUES (%s, %s, 1, NULL)
                """,
                [(user_id, "forex"), (user_id, "binary")],
            )
    return {"status": "success"}
    
@app.post("/api/user/mode")
async def update_mode(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    user_id = user["user_id"]
    new_mode = data.get("mode")
    
    if user_id and new_mode:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if str(new_mode).lower() in ("forex", "binary"):
                    await cur.execute(
                        """
                        SELECT COALESCE(is_enabled, 1) AS is_enabled
                        FROM user_mode_access
                        WHERE user_id = %s AND mode = %s
                        LIMIT 1
                        """,
                        (user_id, str(new_mode).lower()),
                    )
                    access_row = await cur.fetchone()
                    if access_row and truthy_db(access_row.get("is_enabled")) != 1:
                        raise HTTPException(status_code=403, detail=f"{new_mode} access is disabled")
                await cur.execute("UPDATE users SET mode = %s WHERE user_id = %s", (new_mode, user_id))
        return {"status": "success", "mode": new_mode}
    return {"error": "Invalid data"}

def normalize_market_kind(kind: str) -> str:
    raw = str(kind or "").strip().lower()
    if raw in MARKET_KIND_CONFIG:
        return raw
    if raw in MARKET_KIND_ALIASES:
        return MARKET_KIND_ALIASES[raw]
    return "otc" if raw == "otc" else "forex"


def extract_market_rows(payload: Any) -> List[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("pairs", "data", "items", "results", "assets", "symbols", "instruments"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = extract_market_rows(value)
            if nested:
                return nested
    return []


def market_pair_label(row: Dict[str, Any]) -> str:
    direct = (
        row.get("pair")
        or row.get("name")
        or row.get("label")
        or row.get("asset")
        or row.get("display_name")
        or row.get("display")
        or row.get("title")
        or row.get("ticker")
        or row.get("symbol")
    )
    label = str(direct or "").strip()
    if label:
        return label
    base = str(row.get("base") or row.get("base_asset") or row.get("currency_base") or "").strip()
    quote = str(row.get("quote") or row.get("quote_asset") or row.get("currency_quote") or "").strip()
    return f"{base}/{quote}" if base and quote else ""


def normalize_market_symbol(value: str) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
        .replace(" ", "")
        .replace("/", "")
        .replace("-", "")
        .replace("_", "")
    )


def normalize_market_pairs(payload: Any) -> List[Dict[str, Any]]:
    normalized = []
    seen = set()
    for row in extract_market_rows(payload):
        if not isinstance(row, dict):
            continue
        pair = market_pair_label(row)
        symbol = normalize_market_symbol(row.get("symbol") or row.get("ticker") or row.get("code") or row.get("asset") or pair)
        if not pair or not symbol or symbol in seen:
            continue
        seen.add(symbol)
        payout_raw = row.get("payout")
        if payout_raw is None:
            payout_raw = row.get("profit", row.get("percent"))
        try:
            payout = int(float(payout_raw)) if payout_raw is not None else None
        except (TypeError, ValueError):
            payout = None
        normalized.append({"pair": pair, "payout": payout})
    return sorted(normalized, key=lambda item: (item["payout"] is None, -(item["payout"] or 0), item["pair"]))


def parse_expiration_options(raw_value: str) -> List[Dict[str, str]]:
    values = []
    seen = set()
    for item in str(raw_value or "").replace(";", ",").split(","):
        value = item.strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append({"value": value, "label": value})
    return values


def merge_expiration_options(*groups: List[Dict[str, str]]) -> List[Dict[str, str]]:
    merged = []
    seen = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or item.get("label") or "").strip().lower()
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append({"value": value, "label": str(item.get("label") or value)})
    return merged or parse_expiration_options(BINARY_EXPIRATION_OPTIONS)


async def fetch_devsbite_market_pairs(kind: str, min_payout: int) -> List[Dict[str, Any]]:
    token = os.getenv("DEVSBITE_TOKEN")
    if not token:
        return []
    market_kind = normalize_market_kind(kind)
    pair_path = MARKET_KIND_CONFIG.get(market_kind, MARKET_KIND_CONFIG["forex"])["path"]
    url = f"{DEVSBITE_API_BASE_URL}/pairs/{pair_path}"
    headers = {
        "accept": "application/json",
        "X-Client-Token": token,
        "Cache-Control": "no-cache",
    }
    params = {"min_payout": max(int(min_payout or 0), 0)}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params, timeout=12.0)
            response.raise_for_status()
            return normalize_market_pairs(response.json())
        except Exception:
            return []


async def fetch_binary_expiration_options() -> List[Dict[str, str]]:
    defaults = parse_expiration_options(BINARY_EXPIRATION_OPTIONS)
    token = os.getenv("DEVSBITE_TOKEN")
    if not token or not DEVSBITE_EXPIRATIONS_URL:
        return defaults
    headers = {
        "accept": "application/json",
        "X-Client-Token": token,
        "Cache-Control": "no-cache",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(DEVSBITE_EXPIRATIONS_URL, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return defaults
    if isinstance(data, dict):
        raw_values = data.get("expirations") or data.get("items") or data.get("data") or []
    elif isinstance(data, list):
        raw_values = data
    else:
        raw_values = []
    parsed = []
    for item in raw_values:
        if isinstance(item, dict):
            value = item.get("value") or item.get("label") or item.get("expiration") or item.get("time")
            label = item.get("label") or value
            if value:
                parsed.append({"value": str(value).strip().lower(), "label": str(label).strip()})
        else:
            value = str(item or "").strip().lower()
            if value:
                parsed.append({"value": value, "label": value})
    return merge_expiration_options(defaults, parsed)


async def get_market_options_payload(kind: str, min_payout: int) -> Dict[str, Any]:
    market_kind = normalize_market_kind(kind)
    pairs = await fetch_devsbite_market_pairs(market_kind, min_payout)
    if market_kind == "forex":
        pairs = merge_custom_market_assets(pairs, get_custom_forex_currency_assets())
    expirations = await fetch_binary_expiration_options()
    return {
        "kind": market_kind,
        "market_title": MARKET_KIND_CONFIG.get(market_kind, MARKET_KIND_CONFIG["forex"])["title"],
        "available_markets": [{"key": key, "title": value["title"]} for key, value in MARKET_KIND_CONFIG.items()],
        "pairs": pairs,
        "expirations": expirations,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/market/options")
async def get_market_options(
    kind: str = Query(default="forex"),
    min_payout: int = Query(default=DEVSBITE_MIN_PAYOUT, ge=0, le=100),
    user=Depends(get_telegram_user),
):
    return await get_market_options_payload(kind, min_payout)


@app.get("/api/pairs/forex")
async def get_forex_pairs(user=Depends(get_telegram_user)):
    payload = await get_market_options_payload("forex", DEVSBITE_MIN_PAYOUT)
    return {"pairs": payload["pairs"]}


@app.get("/api/pairs/otc")
async def get_otc_pairs(user=Depends(get_telegram_user)):
    payload = await get_market_options_payload("otc", DEVSBITE_MIN_PAYOUT)
    return {"pairs": payload["pairs"]}

@app.get("/api/pairs/otc/stocks")
async def get_otc_stock_pairs(user=Depends(get_telegram_user)):
    payload = await get_market_options_payload("stocks", DEVSBITE_MIN_PAYOUT)
    assets = []
    for item in payload["pairs"]:
        asset = item.get("pair") or item.get("asset") or item.get("symbol") or item.get("name")
        if asset:
            next_item = dict(item)
            next_item["asset"] = asset
            assets.append(next_item)
    return {"assets": assets, "pairs": payload["pairs"]}

@app.get("/api/pairs/forex/stocks")
async def get_forex_stock_pairs(user=Depends(get_telegram_user)):
    assets = get_forex_stock_assets()
    return {"assets": assets, "pairs": assets}


@app.get("/api/pairs")
async def get_pairs_by_kind(kind: str = Query(default="forex"), user=Depends(get_telegram_user)):
    payload = await get_market_options_payload(kind, DEVSBITE_MIN_PAYOUT)
    return {
        "kind": payload["kind"],
        "market_title": payload["market_title"],
        "pairs": payload["pairs"],
    }


@app.get("/api/expirations")
async def get_expiration_options(user=Depends(get_telegram_user)):
    return {"expirations": await fetch_binary_expiration_options()}
            
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
            pairs = normalize_forex_stream_assets("indices", response.json())
            return merge_custom_market_assets(pairs, get_custom_forex_index_assets())
        except Exception as e:
            print(f"Indices API Error: {e}")
            return get_custom_forex_index_assets()
            
@app.get("/api/analysis/active")
async def get_active_analyses(user=Depends(get_telegram_user)):
    user_id = user["user_id"]
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT a.id, a.user_id, a.pair, a.timeframe, a.strategy_id, a.analysis_type,
                       a.market_kind, a.entry_price, a.exit_price, a.raw_data, a.news_data,
                       a.status, a.created_at, a.closed_at, p.name as strategy_name
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.user_id = %s AND a.status = 'active'
                ORDER BY a.created_at DESC
            """, (user_id,))
            analyses = await cur.fetchall()
            analyses = [serialize_user_analysis(a) for a in analyses]

    return {"analyses": analyses}

@app.get("/api/analysis/history")
async def get_analysis_history(
    strategy_id: Optional[int] = Query(default=None),
    analysis_type: Optional[str] = Query(default=None),
    user=Depends(get_telegram_user),
):
    user_id = int(user["user_id"])
    strategy_filter = int(strategy_id) if strategy_id is not None and int(strategy_id) > 0 else None
    type_filter = str(analysis_type or "").strip().lower()
    if type_filter not in ("forex", "binary"):
        type_filter = None
    where_clause = "a.user_id = %s AND a.status != 'active'"
    params = [user_id]
    if strategy_filter is not None:
        where_clause += " AND a.strategy_id = %s"
        params.append(strategy_filter)
    if type_filter is not None:
        where_clause += " AND LOWER(COALESCE(a.analysis_type, 'forex')) = %s"
        params.append(type_filter)

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(f"""
                SELECT a.id, a.pair, a.timeframe, a.status, a.created_at, a.closed_at,
                       a.analysis_type, a.market_kind, a.entry_price, a.exit_price,
                       a.strategy_id, a.raw_data, p.name as strategy_name, p.public_winrate
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE {where_clause}
                ORDER BY a.created_at DESC
            """, tuple(params))
            history = await cur.fetchall()
            history = [serialize_user_analysis(item) for item in history]

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
            "analysis_type": type_filter,
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

@app.post("/api/analysis/binary")
async def create_binary_analysis(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    user_id = int(user["user_id"])
    pair = str(data.get("pair") or "").strip()
    interval_raw = str(data.get("exp") or "1m").strip().lower()
    market_kind = normalize_market_kind(data.get("market") or data.get("market_kind") or "forex")
    strategy_id = data.get("strategy_id")
    try:
        strategy_id_int = int(strategy_id) if strategy_id is not None and str(strategy_id).strip() else None
    except (TypeError, ValueError):
        strategy_id_int = None
    if strategy_id_int is None:
        strategy_id_int = await get_user_strategy_id(user_id)
    allowed_indicators = data.get("allowed_indicators", [])
    if not isinstance(allowed_indicators, list):
        allowed_indicators = []
    if not pair:
        raise HTTPException(status_code=400, detail="Pair is required")

    analysis_interval = binary_interval_for_analysis(interval_raw)
    formatted_pair = format_pair_for_advanced_analysis(pair)
    token = os.getenv("DEVSBITE_TOKEN")
    url = (os.getenv("ANALYSIS_GATEWAY_URL") or "https://api.devsbite.com/analysis/advanced").strip()
    headers = {"accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["X-Client-Token"] = token
    payload = {
        "symbol": formatted_pair,
        "interval": analysis_interval,
        "allowed_indicators": allowed_indicators,
        "exchange": data.get("exchange"),
    }

    stream_override = await resolve_stream_override(
        strategy_id_int,
        analysis_type="binary",
        requested_symbol=pair,
        requested_market=market_kind,
    )
    if stream_override:
        analysis_data = build_stream_local_analysis(
            pair,
            analysis_interval,
            allowed_indicators,
            stream_override,
            analysis_type="binary",
            market_kind=market_kind,
        )
    elif market_kind == "forex":
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
                resp.raise_for_status()
                upstream_data = resp.json()
                baseline_analysis_data = compute_analysis_decision(
                    upstream_data,
                    symbol=formatted_pair,
                    interval=analysis_interval,
                    allowed_indicators=allowed_indicators,
                )
                analysis_settings = await get_admin_analysis_settings()
                if analysis_settings.get("engine") == "gpt":
                    if not analysis_settings.get("gpt_api_key"):
                        print("GPT binary analysis is not configured; using baseline analysis")
                        analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
                    else:
                        strategy_context = await get_strategy_context(strategy_id_int)
                        try:
                            analysis_data = await analysis_ai_service.generate_gpt_analysis(
                                api_key=analysis_settings.get("gpt_api_key") or "",
                                model=analysis_settings.get("gpt_model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL,
                                prompt=analysis_settings.get("gpt_prompt") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT,
                                raw_payload=upstream_data,
                                symbol=formatted_pair,
                                interval=analysis_interval,
                                allowed_indicators=allowed_indicators,
                                strategy=strategy_context,
                                baseline_analysis=baseline_analysis_data,
                            )
                        except Exception as e:
                            print(f"GPT binary analysis error: {e}; using baseline analysis")
                            analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
                else:
                    analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
            except httpx.HTTPStatusError as e:
                error_text = e.response.text
                print(f"BINARY ANALYSIS GATEWAY ERROR [{e.response.status_code}]: {error_text} (Payload: {payload})")
                return {"error": f"API Error: {error_text}"}
            except ValueError as e:
                return {"error": f"Analysis parse error: {str(e)}"}
            except Exception as e:
                return {"error": str(e)}
    else:
        try:
            upstream_data = await fetch_binary_quote_payload(
                market_kind,
                pair,
                max(300, min(parse_timeframe_seconds(interval_raw) * 120, 86400)),
                prefer_history=True,
            )
            quote_price = extract_price_from_payload(upstream_data)
            if not quote_price:
                raise ValueError("Live price is unavailable")
            quote_candles = build_binary_quote_candles(upstream_data, float(quote_price), pair, interval_raw)
            quote_indicators = calculate_binary_quote_indicators(quote_candles, float(quote_price))
            baseline_analysis_data = compute_analysis_decision(
                {
                    "ok": True,
                    "symbol": pair,
                    "interval": analysis_interval,
                    "price": quote_price,
                    "indicators": quote_indicators,
                    "candles": quote_candles,
                    "session": {"multiplier": 1.0, "reason": f"quote_{market_kind}"},
                    "quote_payload": upstream_data,
                },
                symbol=pair,
                interval=analysis_interval,
                allowed_indicators=allowed_indicators,
            )
            if (
                str(baseline_analysis_data.get("recommendation") or "").upper() == "NEUTRAL"
                and allowed_indicators
                and not baseline_analysis_data.get("indicators")
            ):
                baseline_analysis_data = compute_analysis_decision(
                    {
                        "ok": True,
                        "symbol": pair,
                        "interval": analysis_interval,
                        "price": quote_price,
                        "indicators": quote_indicators,
                        "candles": quote_candles,
                        "session": {"multiplier": 1.0, "reason": f"quote_{market_kind}"},
                        "quote_payload": upstream_data,
                    },
                    symbol=pair,
                    interval=analysis_interval,
                    allowed_indicators=[],
                )
            analysis_settings = await get_admin_analysis_settings()
            if analysis_settings.get("engine") == "gpt":
                if not analysis_settings.get("gpt_api_key"):
                    print("GPT binary analysis is not configured; using baseline analysis")
                    analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
                else:
                    strategy_context = await get_strategy_context(strategy_id_int)
                    try:
                        analysis_data = await analysis_ai_service.generate_gpt_analysis(
                            api_key=analysis_settings.get("gpt_api_key") or "",
                            model=analysis_settings.get("gpt_model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL,
                            prompt=analysis_settings.get("gpt_prompt") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_PROMPT,
                            raw_payload=upstream_data,
                            symbol=pair,
                            interval=analysis_interval,
                            allowed_indicators=allowed_indicators,
                            strategy=strategy_context,
                            baseline_analysis=baseline_analysis_data,
                        )
                    except Exception as e:
                        print(f"GPT binary analysis error: {e}; using baseline analysis")
                        analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
            else:
                analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
        except ValueError as e:
            return {"error": f"Analysis parse error: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}

    analysis_data = ensure_analysis_key_levels(analysis_data, preferred_signal=analysis_data.get("recommendation"))
    analysis_data = ensure_analysis_key_levels(analysis_data, preferred_signal=analysis_data.get("recommendation"))
    analysis_data = enforce_binary_signal(analysis_data)
    recommendation = str(analysis_data.get("recommendation") or analysis_data.get("signal") or "").strip().upper()
    if recommendation not in ("BUY", "SELL"):
        return {"error": "Market is neutral right now. Try another pair or expiration."}

    analysis_pair = str(pair).strip() or pair
    analysis_market_kind = normalize_market_kind(market_kind)

    entry_price = None
    for key in ("price", "entry_price"):
        try:
            value = float(analysis_data.get(key))
            if value > 0:
                entry_price = value
                break
        except (TypeError, ValueError):
            pass
    if not entry_price:
        entry_price = await fetch_binary_quote_price(analysis_market_kind, analysis_pair)
    if entry_price:
        analysis_data["price"] = float(entry_price)
        analysis_data["entry_price"] = float(entry_price)
    else:
        return {"error": "Live price is unavailable right now. Try another pair or expiration."}
    analysis_data["symbol"] = analysis_pair
    analysis_data["market_kind"] = analysis_market_kind
    analysis_data["selected_expiration"] = interval_raw
    analysis_data["analysis_interval"] = analysis_interval
    analysis_data["fetched_at"] = datetime.utcnow().isoformat() + "Z"
    news_data = await fetch_news_data()

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                INSERT INTO user_analyses (
                    user_id, pair, timeframe, strategy_id, analysis_type, market_kind,
                    entry_price, raw_data, news_data, status
                )
                VALUES (%s, %s, %s, %s, 'binary', %s, %s, %s, %s, 'active')
                """,
                (
                    user_id,
                    analysis_pair,
                    interval_raw,
                    strategy_id_int,
                    analysis_market_kind,
                    float(entry_price or 0) if entry_price else None,
                    json.dumps(analysis_data, ensure_ascii=False),
                    json.dumps(news_data, ensure_ascii=False),
                ),
            )
            analysis_id = int(cur.lastrowid or 0)
            await cur.execute(
                """
                SELECT a.id, a.user_id, a.pair, a.timeframe, a.strategy_id, a.analysis_type,
                       a.market_kind, a.entry_price, a.exit_price, a.raw_data, a.news_data,
                       a.status, a.created_at, a.closed_at, p.name as strategy_name
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.id = %s
                LIMIT 1
                """,
                (analysis_id,),
            )
            row = await cur.fetchone()

    return {
        "status": "success",
        "analysis_id": analysis_id,
        "data": analysis_data,
        "news_data": news_data,
        "analysis": serialize_user_analysis(row or {}),
    }

@app.post("/api/analysis/settle")
async def settle_analysis_now(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    analysis_id = int(data.get("analysis_id") or 0)
    user_id = int(user["user_id"])
    if not analysis_id:
        raise HTTPException(status_code=400, detail="Analysis id is required")
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT a.id, a.user_id, a.pair, a.timeframe, a.strategy_id, a.analysis_type,
                       a.market_kind, a.entry_price, a.exit_price, a.raw_data, a.news_data,
                       a.status, a.created_at, a.closed_at, p.name as strategy_name
                FROM user_analyses a
                LEFT JOIN presets p ON a.strategy_id = p.id
                WHERE a.id = %s AND a.user_id = %s
                LIMIT 1
                """,
                (analysis_id, user_id),
            )
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if row.get("status") != "active":
        return {"status": "success", "analysis": serialize_user_analysis(row)}
    updated = await settle_user_analysis_row(row)
    return {"status": "success", "analysis": updated}
    
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

    stream_override = await resolve_stream_override(
        strategy_id_int,
        analysis_type="forex",
        requested_symbol=pair,
    )
    if stream_override:
        analysis_data = build_stream_local_analysis(
            str(pair or "").strip(),
            interval,
            allowed_indicators,
            stream_override,
            analysis_type="forex",
            market_kind=normalize_forex_stream_market(stream_override.get("emulation_market") or ""),
        )
        analysis_pair = str(pair).strip() or pair
        analysis_data["symbol"] = analysis_pair
        news_data = await fetch_news_data()
    else:
        async with httpx.AsyncClient() as client:
            try:
                upstream_data = None
                baseline_analysis_data = None
                gateway_error_text = ""
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
                except httpx.HTTPStatusError as e:
                    gateway_error_text = e.response.text
                    print(f"ANALYSIS GATEWAY ERROR [{e.response.status_code}]: {gateway_error_text} (Payload: {payload})")

                fallback_needed = (
                    has_explicit_twelvedata_mapping(pair)
                    or upstream_data is None
                    or not isinstance(baseline_analysis_data, dict)
                    or not isinstance(baseline_analysis_data.get("indicators"), dict)
                    or len(baseline_analysis_data.get("indicators") or {}) == 0
                )
                if fallback_needed:
                    fallback = await build_twelvedata_based_analysis(pair, interval, allowed_indicators)
                    if fallback:
                        upstream_data, baseline_analysis_data = fallback
                        formatted_pair = str(pair or "").strip()
                    elif upstream_data is None:
                        return {"error": f"API Error: {gateway_error_text or 'Price not found'}"}

                analysis_settings = await get_admin_analysis_settings()
                if analysis_settings.get("engine") == "gpt":
                    if not analysis_settings.get("gpt_api_key"):
                        print("GPT analysis is not configured; using baseline analysis")
                        analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
                    else:
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
                            print(f"GPT analysis error: {e}; using baseline analysis")
                            analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
                else:
                    analysis_data = fallback_to_baseline_analysis(baseline_analysis_data)
                analysis_data = ensure_analysis_key_levels(analysis_data, preferred_signal=analysis_data.get("recommendation"))
                analysis_pair = str(pair).strip() or pair
                analysis_data["symbol"] = analysis_pair
                news_data = await fetch_news_data()
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
                (user_id, analysis_pair, interval_raw, strategy_id_int, json.dumps(analysis_data), json.dumps(news_data)),
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
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    aio_visit_uuid = extract_aio_visit_uuid_from_start_text(message.text)

    if db_pool:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (user_id, username, first_name, aio_visit_uuid, lang, mode)
                    VALUES (%s, %s, %s, %s, 'ru', 'forex')
                    ON DUPLICATE KEY UPDATE
                        username = VALUES(username),
                        first_name = VALUES(first_name),
                        aio_visit_uuid = CASE
                            WHEN (aio_visit_uuid IS NULL OR TRIM(aio_visit_uuid) = '')
                                 AND VALUES(aio_visit_uuid) IS NOT NULL
                            THEN VALUES(aio_visit_uuid)
                            ELSE aio_visit_uuid
                        END
                    """,
                    (user_id, username, first_name, aio_visit_uuid),
                )
                await cur.executemany(
                    """
                    INSERT IGNORE INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                    VALUES (%s, %s, 1, NULL)
                    """,
                    [(user_id, "forex"), (user_id, "binary")],
                )

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


def normalize_ai_chat_title(title: str) -> str:
    raw = str(title or "").strip()
    translations = {
        "Новый диалог": "New Chat",
        "новый диалог": "New Chat",
        "Приветствие": "Welcome",
        "приветствие": "Welcome",
    }
    return translations.get(raw, raw or "New Chat")


def normalize_ai_chat_row(row):
    if isinstance(row, dict):
        row["title"] = normalize_ai_chat_title(row.get("title"))
    return row

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
            
            return {"status": "success", "chat_id": chat['id'], "title": normalize_ai_chat_title(chat.get("title")), "messages": messages}

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
            chats = [normalize_ai_chat_row(chat) for chat in chats]
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
        analysis_consumer(),
        pocket_balance_sync_worker()
    )

if __name__ == "__main__":
    async def main_wrapper():
        try:
            await main()
        except KeyboardInterrupt:
            pass
    asyncio.run(main_wrapper())

