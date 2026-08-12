import os
import asyncio
import aiomysql
import httpx
import hashlib
import hmac
import json
import secrets
import random
import re
import shutil
from decimal import Decimal
from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from fastapi import FastAPI, Request, Depends, HTTPException, Header, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
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
    from backend.studio_statistics import (
        aggregate_studio_statistics,
        decode_strategy_winrates,
        deduplicate_strategy_options,
        normalize_daily_stat,
        normalize_date_range,
        parse_iso_date,
    )
except ModuleNotFoundError:
    from studio_statistics import (
        aggregate_studio_statistics,
        decode_strategy_winrates,
        deduplicate_strategy_options,
        normalize_daily_stat,
        normalize_date_range,
        parse_iso_date,
    )
try:
    from backend.db_bootstrap import ensure_database_schema
except ModuleNotFoundError:
    from db_bootstrap import ensure_database_schema
try:
    from backend.stream_matching import stream_requested_asset_matches
except ModuleNotFoundError:
    from stream_matching import stream_requested_asset_matches
try:
    from backend.stream_indicators import (
        coherent_stream_indicator_value,
        stream_indicator_is_neutral_only,
    )
except ModuleNotFoundError:
    from stream_indicators import (
        coherent_stream_indicator_value,
        stream_indicator_is_neutral_only,
    )
try:
    from backend.video_note import prepare_square_video_note
except ModuleNotFoundError:
    from video_note import prepare_square_video_note
try:
    from backend.binary_signal import enforce_binary_signal as normalize_binary_signal
except ModuleNotFoundError:
    from binary_signal import enforce_binary_signal as normalize_binary_signal
try:
    from backend.strategy_indicators import (
        align_analysis_indicators_to_strategy,
        choose_effective_indicator_keys,
    )
except ModuleNotFoundError:
    from strategy_indicators import (
        align_analysis_indicators_to_strategy,
        choose_effective_indicator_keys,
    )
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
        AIO_GEO_CONVERSION_TYPE_UUID,
        build_aio_field_trigger_url,
        build_aio_fields_trigger_url,
        build_aio_pocket_deposit_conversion_url,
        build_aio_pocket_ftd_conversion_url,
        build_aio_pocket_registration_conversion_url,
        build_aio_postback_url,
        extract_aio_visit_uuid_from_start_text,
        normalize_aio_event_slug,
        normalize_aio_country_code,
        normalize_aio_revenue,
        normalize_aio_visit_uuid,
    )
except ModuleNotFoundError:
    from aio_tracking import (
        AIO_GEO_CONVERSION_TYPE_UUID,
        build_aio_field_trigger_url,
        build_aio_fields_trigger_url,
        build_aio_pocket_deposit_conversion_url,
        build_aio_pocket_ftd_conversion_url,
        build_aio_pocket_registration_conversion_url,
        build_aio_postback_url,
        extract_aio_visit_uuid_from_start_text,
        normalize_aio_event_slug,
        normalize_aio_country_code,
        normalize_aio_revenue,
        normalize_aio_visit_uuid,
    )
try:
    from backend.bot_funnel import (
        CHATTERFY_BOT_START_EVENT,
        CHATTERFY_START_EVENT,
        CHANNEL_SUBSCRIBE_EVENT,
        QUIZ_COMPLETE_EVENT,
        get_aio_question_field,
        get_next_quiz_step,
        get_quiz_options,
        get_quiz_question,
        get_quiz_steps_to_complete,
        is_active_channel_member,
        is_skip_answer,
        is_valid_quiz_step,
        map_quiz_answer_locally,
        normalize_channel_settings,
        normalize_final_message_config,
        normalize_quiz_answer,
        normalize_quiz_config,
        normalize_quiz_step,
        validate_final_message_config,
    )
except ModuleNotFoundError:
    from bot_funnel import (
        CHATTERFY_BOT_START_EVENT,
        CHATTERFY_START_EVENT,
        CHANNEL_SUBSCRIBE_EVENT,
        QUIZ_COMPLETE_EVENT,
        get_aio_question_field,
        get_next_quiz_step,
        get_quiz_options,
        get_quiz_question,
        get_quiz_steps_to_complete,
        is_active_channel_member,
        is_skip_answer,
        is_valid_quiz_step,
        map_quiz_answer_locally,
        normalize_channel_settings,
        normalize_final_message_config,
        normalize_quiz_answer,
        normalize_quiz_config,
        normalize_quiz_step,
        validate_final_message_config,
    )
try:
    from backend.chatterfy_pocket import CHATTERFY_POCKET_EVENT_SLUGS, build_chatterfy_pocket_postback_url
except ModuleNotFoundError:
    from chatterfy_pocket import CHATTERFY_POCKET_EVENT_SLUGS, build_chatterfy_pocket_postback_url
try:
    from backend.chatterfy_tracking import normalize_chatterfy_event
except ModuleNotFoundError:
    from chatterfy_tracking import normalize_chatterfy_event
try:
    from backend.registration_links import (
        DEFAULT_REGISTRATION_URL,
        build_registration_url,
        parse_registration_link_target,
    )
except ModuleNotFoundError:
    from registration_links import (
        DEFAULT_REGISTRATION_URL,
        build_registration_url,
        parse_registration_link_target,
    )
try:
    from backend.access_policy import (
        ACCESS_POLICY_REGISTRATION_DEPOSIT,
        normalize_access_policy,
        normalize_min_deposit,
        system_policy_grants_signal_access,
    )
except ModuleNotFoundError:
    from access_policy import (
        ACCESS_POLICY_REGISTRATION_DEPOSIT,
        normalize_access_policy,
        normalize_min_deposit,
        system_policy_grants_signal_access,
    )
try:
    from backend.profile_editing import (
        normalize_profile_name,
        normalize_profile_trader_id,
    )
except ModuleNotFoundError:
    from profile_editing import (
        normalize_profile_name,
        normalize_profile_trader_id,
    )
try:
    from backend.user_data_archive import (
        ARCHIVE_VERSION,
        build_archive_summary,
        clear_cache_confirmation,
        deserialize_archive_payload,
        serialize_archive_payload,
        validate_clear_cache_confirmation,
    )
except ModuleNotFoundError:
    from user_data_archive import (
        ARCHIVE_VERSION,
        build_archive_summary,
        clear_cache_confirmation,
        deserialize_archive_payload,
        serialize_archive_payload,
        validate_clear_cache_confirmation,
    )
try:
    from backend.aichatter_admin import (
        clear_aichatter_user_data,
        create_aichatter_admin_router,
        get_aichatter_user_summary,
        snapshot_aichatter_user_data,
        sync_aichatter_pocket_event,
        sync_shared_ai_access_settings,
    )
except ModuleNotFoundError:
    from aichatter_admin import (
        clear_aichatter_user_data,
        create_aichatter_admin_router,
        get_aichatter_user_summary,
        snapshot_aichatter_user_data,
        sync_aichatter_pocket_event,
        sync_shared_ai_access_settings,
    )
try:
    from backend.manager_stats import (
        MANAGER_STATS_AUDIT_STATUSES,
        STAFF_ROLE_ADMIN,
        STAFF_ROLES,
        format_manager_stats,
        normalize_staff_role,
        parse_stats_target,
    )
except ModuleNotFoundError:
    from manager_stats import (
        MANAGER_STATS_AUDIT_STATUSES,
        STAFF_ROLE_ADMIN,
        STAFF_ROLES,
        format_manager_stats,
        normalize_staff_role,
        parse_stats_target,
    )
try:
    from backend.staff_permissions import (
        ADMIN_CENTER_PERMISSIONS,
        ALL_PERMISSIONS,
        PERM_AICHATTER_MANAGE,
        PERM_BROADCAST_MANAGE,
        PERM_DASHBOARD_VIEW,
        PERM_SETTINGS_AI,
        PERM_SETTINGS_API,
        PERM_SETTINGS_FUNNEL,
        PERM_SETTINGS_INTERFACE,
        PERM_SETTINGS_STREAMS,
        PERM_SETTINGS_SYSTEM_ACCESS,
        PERM_STAFF_ADD,
        PERM_STAFF_MANAGE,
        PERM_STAFF_VIEW,
        PERM_STATS_COMMAND,
        PERM_STATS_MANAGE,
        PERM_STATS_VIEW,
        PERM_STRATEGIES_MANAGE,
        PERM_USERS_ACCESS,
        PERM_USERS_ARCHIVE_CLEAR,
        PERM_USERS_BALANCE,
        PERM_USERS_BLOCK,
        PERM_USERS_DELETE,
        PERM_USERS_PROFILE_EDIT,
        PERM_USERS_VIEW,
        SETTINGS_PERMISSIONS,
        has_any_permission,
        has_permission,
        normalize_staff_permissions,
        permissions_are_subset,
        role_default_permissions,
    )
except ModuleNotFoundError:
    from staff_permissions import (
        ADMIN_CENTER_PERMISSIONS,
        ALL_PERMISSIONS,
        PERM_AICHATTER_MANAGE,
        PERM_BROADCAST_MANAGE,
        PERM_DASHBOARD_VIEW,
        PERM_SETTINGS_AI,
        PERM_SETTINGS_API,
        PERM_SETTINGS_FUNNEL,
        PERM_SETTINGS_INTERFACE,
        PERM_SETTINGS_STREAMS,
        PERM_SETTINGS_SYSTEM_ACCESS,
        PERM_STAFF_ADD,
        PERM_STAFF_MANAGE,
        PERM_STAFF_VIEW,
        PERM_STATS_COMMAND,
        PERM_STATS_MANAGE,
        PERM_STATS_VIEW,
        PERM_STRATEGIES_MANAGE,
        PERM_USERS_ACCESS,
        PERM_USERS_ARCHIVE_CLEAR,
        PERM_USERS_BALANCE,
        PERM_USERS_BLOCK,
        PERM_USERS_DELETE,
        PERM_USERS_PROFILE_EDIT,
        PERM_USERS_VIEW,
        SETTINGS_PERMISSIONS,
        has_any_permission,
        has_permission,
        normalize_staff_permissions,
        permissions_are_subset,
        role_default_permissions,
    )

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
AFFILIATE_API_SECRET = (os.getenv("AFFILIATE_API_SECRET") or "").strip()
AFFILIATE_BOT_ID = (os.getenv("AFFILIATE_BOT_ID") or "elizabethvane").strip() or "elizabethvane"
AI_CHAT_MIN_DEPOSIT = max(0.0, float((os.getenv("AI_CHAT_MIN_DEPOSIT") or "10").strip() or "10"))
AI_CHATTER_GATEWAY_URL = (
    os.getenv("AI_CHATTER_GATEWAY_URL") or "http://127.0.0.1:8091/incoming"
).strip()
AI_CHATTER_GATEWAY_SECRET = (os.getenv("AI_CHATTER_GATEWAY_SECRET") or "").strip()
CHATTERFY_WEBHOOK_SECRET = (os.getenv("CHATTERFY_WEBHOOK_SECRET") or "").strip()
AIO_GEO_POSTBACK_SECRET = (os.getenv("AIO_GEO_POSTBACK_SECRET") or "").strip()
BOT_AI_MANAGER_ENABLED = (
    (os.getenv("BOT_AI_MANAGER_ENABLED") or "1").strip().lower()
    not in {"0", "false", "no", "off"}
)
BOT_CHANNEL_CLICK_SECRET = (os.getenv("BOT_CHANNEL_CLICK_SECRET") or "").strip()
_web_app_parts = urlsplit((os.getenv("WEB_APP_URL") or "").strip())
BOT_PUBLIC_BASE_URL = (
    os.getenv("BOT_PUBLIC_BASE_URL")
    or (f"{_web_app_parts.scheme}://{_web_app_parts.netloc}" if _web_app_parts.scheme and _web_app_parts.netloc else "")
).strip().rstrip("/")
channel_join_request_link = ""

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db_pool = None
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
START_VIDEO_NOTE_FALLBACK_PATH = (
    os.getenv("START_VIDEO_NOTE_PATH")
    or os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "elizabeth_start_video_note.mp4")
)
_runtime_api_port = str(os.getenv("API_PORT") or "").strip()
_runtime_environment = (
    "test"
    if _runtime_api_port == "7999"
    else ("prod" if _runtime_api_port == "8000" else "local")
)
_default_quiz_intro_library_dir = (
    os.path.join("/var/lib/elizabethvane", _runtime_environment, "quiz_intro_videos")
    if os.name != "nt" and _runtime_environment in {"test", "prod"}
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "media", "quiz_intro_library")
)
QUIZ_INTRO_VIDEO_LIBRARY_DIR = (
    os.getenv("QUIZ_INTRO_VIDEO_LIBRARY_DIR")
    or _default_quiz_intro_library_dir
)
START_VIDEO_NOTE_MANAGED_PATH = (
    os.getenv("QUIZ_INTRO_VIDEO_PATH")
    or os.path.join(QUIZ_INTRO_VIDEO_LIBRARY_DIR, "active.mp4")
)
MAX_QUIZ_INTRO_VIDEO_SIZE = 50 * 1024 * 1024


def resolve_start_video_note_path():
    if START_VIDEO_NOTE_MANAGED_PATH and os.path.isfile(START_VIDEO_NOTE_MANAGED_PATH):
        return START_VIDEO_NOTE_MANAGED_PATH, "uploaded"
    if START_VIDEO_NOTE_FALLBACK_PATH and os.path.isfile(START_VIDEO_NOTE_FALLBACK_PATH):
        return START_VIDEO_NOTE_FALLBACK_PATH, "default"
    return "", "missing"


def get_quiz_intro_video_status(enabled: Any = True) -> Dict[str, Any]:
    path, source = resolve_start_video_note_path()
    try:
        file_size = os.path.getsize(path) if path else 0
    except OSError:
        file_size = 0
    return {
        "enabled": bool(int(enabled or 0)),
        "file_exists": bool(path),
        "file_name": os.path.basename(path) if path else "",
        "file_size": file_size,
        "source": source,
        "max_size": MAX_QUIZ_INTRO_VIDEO_SIZE,
    }


def get_quiz_intro_library_file_path(storage_name: str) -> str:
    normalized = str(storage_name or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}\.mp4", normalized):
        raise ValueError("Invalid quiz intro video storage name")
    library_root = os.path.realpath(QUIZ_INTRO_VIDEO_LIBRARY_DIR)
    file_path = os.path.realpath(os.path.join(library_root, normalized))
    if os.path.dirname(file_path) != library_root:
        raise ValueError("Invalid quiz intro video storage path")
    return file_path


def save_quiz_intro_video_file(payload: bytes, target_path: str) -> None:
    target_dir = os.path.dirname(target_path) or "."
    os.makedirs(target_dir, exist_ok=True)
    temp_path = os.path.join(
        target_dir,
        f".{os.path.basename(target_path)}.upload-{secrets.token_hex(6)}",
    )
    try:
        with open(temp_path, "wb") as uploaded_file:
            uploaded_file.write(payload)
            uploaded_file.flush()
            os.fsync(uploaded_file.fileno())
        os.replace(temp_path, target_path)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


async def activate_quiz_intro_video_file(source_path: str) -> None:
    prepared_path = await prepare_square_video_note(source_path)
    if not prepared_path:
        raise ValueError("MP4 could not be converted to a Telegram video note")
    target_dir = os.path.dirname(START_VIDEO_NOTE_MANAGED_PATH) or "."
    os.makedirs(target_dir, exist_ok=True)
    temp_path = os.path.join(
        target_dir,
        f".active.mp4.select-{secrets.token_hex(6)}",
    )
    try:
        shutil.copy2(prepared_path, temp_path)
        with open(temp_path, "rb") as active_file:
            os.fsync(active_file.fileno())
        os.replace(temp_path, START_VIDEO_NOTE_MANAGED_PATH)
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass


def get_file_sha256(file_path: str) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid_mp4_payload(payload: bytes) -> bool:
    return bool(payload) and b"ftyp" in payload[:64]


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


async def get_staff_profile(user_id: int) -> Optional[Dict[str, Any]]:
    if not db_pool:
        return None
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, role, is_active, display_name,
                       permissions_json, is_protected
                FROM admin_users
                WHERE user_id = %s AND is_active = 1
                LIMIT 1
                """,
                (user_id,),
            )
            row = await cur.fetchone()
    if not row:
        return None
    role = str(row.get("role") or "").strip().lower()
    if role not in STAFF_ROLES:
        return None
    is_protected = bool(int(row.get("is_protected") or 0))
    return {
        "user_id": int(row.get("user_id") or user_id),
        "role": role,
        "is_active": True,
        "display_name": str(row.get("display_name") or "").strip(),
        "is_protected": is_protected,
        "permissions": normalize_staff_permissions(
            row.get("permissions_json"),
            role,
            protected=is_protected,
        ),
    }


async def get_staff_role(user_id: int) -> Optional[str]:
    profile = await get_staff_profile(user_id)
    return profile.get("role") if profile else None


async def is_admin_user(user_id: int) -> bool:
    return await get_staff_role(user_id) == STAFF_ROLE_ADMIN


async def has_admin_center_access(user_id: int) -> bool:
    profile = await get_staff_profile(user_id)
    return bool(profile and has_any_permission(profile, ADMIN_CENTER_PERMISSIONS))


async def get_admin_user(
    user=Depends(get_telegram_user),
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
):
    profile = await get_staff_profile(int(user["user_id"]))
    if not profile or not has_any_permission(profile, ADMIN_CENTER_PERMISSIONS):
        raise HTTPException(status_code=403, detail="Admin access denied")

    expected = get_admin_panel_token()
    provided = (x_admin_token or "").strip()
    if provided and secrets.compare_digest(provided, expected):
        return {**user, **profile}

    # Telegram WebApp initData already proves the user identity; keep old
    # admin buttons working even if their URL token was rotated by a deploy.
    return {**user, **profile}


def require_permission(permission: str):
    async def dependency(admin=Depends(get_admin_user)):
        if not has_permission(admin, permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для этого действия")
        return admin

    return dependency


def require_any_permission(*permissions: str):
    async def dependency(admin=Depends(get_admin_user)):
        if not has_any_permission(admin, permissions):
            raise HTTPException(status_code=403, detail="Недостаточно прав для этого раздела")
        return admin

    return dependency


app.include_router(create_aichatter_admin_router(require_permission(PERM_AICHATTER_MANAGE)))


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


async def resolve_effective_indicator_keys(strategy_id: Optional[int], client_keys: Any) -> List[str]:
    database_keys: List[str] = []
    if db_pool and strategy_id is not None:
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT GROUP_CONCAT(i.`key` ORDER BY i.id SEPARATOR ',') AS indicator_keys
                        FROM preset_indicators pi
                        JOIN indicators i ON i.id = pi.indicator_id
                        WHERE pi.preset_id = %s
                        """,
                        (int(strategy_id),),
                    )
                    row = await cur.fetchone()
            database_keys = [item.strip() for item in str((row or {}).get("indicator_keys") or "").split(",") if item.strip()]
        except Exception as e:
            print(f"Strategy indicator keys fallback: {e}")
            database_keys = []
    return choose_effective_indicator_keys(client_keys if isinstance(client_keys, list) else [], database_keys)


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
    try:
        indicator_price = float(analysis_data.get("price") or analysis_data.get("entry_price") or 100.0)
    except (TypeError, ValueError):
        indicator_price = 100.0

    if isinstance(indicators, dict):
        indicator_keys = list(indicators.keys())
        indicator_count = len(indicator_keys)

        locked_signals = {}
        for indicator_key in indicator_keys:
            has_manual_override = False
            for alias in aliases_for_indicator(indicator_key):
                raw_override = manual_overrides.get(alias)
                manual_signal = (
                    str(raw_override.get("signal") or "").strip().upper()
                    if isinstance(raw_override, dict)
                    else str(raw_override or "").strip().upper()
                )
                if manual_signal in ("BUY", "SELL", "NEUTRAL"):
                    locked_signals[indicator_key] = manual_signal
                    has_manual_override = True
                    break
            if not has_manual_override and stream_indicator_is_neutral_only(indicator_key):
                locked_signals[indicator_key] = "NEUTRAL"

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
                has_manual_value = False
                for alias in aliases_for_indicator(indicator_key):
                    raw_override = manual_overrides.get(alias)
                    if isinstance(raw_override, dict):
                        manual_value = str(raw_override.get("value") or "").strip()
                        if manual_value:
                            indicator_data["value"] = manual_value
                            has_manual_value = True
                            break
                if not has_manual_value:
                    indicator_data["value"] = coherent_stream_indicator_value(indicator_key, signal, indicator_price)
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

    indicators = {
        key: {"value": coherent_stream_indicator_value(key, "NEUTRAL", price), "signal": "NEUTRAL"}
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

async def get_quiz_intro_video_library() -> List[Dict[str, Any]]:
    active_file_exists = os.path.isfile(START_VIDEO_NOTE_MANAGED_PATH)
    rows: List[Dict[str, Any]] = []
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT id, storage_name, original_name, file_size, sha256,
                               is_active, uploaded_by, activated_by,
                               created_at, activated_at
                        FROM admin_quiz_intro_videos
                        WHERE environment = %s
                        ORDER BY is_active DESC, created_at DESC, id DESC
                        """,
                        (_runtime_environment,),
                    )
                    rows = list(await cur.fetchall() or [])
        except Exception as exc:
            print(f"Quiz intro video library fallback: {exc}")
            rows = []

    uploaded_items = []
    for row in rows:
        try:
            file_path = get_quiz_intro_library_file_path(row.get("storage_name") or "")
        except ValueError:
            file_path = ""
        file_exists = bool(file_path and os.path.isfile(file_path))
        uploaded_items.append(
            {
                "id": int(row.get("id") or 0),
                "kind": "uploaded",
                "original_name": str(row.get("original_name") or "video.mp4"),
                "file_name": str(row.get("storage_name") or ""),
                "file_size": int(row.get("file_size") or 0),
                "sha256": str(row.get("sha256") or ""),
                "is_active": bool(row.get("is_active")) and active_file_exists and file_exists,
                "is_default": False,
                "file_exists": file_exists,
                "uploaded_by": row.get("uploaded_by"),
                "activated_by": row.get("activated_by"),
                "created_at": row.get("created_at"),
                "activated_at": row.get("activated_at"),
            }
        )

    try:
        default_size = (
            os.path.getsize(START_VIDEO_NOTE_FALLBACK_PATH)
            if os.path.isfile(START_VIDEO_NOTE_FALLBACK_PATH)
            else 0
        )
    except OSError:
        default_size = 0
    default_item = {
        "id": "default",
        "kind": "default",
        "original_name": os.path.basename(START_VIDEO_NOTE_FALLBACK_PATH),
        "file_name": os.path.basename(START_VIDEO_NOTE_FALLBACK_PATH),
        "file_size": default_size,
        "sha256": "",
        "is_active": not active_file_exists,
        "is_default": True,
        "file_exists": os.path.isfile(START_VIDEO_NOTE_FALLBACK_PATH),
        "uploaded_by": None,
        "activated_by": None,
        "created_at": None,
        "activated_at": None,
    }
    return [default_item, *uploaded_items]


async def attach_quiz_intro_video_media(
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    library = await get_quiz_intro_video_library()
    status = get_quiz_intro_video_status(settings.get("quiz_intro_video_enabled", 1))
    active_item = next((item for item in library if item.get("is_active")), None)
    if active_item:
        status.update(
            {
                "id": active_item.get("id"),
                "file_name": active_item.get("original_name") or status.get("file_name"),
                "file_size": active_item.get("file_size") or status.get("file_size"),
                "source": active_item.get("kind") or status.get("source"),
                "sha256": active_item.get("sha256") or "",
                "created_at": active_item.get("created_at"),
            }
        )
    settings["quiz_intro_video"] = status
    settings["quiz_intro_video_library"] = library
    return settings


async def activate_quiz_intro_video(video_id: int, admin_user_id: int) -> Dict[str, Any]:
    video_id = int(video_id)
    previous_row = None
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT id, storage_name, original_name, file_size, sha256
                FROM admin_quiz_intro_videos
                WHERE id = %s AND environment = %s
                LIMIT 1
                """,
                (video_id, _runtime_environment),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Saved MP4 file not found")
            await cur.execute(
                """
                SELECT id, storage_name
                FROM admin_quiz_intro_videos
                WHERE environment = %s AND is_active = 1
                ORDER BY activated_at DESC, id DESC
                LIMIT 1
                """,
                (_runtime_environment,),
            )
            previous_row = await cur.fetchone()

    try:
        source_path = get_quiz_intro_library_file_path(row.get("storage_name") or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not os.path.isfile(source_path):
        raise HTTPException(status_code=404, detail="Saved MP4 file is missing on disk")

    try:
        await activate_quiz_intro_video_file(source_path)
        async with db_pool.acquire() as conn:
            await conn.begin()
            try:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        UPDATE admin_quiz_intro_videos
                        SET is_active = 0
                        WHERE environment = %s AND is_active = 1
                        """,
                        (_runtime_environment,),
                    )
                    await cur.execute(
                        """
                        UPDATE admin_quiz_intro_videos
                        SET is_active = 1,
                            activated_by = %s,
                            activated_at = NOW()
                        WHERE id = %s AND environment = %s
                        """,
                        (int(admin_user_id), video_id, _runtime_environment),
                    )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise
    except Exception as exc:
        try:
            if previous_row and int(previous_row.get("id") or 0) != video_id:
                previous_path = get_quiz_intro_library_file_path(
                    previous_row.get("storage_name") or ""
                )
                if os.path.isfile(previous_path):
                    await activate_quiz_intro_video_file(previous_path)
            elif not previous_row and os.path.isfile(START_VIDEO_NOTE_MANAGED_PATH):
                os.remove(START_VIDEO_NOTE_MANAGED_PATH)
        except Exception:
            pass
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Could not activate MP4 file: {exc}") from exc
    return row


async def reset_quiz_intro_video_to_default() -> None:
    previous_row = None
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT id, storage_name
                FROM admin_quiz_intro_videos
                WHERE environment = %s AND is_active = 1
                ORDER BY activated_at DESC, id DESC
                LIMIT 1
                """,
                (_runtime_environment,),
            )
            previous_row = await cur.fetchone()
    try:
        if os.path.isfile(START_VIDEO_NOTE_MANAGED_PATH):
            os.remove(START_VIDEO_NOTE_MANAGED_PATH)
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE admin_quiz_intro_videos
                    SET is_active = 0
                    WHERE environment = %s AND is_active = 1
                    """,
                    (_runtime_environment,),
                )
    except Exception as exc:
        try:
            if previous_row:
                previous_path = get_quiz_intro_library_file_path(
                    previous_row.get("storage_name") or ""
                )
                if os.path.isfile(previous_path):
                    await activate_quiz_intro_video_file(previous_path)
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Could not restore the default MP4 file: {exc}",
        ) from exc


async def get_support_links_row():
    fallback = {
        "channel_url": (os.getenv("CHANNEL_URL") or "").strip(),
        "support_url": (os.getenv("SUPPORT_URL") or "").strip(),
        "channel_id": (os.getenv("CHANNEL_ID") or "").strip(),
        "check_subscription_enabled": (os.getenv("CHECK_SUBSCRIPTION_ENABLED") or "").strip(),
        "quiz_intro_video_enabled": 1,
        "quiz_config": {},
        "final_message_config": {},
    }
    if not db_pool:
        settings = normalize_channel_settings(fallback)
        settings["quiz_intro_video_enabled"] = 1
        settings["quiz_config"] = normalize_quiz_config()
        settings["final_message_config"] = normalize_final_message_config()
        return await attach_quiz_intro_video_media(settings)
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT channel_id, channel_url, support_url, check_subscription_enabled,
                           quiz_intro_video_enabled, quiz_config, final_message_config
                    FROM admin_support_links
                    WHERE id = 1
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
    except Exception as e:
        print(f"Support links fallback: {e}")
        settings = normalize_channel_settings(fallback)
        settings["quiz_intro_video_enabled"] = 1
        settings["quiz_config"] = normalize_quiz_config()
        settings["final_message_config"] = normalize_final_message_config()
        return await attach_quiz_intro_video_media(settings)
    if not row:
        settings = normalize_channel_settings(fallback)
        settings["quiz_intro_video_enabled"] = 1
        settings["quiz_config"] = normalize_quiz_config()
        settings["final_message_config"] = normalize_final_message_config()
        return await attach_quiz_intro_video_media(settings)
    merged = {
        "channel_id": row.get("channel_id") or fallback["channel_id"],
        "channel_url": row.get("channel_url") or fallback["channel_url"],
        "support_url": row.get("support_url") or fallback["support_url"],
        "check_subscription_enabled": row.get("check_subscription_enabled")
        if row.get("check_subscription_enabled") is not None
        else fallback["check_subscription_enabled"],
        "quiz_intro_video_enabled": row.get("quiz_intro_video_enabled")
        if row.get("quiz_intro_video_enabled") is not None
        else fallback["quiz_intro_video_enabled"],
        "quiz_config": row.get("quiz_config") or fallback["quiz_config"],
        "final_message_config": row.get("final_message_config") or fallback["final_message_config"],
    }
    settings = normalize_channel_settings(merged)
    settings["quiz_config"] = normalize_quiz_config(merged.get("quiz_config"))
    settings["final_message_config"] = normalize_final_message_config(merged.get("final_message_config"))
    settings["quiz_intro_video_enabled"] = 1 if bool(
        int(merged.get("quiz_intro_video_enabled") or 0)
    ) else 0
    return await attach_quiz_intro_video_media(settings)


async def get_quiz_config_row():
    settings = await get_support_links_row()
    return normalize_quiz_config(settings.get("quiz_config"))


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


def require_affiliate_api_secret(provided_secret: str) -> None:
    if not AFFILIATE_API_SECRET:
        raise HTTPException(status_code=503, detail="Affiliate API is not configured")
    if not secrets.compare_digest(provided_secret or "", AFFILIATE_API_SECRET):
        raise HTTPException(status_code=403, detail="Invalid affiliate API secret")


def affiliate_api_response(
    success: bool,
    code: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {"success": success, "code": code, "message": message, "data": data}


def validate_affiliate_bot_id(bot_id: Any) -> None:
    if str(bot_id or "").strip() != AFFILIATE_BOT_ID:
        raise HTTPException(status_code=400, detail="Unknown affiliate bot id")


async def get_affiliate_user(*, telegram_id: Optional[int] = None, trader_id: str = ""):
    if not db_pool:
        return None
    clauses = []
    params = []
    if telegram_id:
        clauses.append("user_id = %s")
        params.append(int(telegram_id))
    if trader_id:
        clauses.append("trader_id = %s")
        params.append(str(trader_id).strip())
    if not clauses:
        return None
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                f"""
                SELECT user_id, username, first_name, trader_id,
                       COALESCE(pocket_registered, 0) AS pocket_registered,
                       COALESCE(pocket_deposited, 0) AS pocket_deposited,
                       COALESCE(pocket_deposit_amount, 0) AS pocket_deposit_amount,
                       pocket_registered_at
                FROM users
                WHERE {' OR '.join(clauses)}
                ORDER BY CASE WHEN user_id = %s THEN 0 ELSE 1 END
                LIMIT 1
                """,
                tuple(params + [int(telegram_id or 0)]),
            )
            return await cur.fetchone()


@app.post("/affiliate/check-user-globally")
async def affiliate_check_user_globally(
    payload: Dict[str, Any],
    x_affiliate_secret: str = Header(default="", alias="X-Affiliate-Secret"),
):
    require_affiliate_api_secret(x_affiliate_secret)
    validate_affiliate_bot_id(payload.get("bot_id"))
    return affiliate_api_response(
        True,
        "ok",
        "Global user check completed",
        {"tg_user_id": payload.get("tg_user_id"), "matches": [], "has_registered_match": False},
    )


@app.post("/affiliate/check-registration")
async def affiliate_check_registration(
    payload: Dict[str, Any],
    x_affiliate_secret: str = Header(default="", alias="X-Affiliate-Secret"),
):
    require_affiliate_api_secret(x_affiliate_secret)
    validate_affiliate_bot_id(payload.get("bot_id"))
    telegram_id = int(payload.get("tg_user_id") or 0)
    trader_id = str(payload.get("trader_id") or "").strip()
    if not telegram_id or not trader_id:
        return affiliate_api_response(False, "invalid_request", "Telegram ID and trader ID are required")
    user = await get_affiliate_user(telegram_id=telegram_id, trader_id=trader_id)
    if (
        not user
        or int(user.get("user_id") or 0) != telegram_id
        or str(user.get("trader_id") or "").strip() != trader_id
    ):
        return affiliate_api_response(False, "user_not_found", "Registration was not found")
    if not int(user.get("pocket_registered") or 0):
        return affiliate_api_response(False, "registration_not_confirmed", "Registration is not confirmed")
    return affiliate_api_response(
        True,
        "registered",
        "Registration confirmed",
        {
            "bot_id": AFFILIATE_BOT_ID,
            "tg_user_id": telegram_id,
            "trader_id": trader_id,
            "registration_status": 1,
            "reg_date": user.get("pocket_registered_at"),
        },
    )


@app.post("/affiliate/check-deposit")
async def affiliate_check_deposit(
    payload: Dict[str, Any],
    x_affiliate_secret: str = Header(default="", alias="X-Affiliate-Secret"),
):
    require_affiliate_api_secret(x_affiliate_secret)
    validate_affiliate_bot_id(payload.get("bot_id"))
    telegram_id = int(payload.get("tg_user_id") or 0)
    user = await get_affiliate_user(telegram_id=telegram_id)
    if not user or not str(user.get("trader_id") or "").strip():
        return affiliate_api_response(False, "no_trader_id", "Trader ID was not found")
    deposit_sum = float(user.get("pocket_deposit_amount") or 0)
    data = {
        "tg_user_id": telegram_id,
        "trader_id": user.get("trader_id"),
        "sum_deposits": deposit_sum,
        "min_deposit": AI_CHAT_MIN_DEPOSIT,
        "shortage": max(0.0, AI_CHAT_MIN_DEPOSIT - deposit_sum),
        "deposit_status": int(user.get("pocket_deposited") or 0),
    }
    if not int(user.get("pocket_deposited") or 0) or deposit_sum < AI_CHAT_MIN_DEPOSIT:
        code = "no_deposits" if deposit_sum <= 0 else "below_threshold"
        return affiliate_api_response(False, code, "Deposit is not confirmed", data)
    return affiliate_api_response(True, "confirmed", "Deposit confirmed", data)


@app.get("/affiliate/user-info")
async def affiliate_user_info(
    bot_id: str = Query(...),
    trader_id: str = Query(...),
    x_affiliate_secret: str = Header(default="", alias="X-Affiliate-Secret"),
):
    require_affiliate_api_secret(x_affiliate_secret)
    validate_affiliate_bot_id(bot_id)
    user = await get_affiliate_user(trader_id=str(trader_id or "").strip())
    if not user:
        return affiliate_api_response(False, "user_not_found", "User was not found")
    return affiliate_api_response(
        True,
        "ok",
        "User information loaded",
        {
            "client_id": user.get("trader_id"),
            "reg_date": user.get("pocket_registered_at"),
            "deposits_sum": float(user.get("pocket_deposit_amount") or 0),
            "registration_status": int(user.get("pocket_registered") or 0),
            "deposit_status": int(user.get("pocket_deposited") or 0),
        },
    )


def normalize_settings_toggle(value: object, default: int = 1) -> int:
    if value is None:
        return 1 if default else 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "0", "false", "no", "off", "none"}:
            return 0
        if normalized in {"1", "true", "yes", "on"}:
            return 1
    return 1 if bool(value) else 0


def serialize_system_access_settings(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    policy = normalize_access_policy((row or {}).get("policy"))
    min_deposit = normalize_min_deposit((row or {}).get("min_deposit_amount"))
    return {
        "policy": policy,
        "min_deposit_amount": str(min_deposit),
        "registration_url": str((row or {}).get("registration_url") or DEFAULT_REGISTRATION_URL).strip(),
        "registration_button_bot_enabled": normalize_settings_toggle(
            (row or {}).get("registration_button_bot_enabled"), 1
        ),
        "registration_button_app_enabled": normalize_settings_toggle(
            (row or {}).get("registration_button_app_enabled"), 1
        ),
        "updated_at": (row or {}).get("updated_at"),
        "updated_by": (row or {}).get("updated_by"),
    }


async def get_system_access_settings_row() -> Dict[str, Any]:
    default_settings = serialize_system_access_settings(
        {
            "policy": ACCESS_POLICY_REGISTRATION_DEPOSIT,
            "min_deposit_amount": "0",
            "registration_url": DEFAULT_REGISTRATION_URL,
            "registration_button_bot_enabled": 1,
            "registration_button_app_enabled": 1,
        }
    )
    if not db_pool:
        return default_settings
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT policy, min_deposit_amount, registration_url,
                           registration_button_bot_enabled, registration_button_app_enabled,
                           updated_at, updated_by
                    FROM admin_system_access_settings
                    WHERE id = 1
                    LIMIT 1
                    """
                )
                row = await cur.fetchone()
        return serialize_system_access_settings(row) if row else default_settings
    except Exception as e:
        print(f"System access settings fallback: {e}")
        return default_settings


def normalize_chatterfy_lead_id(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 255:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._:@-]+", normalized):
        return ""
    return normalized


def normalize_chatterfy_tracker_click_id(value: object) -> str:
    """Normalize the opaque Chatterfy tracker click ID."""
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 255:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._~:@+\-=]+", normalized):
        return ""
    return normalized


async def get_personal_registration_link(user_id: int) -> Optional[Dict[str, Any]]:
    if not db_pool or int(user_id or 0) <= 0:
        return None

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, aio_visit_uuid, chatterfy_lead_id,
                       trader_id, profile_trader_id, country,
                       pocket_site_id, pocket_cid, pocket_sub_id1,
                       pocket_sub_id2, pocket_sub_id3,
                       COALESCE(pocket_registered, 0) AS pocket_registered
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            user_row = await cur.fetchone()
    if not user_row:
        return None

    access_settings = await get_system_access_settings_row()
    aio_visit_uuid = normalize_aio_visit_uuid(user_row.get("aio_visit_uuid"))
    if not aio_visit_uuid:
        aio_visit_uuid = normalize_aio_visit_uuid(user_row.get("pocket_sub_id2")) or ""
    chatterfy_lead_id = normalize_chatterfy_lead_id(
        user_row.get("chatterfy_lead_id") or user_row.get("pocket_sub_id3")
    )
    registration_url = build_registration_url(
        access_settings.get("registration_url") or DEFAULT_REGISTRATION_URL,
        click_id=int(user_row["user_id"]),
        aio_visit_uuid=aio_visit_uuid,
        chatterfy_lead_id=chatterfy_lead_id,
        values={
            "site_id": user_row.get("pocket_site_id") or "",
            "trader_id": user_row.get("profile_trader_id") or user_row.get("trader_id") or "",
            "cid": user_row.get("pocket_cid") or "",
            "sub_id1": user_row.get("pocket_sub_id1") or "",
            "country": user_row.get("country") or "",
        },
    )
    return {
        "url": registration_url,
        "registered": truthy_db(user_row.get("pocket_registered")) == 1,
        "show_in_bot": normalize_settings_toggle(
            access_settings.get("registration_button_bot_enabled"), 1
        ) == 1,
        "show_in_app": normalize_settings_toggle(
            access_settings.get("registration_button_app_enabled"), 1
        ) == 1,
    }


def truthy_db(value) -> int:
    try:
        return 1 if int(value or 0) == 1 else 0
    except (TypeError, ValueError):
        return 0


SIGNAL_ACCESS_REQUIRED_DETAIL = "signal_access_required"


async def get_signal_access_status(user_id: int, mode: str) -> Dict[str, Any]:
    if not user_id or not db_pool:
        return {"access": 0}
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in ("forex", "binary"):
        return {"access": 0}
    settings = await get_system_access_settings_row()
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT
                    u.user_id,
                    COALESCE(u.is_blocked, 0) AS is_blocked,
                    COALESCE(u.pocket_registered, 0) AS pocket_registered,
                    COALESCE(u.pocket_deposited, 0) AS pocket_deposited,
                    COALESCE(u.pocket_deposit_amount, 0) AS pocket_deposit_amount,
                    COALESCE(uma.is_enabled, 0) AS manual_access,
                    COALESCE(uma.override_mode, 'inherit') AS override_mode
                FROM users u
                LEFT JOIN user_mode_access uma ON uma.user_id = u.user_id AND uma.mode = %s
                WHERE u.user_id = %s
                LIMIT 1
                """,
                (normalized_mode, user_id),
            )
            row = await cur.fetchone()
    if not row:
        return {"access": 0, "policy": settings.get("policy")}
    if truthy_db(row.get("is_blocked")) == 1:
        return {"access": 0, "policy": "blocked"}
    override_mode = str(row.get("override_mode") or "inherit").strip().lower()
    if override_mode == "allow":
        return {"access": 1, "policy": "manual_allow"}
    if override_mode == "deny":
        return {"access": 0, "policy": "manual_deny"}
    return {
        "access": 1 if system_policy_grants_signal_access(settings, row) else 0,
        "policy": settings.get("policy"),
        "min_deposit_amount": settings.get("min_deposit_amount"),
    }


async def require_signal_access(user_id: int, mode: str) -> Dict[str, Any]:
    status = await get_signal_access_status(user_id, mode)
    if truthy_db(status.get("access")) != 1:
        raise HTTPException(status_code=403, detail=SIGNAL_ACCESS_REQUIRED_DETAIL)
    return status


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


def numeric_payload_value(payload: Any, *keys: str) -> float:
    if not isinstance(payload, dict):
        return 0.0
    for key in keys:
        try:
            amount = float(payload.get(key))
        except (TypeError, ValueError):
            continue
        if amount > 0:
            return round(amount, 2)
    return 0.0


def extract_pocket_registration_status(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {"registered": 0, "registered_at": None}
    registered_at = payload.get("registered_at") or payload.get("registration_date") or payload.get("created_at")
    registered = 1 if (payload.get("user_id") or registered_at or payload.get("status")) else 0
    return {"registered": registered, "registered_at": str(registered_at).strip()[:64] if registered_at else None}


def extract_pocket_deposit_status(payload: Any) -> Dict[str, Any]:
    amount = numeric_payload_value(
        payload, "sum_deposits", "sum_ftd", "ftd_amount", "total_deposits", "deposit_amount", "deposits"
    )
    return {"deposited": 1 if amount > 0 else 0, "deposit_amount": amount}


async def fetch_pocket_user_info(trader_id: str, partner_id: str, api_token: str) -> Dict[str, Any]:
    url = build_pocket_user_info_url(trader_id, partner_id, api_token)
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=12.0)
        response.raise_for_status()
        return response.json()


async def sync_pocket_balance_for_user(user_row: Dict[str, Any], pocket_settings: Dict[str, Any]) -> bool:
    user_id = int(user_row.get("user_id") or 0)
    trader_id = str(user_row.get("trader_id") or "").strip()
    manual_trader_id = str(user_row.get("profile_trader_id") or "").strip()
    partner_id = str(pocket_settings.get("partner_id") or "").strip()
    api_token = str(pocket_settings.get("api_token") or "").strip()
    if manual_trader_id or not user_id or not trader_id or not partner_id or not api_token:
        return False
    try:
        payload = await fetch_pocket_user_info(trader_id, partner_id, api_token)
        balance = extract_pocket_balance(payload)
        registration_status = extract_pocket_registration_status(payload)
        deposit_status = extract_pocket_deposit_status(payload)
        if balance is None:
            raise ValueError("Pocket response does not contain balance")
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE users
                    SET balance = %s,
                        balance_synced_at = NOW(),
                        balance_sync_error = NULL,
                        pocket_registered = %s,
                        pocket_deposited = %s,
                        pocket_registered_at = COALESCE(%s, pocket_registered_at),
                        pocket_deposit_amount = GREATEST(COALESCE(pocket_deposit_amount, 0), %s),
                        pocket_checked_at = NOW()
                    WHERE user_id = %s
                    """,
                    (
                        balance,
                        registration_status["registered"],
                        deposit_status["deposited"],
                        registration_status["registered_at"],
                        deposit_status["deposit_amount"],
                        user_id,
                    ),
                )
        await sync_aio_profile_status_fields(user_id)
        return True
    except Exception as e:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE users
                    SET balance_synced_at = NOW(),
                        balance_sync_error = %s,
                        pocket_checked_at = NOW()
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
                        SELECT user_id, trader_id, profile_trader_id
                        FROM users
                        WHERE balance_sync_enabled = 1
                          AND trader_id IS NOT NULL
                          AND TRIM(trader_id) != ''
                          AND (profile_trader_id IS NULL OR TRIM(profile_trader_id) = '')
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


def get_aio_geo_postback_secret() -> str:
    return (os.getenv("AIO_GEO_POSTBACK_SECRET") or AIO_GEO_POSTBACK_SECRET or "").strip()


def require_aio_geo_postback_secret(supplied_secret: str) -> None:
    expected_secret = get_aio_geo_postback_secret()
    if not expected_secret:
        raise HTTPException(status_code=503, detail="AIO geo postback is not configured")
    if not supplied_secret or not secrets.compare_digest(str(supplied_secret), expected_secret):
        raise HTTPException(status_code=401, detail="Invalid AIO postback secret")


async def apply_pending_aio_geo_for_visit(
    aio_visit_uuid: str,
    conversion_type_uuid: str = "",
) -> Dict[str, Any]:
    """Apply stored AIO geo data once a visit is linked to exactly one user."""
    normalized_visit_uuid = normalize_aio_visit_uuid(aio_visit_uuid)
    normalized_conversion_uuid = normalize_aio_visit_uuid(conversion_type_uuid) or ""
    if not normalized_visit_uuid:
        return {"status": "skipped", "reason": "invalid_aio_visit_uuid"}
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}

    async with db_pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT id, conversion_type_uuid, country_code, received_at
                    FROM aio_inbound_postbacks
                    WHERE aio_visit_uuid = %s
                      AND (%s = '' OR conversion_type_uuid = %s)
                    ORDER BY received_at DESC, id DESC
                    FOR UPDATE
                    """,
                    (
                        normalized_visit_uuid,
                        normalized_conversion_uuid,
                        normalized_conversion_uuid,
                    ),
                )
                inbound_rows = list(await cur.fetchall() or [])
                if not inbound_rows:
                    await conn.commit()
                    return {"status": "pending", "reason": "postback_not_received"}

                await cur.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE aio_visit_uuid = %s
                    ORDER BY user_id ASC
                    LIMIT 2
                    FOR UPDATE
                    """,
                    (normalized_visit_uuid,),
                )
                user_rows = list(await cur.fetchall() or [])
                inbound_ids = [int(row["id"]) for row in inbound_rows]

                if not user_rows:
                    await cur.executemany(
                        """
                        UPDATE aio_inbound_postbacks
                        SET user_id = NULL, status = 'pending', applied_at = NULL
                        WHERE id = %s
                        """,
                        [(row_id,) for row_id in inbound_ids],
                    )
                    await conn.commit()
                    return {
                        "status": "pending",
                        "reason": "user_not_linked",
                        "aio_visit_uuid": normalized_visit_uuid,
                    }

                if len(user_rows) > 1:
                    await cur.executemany(
                        """
                        UPDATE aio_inbound_postbacks
                        SET user_id = NULL, status = 'conflict', applied_at = NULL
                        WHERE id = %s
                        """,
                        [(row_id,) for row_id in inbound_ids],
                    )
                    await conn.commit()
                    return {
                        "status": "conflict",
                        "reason": "aio_visit_uuid_is_not_unique",
                        "aio_visit_uuid": normalized_visit_uuid,
                    }

                user_id = int(user_rows[0]["user_id"])
                latest_row = inbound_rows[0]
                country_code = normalize_aio_country_code(latest_row.get("country_code"))
                if not country_code:
                    await conn.rollback()
                    return {"status": "skipped", "reason": "invalid_stored_geo"}

                await cur.execute(
                    """
                    UPDATE users
                    SET aio_country_code = %s,
                        country = CASE
                            WHEN country IS NULL OR TRIM(country) = '' THEN %s
                            ELSE country
                        END
                    WHERE user_id = %s
                    """,
                    (country_code, country_code, user_id),
                )
                await cur.executemany(
                    """
                    UPDATE aio_inbound_postbacks
                    SET user_id = %s, status = 'applied', applied_at = NOW()
                    WHERE id = %s
                    """,
                    [(user_id, row_id) for row_id in inbound_ids],
                )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise

    return {
        "status": "applied",
        "user_id": user_id,
        "aio_visit_uuid": normalized_visit_uuid,
        "conversion_type_uuid": str(latest_row.get("conversion_type_uuid") or ""),
        "geo": country_code,
    }


async def apply_pending_aio_geo_for_user(user_id: int) -> Dict[str, Any]:
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT aio_visit_uuid FROM users WHERE user_id = %s LIMIT 1",
                (int(user_id),),
            )
            user_row = await cur.fetchone() or {}
    aio_visit_uuid = normalize_aio_visit_uuid(user_row.get("aio_visit_uuid"))
    if not aio_visit_uuid:
        return {"status": "pending", "reason": "missing_aio_visit_uuid"}
    return await apply_pending_aio_geo_for_visit(aio_visit_uuid)


@app.api_route("/api/v1/trigger/conversion-request", methods=["GET", "POST"])
@app.api_route("/api/integrations/aio/geo", methods=["GET", "POST"])
async def receive_aio_geo_postback(request: Request):
    """Receive an AIO country conversion and retain it until the user is linked."""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    payload = await read_postback_payload(request)
    supplied_secret = str(
        payload.get("secret") or request.headers.get("X-AIO-Geo-Secret") or ""
    ).strip()
    require_aio_geo_postback_secret(supplied_secret)

    raw_visit_uuid = (
        payload.get("click_id")
        or payload.get("visit_uuid")
        or payload.get("aio_visit_uuid")
        or ""
    )
    raw_conversion_uuid = (
        payload.get("conversion_type_uuid")
        or payload.get("conversion_uuid")
        or payload.get("conversion_type")
        or payload.get("conversion")
        or ""
    )
    raw_country_code = payload.get("geo") or payload.get("country_code") or payload.get("country") or ""
    aio_visit_uuid = normalize_aio_visit_uuid(raw_visit_uuid)
    conversion_type_uuid = normalize_aio_visit_uuid(raw_conversion_uuid)
    country_code = normalize_aio_country_code(raw_country_code)

    if not aio_visit_uuid:
        raise HTTPException(status_code=400, detail="Valid click_id is required")
    if not conversion_type_uuid:
        raise HTTPException(status_code=400, detail="Valid conversion_type_uuid is required")
    if conversion_type_uuid != AIO_GEO_CONVERSION_TYPE_UUID:
        raise HTTPException(status_code=400, detail="Unsupported AIO conversion type")
    if not country_code:
        raise HTTPException(status_code=400, detail="Valid ISO 3166-1 alpha-2 geo is required")

    safe_payload = {
        key: ("***" if str(key).lower() in {"secret", "token", "signature"} else value)
        for key, value in payload.items()
    }
    source_ip = request.client.host if request.client else ""
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO aio_inbound_postbacks (
                    aio_visit_uuid, conversion_type_uuid, country_code, user_id,
                    status, raw_payload, source_ip, received_at, applied_at
                )
                VALUES (%s, %s, %s, NULL, 'pending', %s, %s, NOW(), NULL)
                ON DUPLICATE KEY UPDATE
                    country_code = VALUES(country_code),
                    user_id = NULL,
                    status = 'pending',
                    raw_payload = VALUES(raw_payload),
                    source_ip = VALUES(source_ip),
                    received_at = NOW(),
                    applied_at = NULL
                """,
                (
                    aio_visit_uuid,
                    conversion_type_uuid,
                    country_code,
                    json.dumps(safe_payload, ensure_ascii=False, default=str),
                    source_ip,
                ),
            )

    result = await apply_pending_aio_geo_for_visit(aio_visit_uuid, conversion_type_uuid)
    return {
        "status": result.get("status"),
        "click_id": aio_visit_uuid,
        "conversion_type_uuid": conversion_type_uuid,
        "geo": country_code,
        "user_id": result.get("user_id"),
        "reason": result.get("reason"),
    }


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
    safe_payload = {
        key: ("***" if str(key).lower() in {"secret", "token", "signature"} else value)
        for key, value in raw_payload.items()
    }
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT IGNORE INTO pocket_postback_events (
                    event_slug, unique_key, user_id, click_id, trader_id, deposit_amount,
                    country, site_id, cid, sub_id1, sub_id2, sub_id3, provider_event_id, payload_fingerprint,
                    raw_payload, status, reason, source_ip
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    normalized.get("event_slug") or "unknown",
                    normalized.get("unique_key") or "unknown",
                    user_id,
                    normalized.get("click_id") or None,
                    normalized.get("trader_id") or None,
                    normalized.get("deposit_amount") or "0.00",
                    normalized.get("country") or None,
                    normalized.get("site_id") or None,
                    normalized.get("cid") or None,
                    normalized.get("sub_id1") or None,
                    normalized.get("sub_id2") or None,
                    normalized.get("sub_id3") or None,
                    normalized.get("provider_event_id") or None,
                    normalized.get("payload_fingerprint") or None,
                    json.dumps(safe_payload, ensure_ascii=False, default=str),
                    status,
                    reason,
                    source_ip,
                ),
            )
            return int(cur.lastrowid)


async def update_pocket_aichatter_delivery(log_id: int, result: Dict[str, Any]) -> None:
    if not log_id or not db_pool:
        return
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE pocket_postback_events
            SET aichatter_status = %s, aichatter_error = %s, aichatter_synced_at = NOW()
            WHERE id = %s
            """,
            (result.get("status"), result.get("error") or result.get("reason"), log_id),
        )


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


async def send_aio_postback_event(
    user_id: int,
    event_slug: str,
    revenue: Optional[object] = None,
    currency: Optional[str] = None,
    unique_key: Optional[str] = None,
) -> Dict[str, Any]:
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}

    normalized_event_slug = normalize_aio_event_slug(event_slug)
    if not normalized_event_slug:
        return {"status": "skipped", "reason": "invalid_event_slug"}

    default_unique_key = f"{normalized_event_slug}:{user_id}"
    normalized_unique_key = str(unique_key or default_unique_key).strip()[:128] or default_unique_key
    normalized_currency = str(currency or "").strip().upper()[:8] or None
    normalized_revenue = normalize_aio_revenue(revenue)

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT aio_visit_uuid FROM users WHERE user_id = %s LIMIT 1", (user_id,))
            user_row = await cur.fetchone()
            aio_visit_uuid = normalize_aio_visit_uuid((user_row or {}).get("aio_visit_uuid"))
            if not aio_visit_uuid:
                return {"status": "skipped", "reason": "missing_aio_visit_uuid"}

            request_url = build_aio_postback_url(
                aio_visit_uuid,
                normalized_event_slug,
                revenue=normalized_revenue,
                currency=normalized_currency,
                unique_key=normalized_unique_key,
            )

            await cur.execute(
                """
                INSERT IGNORE INTO aio_postback_events (
                    user_id, aio_visit_uuid, event_slug, unique_key, revenue, currency, request_url, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                """,
                (
                    user_id,
                    aio_visit_uuid,
                    normalized_event_slug,
                    normalized_unique_key,
                    normalized_revenue,
                    normalized_currency,
                    request_url,
                ),
            )
            if cur.rowcount == 0:
                await cur.execute(
                    """
                    SELECT id, status, request_url
                    FROM aio_postback_events
                    WHERE aio_visit_uuid = %s AND event_slug = %s AND unique_key = %s
                    LIMIT 1
                    """,
                    (aio_visit_uuid, normalized_event_slug, normalized_unique_key),
                )
                existing_event = await cur.fetchone() or {}
                if existing_event:
                    return {
                        "status": "skipped",
                        "reason": "duplicate",
                        "event_id": existing_event.get("id"),
                        "previous_status": existing_event.get("status"),
                    }
            else:
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


async def send_pending_chatterfy_start_event(
    user_id: int,
    event_slug: str = CHATTERFY_START_EVENT,
) -> Dict[str, Any]:
    """Deliver the source-specific Chatterfy start once an AIO visit UUID is known."""
    normalized_event_slug = normalize_chatterfy_event(event_slug)
    if normalized_event_slug not in {CHATTERFY_START_EVENT, CHATTERFY_BOT_START_EVENT}:
        return {"status": "skipped", "reason": "unsupported_chatterfy_start_event"}
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT chatterfy_lead_id, chatterfy_bot_lead_id, aio_visit_uuid
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            user_row = await cur.fetchone() or {}
    lead_field = (
        "chatterfy_bot_lead_id"
        if normalized_event_slug == CHATTERFY_BOT_START_EVENT
        else "chatterfy_lead_id"
    )
    if not normalize_chatterfy_lead_id(user_row.get(lead_field)):
        return {"status": "skipped", "reason": "missing_chatterfy_lead_id"}
    if not normalize_aio_visit_uuid(user_row.get("aio_visit_uuid")):
        return {"status": "pending", "reason": "missing_aio_visit_uuid"}
    return await send_aio_postback_event(
        int(user_id),
        normalized_event_slug,
        unique_key=f"{normalized_event_slug}:{int(user_id)}",
    )


async def send_pending_chatterfy_start_events(user_id: int) -> Dict[str, Any]:
    """Retry both independent Chatterfy starts when tracking arrives later."""
    account_result = await send_pending_chatterfy_start_event(user_id, CHATTERFY_START_EVENT)
    bot_result = await send_pending_chatterfy_start_event(user_id, CHATTERFY_BOT_START_EVENT)
    return {"account": account_result, "bot": bot_result}


async def send_pocket_aio_delivery(
    *,
    user_id: int,
    event_slug: str,
    unique_key: str,
    trader_id: str = "",
    deposit_amount: object = 0,
    total_deposit_amount: object = 0,
) -> Dict[str, Any]:
    postback_result = await send_aio_pocket_conversion(
        user_id=user_id,
        event_slug=event_slug,
        trader_id=trader_id,
        unique_key=unique_key,
        revenue=deposit_amount if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT} else "",
    )
    fields = []
    if trader_id:
        fields.append(await send_aio_field_value(user_id, "tg_trader_id", trader_id))
    if event_slug == POCKET_FTD_EVENT:
        fields.append(await send_aio_field_value(user_id, "tg_first_dep", deposit_amount))
    if event_slug in {POCKET_FTD_EVENT, POCKET_DEPOSIT_EVENT}:
        fields.append(await send_aio_field_value(user_id, "tg_sum_dep", total_deposit_amount))
    return {"status": postback_result.get("status"), "postback": postback_result, "fields": fields}


async def send_aio_user_fields(user_id: int, first_name: str = "", username: str = "") -> Dict[str, Any]:
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT aio_visit_uuid FROM users WHERE user_id = %s LIMIT 1", (user_id,))
            user_row = await cur.fetchone()

    aio_visit_uuid = normalize_aio_visit_uuid((user_row or {}).get("aio_visit_uuid"))
    if not aio_visit_uuid:
        return {"status": "skipped", "reason": "missing_aio_visit_uuid"}

    fields = {
        "tgid": str(user_id),
        "tg_first_name": str(first_name or "").strip(),
        "tg_username": str(username or "").strip().lstrip("@"),
    }
    request_urls = [
        build_aio_field_trigger_url(aio_visit_uuid, field_name, field_value)
        for field_name, field_value in fields.items()
        if field_name == "tgid" or field_value
    ]

    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for request_url in request_urls:
            try:
                response = await client.get(request_url)
                results.append(
                    {
                        "url": request_url,
                        "status": "sent" if response.status_code < 400 else "failed",
                        "response_status": response.status_code,
                        "response_body": response.text[:4000],
                    }
                )
            except Exception as exc:
                results.append({"url": request_url, "status": "failed", "error": str(exc)[:4000]})

    return {"status": "sent", "count": len(results), "results": results}


class AIChatterDialogStartRequest(BaseModel):
    user_id: int
    first_name: str = ""
    username: str = ""
    aio_visit_uuid: str = ""
    chatterfy_lead_id: str = ""


class ChatterfyLeadBindingRequest(BaseModel):
    user_id: int
    chatterfy_lead_id: str
    aio_visit_uuid: str = ""
    tracker_click_id: str = ""
    first_name: str = ""
    username: str = ""


def require_ai_chatter_gateway_secret(supplied_secret: str) -> None:
    if not AI_CHATTER_GATEWAY_SECRET:
        raise HTTPException(status_code=503, detail="AI Chatter integration is not configured")
    if not secrets.compare_digest(str(supplied_secret or ""), AI_CHATTER_GATEWAY_SECRET):
        raise HTTPException(status_code=401, detail="Invalid AI Chatter secret")


def require_chatterfy_webhook_secret(supplied_secret: str) -> None:
    if not CHATTERFY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Chatterfy webhook is not configured")
    if not secrets.compare_digest(str(supplied_secret or ""), CHATTERFY_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid Chatterfy webhook secret")


async def bind_user_tracking_identity(
    user_id: int,
    *,
    chatterfy_lead_id: str = "",
    aio_visit_uuid: str = "",
    tracker_click_id: str = "",
    first_name: str = "",
    username: str = "",
    chatterfy_source: str = "account",
) -> Dict[str, str]:
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database is unavailable")
    if int(user_id or 0) <= 0:
        raise HTTPException(status_code=400, detail="user_id must be positive")

    normalized_source = str(chatterfy_source or "account").strip().lower()
    if normalized_source not in {"account", "bot"}:
        raise HTTPException(status_code=400, detail="Invalid chatterfy_source")
    lead_column = "chatterfy_bot_lead_id" if normalized_source == "bot" else "chatterfy_lead_id"

    raw_lead_id = str(chatterfy_lead_id or "").strip()
    normalized_lead_id = normalize_chatterfy_lead_id(raw_lead_id)
    if raw_lead_id and not normalized_lead_id:
        raise HTTPException(status_code=400, detail="Invalid chatterfy_lead_id")
    raw_aio_visit_uuid = str(aio_visit_uuid or "").strip()
    normalized_aio_visit_uuid = normalize_aio_visit_uuid(raw_aio_visit_uuid) or ""
    if raw_aio_visit_uuid and not normalized_aio_visit_uuid:
        raise HTTPException(status_code=400, detail="Invalid aio_visit_uuid")
    raw_tracker_click_id = str(tracker_click_id or "").strip()
    normalized_tracker_click_id = normalize_chatterfy_tracker_click_id(raw_tracker_click_id)
    if raw_tracker_click_id and not normalized_tracker_click_id:
        raise HTTPException(status_code=400, detail="Invalid tracker_click_id")
    normalized_first_name = str(first_name or "").strip()[:255]
    normalized_username = str(username or "").strip().lstrip("@")[:255]
    if normalized_username and not re.fullmatch(r"[A-Za-z0-9_]{5,32}", normalized_username):
        normalized_username = ""
    if (
        not normalized_lead_id
        and not normalized_aio_visit_uuid
        and not normalized_tracker_click_id
        and not normalized_first_name
        and not normalized_username
    ):
        raise HTTPException(status_code=400, detail="At least one profile value is required")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if normalized_lead_id:
                await cur.execute(
                    f"""
                    SELECT user_id
                    FROM users
                    WHERE user_id <> %s
                      AND ({lead_column} = %s OR pocket_sub_id3 = %s)
                    LIMIT 1
                    """,
                    (int(user_id), normalized_lead_id, normalized_lead_id),
                )
                if await cur.fetchone():
                    raise HTTPException(status_code=409, detail="chatterfy_lead_id is already linked")
            await cur.execute(
                """
                INSERT INTO users (
                    user_id, username, first_name, aio_visit_uuid,
                    chatterfy_tracker_click_id, lang, mode
                )
                VALUES (
                    %s, NULLIF(%s, ''), NULLIF(%s, ''), NULLIF(%s, ''),
                    NULLIF(%s, ''), 'ru', 'forex'
                )
                ON DUPLICATE KEY UPDATE
                    username = CASE
                        WHEN VALUES(username) IS NOT NULL
                             AND (username IS NULL OR TRIM(username) = '')
                            THEN VALUES(username)
                        ELSE username
                    END,
                    first_name = CASE
                        WHEN VALUES(first_name) IS NOT NULL
                             AND (first_name IS NULL OR TRIM(first_name) = '')
                            THEN VALUES(first_name)
                        ELSE first_name
                    END,
                    aio_visit_uuid = CASE
                        WHEN VALUES(aio_visit_uuid) IS NOT NULL THEN VALUES(aio_visit_uuid)
                        ELSE aio_visit_uuid
                    END,
                    chatterfy_tracker_click_id = CASE
                        WHEN VALUES(chatterfy_tracker_click_id) IS NOT NULL
                            THEN VALUES(chatterfy_tracker_click_id)
                        ELSE chatterfy_tracker_click_id
                    END
                """,
                (
                    int(user_id),
                    normalized_username,
                    normalized_first_name,
                    normalized_aio_visit_uuid,
                    normalized_tracker_click_id,
                ),
            )
            if normalized_lead_id:
                await cur.execute(
                    f"UPDATE users SET {lead_column} = %s WHERE user_id = %s",
                    (normalized_lead_id, int(user_id)),
                )
            await cur.executemany(
                """
                INSERT IGNORE INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                VALUES (%s, %s, 0, NULL)
                """,
                [(int(user_id), "forex"), (int(user_id), "binary")],
            )
    if normalized_aio_visit_uuid:
        await apply_pending_aio_geo_for_user(int(user_id))
    asyncio.create_task(sync_aio_profile_status_fields(int(user_id)))
    return {
        "aio_visit_uuid": normalized_aio_visit_uuid,
        "chatterfy_lead_id": normalized_lead_id if normalized_source == "account" else "",
        "chatterfy_bot_lead_id": normalized_lead_id if normalized_source == "bot" else "",
        "tracker_click_id": normalized_tracker_click_id,
        "first_name": normalized_first_name,
        "username": normalized_username,
        "source": normalized_source,
    }


@app.post("/api/internal/chatterfy/lead")
async def receive_chatterfy_lead_binding(
    payload: ChatterfyLeadBindingRequest,
    x_ai_chatter_secret: str = Header(default="", alias="X-AI-Chatter-Secret"),
):
    """Persist the Chatterfy lead-to-Telegram mapping before registration."""
    require_ai_chatter_gateway_secret(x_ai_chatter_secret)
    tracking = await bind_user_tracking_identity(
        payload.user_id,
        chatterfy_lead_id=payload.chatterfy_lead_id,
        aio_visit_uuid=payload.aio_visit_uuid,
        tracker_click_id=payload.tracker_click_id,
        first_name=payload.first_name,
        username=payload.username,
    )
    return {"status": "ok", "tracking": tracking}


@app.api_route("/api/integrations/chatterfy/lead", methods=["GET", "POST"])
async def receive_chatterfy_lead_postback(request: Request):
    """Bind a Chatterfy chat to Telegram using a dedicated webhook secret."""
    payload = await read_postback_payload(request)
    supplied_secret = str(
        payload.get("secret") or request.headers.get("X-AI-Chatter-Secret") or ""
    ).strip()
    require_chatterfy_webhook_secret(supplied_secret)

    event_slug = normalize_chatterfy_event(payload.get("event") or payload.get("event_slug"))
    if event_slug not in {CHATTERFY_START_EVENT, CHATTERFY_BOT_START_EVENT}:
        raise HTTPException(status_code=400, detail="Unsupported Chatterfy event")
    chatterfy_source = "bot" if event_slug == CHATTERFY_BOT_START_EVENT else "account"

    raw_user_id = payload.get("tgid") or payload.get("tg_user_id") or payload.get("user_id")
    try:
        user_id = int(str(raw_user_id or "").strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Valid tgid is required")
    lead_id = (
        payload.get("chatterfy_lead_id")
        or payload.get("lead_id")
        or payload.get("leadid")
        or payload.get("chatterfy_id")
        or payload.get("contact_id")
        or payload.get("subscriber_id")
        or payload.get("dialog_id")
        or payload.get("chat_id")
        or ""
    )
    raw_aio_visit_uuid = str(
        payload.get("start0")
        or payload.get("aio_visit_uuid")
        or payload.get("visit_uuid")
        or ""
    ).strip()
    explicit_tracker_click_id = (
        payload.get("tracker_click_id")
        or payload.get("tracker.clickid")
        or payload.get("tracker_clickid")
        or payload.get("clickid")
        or ""
    )
    aio_visit_uuid = normalize_aio_visit_uuid(raw_aio_visit_uuid) or ""
    tracker_click_id = explicit_tracker_click_id
    if not tracker_click_id and raw_aio_visit_uuid and not aio_visit_uuid:
        # Compatibility with the original URL where tracker.clickid was sent
        # under the aio_visit_uuid query key.
        tracker_click_id = raw_aio_visit_uuid
    first_name = (
        payload.get("first_name")
        or payload.get("tg_first_name")
        or payload.get("telegram_first_name")
        or payload.get("tg_name")
        or payload.get("name")
        or ""
    )
    username = (
        payload.get("tg_username")
        or payload.get("telegram_username")
        or payload.get("username")
        or ""
    )
    tracking = await bind_user_tracking_identity(
        user_id,
        chatterfy_lead_id=str(lead_id),
        aio_visit_uuid=str(aio_visit_uuid),
        tracker_click_id=str(tracker_click_id),
        first_name=str(first_name),
        username=str(username),
        chatterfy_source=chatterfy_source,
    )
    event_result = await send_pending_chatterfy_start_event(user_id, event_slug)
    return {"status": "ok", "tracking": tracking, "event": event_result}


@app.post("/api/internal/aichatter/dialog-start")
async def receive_ai_chatter_dialog_start(
    payload: AIChatterDialogStartRequest,
    x_ai_chatter_secret: str = Header(default="", alias="X-AI-Chatter-Secret"),
):
    """Accept the first-dialog signal from the isolated AI Chatter service."""
    require_ai_chatter_gateway_secret(x_ai_chatter_secret)
    if payload.user_id <= 0:
        raise HTTPException(status_code=400, detail="user_id must be positive")

    if (
        payload.chatterfy_lead_id
        or payload.aio_visit_uuid
        or payload.first_name
        or payload.username
    ):
        await bind_user_tracking_identity(
            payload.user_id,
            chatterfy_lead_id=payload.chatterfy_lead_id,
            aio_visit_uuid=payload.aio_visit_uuid,
            first_name=payload.first_name,
            username=payload.username,
        )

    event_result = await send_pending_chatterfy_start_event(payload.user_id)
    return {"status": "ok", "event": event_result}


async def send_aio_field_value(user_id: int, field_name: str, field_value: object) -> Dict[str, Any]:
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT aio_visit_uuid FROM users WHERE user_id = %s LIMIT 1", (user_id,))
            user_row = await cur.fetchone()

    aio_visit_uuid = normalize_aio_visit_uuid((user_row or {}).get("aio_visit_uuid"))
    if not aio_visit_uuid:
        return {"status": "skipped", "reason": "missing_aio_visit_uuid"}

    try:
        request_url = build_aio_field_trigger_url(aio_visit_uuid, field_name, field_value)
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc)}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(request_url)
        return {
            "status": "sent" if response.status_code < 400 else "failed",
            "response_status": response.status_code,
            "response_body": response.text[:4000],
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)[:4000]}


AIO_PROFILE_STATUS_FIELD_COLUMNS = {
    "tg_dep_ok": "aio_dep_ok_synced_value",
    "tg_vip": "aio_vip_synced_value",
    "tg_copy": "aio_copy_synced_value",
}


async def sync_aio_profile_status_fields(user_id: int) -> Dict[str, Any]:
    """Synchronize stable 0/1 customer status fields with the linked AIO visit."""
    if not db_pool:
        return {"status": "skipped", "reason": "db_unavailable"}

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT aio_visit_uuid, aio_status_fields_visit_uuid,
                       aio_dep_ok_synced_value, aio_vip_synced_value,
                       aio_copy_synced_value,
                       COALESCE(pocket_deposited, 0) AS pocket_deposited
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            user_row = await cur.fetchone() or {}

    aio_visit_uuid = normalize_aio_visit_uuid(user_row.get("aio_visit_uuid"))
    if not aio_visit_uuid:
        return {"status": "skipped", "reason": "missing_aio_visit_uuid"}

    # Deposit is authoritative in Pocket. VIP and Copy do not yet have a
    # corresponding access entity in Elizabeth, so they start at a truthful 0.
    desired_values = {
        "tg_dep_ok": 1 if truthy_db(user_row.get("pocket_deposited")) == 1 else 0,
        "tg_vip": 0,
        "tg_copy": 0,
    }
    synced_visit_uuid = normalize_aio_visit_uuid(
        user_row.get("aio_status_fields_visit_uuid")
    )
    visit_changed = synced_visit_uuid != aio_visit_uuid
    fields_to_send = {
        field_name: desired_value
        for field_name, desired_value in desired_values.items()
        if visit_changed
        or user_row.get(AIO_PROFILE_STATUS_FIELD_COLUMNS[field_name]) is None
        or truthy_db(user_row.get(AIO_PROFILE_STATUS_FIELD_COLUMNS[field_name])) != desired_value
    }
    if not fields_to_send:
        return {"status": "skipped", "reason": "up_to_date"}

    try:
        request_url = build_aio_fields_trigger_url(aio_visit_uuid, fields_to_send)
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc)}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(request_url)
        if response.status_code >= 400:
            return {
                "status": "failed",
                "response_status": response.status_code,
                "response_body": response.text[:4000],
            }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)[:4000]}

    assignments = ["aio_status_fields_visit_uuid = %s"]
    update_values: List[object] = [aio_visit_uuid]
    for field_name, field_value in fields_to_send.items():
        assignments.append(f"{AIO_PROFILE_STATUS_FIELD_COLUMNS[field_name]} = %s")
        update_values.append(field_value)
    update_values.extend((int(user_id), aio_visit_uuid))
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                UPDATE users
                SET {', '.join(assignments)}
                WHERE user_id = %s AND aio_visit_uuid = %s
                """,
                tuple(update_values),
            )
            updated = cur.rowcount > 0
    if not updated:
        return {"status": "skipped", "reason": "aio_visit_uuid_changed"}
    return {
        "status": "sent",
        "response_status": response.status_code,
        "fields": fields_to_send,
    }


async def aio_profile_status_backfill_worker() -> None:
    """Initialize unsent AIO status flags for profiles created before this feature."""
    await asyncio.sleep(3)
    if not db_pool:
        return
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE NULLIF(TRIM(aio_visit_uuid), '') IS NOT NULL
                      AND (
                          COALESCE(aio_status_fields_visit_uuid, '') <> LOWER(TRIM(aio_visit_uuid))
                          OR aio_dep_ok_synced_value IS NULL
                          OR aio_vip_synced_value IS NULL
                          OR aio_copy_synced_value IS NULL
                          OR aio_dep_ok_synced_value <> CASE WHEN COALESCE(pocket_deposited, 0) = 1 THEN 1 ELSE 0 END
                          OR aio_vip_synced_value <> 0
                          OR aio_copy_synced_value <> 0
                      )
                    ORDER BY user_id ASC
                    LIMIT 5000
                    """
                )
                user_ids = [int(row["user_id"]) for row in (await cur.fetchall() or [])]
        for offset in range(0, len(user_ids), 10):
            batch = user_ids[offset : offset + 10]
            results = await asyncio.gather(
                *(sync_aio_profile_status_fields(user_id) for user_id in batch),
                return_exceptions=True,
            )
            for user_id, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"[AIO] Status-field backfill failed for user {user_id}: {result}")
                elif result.get("status") == "failed":
                    print(f"[AIO] Status-field backfill was rejected for user {user_id}: {result}")
            await asyncio.sleep(0.1)
    except Exception as exc:
        print(f"[AIO] Status-field backfill worker failed: {exc}")


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
                await cur.execute(
                    """
                    SELECT id, status, request_url
                    FROM aio_postback_events
                    WHERE aio_visit_uuid = %s AND event_slug = %s AND unique_key = %s
                    LIMIT 1
                    """,
                    (aio_visit_uuid, aio_event_slug, normalized_unique_key),
                )
                existing_event = await cur.fetchone() or {}
                if existing_event.get("status") != "failed":
                    return {"status": "skipped", "reason": "duplicate", "event_id": existing_event.get("id")}
                event_id = int(existing_event["id"])
                request_url = existing_event.get("request_url") or request_url
                await cur.execute(
                    "UPDATE aio_postback_events SET status = 'pending', error = NULL WHERE id = %s",
                    (event_id,),
                )
            else:
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


async def process_pocket_postback(request: Request, forced_event: Optional[str] = None):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database is unavailable")

    expected_secret = get_pocket_postback_secret()
    if not expected_secret:
        raise HTTPException(status_code=503, detail="Pocket postback secret is not configured")

    payload = await read_postback_payload(request)
    if forced_event:
        payload["event"] = forced_event
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
    sub_id3 = normalized.get("sub_id3") or ""
    aio_visit_uuid_from_postback = normalize_aio_visit_uuid(sub_id2) or ""
    chatterfy_lead_id_from_postback = normalize_chatterfy_lead_id(sub_id3)
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

    if chatterfy_lead_id_from_postback:
        async with db_pool.acquire() as identity_conn:
            async with identity_conn.cursor(aiomysql.DictCursor) as identity_cur:
                await identity_cur.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE user_id <> %s
                      AND (chatterfy_lead_id = %s OR pocket_sub_id3 = %s)
                    LIMIT 1
                    """,
                    (
                        int(telegram_id),
                        chatterfy_lead_id_from_postback,
                        chatterfy_lead_id_from_postback,
                    ),
                )
                conflicting_user = await identity_cur.fetchone()
        if conflicting_user:
            log_id = await insert_pocket_postback_log(
                normalized,
                payload,
                "skipped",
                "chatterfy_lead_conflict",
                telegram_id,
                source_ip,
            )
            return {
                "status": "skipped",
                "reason": "chatterfy_lead_conflict",
                "log_id": log_id,
            }

    if event_slug == POCKET_DEPOSIT_EVENT and not normalized.get("provider_event_id"):
        minute_bucket = datetime.utcnow().strftime("%Y%m%d%H%M")
        normalized["unique_key"] = f"{normalized.get('unique_key')}:{minute_bucket}"[:191]

    safe_payload = {
        key: ("***" if str(key).lower() in {"secret", "token", "signature"} else value)
        for key, value in payload.items()
    }
    async with db_pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT user_id, aio_visit_uuid, chatterfy_lead_id
                    FROM users
                    WHERE user_id = %s
                    LIMIT 1 FOR UPDATE
                    """,
                    (telegram_id,),
                )
                user_row = await cur.fetchone()
                if not user_row:
                    await cur.execute(
                        """
                        INSERT INTO users (
                            user_id, aio_visit_uuid, chatterfy_lead_id, lang, mode
                        )
                        VALUES (%s, NULLIF(%s, ''), NULLIF(%s, ''), 'ru', 'forex')
                        ON DUPLICATE KEY UPDATE user_id = VALUES(user_id)
                        """,
                        (
                            int(telegram_id),
                            aio_visit_uuid_from_postback,
                            chatterfy_lead_id_from_postback,
                        ),
                    )
                    user_row = {
                        "user_id": int(telegram_id),
                        "aio_visit_uuid": aio_visit_uuid_from_postback,
                        "chatterfy_lead_id": chatterfy_lead_id_from_postback,
                    }
                await cur.executemany(
                    """
                    INSERT IGNORE INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                    VALUES (%s, %s, 0, NULL)
                    """,
                    [(int(telegram_id), "forex"), (int(telegram_id), "binary")],
                )

                if event_slug == POCKET_DEPOSIT_EVENT and not normalized.get("provider_event_id"):
                    await cur.execute(
                        """
                        SELECT id, status
                        FROM pocket_postback_events
                        WHERE event_slug = %s AND payload_fingerprint = %s
                          AND created_at >= NOW() - INTERVAL 2 MINUTE
                        ORDER BY id DESC LIMIT 1
                        """,
                        (event_slug, normalized.get("payload_fingerprint")),
                    )
                    recent_duplicate = await cur.fetchone()
                    if recent_duplicate:
                        await conn.rollback()
                        return {
                            "status": "duplicate", "reason": "recent_exact_duplicate",
                            "log_id": recent_duplicate.get("id"),
                        }

                await cur.execute(
                    """
                    INSERT IGNORE INTO pocket_postback_events (
                        event_slug, unique_key, user_id, click_id, trader_id, deposit_amount,
                        country, site_id, cid, sub_id1, sub_id2, sub_id3, provider_event_id, payload_fingerprint,
                        raw_payload, status, source_ip
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'received', %s)
                    """,
                    (
                        event_slug, normalized.get("unique_key"), telegram_id, click_id or None,
                        trader_id or None, f"{deposit_amount:.2f}", normalized.get("country") or None,
                        site_id or None, cid or None,
                        sub_id1 or None, sub_id2 or None, sub_id3 or None,
                        normalized.get("provider_event_id") or None,
                        normalized.get("payload_fingerprint") or None,
                        json.dumps(safe_payload, ensure_ascii=False, default=str), source_ip,
                    ),
                )
                if cur.rowcount == 0:
                    await cur.execute(
                        "SELECT id, status FROM pocket_postback_events WHERE unique_key = %s LIMIT 1",
                        (normalized.get("unique_key"),),
                    )
                    duplicate_row = await cur.fetchone() or {}
                    await conn.rollback()
                    return {"status": "duplicate", "reason": "already_processed", "log_id": duplicate_row.get("id")}
                log_id = int(cur.lastrowid)

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
                            pocket_sub_id3 = CASE WHEN %s <> '' THEN %s ELSE pocket_sub_id3 END,
                            aio_visit_uuid = CASE WHEN %s <> '' THEN %s ELSE aio_visit_uuid END,
                            chatterfy_lead_id = CASE WHEN %s <> '' THEN %s ELSE chatterfy_lead_id END,
                            country = CASE WHEN %s <> '' THEN %s ELSE country END,
                            pocket_registered = 1,
                            pocket_registered_at = COALESCE(pocket_registered_at, DATE_FORMAT(NOW(), '%%Y-%%m-%%dT%%H:%%i:%%sZ')),
                            pocket_checked_at = NOW()
                        WHERE user_id = %s
                        """,
                        (trader_id, trader_id, click_id, click_id, site_id, site_id, cid, cid,
                         sub_id1, sub_id1, sub_id2, sub_id2, sub_id3, sub_id3,
                         aio_visit_uuid_from_postback, aio_visit_uuid_from_postback,
                         chatterfy_lead_id_from_postback, chatterfy_lead_id_from_postback,
                         normalized.get("country") or "", normalized.get("country") or "", telegram_id),
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
                            pocket_sub_id3 = CASE WHEN %s <> '' THEN %s ELSE pocket_sub_id3 END,
                            aio_visit_uuid = CASE WHEN %s <> '' THEN %s ELSE aio_visit_uuid END,
                            chatterfy_lead_id = CASE WHEN %s <> '' THEN %s ELSE chatterfy_lead_id END,
                            country = CASE WHEN %s <> '' THEN %s ELSE country END,
                            pocket_registered = 1,
                            pocket_registered_at = COALESCE(pocket_registered_at, DATE_FORMAT(NOW(), '%%Y-%%m-%%dT%%H:%%i:%%sZ')),
                            pocket_deposited = 1,
                            pocket_deposit_amount = COALESCE(pocket_deposit_amount, 0) + %s,
                            pocket_checked_at = NOW()
                        WHERE user_id = %s
                        """,
                        (trader_id, trader_id, click_id, click_id, site_id, site_id, cid, cid,
                         sub_id1, sub_id1, sub_id2, sub_id2, sub_id3, sub_id3,
                         aio_visit_uuid_from_postback, aio_visit_uuid_from_postback,
                         chatterfy_lead_id_from_postback, chatterfy_lead_id_from_postback,
                         normalized.get("country") or "", normalized.get("country") or "",
                         f"{deposit_amount:.2f}", telegram_id),
                    )
                await cur.execute(
                    """
                    SELECT COALESCE(pocket_deposit_amount, 0) AS pocket_deposit_amount,
                           aio_visit_uuid, chatterfy_lead_id
                    FROM users
                    WHERE user_id = %s
                    """,
                    (telegram_id,),
                )
                updated_user_row = await cur.fetchone() or {}
                status = "registered" if event_slug == POCKET_REGISTRATION_EVENT else "deposited"
                await cur.execute("UPDATE pocket_postback_events SET status = %s WHERE id = %s", (status, log_id))
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    aio_geo_result = await apply_pending_aio_geo_for_user(int(telegram_id))
    signal_access_status = await get_signal_access_status(int(telegram_id), "forex")
    access_granted = truthy_db(signal_access_status.get("access")) == 1
    total_deposit_amount = normalize_deposit_amount((updated_user_row or {}).get("pocket_deposit_amount"))
    aio_result = await send_pocket_aio_delivery(
        user_id=int(telegram_id),
        event_slug=event_slug,
        unique_key=normalized.get("unique_key") or event_slug,
        trader_id=trader_id,
        deposit_amount=f"{deposit_amount:.2f}",
        total_deposit_amount=f"{total_deposit_amount:.2f}",
    )
    aio_status_fields_result = await sync_aio_profile_status_fields(int(telegram_id))
    chatterfy_start_result = await send_pending_chatterfy_start_events(int(telegram_id))
    try:
        aichatter_result = await sync_aichatter_pocket_event(
            user_id=int(telegram_id),
            event_slug=event_slug,
            unique_key=normalized.get("unique_key") or event_slug,
            trader_id=trader_id,
            click_id=click_id,
            deposit_amount=deposit_amount,
            metadata={
                "site_id": site_id, "cid": cid, "sub_id1": sub_id1,
                "sub_id2": sub_id2, "sub_id3": sub_id3,
                "ac": normalized.get("ac"), "country": normalized.get("country"),
                "promo": normalized.get("promo"), "device_type": normalized.get("device_type"),
            },
        )
    except Exception as exc:
        aichatter_result = {"status": "failed", "error": str(exc)[:1000]}
    await update_pocket_aichatter_delivery(log_id, aichatter_result)
    chatterfy_result = await send_chatterfy_pocket_postback(
        log_id=log_id,
        event_slug=event_slug,
        clickid=sub_id3,
        trader_id=trader_id,
        trader_aio_id=(updated_user_row or {}).get("aio_visit_uuid") or "",
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
        "sub_id3": sub_id3 or None,
        "access_granted": access_granted,
        "access_policy": signal_access_status.get("policy"),
        "aio": aio_result,
        "aio_status_fields": aio_status_fields_result,
        "aio_geo": aio_geo_result,
        "chatterfy_start": chatterfy_start_result,
        "aichatter": aichatter_result,
        "chatterfy": chatterfy_result,
    }


@app.api_route("/api/integrations/pocket/postback", methods=["GET", "POST"])
async def pocket_postback(request: Request):
    return await process_pocket_postback(request)


@app.api_route("/postback/{bot_id}/{event_code}", methods=["GET", "POST"])
async def pocket_public_postback(bot_id: str, event_code: str, request: Request):
    if str(bot_id or "").strip().lower() != "elizabethvane":
        raise HTTPException(status_code=404, detail="Unknown affiliate bot")
    event_map = {"reg": "reg", "dep1": "dep1", "dep": "dep"}
    forced_event = event_map.get(str(event_code or "").strip().lower())
    if not forced_event:
        raise HTTPException(status_code=404, detail="Unknown Pocket event")
    return await process_pocket_postback(request, forced_event=forced_event)


def normalize_access_payload(value) -> int:
    return 1 if bool(value) else 0


async def fetch_admin_user_row(cur, user_id: int) -> Optional[Dict[str, Any]]:
    await cur.execute(
        """
        SELECT u.user_id, u.username,
               u.first_name AS telegram_first_name,
               COALESCE(NULLIF(TRIM(u.profile_name), ''), u.first_name) AS first_name,
               u.profile_name, u.avatar_url, u.mode, u.lang, u.strategy_id,
               u.trader_id AS pocket_trader_id,
               COALESCE(NULLIF(TRIM(u.profile_trader_id), ''), u.trader_id) AS trader_id,
               u.profile_trader_id,
               CASE WHEN NULLIF(TRIM(u.profile_trader_id), '') IS NULL THEN 0 ELSE 1 END AS trader_id_is_manual,
               COALESCE(u.profile_edit_allowed, 0) AS profile_edit_allowed,
               u.profile_updated_at,
               COALESCE(u.balance, 0) AS balance,
               COALESCE(u.pocket_registered, 0) AS pocket_registered,
               COALESCE(u.pocket_deposited, 0) AS pocket_deposited,
               COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
               u.balance_synced_at, u.balance_sync_error,
               COALESCE(fx.is_enabled, 0) AS forex_access,
               COALESCE(bin.is_enabled, 0) AS binary_access,
               COALESCE(u.is_blocked, 0) AS is_blocked, u.blocked_at, u.blocked_by, u.created_at,
               p.name AS strategy_name,
               CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
               a.granted_at
        FROM users u
        LEFT JOIN presets p ON p.id = u.strategy_id
        LEFT JOIN admin_users a ON a.user_id = u.user_id AND a.role = 'admin'
        LEFT JOIN user_mode_access fx ON fx.user_id = u.user_id AND fx.mode = 'forex'
        LEFT JOIN user_mode_access bin ON bin.user_id = u.user_id AND bin.mode = 'binary'
        WHERE u.user_id = %s
        LIMIT 1
        """,
        (user_id,),
    )
    return await cur.fetchone()


async def snapshot_main_user_data(user_id: int) -> Dict[str, list]:
    user_id = int(user_id)
    snapshot: Dict[str, list] = {}
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user_rows = list(await cur.fetchall() or [])
            if not user_rows:
                raise HTTPException(status_code=404, detail="User not found")
            snapshot["users"] = user_rows

            direct_queries = (
                ("user_onboarding", "SELECT * FROM user_onboarding WHERE user_id = %s"),
                (
                    "user_mode_access",
                    "SELECT * FROM user_mode_access WHERE user_id = %s ORDER BY mode ASC",
                ),
                (
                    "user_analyses",
                    "SELECT * FROM user_analyses WHERE user_id = %s ORDER BY id ASC",
                ),
                (
                    "user_presets",
                    "SELECT * FROM user_presets WHERE user_id = %s ORDER BY preset_id ASC",
                ),
                (
                    "ai_chats",
                    "SELECT * FROM ai_chats WHERE user_id = %s ORDER BY id ASC",
                ),
                (
                    "aio_postback_events",
                    "SELECT * FROM aio_postback_events WHERE user_id = %s ORDER BY id ASC",
                ),
                (
                    "aio_inbound_postbacks",
                    "SELECT * FROM aio_inbound_postbacks WHERE user_id = %s ORDER BY id ASC",
                ),
                (
                    "pocket_postback_events",
                    "SELECT * FROM pocket_postback_events WHERE user_id = %s ORDER BY id ASC",
                ),
                (
                    "preserved_staff_access",
                    "SELECT * FROM admin_users WHERE user_id = %s",
                ),
                (
                    "preserved_manager_audit",
                    """
                    SELECT *
                    FROM manager_stats_audit
                    WHERE target_user_id = %s OR requested_by = %s
                    ORDER BY id ASC
                    """,
                ),
            )
            for table_name, query in direct_queries:
                params = (user_id, user_id) if table_name == "preserved_manager_audit" else (user_id,)
                await cur.execute(query, params)
                snapshot[table_name] = list(await cur.fetchall() or [])

            await cur.execute(
                """
                SELECT m.*
                FROM ai_messages m
                JOIN ai_chats c ON c.id = m.chat_id
                WHERE c.user_id = %s
                ORDER BY m.id ASC
                """,
                (user_id,),
            )
            snapshot["ai_messages"] = list(await cur.fetchall() or [])

            preset_ids = [
                int(row.get("preset_id"))
                for row in snapshot["user_presets"]
                if row.get("preset_id") is not None
            ]
            if preset_ids:
                placeholders = ",".join(["%s"] * len(preset_ids))
                await cur.execute(
                    f"""
                    SELECT *
                    FROM presets
                    WHERE is_system = 0 AND id IN ({placeholders})
                    ORDER BY id ASC
                    """,
                    tuple(preset_ids),
                )
                custom_presets = list(await cur.fetchall() or [])
                snapshot["custom_presets"] = custom_presets
                custom_ids = [int(row["id"]) for row in custom_presets]
                if custom_ids:
                    custom_placeholders = ",".join(["%s"] * len(custom_ids))
                    await cur.execute(
                        f"""
                        SELECT *
                        FROM preset_indicators
                        WHERE preset_id IN ({custom_placeholders})
                        ORDER BY preset_id ASC, indicator_id ASC
                        """,
                        tuple(custom_ids),
                    )
                    snapshot["custom_preset_indicators"] = list(await cur.fetchall() or [])
                else:
                    snapshot["custom_preset_indicators"] = []
            else:
                snapshot["custom_presets"] = []
                snapshot["custom_preset_indicators"] = []
    return snapshot


async def clear_main_user_data(user_id: int, archive_id: int) -> Dict[str, int]:
    user_id = int(user_id)
    archive_id = int(archive_id)
    deleted: Dict[str, int] = {}
    async with db_pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT up.preset_id
                    FROM user_presets up
                    JOIN presets p ON p.id = up.preset_id
                    WHERE up.user_id = %s AND p.is_system = 0
                    """,
                    (user_id,),
                )
                custom_preset_ids = [
                    int(row["preset_id"])
                    for row in (await cur.fetchall() or [])
                ]
                await cur.execute(
                    "SELECT id FROM ai_chats WHERE user_id = %s",
                    (user_id,),
                )
                chat_ids = [int(row["id"]) for row in (await cur.fetchall() or [])]
                await cur.execute(
                    """
                    SELECT COLUMN_NAME
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                      AND COLUMN_NAME IN ('access', 'deposit')
                    """
                )
                legacy_columns = {
                    str(row["COLUMN_NAME"])
                    for row in (await cur.fetchall() or [])
                }

            async with conn.cursor() as cur:
                if chat_ids:
                    placeholders = ",".join(["%s"] * len(chat_ids))
                    await cur.execute(
                        f"DELETE FROM ai_messages WHERE chat_id IN ({placeholders})",
                        tuple(chat_ids),
                    )
                    deleted["ai_messages"] = max(0, int(cur.rowcount or 0))
                else:
                    deleted["ai_messages"] = 0

                direct_deletes = (
                    ("ai_chats", "DELETE FROM ai_chats WHERE user_id = %s"),
                    ("user_analyses", "DELETE FROM user_analyses WHERE user_id = %s"),
                    ("user_onboarding", "DELETE FROM user_onboarding WHERE user_id = %s"),
                    ("user_mode_access", "DELETE FROM user_mode_access WHERE user_id = %s"),
                    ("aio_postback_events", "DELETE FROM aio_postback_events WHERE user_id = %s"),
                    ("aio_inbound_postbacks", "DELETE FROM aio_inbound_postbacks WHERE user_id = %s"),
                    ("pocket_postback_events", "DELETE FROM pocket_postback_events WHERE user_id = %s"),
                    ("user_presets", "DELETE FROM user_presets WHERE user_id = %s"),
                )
                for table_name, query in direct_deletes:
                    await cur.execute(query, (user_id,))
                    deleted[table_name] = max(0, int(cur.rowcount or 0))

                if custom_preset_ids:
                    placeholders = ",".join(["%s"] * len(custom_preset_ids))
                    await cur.execute(
                        f"DELETE FROM preset_indicators WHERE preset_id IN ({placeholders})",
                        tuple(custom_preset_ids),
                    )
                    deleted["custom_preset_indicators"] = max(0, int(cur.rowcount or 0))
                    await cur.execute(
                        f"DELETE FROM presets WHERE is_system = 0 AND id IN ({placeholders})",
                        tuple(custom_preset_ids),
                    )
                    deleted["custom_presets"] = max(0, int(cur.rowcount or 0))
                else:
                    deleted["custom_preset_indicators"] = 0
                    deleted["custom_presets"] = 0

                reset_parts = [
                    "aio_visit_uuid = NULL",
                    "aio_country_code = NULL",
                    "aio_status_fields_visit_uuid = NULL",
                    "aio_dep_ok_synced_value = NULL",
                    "aio_vip_synced_value = NULL",
                    "aio_copy_synced_value = NULL",
                    "chatterfy_lead_id = NULL",
                    "chatterfy_bot_lead_id = NULL",
                    "chatterfy_tracker_click_id = NULL",
                    "trader_id = NULL",
                    "profile_name = NULL",
                    "profile_trader_id = NULL",
                    "profile_updated_at = NULL",
                    "pocket_click_id = NULL",
                    "pocket_site_id = NULL",
                    "pocket_cid = NULL",
                    "pocket_sub_id1 = NULL",
                    "pocket_sub_id2 = NULL",
                    "pocket_sub_id3 = NULL",
                    "pocket_registered = 0",
                    "pocket_deposited = 0",
                    "pocket_registered_at = NULL",
                    "pocket_deposit_amount = 0",
                    "country = NULL",
                    "pocket_checked_at = NULL",
                    "balance = 0",
                    "balance_sync_enabled = 0",
                    "balance_synced_at = NULL",
                    "balance_sync_error = NULL",
                    "mode = 'forex'",
                    "strategy_id = NULL",
                    "is_blocked = 0",
                    "blocked_by = NULL",
                    "blocked_at = NULL",
                ]
                if "access" in legacy_columns:
                    reset_parts.append("access = 0")
                if "deposit" in legacy_columns:
                    reset_parts.append("deposit = 0")
                await cur.execute(
                    f"UPDATE users SET {', '.join(reset_parts)} WHERE user_id = %s",
                    (user_id,),
                )

                await cur.execute(
                    """
                    UPDATE user_data_archives
                    SET archive_status = 'complete',
                        error = NULL,
                        completed_at = NOW()
                    WHERE id = %s AND user_id = %s
                    """,
                    (archive_id, user_id),
                )
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
    return deleted


async def mark_user_archive_failed(archive_id: int, user_id: int, error: str) -> None:
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE user_data_archives
                SET archive_status = 'partial',
                    error = %s,
                    completed_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (str(error or "Unknown error")[:4000], int(archive_id), int(user_id)),
            )


@app.get("/api/support/links")
async def get_support_links():
    links = await get_support_links_row()
    channel_url = links["channel_url"]
    support_url = links["support_url"]
    return {
        "channel_url": channel_url,
        "support_url": support_url,
        "channel_id": links["channel_id"],
        "check_subscription_enabled": links["check_subscription_enabled"],
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
            "display_name": admin.get("display_name") or "",
            "role": admin.get("role") or "manager",
            "is_protected": bool(admin.get("is_protected")),
            "permissions": admin.get("permissions") or {},
        },
    }


@app.get("/api/admin/stats")
async def admin_stats(
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    admin=Depends(require_permission(PERM_DASHBOARD_VIEW)),
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
            admins_total = await safe_count(cur, "SELECT COUNT(*) AS cnt FROM admin_users WHERE is_active = 1 AND role = 'admin'")
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


def serialize_studio_stat_day(row: Dict[str, Any]) -> Dict[str, Any]:
    stat_date = row.get("stat_date") or row.get("date")
    return {
        "date": stat_date.isoformat() if hasattr(stat_date, "isoformat") else str(stat_date or ""),
        "new_users": int(row.get("new_users") or 0),
        "total_users": (
            int(row["total_users"])
            if row.get("total_users") not in (None, "")
            else None
        ),
        "deals": int(row.get("deals") or 0),
        "volume": f"{Decimal(str(row.get('volume') or 0)):.2f}",
        "strategy_winrates": decode_strategy_winrates(row.get("strategy_winrates")),
        "updated_by": row.get("updated_by"),
        "updated_at": (
            row["updated_at"].isoformat()
            if hasattr(row.get("updated_at"), "isoformat")
            else str(row.get("updated_at") or "")
        ),
    }


async def get_studio_strategy_options(cur) -> List[Dict[str, Any]]:
    await cur.execute(
        """
        SELECT id, name, icon, is_system
        FROM presets
        ORDER BY is_system DESC, id ASC
        """
    )
    return deduplicate_strategy_options(await cur.fetchall() or [])


@app.get("/api/admin/studio-statistics")
async def admin_studio_statistics(
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    admin=Depends(require_permission(PERM_STATS_VIEW)),
):
    try:
        range_start, range_end = normalize_date_range(date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT stat_date, new_users, total_users, deals, volume,
                       strategy_winrates, updated_by, updated_at
                FROM admin_studio_daily_stats
                WHERE stat_date BETWEEN %s AND %s
                ORDER BY stat_date ASC
                """,
                (range_start.isoformat(), range_end.isoformat()),
            )
            rows = await cur.fetchall() or []

            await cur.execute(
                """
                SELECT total_users
                FROM admin_studio_daily_stats
                WHERE stat_date <= %s
                  AND total_users IS NOT NULL
                ORDER BY stat_date DESC
                LIMIT 1
                """,
                (range_end.isoformat(),),
            )
            total_row = await cur.fetchone() or {}
            cumulative_total_users = total_row.get("total_users")
            if cumulative_total_users is None:
                await cur.execute(
                    """
                    SELECT COALESCE(SUM(new_users), 0) AS total_users
                    FROM admin_studio_daily_stats
                    WHERE stat_date <= %s
                    """,
                    (range_end.isoformat(),),
                )
                cumulative_total_users = int((await cur.fetchone() or {}).get("total_users") or 0)

            strategies = await get_studio_strategy_options(cur)

    summary = aggregate_studio_statistics(
        rows,
        cumulative_total_users=int(cumulative_total_users or 0),
    )
    return {
        "status": "success",
        "period": {
            "from": range_start.isoformat(),
            "to": range_end.isoformat(),
        },
        "summary": summary,
        "days": [serialize_studio_stat_day(row) for row in rows],
        "strategies": strategies,
    }


@app.get("/api/admin/studio-statistics/day/{stat_date}")
async def admin_studio_statistics_day(
    stat_date: str,
    admin=Depends(require_permission(PERM_STATS_MANAGE)),
):
    try:
        normalized_date = parse_iso_date(stat_date, "date")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT stat_date, new_users, total_users, deals, volume,
                       strategy_winrates, updated_by, updated_at
                FROM admin_studio_daily_stats
                WHERE stat_date = %s
                LIMIT 1
                """,
                (normalized_date.isoformat(),),
            )
            row = await cur.fetchone()
            strategies = await get_studio_strategy_options(cur)
    return {
        "status": "success",
        "day": serialize_studio_stat_day(row) if row else None,
        "strategies": strategies,
    }


@app.post("/api/admin/studio-statistics/day")
async def admin_studio_statistics_save_day(
    request: Request,
    admin=Depends(require_permission(PERM_STATS_MANAGE)),
):
    try:
        normalized = normalize_daily_stat(await request.json())
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                INSERT INTO admin_studio_daily_stats (
                    stat_date, new_users, total_users, deals, volume,
                    strategy_winrates, updated_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    new_users = VALUES(new_users),
                    total_users = VALUES(total_users),
                    deals = VALUES(deals),
                    volume = VALUES(volume),
                    strategy_winrates = VALUES(strategy_winrates),
                    updated_by = VALUES(updated_by)
                """,
                (
                    normalized["date"].isoformat(),
                    normalized["new_users"],
                    normalized["total_users"],
                    normalized["deals"],
                    str(normalized["volume"]),
                    json.dumps(normalized["strategy_winrates"], ensure_ascii=False),
                    int(admin["user_id"]),
                ),
            )
            await cur.execute(
                """
                SELECT stat_date, new_users, total_users, deals, volume,
                       strategy_winrates, updated_by, updated_at
                FROM admin_studio_daily_stats
                WHERE stat_date = %s
                LIMIT 1
                """,
                (normalized["date"].isoformat(),),
            )
            row = await cur.fetchone()
    return {"status": "success", "day": serialize_studio_stat_day(row or {})}


@app.delete("/api/admin/studio-statistics/day/{stat_date}")
async def admin_studio_statistics_delete_day(
    stat_date: str,
    admin=Depends(require_permission(PERM_STATS_MANAGE)),
):
    try:
        normalized_date = parse_iso_date(stat_date, "date")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM admin_studio_daily_stats WHERE stat_date = %s",
                (normalized_date.isoformat(),),
            )
            deleted = cur.rowcount > 0
    return {
        "status": "success",
        "date": normalized_date.isoformat(),
        "deleted": deleted,
    }


@app.get("/api/admin/users/{target_user_id}/archives")
async def admin_user_data_archives(
    target_user_id: int,
    admin=Depends(require_permission(PERM_USERS_ARCHIVE_CLEAR)),
):
    target_user_id = int(target_user_id or 0)
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT a.id, a.user_id, a.archived_by, a.archive_status,
                       a.summary, a.error, a.archived_at, a.completed_at,
                       COALESCE(NULLIF(TRIM(actor.profile_name), ''),
                                NULLIF(TRIM(actor.first_name), ''),
                                NULLIF(TRIM(actor.username), ''),
                                CAST(a.archived_by AS CHAR)) AS archived_by_name
                FROM user_data_archives a
                LEFT JOIN users actor ON actor.user_id = a.archived_by
                WHERE a.user_id = %s
                ORDER BY a.archived_at DESC, a.id DESC
                """,
                (target_user_id,),
            )
            rows = list(await cur.fetchall() or [])
    for row in rows:
        row["summary"] = deserialize_archive_payload(row.get("summary"))
    return {
        "status": "success",
        "archives": rows,
        "confirmation_phrase": clear_cache_confirmation(target_user_id),
    }


@app.get("/api/admin/users/{target_user_id}/archives/{archive_id}")
async def admin_user_data_archive_detail(
    target_user_id: int,
    archive_id: int,
    admin=Depends(require_permission(PERM_USERS_ARCHIVE_CLEAR)),
):
    target_user_id = int(target_user_id or 0)
    archive_id = int(archive_id or 0)
    if not target_user_id or not archive_id:
        raise HTTPException(status_code=400, detail="User and archive ids are required")
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT id, user_id, archived_by, archive_status, summary,
                       snapshot, error, archived_at, completed_at
                FROM user_data_archives
                WHERE id = %s AND user_id = %s
                LIMIT 1
                """,
                (archive_id, target_user_id),
            )
            row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Archive not found")
    row["summary"] = deserialize_archive_payload(row.get("summary"))
    row["snapshot"] = deserialize_archive_payload(row.get("snapshot"))
    return {"status": "success", "archive": row}


@app.post("/api/admin/users/{target_user_id}/clear-cache")
async def admin_clear_user_cache(
    target_user_id: int,
    request: Request,
    admin=Depends(require_permission(PERM_USERS_ARCHIVE_CLEAR)),
):
    target_user_id = int(target_user_id or 0)
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")
    payload = await request.json()
    if not validate_clear_cache_confirmation(
        target_user_id,
        payload.get("confirmation"),
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Type {clear_cache_confirmation(target_user_id)} to confirm",
        )

    main_snapshot = await snapshot_main_user_data(target_user_id)
    aichatter_snapshot = await snapshot_aichatter_user_data(target_user_id)
    user_row = (main_snapshot.get("users") or [{}])[0]
    display_name = (
        str(user_row.get("profile_name") or "").strip()
        or str(user_row.get("first_name") or "").strip()
        or str(user_row.get("username") or "").strip()
        or f"User {target_user_id}"
    )
    trader_id = (
        str(user_row.get("profile_trader_id") or "").strip()
        or str(user_row.get("trader_id") or "").strip()
    )
    snapshot = {
        "version": ARCHIVE_VERSION,
        "identity": {
            "user_id": target_user_id,
            "display_name": display_name,
            "username": str(user_row.get("username") or ""),
            "trader_id": trader_id,
            "telegram_name": str(user_row.get("first_name") or ""),
            "profile_name": str(user_row.get("profile_name") or ""),
            "profile_trader_id": str(user_row.get("profile_trader_id") or ""),
            "pocket_trader_id": str(user_row.get("trader_id") or ""),
            "balance": user_row.get("balance"),
            "deposit_amount": user_row.get("pocket_deposit_amount"),
            "country": str(user_row.get("country") or ""),
            "pocket_registered": bool(user_row.get("pocket_registered")),
            "pocket_deposited": bool(user_row.get("pocket_deposited")),
        },
        "created_at": datetime.utcnow().isoformat() + "Z",
        "main_app": main_snapshot,
        "ai_chatter": aichatter_snapshot,
        "preserved": {
            "telegram_identity": True,
            "staff_access": True,
            "archive_history": True,
            "profile_edit_permission": True,
            "manager_audit": True,
        },
    }
    summary = build_archive_summary(snapshot)
    snapshot_json = serialize_archive_payload(snapshot)
    summary_json = serialize_archive_payload(summary)
    archive_id = 0

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_data_archives
                    (user_id, archived_by, archive_status, summary, snapshot)
                VALUES (%s, %s, 'pending', %s, %s)
                """,
                (
                    target_user_id,
                    int(admin["user_id"]),
                    summary_json,
                    snapshot_json,
                ),
            )
            archive_id = int(cur.lastrowid or 0)
    if not archive_id:
        raise HTTPException(status_code=500, detail="Could not create user archive")

    try:
        aichatter_deleted = await clear_aichatter_user_data(target_user_id)
        main_deleted = await clear_main_user_data(target_user_id, archive_id)
    except Exception as exc:
        await mark_user_archive_failed(archive_id, target_user_id, str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"Archive #{archive_id} was created, but cache clearing was incomplete",
        ) from exc

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            updated_user = await fetch_admin_user_row(cur, target_user_id)
    return {
        "status": "success",
        "archive_id": archive_id,
        "archive": {
            "id": archive_id,
            "user_id": target_user_id,
            "archive_status": "complete",
            "summary": summary,
        },
        "deleted": {
            "main_app": main_deleted,
            "ai_chatter": aichatter_deleted,
        },
        "user": updated_user,
    }


@app.get("/api/admin/users")
async def admin_users(
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    pocket_status: str = "all",
    admin=Depends(require_permission(PERM_USERS_VIEW)),
):
    limit = max(1, min(int(limit), 300))
    offset = max(0, int(offset))
    search = (search or "").strip()
    like = f"%{search}%"
    pocket_status = str(pocket_status or "all").strip().lower()
    pocket_filter_sql = {
        "all": "1 = 1",
        "not_registered": (
            "COALESCE(u.pocket_registered, 0) = 0 "
            "AND COALESCE(u.pocket_deposited, 0) = 0"
        ),
        "registered": (
            "COALESCE(u.pocket_registered, 0) = 1 "
            "AND COALESCE(u.pocket_deposited, 0) = 0"
        ),
        "deposited": "COALESCE(u.pocket_deposited, 0) = 1",
    }.get(pocket_status)
    if not pocket_filter_sql:
        raise HTTPException(status_code=400, detail="Unknown Pocket status filter")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await cur.execute(
                    f"""
                    SELECT u.user_id, u.username,
                           u.first_name AS telegram_first_name,
                           COALESCE(NULLIF(TRIM(u.profile_name), ''), u.first_name) AS first_name,
                           u.profile_name, u.avatar_url, u.mode, u.lang, u.strategy_id,
                           u.trader_id AS pocket_trader_id,
                           COALESCE(NULLIF(TRIM(u.profile_trader_id), ''), u.trader_id) AS trader_id,
                           u.profile_trader_id,
                           CASE WHEN NULLIF(TRIM(u.profile_trader_id), '') IS NULL THEN 0 ELSE 1 END AS trader_id_is_manual,
                           COALESCE(u.profile_edit_allowed, 0) AS profile_edit_allowed,
                           u.profile_updated_at,
                           COALESCE(u.balance, 0) AS balance,
                           COALESCE(u.pocket_registered, 0) AS pocket_registered,
                           COALESCE(u.pocket_deposited, 0) AS pocket_deposited,
                           COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
                           u.balance_synced_at, u.balance_sync_error,
                           COALESCE(fx.is_enabled, 0) AS forex_access,
                           COALESCE(bin.is_enabled, 0) AS binary_access,
                           COALESCE(u.is_blocked, 0) AS is_blocked, u.blocked_at, u.blocked_by, u.created_at,
                           p.name AS strategy_name,
                           CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
                           a.granted_at
                    FROM users u
                    LEFT JOIN presets p ON p.id = u.strategy_id
                    LEFT JOIN admin_users a ON a.user_id = u.user_id AND a.role = 'admin'
                    LEFT JOIN user_mode_access fx ON fx.user_id = u.user_id AND fx.mode = 'forex'
                    LEFT JOIN user_mode_access bin ON bin.user_id = u.user_id AND bin.mode = 'binary'
                    WHERE {pocket_filter_sql}
                      AND (
                        %s = ''
                        OR CAST(u.user_id AS CHAR) LIKE %s
                        OR COALESCE(u.username, '') LIKE %s
                        OR COALESCE(u.first_name, '') LIKE %s
                        OR COALESCE(u.profile_name, '') LIKE %s
                        OR COALESCE(u.trader_id, '') LIKE %s
                        OR COALESCE(u.profile_trader_id, '') LIKE %s
                    )
                    ORDER BY u.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (search, like, like, like, like, like, like, limit, offset),
                )
                users_rows = await cur.fetchall()
            except Exception:
                await cur.execute(
                    f"""
                    SELECT u.user_id, u.username, u.first_name AS telegram_first_name,
                           u.first_name, NULL AS profile_name, u.avatar_url, u.mode, u.lang, u.strategy_id,
                           NULL AS pocket_trader_id, NULL AS trader_id, NULL AS profile_trader_id,
                           0 AS trader_id_is_manual, 0 AS profile_edit_allowed, NULL AS profile_updated_at,
                           0 AS balance,
                           0 AS pocket_registered, 0 AS pocket_deposited,
                           0 AS balance_sync_enabled, NULL AS balance_synced_at, NULL AS balance_sync_error,
                           0 AS forex_access, 0 AS binary_access,
                           0 AS is_blocked, NULL AS blocked_at, NULL AS blocked_by, NULL AS created_at,
                           p.name AS strategy_name,
                           CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin,
                           a.granted_at
                    FROM users u
                    LEFT JOIN presets p ON p.id = u.strategy_id
                    LEFT JOIN admin_users a ON a.user_id = u.user_id AND a.role = 'admin'
                    WHERE {pocket_filter_sql}
                      AND (%s = '' OR CAST(u.user_id AS CHAR) LIKE %s OR COALESCE(u.username, '') LIKE %s OR COALESCE(u.first_name, '') LIKE %s)
                    ORDER BY u.user_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (search, like, like, like, limit, offset),
                )
                users_rows = await cur.fetchall()

            await cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM users u
                WHERE {pocket_filter_sql}
                  AND (
                    %s = ''
                    OR CAST(u.user_id AS CHAR) LIKE %s
                    OR COALESCE(u.username, '') LIKE %s
                    OR COALESCE(u.first_name, '') LIKE %s
                    OR COALESCE(u.profile_name, '') LIKE %s
                    OR COALESCE(u.trader_id, '') LIKE %s
                    OR COALESCE(u.profile_trader_id, '') LIKE %s
                )
                """,
                (search, like, like, like, like, like, like),
            )
            total = int((await cur.fetchone() or {}).get("cnt") or 0)

    return {
        "status": "success",
        "users": users_rows or [],
        "total": total,
        "limit": limit,
        "offset": offset,
        "pocket_status": pocket_status,
    }


@app.get("/api/admin/users/{target_user_id}/profile")
@app.get("/api/admin/users/{target_user_id}/pocket")
async def admin_user_profile_details(
    target_user_id: int,
    admin=Depends(require_permission(PERM_USERS_VIEW)),
):
    target_user_id = int(target_user_id or 0)
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, trader_id, pocket_click_id, pocket_site_id, pocket_cid,
                       pocket_sub_id1, pocket_sub_id2, pocket_sub_id3,
                       COALESCE(pocket_registered, 0) AS pocket_registered,
                       COALESCE(pocket_deposited, 0) AS pocket_deposited,
                       pocket_registered_at,
                       COALESCE(pocket_deposit_amount, 0) AS pocket_deposit_amount,
                       country, pocket_checked_at, aio_visit_uuid, aio_country_code, chatterfy_lead_id,
                       chatterfy_tracker_click_id
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (target_user_id,),
            )
            pocket_row = await cur.fetchone()
            if not pocket_row:
                raise HTTPException(status_code=404, detail="User not found")

            user_row = await fetch_admin_user_row(cur, target_user_id)

            await cur.execute(
                """
                SELECT quiz_name, quiz_age, quiz_experience, quiz_broker_experience,
                       quiz_capital, current_step, quiz_completed_at,
                       channel_subscribed_at, channel_gate_completed_at,
                       created_at, updated_at
                FROM user_onboarding
                WHERE user_id = %s
                LIMIT 1
                """,
                (target_user_id,),
            )
            onboarding = await cur.fetchone()

            await cur.execute(
                """
                SELECT COUNT(*) AS analyses_total,
                       COALESCE(SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END), 0) AS analyses_active,
                       COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS deals_won,
                       COALESCE(SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END), 0) AS deals_lost,
                       COALESCE(SUM(CASE WHEN status IN ('success', 'fail')
                                         AND COALESCE(closed_at, updated_at, created_at) >= NOW() - INTERVAL 7 DAY
                                        THEN 1 ELSE 0 END), 0) AS deals_7d,
                       COALESCE(SUM(CASE WHEN status = 'success'
                                         AND COALESCE(closed_at, updated_at, created_at) >= NOW() - INTERVAL 7 DAY
                                        THEN 1 ELSE 0 END), 0) AS wins_7d,
                       MAX(created_at) AS last_analysis_at
                FROM user_analyses
                WHERE user_id = %s
                """,
                (target_user_id,),
            )
            analysis_summary = await cur.fetchone() or {}

            await cur.execute(
                """
                SELECT ua.id, ua.pair, ua.timeframe, ua.analysis_type, ua.market_kind,
                       ua.status, ua.created_at, ua.closed_at,
                       COALESCE(p.name, CAST(ua.strategy_id AS CHAR)) AS strategy_name
                FROM user_analyses ua
                LEFT JOIN presets p ON p.id = ua.strategy_id
                WHERE ua.user_id = %s
                ORDER BY ua.created_at DESC, ua.id DESC
                LIMIT 8
                """,
                (target_user_id,),
            )
            recent_analyses = list(await cur.fetchall() or [])

            await cur.execute(
                """
                SELECT COUNT(DISTINCT c.id) AS chats_count,
                       COUNT(m.id) AS messages_count,
                       MAX(m.created_at) AS last_ai_message_at
                FROM ai_chats c
                LEFT JOIN ai_messages m ON m.chat_id = c.id
                WHERE c.user_id = %s
                """,
                (target_user_id,),
            )
            ai_app_summary = await cur.fetchone() or {}

            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM user_presets WHERE user_id = %s",
                (target_user_id,),
            )
            strategies_count = int((await cur.fetchone() or {}).get("cnt") or 0)

            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM user_data_archives WHERE user_id = %s",
                (target_user_id,),
            )
            archives_count = int((await cur.fetchone() or {}).get("cnt") or 0)

            await cur.execute(
                """
                SELECT id, event_slug, status, reason, trader_id, deposit_amount,
                       country, site_id, cid, sub_id1, sub_id2, sub_id3,
                       chatterfy_status, chatterfy_response_status, chatterfy_error,
                       aichatter_status, aichatter_error, created_at
                FROM pocket_postback_events
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 50
                """,
                (target_user_id,),
            )
            postbacks = list(await cur.fetchall() or [])

            aio_visit_uuid = normalize_aio_visit_uuid(pocket_row.get("aio_visit_uuid")) or ""
            await cur.execute(
                """
                SELECT id, aio_visit_uuid, conversion_type_uuid, country_code,
                       status, received_at, applied_at, updated_at
                FROM aio_inbound_postbacks
                WHERE user_id = %s
                   OR (%s <> '' AND aio_visit_uuid = %s)
                ORDER BY received_at DESC, id DESC
                LIMIT 50
                """,
                (target_user_id, aio_visit_uuid, aio_visit_uuid),
            )
            aio_inbound_postbacks = list(await cur.fetchall() or [])

            await cur.execute(
                """
                SELECT id, aio_visit_uuid, event_slug, unique_key, revenue, currency,
                       status, response_status, error, sent_at, created_at
                FROM aio_postback_events
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT 50
                """,
                (target_user_id,),
            )
            aio_outbound_events = list(await cur.fetchall() or [])

    deals_won = int(analysis_summary.get("deals_won") or 0)
    deals_lost = int(analysis_summary.get("deals_lost") or 0)
    completed_deals = deals_won + deals_lost
    wins_7d = int(analysis_summary.get("wins_7d") or 0)
    deals_7d = int(analysis_summary.get("deals_7d") or 0)
    activity = {
        **analysis_summary,
        **ai_app_summary,
        "completed_deals": completed_deals,
        "winrate": round((deals_won / completed_deals) * 100, 1) if completed_deals else None,
        "winrate_7d": round((wins_7d / deals_7d) * 100, 1) if deals_7d else None,
        "strategies_count": strategies_count,
        "archives_count": archives_count,
        "recent_analyses": recent_analyses,
    }

    try:
        ai_chatter = await get_aichatter_user_summary(target_user_id)
    except HTTPException as exc:
        ai_chatter = {
            "available": False,
            "exists": False,
            "error": str(exc.detail or "AI Chatter is unavailable"),
        }
    except Exception:
        ai_chatter = {
            "available": False,
            "exists": False,
            "error": "AI Chatter is unavailable",
        }

    return {
        "status": "success",
        "user": user_row,
        "onboarding": onboarding,
        "activity": activity,
        "ai_chatter": ai_chatter,
        "pocket": pocket_row,
        "postbacks": postbacks,
        "aio_inbound_postbacks": aio_inbound_postbacks,
        "aio_outbound_events": aio_outbound_events,
    }


@app.post("/api/admin/users/block")
async def admin_block_user(request: Request, admin=Depends(require_permission(PERM_USERS_BLOCK))):
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
            await cur.execute(
                "SELECT user_id FROM admin_users WHERE user_id = %s LIMIT 1",
                (target_user_id,),
            )
            if await cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="Сначала удалите доступ сотрудника в разделе «Менеджеры»",
                )
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
async def admin_update_user_access(request: Request, admin=Depends(require_permission(PERM_USERS_ACCESS))):
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
            await cur.execute(
                "SELECT is_protected FROM admin_users WHERE user_id = %s LIMIT 1",
                (target_user_id,),
            )
            staff_row = await cur.fetchone()
            if staff_row and bool(int(staff_row.get("is_protected") or 0)):
                raise HTTPException(status_code=403, detail="Права системного администратора защищены")

            await cur.executemany(
                """
                INSERT INTO user_mode_access (user_id, mode, is_enabled, override_mode, updated_by)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    is_enabled = VALUES(is_enabled),
                    override_mode = VALUES(override_mode),
                    updated_by = VALUES(updated_by)
                """,
                [
                    (target_user_id, "forex", forex_access, "allow" if forex_access else "deny", updated_by),
                    (target_user_id, "binary", binary_access, "allow" if binary_access else "deny", updated_by),
                ],
            )

            current_mode = str(user_row.get("mode") or "forex").lower()
            if current_mode == "forex" and forex_access != 1 and binary_access == 1:
                await cur.execute("UPDATE users SET mode = 'binary' WHERE user_id = %s", (target_user_id,))
            elif current_mode == "binary" and binary_access != 1 and forex_access == 1:
                await cur.execute("UPDATE users SET mode = 'forex' WHERE user_id = %s", (target_user_id,))

            row = await fetch_admin_user_row(cur, target_user_id)
    return {"status": "success", "user": row}


@app.post("/api/admin/users/profile-edit")
async def admin_update_user_profile_edit_permission(
    request: Request,
    admin=Depends(require_permission(PERM_USERS_PROFILE_EDIT)),
):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")

    profile_edit_allowed = 1 if bool(data.get("profile_edit_allowed")) else 0
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                UPDATE users
                SET profile_edit_allowed = %s
                WHERE user_id = %s
                """,
                (profile_edit_allowed, target_user_id),
            )
            if cur.rowcount == 0:
                await cur.execute(
                    "SELECT user_id FROM users WHERE user_id = %s LIMIT 1",
                    (target_user_id,),
                )
                if not await cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found")
            row = await fetch_admin_user_row(cur, target_user_id)
    return {"status": "success", "user": row}


@app.post("/api/admin/users/balance")
async def admin_update_user_balance(request: Request, admin=Depends(require_permission(PERM_USERS_BALANCE))):
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
            await cur.execute(
                """
                SELECT user_id, trader_id, profile_trader_id
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (target_user_id,),
            )
            user_row = await cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")
            if sync_enabled == 1 and str(user_row.get("profile_trader_id") or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="Manual Trader ID is not eligible for Pocket balance sync",
                )
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
async def admin_delete_user(
    target_user_id: int,
    admin=Depends(require_permission(PERM_USERS_DELETE)),
):
    target_user_id = int(target_user_id or 0)
    if not target_user_id:
        raise HTTPException(status_code=400, detail="User id is required")
    if target_user_id == int(admin.get("user_id") or 0):
        raise HTTPException(status_code=400, detail="You cannot delete yourself")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT user_id FROM admin_users WHERE user_id = %s LIMIT 1",
                (target_user_id,),
            )
            if await cur.fetchone():
                raise HTTPException(
                    status_code=409,
                    detail="Сначала удалите доступ сотрудника в разделе «Менеджеры»",
                )
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


async def get_active_admin_count(cur) -> int:
    await cur.execute(
        "SELECT COUNT(*) AS cnt FROM admin_users WHERE is_active = 1 AND role = %s",
        (STAFF_ROLE_ADMIN,),
    )
    return int((await cur.fetchone() or {}).get("cnt") or 0)


@app.get("/api/admin/staff")
async def admin_staff(admin=Depends(require_permission(PERM_STAFF_VIEW))):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT a.user_id, a.role, a.is_active, a.display_name,
                       a.permissions_json, a.is_protected, a.granted_at, a.granted_by,
                       u.username, u.first_name, u.avatar_url
                FROM admin_users a
                LEFT JOIN users u ON u.user_id = a.user_id
                ORDER BY a.is_active DESC, FIELD(a.role, 'admin', 'manager'), a.granted_at DESC
                """
            )
            rows = await cur.fetchall() or []
    staff_rows = []
    for row in rows:
        item = dict(row)
        item["is_protected"] = bool(int(item.get("is_protected") or 0))
        item["permissions"] = normalize_staff_permissions(
            item.pop("permissions_json", None),
            item.get("role"),
            protected=item["is_protected"],
        )
        staff_rows.append(item)
    return {
        "status": "success",
        "staff": staff_rows,
        "permission_templates": {
            "manager": role_default_permissions("manager"),
            "admin": role_default_permissions("admin"),
        },
    }


@app.get("/api/admin/staff/audit")
async def admin_staff_audit(
    limit: int = Query(default=15, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str = Query(default=""),
    search: str = Query(default=""),
    admin=Depends(require_permission(PERM_STAFF_VIEW)),
):
    normalized_status = str(status or "").strip().lower()
    if normalized_status and normalized_status not in MANAGER_STATS_AUDIT_STATUSES:
        raise HTTPException(status_code=400, detail="Некорректный статус журнала")

    normalized_search = str(search or "").strip()[:100]
    where_parts = []
    params: List[Any] = []
    if normalized_status:
        where_parts.append("audit.result_status = %s")
        params.append(normalized_status)
    if normalized_search:
        like_value = f"%{normalized_search}%"
        where_parts.append(
            """
            (
                CAST(audit.requested_by AS CHAR) LIKE %s
                OR CAST(COALESCE(audit.target_user_id, 0) AS CHAR) LIKE %s
                OR audit.command_name LIKE %s
                OR audit.target_query LIKE %s
                OR COALESCE(requester.username, '') LIKE %s
                OR COALESCE(requester.first_name, '') LIKE %s
                OR COALESCE(target_user.username, '') LIKE %s
                OR COALESCE(target_user.first_name, '') LIKE %s
            )
            """
        )
        params.extend([like_value] * 8)
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                f"""
                SELECT COUNT(*) AS cnt
                FROM manager_stats_audit audit
                LEFT JOIN users requester ON requester.user_id = audit.requested_by
                LEFT JOIN users target_user ON target_user.user_id = audit.target_user_id
                {where_sql}
                """,
                tuple(params),
            )
            total = int((await cur.fetchone() or {}).get("cnt") or 0)
            await cur.execute(
                f"""
                SELECT
                    audit.id,
                    audit.command_name,
                    audit.requested_by,
                    audit.target_query,
                    audit.target_user_id,
                    audit.result_status,
                    audit.created_at,
                    requester.username AS requester_username,
                    requester.first_name AS requester_first_name,
                    requester_staff.role AS requester_role,
                    target_user.username AS target_username,
                    target_user.first_name AS target_first_name
                FROM manager_stats_audit audit
                LEFT JOIN users requester ON requester.user_id = audit.requested_by
                LEFT JOIN admin_users requester_staff ON requester_staff.user_id = audit.requested_by
                LEFT JOIN users target_user ON target_user.user_id = audit.target_user_id
                {where_sql}
                ORDER BY audit.created_at DESC, audit.id DESC
                LIMIT %s OFFSET %s
                """,
                tuple([*params, int(limit), int(offset)]),
            )
            rows = await cur.fetchall()

    return {
        "status": "success",
        "audit": rows or [],
        "total": total,
        "limit": int(limit),
        "offset": int(offset),
    }


@app.post("/api/admin/staff")
async def admin_staff_add(
    request: Request,
    admin=Depends(require_permission(PERM_STAFF_ADD)),
):
    data = await request.json()
    try:
        target_user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        target_user_id = 0
    if target_user_id <= 0:
        raise HTTPException(status_code=400, detail="Укажите корректный Telegram ID")
    if target_user_id == int(admin.get("user_id") or 0):
        raise HTTPException(status_code=400, detail="Нельзя изменять собственный доступ")
    role = str(data.get("role") or "").strip().lower()
    if role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Некорректная роль сотрудника")
    if role == STAFF_ROLE_ADMIN and not bool(admin.get("is_protected")):
        raise HTTPException(status_code=403, detail="Только системный администратор может назначать администраторов")
    display_name = re.sub(r"\s+", " ", str(data.get("display_name") or "").strip())[:100]
    requested_permissions = normalize_staff_permissions(
        data.get("permissions"),
        role,
        use_role_defaults_when_empty="permissions" not in data,
    )
    if not permissions_are_subset(requested_permissions, admin):
        raise HTTPException(status_code=403, detail="Нельзя выдать право, которого нет у вас")
    permissions_json = json.dumps(requested_permissions, ensure_ascii=False, sort_keys=True)

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT role, is_protected FROM admin_users WHERE user_id = %s LIMIT 1",
                (target_user_id,),
            )
            existing = await cur.fetchone()
            if existing and bool(int(existing.get("is_protected") or 0)):
                raise HTTPException(status_code=403, detail="Права системного администратора защищены")
            if (
                existing
                and str(existing.get("role") or "") == STAFF_ROLE_ADMIN
                and not bool(admin.get("is_protected"))
            ):
                raise HTTPException(status_code=403, detail="Только системный администратор может управлять администраторами")
            await cur.execute(
                """
                INSERT INTO admin_users
                    (user_id, role, is_active, display_name, permissions_json, is_protected, granted_by)
                VALUES (%s, %s, 1, %s, %s, 0, %s)
                ON DUPLICATE KEY UPDATE
                    role = VALUES(role),
                    is_active = 1,
                    display_name = VALUES(display_name),
                    permissions_json = VALUES(permissions_json),
                    granted_by = VALUES(granted_by),
                    granted_at = CURRENT_TIMESTAMP
                """,
                (
                    target_user_id,
                    role,
                    display_name or None,
                    permissions_json,
                    int(admin["user_id"]),
                ),
            )
    return {
        "status": "success",
        "user_id": target_user_id,
        "role": role,
        "is_active": 1,
        "display_name": display_name,
        "permissions": requested_permissions,
    }


@app.patch("/api/admin/staff/{target_user_id}")
async def admin_staff_update(
    target_user_id: int,
    request: Request,
    admin=Depends(require_permission(PERM_STAFF_MANAGE)),
):
    target_user_id = int(target_user_id or 0)
    data = await request.json()
    current_admin_id = int(admin["user_id"])
    if target_user_id <= 0:
        raise HTTPException(status_code=400, detail="Укажите корректный Telegram ID")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, role, is_active, display_name,
                       permissions_json, is_protected
                FROM admin_users
                WHERE user_id = %s
                LIMIT 1
                """,
                (target_user_id,),
            )
            existing = await cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
            existing_protected = bool(int(existing.get("is_protected") or 0))
            if target_user_id == current_admin_id:
                raise HTTPException(status_code=400, detail="Нельзя изменять права собственной учётной записи")
            if existing_protected:
                raise HTTPException(status_code=403, detail="Права системного администратора защищены")
            if (
                str(existing.get("role") or "") == STAFF_ROLE_ADMIN
                and not bool(admin.get("is_protected"))
            ):
                raise HTTPException(status_code=403, detail="Только системный администратор может управлять администраторами")

            role = (
                str(data.get("role") or "").strip().lower()
                if "role" in data
                else normalize_staff_role(existing.get("role"))
            )
            if role not in STAFF_ROLES:
                raise HTTPException(status_code=400, detail="Некорректная роль сотрудника")
            if role == STAFF_ROLE_ADMIN and not bool(admin.get("is_protected")):
                raise HTTPException(status_code=403, detail="Только системный администратор может назначать администраторов")
            if "is_active" in data:
                raw_active = data.get("is_active")
                if isinstance(raw_active, str):
                    is_active = 1 if raw_active.strip().lower() in {"1", "true", "yes", "on"} else 0
                else:
                    is_active = 1 if bool(raw_active) else 0
            else:
                is_active = int(existing.get("is_active") or 0)
            removes_admin_access = (
                str(existing.get("role") or "") == STAFF_ROLE_ADMIN
                and int(existing.get("is_active") or 0) == 1
                and (role != STAFF_ROLE_ADMIN or is_active != 1)
            )
            if removes_admin_access and await get_active_admin_count(cur) <= 1:
                raise HTTPException(status_code=400, detail="Нельзя удалить или понизить последнего администратора")

            if "permissions" in data:
                requested_permissions = normalize_staff_permissions(
                    data.get("permissions"),
                    role,
                    use_role_defaults_when_empty=False,
                )
            elif role != str(existing.get("role") or ""):
                requested_permissions = role_default_permissions(role)
            else:
                requested_permissions = normalize_staff_permissions(
                    existing.get("permissions_json"),
                    role,
                )
            if not permissions_are_subset(requested_permissions, admin):
                raise HTTPException(status_code=403, detail="Нельзя выдать право, которого нет у вас")
            display_name = (
                re.sub(r"\s+", " ", str(data.get("display_name") or "").strip())[:100]
                if "display_name" in data
                else str(existing.get("display_name") or "").strip()
            )

            await cur.execute(
                """
                UPDATE admin_users
                SET role = %s,
                    is_active = %s,
                    display_name = %s,
                    permissions_json = %s,
                    granted_by = %s
                WHERE user_id = %s
                """,
                (
                    role,
                    is_active,
                    display_name or None,
                    json.dumps(requested_permissions, ensure_ascii=False, sort_keys=True),
                    current_admin_id,
                    target_user_id,
                ),
            )
    return {
        "status": "success",
        "user_id": target_user_id,
        "role": role,
        "is_active": is_active,
        "display_name": display_name,
        "permissions": requested_permissions,
    }


@app.delete("/api/admin/staff/{target_user_id}")
async def admin_staff_delete(
    target_user_id: int,
    admin=Depends(require_permission(PERM_STAFF_MANAGE)),
):
    target_user_id = int(target_user_id or 0)
    current_admin_id = int(admin["user_id"])
    if target_user_id == current_admin_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить собственную учётную запись")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT user_id, role, is_active, is_protected FROM admin_users WHERE user_id = %s LIMIT 1",
                (target_user_id,),
            )
            existing = await cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Сотрудник не найден")
            if bool(int(existing.get("is_protected") or 0)):
                raise HTTPException(status_code=403, detail="Системного администратора нельзя удалить")
            if (
                str(existing.get("role") or "") == STAFF_ROLE_ADMIN
                and not bool(admin.get("is_protected"))
            ):
                raise HTTPException(status_code=403, detail="Только системный администратор может удалять администраторов")
            if (
                str(existing.get("role") or "") == STAFF_ROLE_ADMIN
                and int(existing.get("is_active") or 0) == 1
                and await get_active_admin_count(cur) <= 1
            ):
                raise HTTPException(status_code=400, detail="Нельзя удалить последнего администратора")
            await cur.execute("DELETE FROM admin_users WHERE user_id = %s", (target_user_id,))
    return {"status": "success", "user_id": target_user_id}


@app.get("/api/admin/admins")
async def admin_admins(admin=Depends(require_permission(PERM_STAFF_VIEW))):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT a.user_id, a.is_active, a.granted_at, a.granted_by,
                       u.username, u.first_name
                FROM admin_users a
                LEFT JOIN users u ON u.user_id = a.user_id
                WHERE a.is_active = 1 AND a.role = 'admin'
                ORDER BY a.granted_at DESC
                """
            )
            rows = await cur.fetchall()
    return {"status": "success", "admins": rows or []}


@app.post("/api/admin/admins/grant")
async def admin_grant(
    request: Request,
    admin=Depends(require_permission(PERM_STAFF_MANAGE)),
):
    if not bool(admin.get("is_protected")):
        raise HTTPException(status_code=403, detail="Только системный администратор может назначать администраторов")
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
            await cur.execute(
                "SELECT is_protected FROM admin_users WHERE user_id = %s LIMIT 1",
                (target_user_id,),
            )
            existing_staff = await cur.fetchone()
            if existing_staff and bool(int(existing_staff.get("is_protected") or 0)):
                raise HTTPException(status_code=403, detail="Права системного администратора защищены")

        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO admin_users (user_id, role, is_active, permissions_json, granted_by)
                VALUES (%s, 'admin', 1, %s, %s)
                ON DUPLICATE KEY UPDATE
                    role = 'admin',
                    is_active = 1,
                    permissions_json = VALUES(permissions_json),
                    granted_by = VALUES(granted_by),
                    granted_at = CURRENT_TIMESTAMP
                """,
                (
                    target_user_id,
                    json.dumps(role_default_permissions("admin"), ensure_ascii=False, sort_keys=True),
                    granted_by,
                ),
            )
    return {"status": "success", "user_id": target_user_id}


@app.post("/api/admin/admins/revoke")
async def admin_revoke(
    request: Request,
    admin=Depends(require_permission(PERM_STAFF_MANAGE)),
):
    if not bool(admin.get("is_protected")):
        raise HTTPException(status_code=403, detail="Только системный администратор может отзывать права администратора")
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
                SELECT user_id, is_protected
                FROM admin_users
                WHERE user_id = %s AND is_active = 1 AND role = 'admin'
                LIMIT 1
                """,
                (target_user_id,),
            )
            existing_admin = await cur.fetchone()
            if not existing_admin:
                raise HTTPException(status_code=404, detail="Admin not found")
            if bool(int(existing_admin.get("is_protected") or 0)):
                raise HTTPException(status_code=403, detail="Права системного администратора защищены")

            await cur.execute("SELECT COUNT(*) AS cnt FROM admin_users WHERE is_active = 1 AND role = 'admin'")
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
async def admin_broadcast(
    request: Request,
    admin=Depends(require_permission(PERM_BROADCAST_MANAGE)),
):
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Broadcast text is required")

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE EXISTS (
                    SELECT 1 FROM user_onboarding onboarding
                    WHERE onboarding.user_id = users.user_id
                )
                   OR EXISTS (
                    SELECT 1 FROM ai_chats chat
                    WHERE chat.user_id = users.user_id
                )
                ORDER BY user_id ASC
                """
            )
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
    admin=Depends(require_permission(PERM_SETTINGS_STREAMS)),
):
    return await get_market_options_payload(kind, min_payout)


@app.get("/api/admin/stream-assets")
async def admin_stream_assets(
    analysis_type: str = Query(default="forex"),
    market: str = Query(default="currencies"),
    min_payout: int = Query(default=DEVSBITE_MIN_PAYOUT, ge=0, le=100),
    admin=Depends(require_permission(PERM_SETTINGS_STREAMS)),
):
    return await get_stream_asset_options_payload(analysis_type, market, min_payout)


@app.get("/api/admin/settings")
async def admin_settings(
    admin=Depends(require_any_permission(*SETTINGS_PERMISSIONS)),
):
    settings: Dict[str, Any] = {}
    if has_permission(admin, PERM_SETTINGS_STREAMS):
        settings["streams"] = await get_stream_settings_row()
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
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
                settings["stream_strategies"] = await cur.fetchall() or []
    if has_permission(admin, PERM_SETTINGS_AI):
        shared_ai_settings = await get_admin_analysis_settings()
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, system_prompt, model, updated_at FROM ai_settings WHERE id = 1")
                ai_settings = await cur.fetchone()
        if not ai_settings:
            ai_settings = {
                "id": 1,
                "system_prompt": "You are a helpful trading assistant.",
                "model": "gpt-4o-mini",
                "updated_at": None,
            }
        ai_settings["openai_api_key"] = ""
        ai_settings["openai_key_configured"] = bool(shared_ai_settings.get("gpt_api_key"))
        settings["ai"] = ai_settings
    if has_permission(admin, PERM_SETTINGS_FUNNEL):
        settings["support"] = await get_support_links_row()
    if has_permission(admin, PERM_SETTINGS_API):
        settings["pocket_api"] = await get_pocket_api_settings_row()
    if has_permission(admin, PERM_SETTINGS_SYSTEM_ACCESS):
        settings["system_access"] = await get_system_access_settings_row()
    return {
        "status": "success",
        "settings": settings,
    }


@app.put("/api/admin/settings/quiz-intro-video")
async def admin_quiz_intro_video_upload(
    request: Request,
    admin=Depends(require_permission(PERM_SETTINGS_FUNNEL)),
):
    raw_content_length = (request.headers.get("content-length") or "").strip()
    if raw_content_length:
        try:
            if int(raw_content_length) > MAX_QUIZ_INTRO_VIDEO_SIZE:
                raise HTTPException(status_code=413, detail="MP4 file is larger than 50 MB")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header")

    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if content_type not in {"video/mp4", "application/mp4", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only MP4 video files are supported")

    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="MP4 file is empty")
    if len(payload) > MAX_QUIZ_INTRO_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="MP4 file is larger than 50 MB")
    if not is_valid_mp4_payload(payload):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid MP4 container")

    raw_original_name = unquote(
        str(request.headers.get("x-file-name") or "").strip()
    )
    original_name = os.path.basename(raw_original_name).strip()[:255]
    if not original_name.lower().endswith(".mp4"):
        original_name = f"quiz-intro-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.mp4"
    payload_sha256 = hashlib.sha256(payload).hexdigest()

    try:
        if os.path.isfile(START_VIDEO_NOTE_FALLBACK_PATH) and secrets.compare_digest(
            payload_sha256,
            get_file_sha256(START_VIDEO_NOTE_FALLBACK_PATH),
        ):
            await reset_quiz_intro_video_to_default()
            support_settings = await get_support_links_row()
            return {
                "status": "success",
                "deduplicated": True,
                "quiz_intro_video": support_settings.get("quiz_intro_video"),
                "quiz_intro_video_library": support_settings.get("quiz_intro_video_library", []),
            }

        storage_name = f"{payload_sha256}.mp4"
        target_path = get_quiz_intro_library_file_path(storage_name)
        if not os.path.isfile(target_path):
            save_quiz_intro_video_file(payload, target_path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not save MP4 file: {exc}")

    upload_deduplicated = False
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                INSERT INTO admin_quiz_intro_videos
                    (environment, storage_name, original_name, file_size, sha256, uploaded_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    original_name = VALUES(original_name),
                    file_size = VALUES(file_size)
                """,
                (
                    _runtime_environment,
                    storage_name,
                    original_name,
                    len(payload),
                    payload_sha256,
                    int(admin["user_id"]),
                ),
            )
            upload_deduplicated = not bool(cur.lastrowid)
            await cur.execute(
                """
                SELECT id
                FROM admin_quiz_intro_videos
                WHERE environment = %s AND sha256 = %s
                LIMIT 1
                """,
                (_runtime_environment, payload_sha256),
            )
            video_row = await cur.fetchone()
    if not video_row:
        raise HTTPException(status_code=500, detail="Could not add MP4 file to the library")

    await activate_quiz_intro_video(int(video_row["id"]), int(admin["user_id"]))
    support_settings = await get_support_links_row()
    return {
        "status": "success",
        "deduplicated": upload_deduplicated,
        "quiz_intro_video": support_settings.get("quiz_intro_video"),
        "quiz_intro_video_library": support_settings.get("quiz_intro_video_library", []),
    }


@app.post("/api/admin/settings/quiz-intro-video/reset")
async def admin_quiz_intro_video_reset(
    admin=Depends(require_permission(PERM_SETTINGS_FUNNEL)),
):
    await reset_quiz_intro_video_to_default()
    support_settings = await get_support_links_row()
    return {
        "status": "success",
        "quiz_intro_video": support_settings.get("quiz_intro_video"),
        "quiz_intro_video_library": support_settings.get("quiz_intro_video_library", []),
    }


@app.post("/api/admin/settings/quiz-intro-video/{video_id}/select")
async def admin_quiz_intro_video_select(
    video_id: int,
    admin=Depends(require_permission(PERM_SETTINGS_FUNNEL)),
):
    await activate_quiz_intro_video(video_id, int(admin["user_id"]))
    support_settings = await get_support_links_row()
    return {
        "status": "success",
        "quiz_intro_video": support_settings.get("quiz_intro_video"),
        "quiz_intro_video_library": support_settings.get("quiz_intro_video_library", []),
    }


@app.delete("/api/admin/settings/quiz-intro-video/{video_id}")
async def admin_quiz_intro_video_delete(
    video_id: int,
    admin=Depends(require_permission(PERM_SETTINGS_FUNNEL)),
):
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT id, storage_name, is_active
                FROM admin_quiz_intro_videos
                WHERE id = %s AND environment = %s
                LIMIT 1
                """,
                (int(video_id), _runtime_environment),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Saved MP4 file not found")
            if bool(row.get("is_active")):
                raise HTTPException(
                    status_code=409,
                    detail="Select another MP4 or restore the default before deleting this file",
                )
            try:
                file_path = get_quiz_intro_library_file_path(row.get("storage_name") or "")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except OSError as exc:
                raise HTTPException(status_code=500, detail=f"Could not delete MP4 file: {exc}")
            await cur.execute(
                """
                DELETE FROM admin_quiz_intro_videos
                WHERE id = %s AND environment = %s AND is_active = 0
                """,
                (int(video_id), _runtime_environment),
            )

    support_settings = await get_support_links_row()
    return {
        "status": "success",
        "quiz_intro_video": support_settings.get("quiz_intro_video"),
        "quiz_intro_video_library": support_settings.get("quiz_intro_video_library", []),
    }


@app.post("/api/admin/settings")
async def admin_settings_update(
    request: Request,
    admin=Depends(require_any_permission(*SETTINGS_PERMISSIONS)),
):
    data = await request.json()
    ai_data = data.get("ai") or {}
    streams_data = data.get("streams") or {}
    support_data = data.get("support") or {}
    pocket_data = data.get("pocket_api") or {}
    system_access_data = data.get("system_access") or {}
    section_permissions = {
        "ai": PERM_SETTINGS_AI,
        "streams": PERM_SETTINGS_STREAMS,
        "support": PERM_SETTINGS_FUNNEL,
        "pocket_api": PERM_SETTINGS_API,
        "system_access": PERM_SETTINGS_SYSTEM_ACCESS,
    }
    for section_key, permission in section_permissions.items():
        if section_key in data and not has_permission(admin, permission):
            raise HTTPException(status_code=403, detail="Недостаточно прав для изменения этого раздела")
    if not any(section_key in data for section_key in section_permissions):
        raise HTTPException(status_code=400, detail="Не указан раздел настроек")

    system_prompt = (ai_data.get("system_prompt") or "").strip()
    model = (ai_data.get("model") or "").strip()
    openai_api_key = (ai_data.get("openai_api_key") or "").strip()

    if "ai" in data:
        if not system_prompt:
            raise HTTPException(status_code=400, detail="system_prompt is required")
        if not model:
            raise HTTPException(status_code=400, detail="model is required")
        if openai_api_key:
            validation = await analysis_ai_service.validate_openai_api_key(openai_api_key, model=model)
            if not validation.get("ok"):
                raise HTTPException(status_code=400, detail=validation.get("error") or "OpenAI key is invalid")

    shared_sync: Dict[str, Any] = {}

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            if "ai" in data:
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
                if openai_api_key:
                    await cur.execute(
                        "UPDATE admin_analysis_settings SET gpt_api_key = %s, updated_by = %s WHERE id = 1",
                        (openai_api_key, int(admin["user_id"])),
                    )
                    shared_sync["openai_api_key"] = openai_api_key
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
                channel_id = normalize_channel_settings(
                    {"channel_id": support_data.get("channel_id")}
                )["channel_id"]
                channel_url = str(support_data.get("channel_url") or "").strip()[:1000]
                support_url = str(support_data.get("support_url") or "").strip()[:1000]
                check_subscription_enabled = 1 if bool(support_data.get("check_subscription_enabled")) else 0
                raw_quiz_intro_video_enabled = support_data.get("quiz_intro_video_enabled", True)
                quiz_intro_video_enabled = 0 if str(raw_quiz_intro_video_enabled).strip().lower() in {
                    "", "0", "false", "no", "off", "none"
                } else 1
                quiz_config = normalize_quiz_config(support_data.get("quiz_config"))
                quiz_config_json = json.dumps(quiz_config, ensure_ascii=False)
                try:
                    final_message_config = validate_final_message_config(
                        support_data.get("final_message_config")
                    )
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
                final_message_config_json = json.dumps(final_message_config, ensure_ascii=False)
                await cur.execute(
                    """
                    INSERT INTO admin_support_links (
                        id, channel_id, channel_url, support_url, check_subscription_enabled,
                        quiz_intro_video_enabled, quiz_config,
                        final_message_config, updated_by
                    )
                    VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        channel_id = VALUES(channel_id),
                        channel_url = VALUES(channel_url),
                        support_url = VALUES(support_url),
                        check_subscription_enabled = VALUES(check_subscription_enabled),
                        quiz_intro_video_enabled = VALUES(quiz_intro_video_enabled),
                        quiz_config = VALUES(quiz_config),
                        final_message_config = VALUES(final_message_config),
                        updated_by = VALUES(updated_by)
                    """,
                    (
                        channel_id,
                        channel_url,
                        support_url,
                        check_subscription_enabled,
                        quiz_intro_video_enabled,
                        quiz_config_json,
                        final_message_config_json,
                        int(admin["user_id"]),
                    ),
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
            if isinstance(system_access_data, dict) and system_access_data:
                await cur.execute(
                    """
                    SELECT registration_button_bot_enabled, registration_button_app_enabled
                    FROM admin_system_access_settings
                    WHERE id = 1
                    LIMIT 1
                    """
                )
                current_visibility = await cur.fetchone() or (1, 1)
                access_policy = normalize_access_policy(system_access_data.get("policy"))
                min_deposit = normalize_min_deposit(system_access_data.get("min_deposit_amount"))
                registration_url = str(system_access_data.get("registration_url") or "").strip()
                registration_button_bot_enabled = normalize_settings_toggle(
                    system_access_data.get("registration_button_bot_enabled", current_visibility[0]), 1
                )
                registration_button_app_enabled = normalize_settings_toggle(
                    system_access_data.get("registration_button_app_enabled", current_visibility[1]), 1
                )
                if registration_url:
                    parsed_registration_url = urlsplit(registration_url)
                    if parsed_registration_url.scheme not in {"http", "https"} or not parsed_registration_url.netloc:
                        raise HTTPException(status_code=400, detail="registration_url must be a full HTTP(S) URL")
                if access_policy != ACCESS_POLICY_REGISTRATION_DEPOSIT:
                    min_deposit = normalize_min_deposit(0)
                await cur.execute(
                    """
                    INSERT INTO admin_system_access_settings
                        (id, policy, min_deposit_amount, registration_url,
                         registration_button_bot_enabled, registration_button_app_enabled,
                         updated_by)
                    VALUES (1, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        policy = VALUES(policy),
                        min_deposit_amount = VALUES(min_deposit_amount),
                        registration_url = VALUES(registration_url),
                        registration_button_bot_enabled = VALUES(registration_button_bot_enabled),
                        registration_button_app_enabled = VALUES(registration_button_app_enabled),
                        updated_by = VALUES(updated_by)
                    """,
                    (
                        access_policy,
                        str(min_deposit),
                        registration_url or None,
                        registration_button_bot_enabled,
                        registration_button_app_enabled,
                        int(admin["user_id"]),
                    ),
                )
                shared_sync["registration_url"] = registration_url
                shared_sync["min_deposit"] = str(min_deposit)
    if shared_sync:
        try:
            await sync_shared_ai_access_settings(**shared_sync)
        except Exception as exc:
            print(f"Shared AI/access settings sync failed: {exc}")
            raise HTTPException(status_code=502, detail="Settings saved, but AI Chatter synchronization failed")
    return {"status": "success"}


@app.get("/api/admin/strategies")
async def admin_strategies(admin=Depends(require_permission(PERM_STRATEGIES_MANAGE))):
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
                           FROM user_presets up
                           WHERE up.preset_id = p.id
                       ) AS owner_users_count,
                       (
                           SELECT MIN(up.user_id)
                           FROM user_presets up
                           WHERE up.preset_id = p.id
                       ) AS owner_user_id,
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
        owner_users_count = int(row.get("owner_users_count") or 0)
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
        row["owner_users_count"] = owner_users_count
        row["can_toggle_system"] = 1 if owner_users_count > 0 else 0
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
async def admin_strategies_validate_gpt_key(
    request: Request,
    admin=Depends(require_permission(PERM_STRATEGIES_MANAGE)),
):
    data = await request.json()
    api_key = (data.get("api_key") or "").strip()
    model = (data.get("model") or analysis_ai_service.DEFAULT_ANALYSIS_GPT_MODEL).strip()
    result = await analysis_ai_service.validate_openai_api_key(api_key, model=model)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "OpenAI key is invalid")
    return {"status": "success", "warning": result.get("warning")}


@app.post("/api/admin/analysis-settings")
async def admin_analysis_settings_update(
    request: Request,
    admin=Depends(require_permission(PERM_STRATEGIES_MANAGE)),
):
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
async def admin_strategies_update(
    request: Request,
    admin=Depends(require_permission(PERM_STRATEGIES_MANAGE)),
):
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

    saved_indicator_count = None
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    p.is_system,
                    (
                        SELECT COUNT(*)
                        FROM user_presets up
                        WHERE up.preset_id = p.id
                    ) AS owner_users_count
                FROM presets p
                WHERE p.id = %s
                LIMIT 1
                """,
                (strategy_id,),
            )
            current_row = await cur.fetchone()
            if not current_row:
                raise HTTPException(status_code=404, detail="Strategy not found")

            current_is_system = int(current_row[0] or 0)
            owner_users_count = int(current_row[1] or 0)
            if current_is_system != is_system and owner_users_count <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Built-in system strategy cannot be converted to a user strategy",
                )

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

            if current_is_system == 1 and is_system == 0:
                await cur.execute(
                    """
                    UPDATE users
                    SET strategy_id = 1
                    WHERE strategy_id = %s
                      AND user_id NOT IN (
                          SELECT up.user_id
                          FROM user_presets up
                          WHERE up.preset_id = %s
                      )
                    """,
                    (strategy_id, strategy_id),
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
                saved_indicator_count = len(valid_ids)
    return {"status": "success", "indicator_count": saved_indicator_count}


@app.post("/api/admin/strategies/delete")
async def admin_strategies_delete(
    request: Request,
    admin=Depends(require_permission(PERM_STRATEGIES_MANAGE)),
):
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
                SELECT u.user_id, u.lang, u.mode, u.username,
                       u.first_name AS telegram_first_name,
                       COALESCE(NULLIF(TRIM(u.profile_name), ''), u.first_name) AS first_name,
                       u.profile_name, u.avatar_url, u.strategy_id,
                       u.trader_id AS pocket_trader_id,
                       COALESCE(NULLIF(TRIM(u.profile_trader_id), ''), u.trader_id) AS trader_id,
                       u.profile_trader_id,
                       CASE WHEN NULLIF(TRIM(u.profile_trader_id), '') IS NULL THEN 0 ELSE 1 END AS trader_id_is_manual,
                       COALESCE(u.profile_edit_allowed, 0) AS profile_edit_allowed,
                       u.profile_updated_at,
                        COALESCE(u.balance, 0) AS balance,
                        COALESCE(u.pocket_registered, 0) AS pocket_registered,
                        COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
                       u.balance_synced_at,
                       COALESCE(fx.is_enabled, 0) AS forex_access,
                       COALESCE(bin.is_enabled, 0) AS binary_access,
                       COALESCE(u.is_blocked, 0) AS is_blocked, u.blocked_at,
                       p.name as strategy_name,
                       CASE WHEN a.user_id IS NULL THEN 0 ELSE a.is_active END AS is_admin
                FROM users u
                LEFT JOIN presets p ON u.strategy_id = p.id
                LEFT JOIN admin_users a ON a.user_id = u.user_id AND a.role = 'admin'
                LEFT JOIN user_mode_access fx ON fx.user_id = u.user_id AND fx.mode = 'forex'
                LEFT JOIN user_mode_access bin ON bin.user_id = u.user_id AND bin.mode = 'binary'
                WHERE u.user_id = %s
            """, (user_id,))
            user = await cur.fetchone()
    if user:
        forex_status = await get_signal_access_status(int(user_id), "forex")
        binary_status = await get_signal_access_status(int(user_id), "binary")
        access_settings = await get_system_access_settings_row()
        admin_center_access = await has_admin_center_access(int(user_id))
        user["forex_access"] = 1 if truthy_db(forex_status.get("access")) == 1 else 0
        user["binary_access"] = 1 if truthy_db(binary_status.get("access")) == 1 else 0
        user["access_policy"] = forex_status.get("policy")
        user["is_admin"] = 1 if admin_center_access else 0
        user["admin_url"] = build_admin_webapp_url() if admin_center_access else ""
        user["registration_link_app_enabled"] = normalize_settings_toggle(
            access_settings.get("registration_button_app_enabled"), 1
        )
    return user or {"error": "Not found"}


@app.post("/api/user/registration-link")
async def get_user_registration_link(user=Depends(get_telegram_user)):
    link_data = await get_personal_registration_link(int(user["user_id"]))
    if not link_data:
        raise HTTPException(status_code=404, detail="User not found")
    if link_data.get("registered"):
        raise HTTPException(status_code=409, detail="registration_already_completed")
    return {"status": "success", "url": link_data["url"]}


@app.patch("/api/user/profile")
async def update_user_profile(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    has_name = "name" in data
    has_trader_id = "trader_id" in data
    if not has_name and not has_trader_id:
        raise HTTPException(status_code=400, detail="Name or Trader ID is required")

    normalized_name = None
    normalized_trader_id = None
    try:
        if has_name:
            normalized_name = normalize_profile_name(data.get("name"))
        if has_trader_id:
            normalized_trader_id = normalize_profile_trader_id(data.get("trader_id"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    user_id = int(user["user_id"])
    update_parts = ["profile_updated_at = NOW()"]
    params: List[Any] = []
    if has_name:
        update_parts.append("profile_name = %s")
        params.append(normalized_name)
    if has_trader_id:
        update_parts.extend(
            [
                "profile_trader_id = %s",
                "balance_sync_enabled = 0",
                "balance_sync_error = NULL",
                "balance_synced_at = NULL",
            ]
        )
        params.append(normalized_trader_id)
    params.append(user_id)

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                f"""
                UPDATE users
                SET {", ".join(update_parts)}
                WHERE user_id = %s
                  AND profile_edit_allowed = 1
                """,
                tuple(params),
            )
            if cur.rowcount == 0:
                await cur.execute(
                    "SELECT profile_edit_allowed FROM users WHERE user_id = %s LIMIT 1",
                    (user_id,),
                )
                permission_row = await cur.fetchone()
                if not permission_row:
                    raise HTTPException(status_code=404, detail="User not found")
                if int(permission_row.get("profile_edit_allowed") or 0) != 1:
                    raise HTTPException(
                        status_code=403,
                        detail="Profile editing is not enabled for this account",
                    )

            await cur.execute(
                """
                SELECT u.user_id, u.username,
                       u.first_name AS telegram_first_name,
                       COALESCE(NULLIF(TRIM(u.profile_name), ''), u.first_name) AS first_name,
                       u.profile_name,
                       u.trader_id AS pocket_trader_id,
                       COALESCE(NULLIF(TRIM(u.profile_trader_id), ''), u.trader_id) AS trader_id,
                       u.profile_trader_id,
                       CASE WHEN NULLIF(TRIM(u.profile_trader_id), '') IS NULL THEN 0 ELSE 1 END AS trader_id_is_manual,
                       COALESCE(u.profile_edit_allowed, 0) AS profile_edit_allowed,
                       COALESCE(u.balance_sync_enabled, 0) AS balance_sync_enabled,
                       u.profile_updated_at
                FROM users u
                WHERE u.user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            updated_user = await cur.fetchone()
    return {"status": "success", "user": updated_user}


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

                await cur.execute(
                    """
                    SELECT p.id
                    FROM presets p
                    JOIN user_presets up ON up.preset_id = p.id
                    WHERE p.id = %s
                      AND up.user_id = %s
                      AND p.is_system = 0
                    LIMIT 1
                    """,
                    (preset_id, user_id),
                )
                if not await cur.fetchone():
                    raise HTTPException(status_code=404, detail="Editable user strategy not found")

                await cur.execute(
                    "UPDATE presets SET name = %s, icon = %s WHERE id = %s AND is_system = 0",
                    (name, icon, preset_id),
                )
                
                await cur.execute("DELETE FROM preset_indicators WHERE preset_id = %s", (preset_id,))
                for ind_id in indicators:
                    await cur.execute("INSERT INTO preset_indicators (preset_id, indicator_id) VALUES (%s, %s)", (preset_id, ind_id))
                return {"status": "success"}

            elif action == "delete":
                preset_id = data.get("preset_id")
                await cur.execute(
                    """
                    SELECT p.id
                    FROM presets p
                    JOIN user_presets up ON up.preset_id = p.id
                    WHERE p.id = %s
                      AND up.user_id = %s
                      AND p.is_system = 0
                    LIMIT 1
                    """,
                    (preset_id, user_id),
                )
                if not await cur.fetchone():
                    raise HTTPException(status_code=404, detail="Deletable user strategy not found")

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
                VALUES (%s, %s, 0, NULL)
                """,
                [(user_id, "forex"), (user_id, "binary")],
            )
    asyncio.create_task(sync_aio_profile_status_fields(int(user_id)))
    return {"status": "success"}
    
@app.post("/api/user/mode")
async def update_mode(request: Request, user=Depends(get_telegram_user)):
    data = await request.json()
    user_id = user["user_id"]
    new_mode = data.get("mode")
    
    if user_id and new_mode:
        normalized_mode = str(new_mode).lower()
        if normalized_mode in ("forex", "binary"):
            access_status = await get_signal_access_status(user_id, normalized_mode)
            if truthy_db(access_status.get("access")) != 1:
                raise HTTPException(status_code=403, detail=SIGNAL_ACCESS_REQUIRED_DETAIL)
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
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
    await require_signal_access(user_id, "binary")
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
    allowed_indicators = await resolve_effective_indicator_keys(strategy_id_int, data.get("allowed_indicators", []))
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
    analysis_data = align_analysis_indicators_to_strategy(analysis_data, allowed_indicators, fill_missing=True)
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
    await require_signal_access(user_id, "forex")
    pair = data.get("pair")
    interval_raw = data.get("exp")
    strategy_id = data.get("strategy_id")
    try:
        strategy_id_int = int(strategy_id) if strategy_id is not None and str(strategy_id).strip() else None
    except (TypeError, ValueError):
        strategy_id_int = None
    if strategy_id_int is None:
        strategy_id_int = await get_user_strategy_id(user_id)
    allowed_indicators = await resolve_effective_indicator_keys(strategy_id_int, data.get("allowed_indicators", []))
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
        analysis_data = align_analysis_indicators_to_strategy(analysis_data, allowed_indicators, fill_missing=True)
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
                analysis_data = align_analysis_indicators_to_strategy(analysis_data, allowed_indicators, fill_missing=True)
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
    
FUNNEL_CHECK_CHANNEL_CALLBACK = "funnel_check_channel"
FUNNEL_CONTINUE_CALLBACK = "funnel_continue"
FUNNEL_OPEN_MENU_CALLBACK = "funnel_open_menu"
QUIZ_ANSWER_CALLBACK_PREFIX = "quiz_answer"
QUALIFICATION_GPT_SYSTEM_PROMPT = """
You classify one Telegram qualification answer for Elizabeth Vane's trading project.
Return exactly one allowed option and nothing else.
If the user does not want to answer, asks to skip, says later, or asks for the channel link, return Skip.
Do not explain your reasoning.
""".strip()


async def build_main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard_rows = [
        [
            InlineKeyboardButton(
                text="Open Elizabeth Vane",
                web_app=WebAppInfo(url=os.getenv("WEB_APP_URL")),
            )
        ]
    ]
    try:
        registration_link = await get_personal_registration_link(user_id)
    except Exception as exc:
        registration_link = None
        print(f"[Bot] registration link button failed for user={user_id}: {exc}")
    if (
        registration_link
        and registration_link.get("show_in_bot")
        and not registration_link.get("registered")
    ):
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="Registration link",
                    url=str(registration_link["url"]),
                )
            ]
        )
    if await has_admin_center_access(user_id):
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text="Admin Center",
                    web_app=WebAppInfo(url=build_admin_webapp_url()),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


async def post_to_ai_chatter(payload: Dict[str, Any]) -> bool:
    if not BOT_AI_MANAGER_ENABLED or not AI_CHATTER_GATEWAY_SECRET:
        return False
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.post(
                AI_CHATTER_GATEWAY_URL,
                json=payload,
                headers={"X-AI-Chatter-Secret": AI_CHATTER_GATEWAY_SECRET},
            )
        response.raise_for_status()
        return True
    except Exception as exc:
        print(f"[AI Chatter gateway] forward failed: {exc}")
        return False


async def forward_message_to_ai_chatter(
    message: types.Message,
    *,
    text_override: Optional[str] = None,
    is_start: bool = False,
) -> bool:
    """Передаёт личное сообщение единому AI-движку без второго Telegram polling."""
    if (
        not message.from_user
        or str(message.chat.type) not in {"private", "ChatType.PRIVATE"}
    ):
        return False
    text = text_override if text_override is not None else (message.text or "")
    voice_file_id = message.voice.file_id if message.voice else ""
    if not text.strip() and not voice_file_id:
        return False
    return await post_to_ai_chatter({
        "user_id": int(message.from_user.id),
        "message_id": int(message.message_id),
        "first_name": message.from_user.first_name or "",
        "username": message.from_user.username or "",
        "text": text,
        "voice_file_id": voice_file_id,
        "is_start": bool(is_start),
    })


async def start_ai_chatter_from_callback(callback: types.CallbackQuery) -> bool:
    if not callback.from_user or not callback.message:
        return False
    return await post_to_ai_chatter({
        "user_id": int(callback.from_user.id),
        "message_id": int(callback.message.message_id),
        "first_name": callback.from_user.first_name or "",
        "username": callback.from_user.username or "",
        "text": "Hello",
        "voice_file_id": "",
        "is_start": True,
    })


async def send_main_menu(chat_id: int, user_id: int, user_name: str):
    global menu_photo_file_id
    welcome_text = (
        f"Welcome, {user_name}!\n\n"
        f"<b>Elizabeth Vane</b> | <code>Private Trading Analytics</code>\n\n"
        f"A professional analytical space for those who value precision. "
        f"We've combined advanced technical analysis methods with the convenience of a Web App.\n\n"
        f"<i>Your market edge begins here.</i>"
    )
    keyboard = await build_main_menu_keyboard(user_id)

    if menu_photo_file_id:
        await bot.send_photo(
            chat_id=chat_id,
            photo=menu_photo_file_id,
            caption=welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    photo_path = resolve_menu_photo_path()
    sent_message = await bot.send_photo(
        chat_id=chat_id,
        photo=FSInputFile(photo_path),
        caption=welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    if sent_message and sent_message.photo:
        menu_photo_file_id = sent_message.photo[-1].file_id
        try:
            with open(menu_file_id_path, "w", encoding="utf-8") as f:
                f.write(menu_photo_file_id)
        except Exception:
            pass


async def get_onboarding_row(user_id: int) -> Optional[Dict[str, Any]]:
    if not db_pool:
        return None
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT user_id, quiz_name, quiz_age, quiz_experience, quiz_broker_experience, quiz_capital, current_step,
                       quiz_completed_at, channel_subscribed_at, channel_gate_completed_at
                FROM user_onboarding
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id,),
            )
            return await cur.fetchone()


async def ensure_onboarding_row(user_id: int) -> Dict[str, Any]:
    if not db_pool:
        return {}
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT IGNORE INTO user_onboarding (user_id, current_step)
                VALUES (%s, 'experience')
                """,
                (user_id,),
            )
            await cur.execute(
                """
                UPDATE user_onboarding
                SET current_step = 'experience'
                WHERE user_id = %s
                  AND quiz_completed_at IS NULL
                  AND current_step NOT IN ('experience', 'broker_experience', 'capital')
                """,
                (user_id,),
            )
    return await get_onboarding_row(user_id) or {}


async def send_quiz_question(chat_id: int, step: str):
    normalized_step = normalize_quiz_step(step)
    quiz_config = await get_quiz_config_row()
    keyboard_rows = [
        [
            InlineKeyboardButton(
                text=option,
                callback_data=f"{QUIZ_ANSWER_CALLBACK_PREFIX}:{normalized_step}:{index}",
            )
        ]
        for index, option in enumerate(get_quiz_options(normalized_step, quiz_config))
    ]
    await bot.send_message(
        chat_id=chat_id,
        text=get_quiz_question(normalized_step, quiz_config),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


async def send_start_video_note(chat_id: int):
    try:
        settings = await get_support_links_row()
        if not bool(int(settings.get("quiz_intro_video_enabled") or 0)):
            return
        video_path, video_source = resolve_start_video_note_path()
        if not video_path:
            print("[Bot] quiz intro video note is enabled, but no MP4 file is available")
            return
        video_note_path = await prepare_square_video_note(video_path)
        if not video_note_path:
            print(f"[Bot] quiz intro video note conversion failed for {video_source} source")
            return
        sent = await bot.send_video_note(
            chat_id=chat_id,
            video_note=FSInputFile(video_note_path),
            length=512,
        )
        if not sent.video_note:
            raise RuntimeError("Telegram returned a message without video_note")
        print(f"[Bot] quiz intro video note sent from {video_source} source")
    except Exception as e:
        print(f"[Bot] quiz intro video note send failed: {e}")


async def send_quiz_welcome(chat_id: int):
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "Hi, this is Elizabeth Vane's assistant.\n\n"
            "To give you a more relevant starting point, I'll ask 3 quick questions.\n"
            "If you prefer not to answer, that's okay - I can just send you the channel link."
        ),
    )


def build_channel_click_signature(user_id: int) -> str:
    if not BOT_CHANNEL_CLICK_SECRET:
        return ""
    return hmac.new(
        BOT_CHANNEL_CLICK_SECRET.encode("utf-8"),
        str(int(user_id)).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def build_channel_click_url(user_id: int, channel_url: str) -> str:
    signature = build_channel_click_signature(user_id)
    if not BOT_PUBLIC_BASE_URL or not signature:
        return channel_url
    query = urlencode({"user_id": int(user_id), "sig": signature})
    return f"{BOT_PUBLIC_BASE_URL}/api/bot/channel/open?{query}"


async def process_channel_open_click(user_id: int):
    if not db_pool:
        return
    first_name = ""
    username = ""
    first_click = False
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT first_name, username FROM users WHERE user_id = %s LIMIT 1",
                (user_id,),
            )
            user = await cur.fetchone() or {}
            first_name = str(user.get("first_name") or "")
            username = str(user.get("username") or "")
            await cur.execute(
                """
                UPDATE user_onboarding
                SET channel_subscribed_at = NOW()
                WHERE user_id = %s AND channel_subscribed_at IS NULL
                """,
                (user_id,),
            )
            first_click = cur.rowcount > 0
    if not first_click:
        return

    await send_aio_postback_event(user_id, CHANNEL_SUBSCRIBE_EVENT)
    await post_to_ai_chatter({
        "user_id": user_id,
        "message_id": int(datetime.now().timestamp() * 1_000_000),
        "first_name": first_name,
        "username": username,
        "text": "Hello",
        "voice_file_id": "",
        "is_start": True,
    })


async def get_channel_join_request_url(settings: Dict[str, Any]) -> str:
    """Return a direct Telegram link that creates a join request.

    Telegram only permits an administrator with invite rights to create this
    type of link. Keep the configured URL as a safe fallback so the funnel does
    not become completely inaccessible while channel permissions are being set.
    """
    global channel_join_request_link
    if channel_join_request_link:
        return channel_join_request_link
    channel_id = settings.get("channel_id")
    if not channel_id:
        return settings["channel_url"]
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=channel_id,
            name="Elizabeth Vane bot funnel",
            creates_join_request=True,
        )
        channel_join_request_link = str(invite.invite_link or "").strip()
    except Exception as exc:
        print(f"[Bot] join-request invite link creation failed: {exc}")
    return channel_join_request_link or settings["channel_url"]


async def complete_channel_subscription(
    user_id: int,
    *,
    first_name: str = "",
    username: str = "",
) -> bool:
    """Mark the first confirmed subscription and start the media funnel once."""
    if not db_pool:
        return False
    first_confirmation = False
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE user_onboarding
                SET channel_subscribed_at = NOW(),
                    channel_gate_completed_at = COALESCE(channel_gate_completed_at, NOW())
                WHERE user_id = %s
                  AND quiz_completed_at IS NOT NULL
                  AND channel_subscribed_at IS NULL
                """,
                (user_id,),
            )
            first_confirmation = cur.rowcount > 0
            await cur.execute(
                """
                UPDATE user_onboarding
                SET channel_gate_completed_at = COALESCE(channel_gate_completed_at, NOW())
                WHERE user_id = %s
                  AND quiz_completed_at IS NOT NULL
                """,
                (user_id,),
            )
    if not first_confirmation:
        return False
    asyncio.create_task(
        deliver_channel_subscription_events(
            user_id,
            first_name=first_name,
            username=username,
        )
    )
    return True


async def deliver_channel_subscription_events(
    user_id: int,
    *,
    first_name: str = "",
    username: str = "",
) -> None:
    try:
        await send_aio_postback_event(user_id, CHANNEL_SUBSCRIBE_EVENT)
    except Exception as exc:
        print(f"[Bot] channel subscription AIO event failed for {user_id}: {exc}")
    try:
        await post_to_ai_chatter({
            "user_id": user_id,
            "message_id": int(datetime.now().timestamp() * 1_000_000),
            "first_name": first_name,
            "username": username,
            "text": "Hello",
            "voice_file_id": "",
            "is_start": True,
        })
    except Exception as exc:
        print(f"[Bot] channel subscription AI start failed for {user_id}: {exc}")


async def is_user_channel_member(user_id: int, channel_id: Any) -> bool:
    normalized_channel_id = normalize_channel_settings(
        {"channel_id": channel_id}
    )["channel_id"]
    if not normalized_channel_id:
        return False
    try:
        member = await bot.get_chat_member(
            chat_id=normalized_channel_id,
            user_id=int(user_id),
        )
    except Exception as exc:
        print(f"[Bot] channel membership check failed for {user_id}: {exc}")
        return False
    return is_active_channel_member(
        getattr(member, "status", ""),
        getattr(member, "is_member", None),
    )


@app.get("/api/bot/channel/open")
async def open_channel_from_bot(
    user_id: int,
    sig: str,
    background_tasks: BackgroundTasks,
):
    expected_signature = build_channel_click_signature(user_id)
    if not expected_signature or not hmac.compare_digest(sig, expected_signature):
        raise HTTPException(status_code=403, detail="Invalid channel link")
    settings = await get_support_links_row()
    background_tasks.add_task(process_channel_open_click, int(user_id))
    return RedirectResponse(settings["channel_url"], status_code=302)


async def send_channel_gate(chat_id: int):
    settings = await get_support_links_row()
    final_message_config = normalize_final_message_config(settings.get("final_message_config"))
    if settings["check_subscription_enabled"]:
        channel_button_url = build_channel_click_url(chat_id, settings["channel_url"])
    else:
        channel_button_url = await get_channel_join_request_url(settings)
    keyboard_rows = [
        [InlineKeyboardButton(text="Open channel", url=channel_button_url)],
        [
            InlineKeyboardButton(
                text=final_message_config["trigger_button_text"],
                callback_data=FUNNEL_CONTINUE_CALLBACK,
            )
        ],
    ]
    await bot.send_message(
        chat_id=chat_id,
        text=f"Here is the channel link:\n{settings['channel_url']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )


def build_funnel_final_keyboard(final_message_config: Dict[str, Any]) -> Optional[InlineKeyboardMarkup]:
    config = normalize_final_message_config(final_message_config)
    keyboard_rows = []
    web_app_url = str(os.getenv("WEB_APP_URL") or "").strip()
    for button in config["buttons"]:
        if button["type"] == "menu":
            telegram_button = InlineKeyboardButton(
                text=button["text"],
                callback_data=FUNNEL_OPEN_MENU_CALLBACK,
            )
        elif button["type"] == "web_app":
            if not web_app_url:
                continue
            telegram_button = InlineKeyboardButton(
                text=button["text"],
                web_app=WebAppInfo(url=web_app_url),
            )
        else:
            telegram_button = InlineKeyboardButton(
                text=button["text"],
                url=button["url"],
            )
        keyboard_rows.append([telegram_button])
    if not keyboard_rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


async def send_funnel_final_message(chat_id: int) -> bool:
    settings = await get_support_links_row()
    final_message_config = normalize_final_message_config(settings.get("final_message_config"))
    if not final_message_config["enabled"]:
        return False
    keyboard = build_funnel_final_keyboard(final_message_config)
    if not keyboard:
        return False
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=final_message_config["message_text"],
            reply_markup=keyboard,
        )
        return True
    except Exception as send_error:
        print(f"[Bot] final funnel message send failed: {send_error}")
        return False


async def show_funnel_final_message(callback: types.CallbackQuery) -> bool:
    if not callback.message:
        return False
    settings = await get_support_links_row()
    final_message_config = normalize_final_message_config(settings.get("final_message_config"))
    if not final_message_config["enabled"]:
        return False
    keyboard = build_funnel_final_keyboard(final_message_config)
    if not keyboard:
        return False
    try:
        await callback.message.edit_text(
            text=final_message_config["message_text"],
            reply_markup=keyboard,
        )
        return True
    except Exception as edit_error:
        print(f"[Bot] final funnel message edit failed: {edit_error}")
    return await send_funnel_final_message(callback.message.chat.id)


@dp.chat_join_request()
async def handle_channel_join_request(request: types.ChatJoinRequest):
    settings = await get_support_links_row()
    if settings["check_subscription_enabled"]:
        return
    configured_channel_id = settings.get("channel_id")
    if configured_channel_id and int(request.chat.id) != int(configured_channel_id):
        return
    try:
        await bot.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=request.from_user.id,
        )
    except Exception as exc:
        print(f"[Bot] join request approval failed for {request.from_user.id}: {exc}")
        return
    started = await complete_channel_subscription(
        int(request.from_user.id),
        first_name=request.from_user.first_name or "",
        username=request.from_user.username or "",
    )
    if started:
        try:
            await bot.send_message(
                chat_id=request.from_user.id,
                text="Your channel request has been approved. Welcome!",
            )
        except Exception as exc:
            print(f"[Bot] join approval notification failed: {exc}")


async def map_quiz_answer_with_ai(step: str, text: str) -> Optional[str]:
    local_answer = map_quiz_answer_locally(step, text)
    if local_answer:
        return local_answer

    normalized_step = normalize_quiz_step(step)
    quiz_config = await get_quiz_config_row()
    options = list(get_quiz_options(normalized_step, quiz_config))
    result = await ai_service.call_openai(
        [
            {"role": "system", "content": QUALIFICATION_GPT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {get_quiz_question(normalized_step, quiz_config)}\n"
                    f"Allowed options: {json.dumps(options, ensure_ascii=False)}\n"
                    f"User answer: {text}"
                ),
            },
        ],
        model=(os.getenv("QUALIFICATION_GPT_MODEL") or os.getenv("OPENAI_FALLBACK_MODEL") or "gpt-4o-mini"),
    )
    if not result.get("ok"):
        return None
    ai_answer = str(result.get("text") or "").strip().strip('"').strip("'")
    if is_skip_answer(ai_answer):
        return "Skip"
    for option in options:
        if option.lower() == ai_answer.lower():
            return option
    return None


async def save_quiz_answer(user_id: int, step: str, answer: str, skip_flow: bool = False) -> tuple[Optional[str], bool]:
    normalized_step = normalize_quiz_step(step)
    normalized_answer = normalize_quiz_answer(normalized_step, answer)
    next_step = None if skip_flow else get_next_quiz_step(normalized_step)
    field_map = {
        "experience": "quiz_experience",
        "broker_experience": "quiz_broker_experience",
        "capital": "quiz_capital",
    }
    field_name = field_map[normalized_step]
    completed_steps = get_quiz_steps_to_complete(normalized_step, skip_flow)

    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            if next_step:
                await cur.execute(
                    f"""
                    UPDATE user_onboarding
                    SET {field_name} = %s,
                        current_step = %s
                    WHERE user_id = %s
                      AND current_step = %s
                      AND quiz_completed_at IS NULL
                    """,
                    (normalized_answer, next_step, user_id, normalized_step),
                )
            else:
                assignments = [f"{field_map[item]} = %s" for item in completed_steps]
                values = [normalized_answer if item == normalized_step else "Skip" for item in completed_steps]
                await cur.execute(
                    f"""
                    UPDATE user_onboarding
                    SET {', '.join(assignments)},
                        current_step = %s,
                        quiz_completed_at = COALESCE(quiz_completed_at, NOW())
                    WHERE user_id = %s
                      AND current_step = %s
                      AND quiz_completed_at IS NULL
                    """,
                    (*values, "skipped" if skip_flow else "completed", user_id, normalized_step),
                )
            saved = cur.rowcount > 0

    if not saved:
        return None, False
    aio_fields = [
        (
            get_aio_question_field(item),
            normalized_answer if item == normalized_step else "Skip",
        )
        for item in completed_steps
    ]
    asyncio.create_task(deliver_quiz_aio_fields(user_id, aio_fields))
    return next_step, True


async def deliver_quiz_aio_fields(
    user_id: int,
    aio_fields: List[tuple[str, str]],
) -> None:
    aio_results = await asyncio.gather(
        *(send_aio_field_value(user_id, field_name, value) for field_name, value in aio_fields),
        return_exceptions=True,
    )
    for (field_name, _), result in zip(aio_fields, aio_results):
        if isinstance(result, Exception):
            print(f"[AIO] Quiz field {field_name} failed for user {user_id}: {result}")
            continue
        if result.get("status") != "sent":
            print(
                f"[AIO] Quiz field {field_name} was not delivered for user {user_id}: "
                f"{result.get('reason') or result.get('error') or result.get('response_body') or result}"
            )


async def finish_quiz_and_open_app(
    message: types.Message,
    user_id: int,
    *,
    skipped: bool = False,
    first_name: str = "",
    username: str = "",
):
    asyncio.create_task(send_aio_postback_event(user_id, QUIZ_COMPLETE_EVENT))
    if skipped:
        await message.answer("No problem.")
    else:
        await message.answer(
            "Thank you, I've saved your answers.\n\n"
            "Later, if you want help with a more suitable broker setup for your capital and experience, "
            "you can message the manager.\n\n"
            "Trading involves risk. The app helps you with structure and analysis, but the final decision is always yours."
        )

    # Users reach the bot from the channel, so completing the questionnaire is
    # sufficient confirmation. Keep the same one-time downstream event/media
    # trigger that previously ran after the channel gate.
    await complete_channel_subscription(
        user_id,
        first_name=first_name,
        username=username,
    )
    final_message_shown = await send_funnel_final_message(message.chat.id)
    if not final_message_shown:
        user_name = first_name or username or "Trader"
        await send_main_menu(message.chat.id, user_id, user_name)


async def route_user_after_start(
    message: types.Message,
    user_id: int,
    user_name: str,
    *,
    username: str = "",
) -> bool:
    # Staff access must not depend on the customer's onboarding state. A
    # manager may still have an unfinished quiz/channel gate, but /start must
    # always give them a way into the Admin Center.
    if await has_admin_center_access(user_id):
        await send_main_menu(message.chat.id, user_id, user_name)
        return False

    if not db_pool:
        await send_main_menu(message.chat.id, user_id, user_name)
        return True

    row = await ensure_onboarding_row(user_id)
    if not row.get("quiz_completed_at"):
        current_step = normalize_quiz_step(row.get("current_step"))
        if current_step == "experience" and not row.get("quiz_experience"):
            await send_start_video_note(message.chat.id)
            await send_quiz_welcome(message.chat.id)
        await send_quiz_question(message.chat.id, current_step)
        return False

    if row.get("channel_gate_completed_at"):
        await send_main_menu(message.chat.id, user_id, user_name)
        return True

    await complete_channel_subscription(
        user_id,
        first_name=user_name,
        username=username,
    )
    final_message_shown = await send_funnel_final_message(message.chat.id)
    if not final_message_shown:
        await send_main_menu(message.chat.id, user_id, user_name)
    return False


async def write_manager_stats_audit(
    requested_by: int,
    target_query: str,
    result_status: str,
    target_user_id: Optional[int] = None,
) -> None:
    await write_manager_command_audit(
        "stats",
        requested_by,
        target_query,
        result_status,
        target_user_id,
    )


async def write_manager_command_audit(
    command_name: str,
    requested_by: int,
    target_query: str,
    result_status: str,
    target_user_id: Optional[int] = None,
) -> None:
    if not db_pool:
        return
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO manager_stats_audit
                        (command_name, requested_by, target_query, target_user_id, result_status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        str(command_name or "unknown").strip().lower()[:16],
                        int(requested_by),
                        str(target_query or "")[:255],
                        int(target_user_id) if target_user_id else None,
                        str(result_status or "unknown")[:32],
                    ),
                )
    except Exception as exc:
        print(f"[Manager command] audit failed: {exc}")


def get_country_from_pocket_rows(rows: List[Dict[str, Any]]) -> str:
    for row in rows or []:
        country = str(row.get("country") or "").strip()
        if country:
            return country
        raw_payload = row.get("raw_payload")
        if not raw_payload:
            continue
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        lowered = {str(key).lower(): value for key, value in payload.items()}
        country = str(lowered.get("country") or "").strip()
        if country:
            return country[:32]
    return ""


async def get_manager_stats_summary(target_kind: str, target_value: Any) -> Optional[Dict[str, Any]]:
    if not db_pool:
        return None
    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if target_kind == "id":
                await cur.execute(
                    """
                    SELECT user_id, username, first_name, country,
                           COALESCE(pocket_deposit_amount, 0) AS deposit_amount
                    FROM users
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (int(target_value),),
                )
            else:
                normalized_username = str(target_value or "").strip().lower().lstrip("@")
                await cur.execute(
                    """
                    SELECT user_id, username, first_name, country,
                           COALESCE(pocket_deposit_amount, 0) AS deposit_amount
                    FROM users
                    WHERE LOWER(COALESCE(username, '')) IN (%s, %s)
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (normalized_username, f"@{normalized_username}"),
                )
            user_row = await cur.fetchone()
            if not user_row:
                return None

            user_id = int(user_row["user_id"])
            await cur.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) AS wins_total,
                    COALESCE(SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END), 0) AS losses_total,
                    COALESCE(SUM(
                        CASE WHEN status = 'success'
                                  AND COALESCE(closed_at, updated_at, created_at) >= NOW() - INTERVAL 7 DAY
                             THEN 1 ELSE 0 END
                    ), 0) AS wins_7d,
                    COALESCE(SUM(
                        CASE WHEN status = 'fail'
                                  AND COALESCE(closed_at, updated_at, created_at) >= NOW() - INTERVAL 7 DAY
                             THEN 1 ELSE 0 END
                    ), 0) AS losses_7d
                FROM user_analyses
                WHERE user_id = %s
                  AND status IN ('success', 'fail')
                """,
                (user_id,),
            )
            result_row = await cur.fetchone() or {}
            await cur.execute(
                """
                SELECT
                    MIN(
                        CASE WHEN event_slug IN ('ftd', 'dep') AND status = 'deposited'
                             THEN created_at ELSE NULL END
                    ) AS first_deposit_at
                FROM pocket_postback_events
                WHERE user_id = %s
                """,
                (user_id,),
            )
            deposit_row = await cur.fetchone() or {}

            if not str(user_row.get("country") or "").strip():
                await cur.execute(
                    """
                    SELECT country, raw_payload
                    FROM pocket_postback_events
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    (user_id,),
                )
                user_row["country"] = get_country_from_pocket_rows(await cur.fetchall())

    return {
        **user_row,
        **result_row,
        "first_deposit_at": deposit_row.get("first_deposit_at"),
    }


@dp.message(Command("stats"))
async def cmd_manager_stats(message: types.Message):
    if not message.from_user:
        return
    requester_id = int(message.from_user.id)
    target_query = str(message.text or "").strip()
    staff_profile = await get_staff_profile(requester_id)
    if not staff_profile or not has_permission(staff_profile, PERM_STATS_COMMAND):
        await write_manager_stats_audit(requester_id, target_query, "denied")
        await message.answer("Insufficient permissions")
        return
    if str(message.chat.type) not in {"private", "ChatType.PRIVATE"}:
        await write_manager_stats_audit(requester_id, target_query, "private_chat_required")
        await message.answer("The /stats command is available only in a private chat with the bot.")
        return

    target_kind, target_value = parse_stats_target(target_query)
    if not target_kind:
        await write_manager_stats_audit(requester_id, target_query, "invalid_query")
        await message.answer("Usage: /stats @nickname or /stats 123456789")
        return

    summary = await get_manager_stats_summary(target_kind, target_value)
    if not summary:
        await write_manager_stats_audit(requester_id, target_query, "not_found")
        await message.answer("Client not found")
        return

    await write_manager_stats_audit(
        requester_id,
        target_query,
        "success",
        int(summary["user_id"]),
    )
    await message.answer(format_manager_stats(summary))


def mask_chatterfy_lead_id(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) <= 8:
        return "***"
    return f"{normalized[:4]}…{normalized[-4:]}"


async def get_registration_link_by_target(target_kind: str, target_value: str) -> Dict[str, Any]:
    if not db_pool:
        return {"status": "unavailable"}

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if target_kind == "username":
                normalized_username = str(target_value or "").strip().lower().lstrip("@")
                if not re.fullmatch(r"[a-z0-9_]{5,32}", normalized_username):
                    return {"status": "invalid_query"}
                await cur.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE LOWER(COALESCE(username, '')) IN (%s, %s)
                    ORDER BY updated_at DESC, user_id DESC
                    LIMIT 2
                    """,
                    (normalized_username, f"@{normalized_username}"),
                )
            else:
                normalized_lead_id = normalize_chatterfy_lead_id(target_value)
                if not normalized_lead_id:
                    return {"status": "invalid_query"}
                await cur.execute(
                    """
                    SELECT user_id
                    FROM users
                    WHERE chatterfy_lead_id = %s OR pocket_sub_id3 = %s
                    ORDER BY updated_at DESC, user_id DESC
                    LIMIT 2
                    """,
                    (normalized_lead_id, normalized_lead_id),
                )
            matches = list(await cur.fetchall() or [])
    if not matches:
        return {"status": "not_found"}
    if len(matches) > 1:
        return {"status": "ambiguous"}

    user_id = int(matches[0]["user_id"])
    link_data = await get_personal_registration_link(user_id)
    if not link_data:
        return {"status": "not_found"}
    return {"status": "success", "user_id": user_id, "url": link_data["url"]}


async def get_registration_link_by_chatterfy_lead_id(lead_id: str) -> Dict[str, Any]:
    return await get_registration_link_by_target("lead_id", lead_id)


@dp.message(Command("link"))
async def cmd_manager_registration_link(message: types.Message):
    if not message.from_user:
        return
    requester_id = int(message.from_user.id)
    raw_command = str(message.text or "").strip()
    target_kind, target_value = parse_registration_link_target(raw_command)
    audit_query = (
        f"/link @{target_value}"
        if target_kind == "username"
        else f"/link {mask_chatterfy_lead_id(str(target_value or ''))}".strip()
    )

    staff_profile = await get_staff_profile(requester_id)
    if not staff_profile or not has_permission(staff_profile, PERM_STATS_COMMAND):
        await write_manager_command_audit("link", requester_id, audit_query, "denied")
        await message.answer("Insufficient permissions")
        return
    if str(message.chat.type) not in {"private", "ChatType.PRIVATE"}:
        await write_manager_command_audit("link", requester_id, audit_query, "private_chat_required")
        await message.answer("The /link command is available only in a private chat with the bot.")
        return
    if not target_kind or not target_value:
        await write_manager_command_audit("link", requester_id, audit_query, "invalid_query")
        await message.answer("Usage: /link @username or /link chatterfy_lead_id")
        return

    result = await get_registration_link_by_target(target_kind, target_value)
    if result.get("status") == "not_found":
        await write_manager_command_audit("link", requester_id, audit_query, "not_found")
        await message.answer("Client link not found")
        return
    if result.get("status") != "success":
        await write_manager_command_audit("link", requester_id, audit_query, "invalid_query")
        await message.answer("The lead ID is not linked uniquely. Contact an administrator.")
        return

    await write_manager_command_audit(
        "link",
        requester_id,
        audit_query,
        "success",
        int(result["user_id"]),
    )
    await message.answer(str(result["url"]), disable_web_page_preview=True)


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
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
                    VALUES (%s, %s, 0, NULL)
                    """,
                    [(user_id, "forex"), (user_id, "binary")],
                )

    asyncio.create_task(send_aio_postback_event(user_id, "bot_start"))
    asyncio.create_task(send_pending_chatterfy_start_events(user_id))
    asyncio.create_task(send_aio_user_fields(user_id, first_name=first_name, username=username))
    asyncio.create_task(sync_aio_profile_status_fields(user_id))
    asyncio.create_task(apply_pending_aio_geo_for_user(user_id))
    ai_chat_ready = await route_user_after_start(
        message,
        user_id,
        user_name,
        username=username,
    )
    if ai_chat_ready:
        await forward_message_to_ai_chatter(message, text_override="Hello", is_start=True)


@dp.message()
async def handle_onboarding_answer(message: types.Message):
    if not db_pool or not message.from_user:
        return
    user_id = int(message.from_user.id)
    row = await get_onboarding_row(user_id)
    if not row:
        return
    if row.get("quiz_completed_at"):
        if row.get("channel_subscribed_at"):
            if not row.get("channel_gate_completed_at"):
                async with db_pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute(
                            """
                            UPDATE user_onboarding
                            SET channel_gate_completed_at = COALESCE(channel_gate_completed_at, NOW())
                            WHERE user_id = %s
                              AND channel_subscribed_at IS NOT NULL
                            """,
                            (user_id,),
                        )
            await forward_message_to_ai_chatter(message)
        return

    current_step = normalize_quiz_step(row.get("current_step"))
    text = message.text or ""
    if "financial advice" in text.lower():
        await message.answer(
            "No. We provide educational content and analytical tools. You make your own trading decisions."
        )
        await send_quiz_question(message.chat.id, current_step)
        return

    answer = await map_quiz_answer_with_ai(current_step, text)
    if not answer:
        await message.answer("Please choose one of the options below, or tap Skip.")
        await send_quiz_question(message.chat.id, current_step)
        return

    skip_flow = is_skip_answer(answer)
    next_step, saved = await save_quiz_answer(user_id, current_step, answer, skip_flow=skip_flow)
    if not saved:
        await message.answer("This question has already changed. Please use the latest options.")
        latest_row = await get_onboarding_row(user_id)
        if latest_row and not latest_row.get("quiz_completed_at"):
            await send_quiz_question(message.chat.id, latest_row.get("current_step") or "experience")
        return
    if next_step:
        await send_quiz_question(message.chat.id, next_step)
        return

    await finish_quiz_and_open_app(
        message,
        user_id,
        skipped=skip_flow,
        first_name=message.from_user.first_name or "",
        username=message.from_user.username or "",
    )


@dp.callback_query(lambda callback: str(callback.data or "").startswith(f"{QUIZ_ANSWER_CALLBACK_PREFIX}:"))
async def handle_quiz_answer_callback(callback: types.CallbackQuery):
    if not callback.message or not callback.from_user:
        return
    parts = str(callback.data or "").split(":")
    if len(parts) != 3:
        await callback.answer("Please try again.", show_alert=True)
        return

    _, raw_step, raw_index = parts
    if not is_valid_quiz_step(raw_step):
        await callback.answer("Please try again.", show_alert=True)
        return
    current_step = normalize_quiz_step(raw_step)
    try:
        quiz_config = await get_quiz_config_row()
        option = get_quiz_options(current_step, quiz_config)[int(raw_index)]
    except (ValueError, IndexError):
        await callback.answer("Please try again.", show_alert=True)
        return

    user_id = int(callback.from_user.id)
    row = await get_onboarding_row(user_id)
    if not row or row.get("quiz_completed_at"):
        await callback.answer()
        return
    if normalize_quiz_step(row.get("current_step")) != current_step:
        await callback.answer("This question has already changed.", show_alert=True)
        return

    skip_flow = is_skip_answer(option)
    next_step, saved = await save_quiz_answer(user_id, current_step, option, skip_flow=skip_flow)
    if not saved:
        await callback.answer("This question has already changed.", show_alert=True)
        return
    await callback.answer("Saved")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as exc:
        print(f"[Bot] quiz keyboard cleanup failed: {exc}")
    if next_step:
        await send_quiz_question(callback.message.chat.id, next_step)
        return

    await finish_quiz_and_open_app(
        callback.message,
        user_id,
        skipped=skip_flow,
        first_name=callback.from_user.first_name or "",
        username=callback.from_user.username or "",
    )


@dp.callback_query(lambda callback: callback.data == FUNNEL_CONTINUE_CALLBACK)
async def handle_funnel_continue(callback: types.CallbackQuery):
    if not callback.message or not callback.from_user:
        return

    user_id = int(callback.from_user.id)
    row = await get_onboarding_row(user_id) or {}
    if not row.get("quiz_completed_at"):
        await callback.answer(
            "Please complete the questions first.",
            show_alert=True,
        )
        return
    await complete_channel_subscription(
        user_id,
        first_name=callback.from_user.first_name or "",
        username=callback.from_user.username or "",
    )

    if db_pool:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE user_onboarding
                    SET channel_gate_completed_at = COALESCE(channel_gate_completed_at, NOW())
                    WHERE user_id = %s
                      AND quiz_completed_at IS NOT NULL
                    """,
                    (user_id,),
                )

    user_name = callback.from_user.first_name or callback.from_user.username or "Trader"
    await callback.answer("Opening trading")
    final_message_shown = await show_funnel_final_message(callback)
    if not final_message_shown:
        await send_main_menu(callback.message.chat.id, user_id, user_name)


@dp.callback_query(lambda callback: callback.data == FUNNEL_OPEN_MENU_CALLBACK)
async def handle_funnel_open_menu(callback: types.CallbackQuery):
    if not callback.message or not callback.from_user:
        return
    await callback.answer()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as edit_error:
        print(f"[Bot] final funnel keyboard cleanup failed: {edit_error}")
    user_name = callback.from_user.first_name or callback.from_user.username or "Trader"
    await send_main_menu(callback.message.chat.id, int(callback.from_user.id), user_name)


@dp.callback_query(lambda callback: callback.data == FUNNEL_CHECK_CHANNEL_CALLBACK)
async def handle_funnel_check_channel(callback: types.CallbackQuery):
    if callback.from_user and db_pool:
        user_id = int(callback.from_user.id)
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE user_onboarding
                    SET channel_subscribed_at = COALESCE(channel_subscribed_at, NOW())
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
        await send_aio_postback_event(user_id, CHANNEL_SUBSCRIBE_EVENT)
        await start_ai_chatter_from_callback(callback)
    await handle_funnel_continue(callback)

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
        pocket_balance_sync_worker(),
        aio_profile_status_backfill_worker(),
    )

if __name__ == "__main__":
    async def main_wrapper():
        try:
            await main()
        except KeyboardInterrupt:
            pass
    asyncio.run(main_wrapper())

