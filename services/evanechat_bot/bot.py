import asyncio
import json
import logging
import math
import os
import random
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from datetime import datetime, time, timedelta
from html import escape
from io import BytesIO
from zoneinfo import ZoneInfo
import aiomysql
import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command
from aiogram.methods.base import TelegramMethod
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    BusinessConnection,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    InputMediaPhoto,
    FSInputFile,
)
from aiogram.dispatcher.router import Router

from db import init_db, to_time
from flows.vip import send_vip_onboarding_flow
from flows.existing_account import send_existing_account_flow
from flows.greeting import send_greeting_flow
from service.funnel import update_user_stage_from_exchange
from service.funnel_media import split_funnel_reply
from service.keyword_trigger import handle_keyword_trigger
from admin.admin import (
    router as admin_router,
    setup_admin,
    refresh_admin_ids_cache,
    ADMIN_IDS as RUNTIME_ADMIN_IDS,
)

from config import (
    API_TOKEN,
    OPENAI_API_KEY,
    DB_CONFIG,
    LOG_CHANNEL_ID,
    MSK_TZ,
    AFFILIATE_BASE_URL,
    AFFILIATE_API_SECRET,
    AFFILIATE_BOT_ID,
    PROMPT_PAGE_SIZE,
    REGISTER_BASE_URL,
    STAGE_NEW,
    STAGE_NAME_KNOWN,
    STAGE_WAITING_PLATFORM_ACCOUNT,
    STAGE_WAITING_EXISTING_ACCOUNT_TRADER_ID,
    STAGE_REG_LINK_SENT,
    STAGE_WAITING_ACCOUNT_ID,
    STAGE_ACCOUNT_ID_SENT,
    STAGE_ACCOUNT_ID_BAD,
    STAGE_ACCOUNT_ID_OK,
    STAGE_WAITING_DEPOSIT,
    STAGE_DEPOSIT_DONE,
    STAGE_TITLES,
    KV_CACHE_TTL,
    FUNNEL_MEDIA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

if not OPENAI_API_KEY:
    print("[AI WARNING] OPENAI_API_KEY не задан, ИИ-ответы отключены")
    ai_client: AsyncOpenAI | None = None
else:
    ai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=OPENAI_API_KEY)
active_openai_api_key: str = OPENAI_API_KEY

db_pool: aiomysql.Pool | None = None

ai_system_prompt: str = ""
AI_ENABLED: bool = True
AI_MODEL: str = os.getenv("AI_MODEL", "gpt-4.1")
BOT_NAME: str = os.getenv("BOT_NAME", "Кирилл")

is_working_flag: bool | None = None
session_clients: set[int] = set()
session_out_messages: int = 0

KV_CACHE: dict[str, str] = {}
KV_CACHE_LOADED_AT: datetime | None = None

pending_reply_tasks: dict[int, asyncio.Task] = {}
pending_reply_buffers: dict[int, dict] = {}
manual_takeover_until: dict[int, datetime] = {}
video_note_prepare_locks: dict[str, asyncio.Lock] = {}
work_enabled_manual: bool = True

work_start: time | None = None
work_end: time | None = None

router = Router()


class ReadBusinessMessage(TelegramMethod[bool]):
    """Совместимость readBusinessMessage с закреплённой версией aiogram."""

    __returning__ = bool
    __api_method__ = "readBusinessMessage"

    business_connection_id: str
    chat_id: int
    message_id: int

def build_register_link(tg_user_id: int) -> str:
    parts = urlsplit(REGISTER_BASE_URL)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["click_id"] = str(tg_user_id)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

def inject_register_link_into_text(reply_text: str, tg_user_id: int) -> str:
    reg_link = build_register_link(tg_user_id)

    pattern = r"(?i)pocket\s*option"

    if re.search(pattern, reply_text):
        def repl(m: re.Match) -> str:
            original = m.group(0)
            return f'<a href="{reg_link}"><b>{original}</b></a>'
        reply_text = re.sub(pattern, repl, reply_text, count=1)
    else:
        reply_text += f"\n\n<b>ССЫЛКА для регистрации на Pocket Option:</b> {reg_link}"

    return reply_text
    
TRADER_ID_REGEX = re.compile(r"\b\d{5,}\b")
TRADER_ID_INLINE_REGEX = re.compile(
    r"\b(?:id|Р°Р№РґРё|trader(?:\s*id)?)\b[\s:=-]*(\d{5,})",
    re.IGNORECASE,
)
TRADER_ID_STANDALONE_REGEX = re.compile(
    r"^\s*(?:id|Р°Р№РґРё|trader(?:\s*id)?)?[\s:=-]*(\d{5,})\s*$",
    re.IGNORECASE,
)

REGISTRATION_CONFIRMED_MARKERS = (
    "успешно проверили",
    "проверили аккаунт",
    "проверка пройдена",
    "id подходит",
    "ид подходит",
    "аккаунт подходит",
    "можно перейти к пополнению",
    "можно пополняться",
    "можешь пополняться",
    "пополняйся",
)

DEPOSIT_CONFIRMED_MARKERS = (
    "доступ выдан",
    "выдал доступ",
    "выдаю доступ",
    "открыл доступ",
    "добавил в vip",
    "ты в vip",
    "vip - команде",
    "выдал бота",
    "вступай",
)

SILENT_ACK_STAGES = {
    STAGE_REG_LINK_SENT,
    STAGE_WAITING_ACCOUNT_ID,
    STAGE_ACCOUNT_ID_SENT,
    STAGE_ACCOUNT_ID_OK,
    STAGE_WAITING_DEPOSIT,
    STAGE_DEPOSIT_DONE,
}

SILENT_ACK_TOKENS = {
    "ok",
    "okay",
    "oks",
    "\u043e\u043a",
    "\u043e\u043a\u0435\u0439",
    "\u043e\u043a\u0435",
    "\u0430\u0433\u0430",
    "\u0443\u0433\u0443",
    "\u044f\u0441\u043d\u043e",
    "\u043f\u043e\u043d\u044f\u043b",
    "\u043f\u043e\u043d\u044f\u043b\u0430",
    "\u043f\u0440\u0438\u043d\u044f\u043b",
    "\u043f\u0440\u0438\u043d\u044f\u043b\u0430",
    "\u043f\u0440\u0438\u043d\u044f\u0442\u043e",
    "\u0445\u043e\u0440\u043e\u0448\u043e",
    "\u0441\u043f\u0430\u0441\u0438\u0431\u043e",
    "\u0431\u043b\u0430\u0433\u043e\u0434\u0430\u0440\u044e",
    "\u0434\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u043b\u0438\u0441\u044c",
    "\u0434\u043e\u0431\u0440\u043e",
}

SILENT_ACK_BLOCKERS = (
    "?",
    "\u043a\u0430\u043a",
    "\u0433\u0434\u0435",
    "\u043a\u043e\u0433\u0434\u0430",
    "\u0447\u0442\u043e",
    "\u043f\u043e\u0447\u0435\u043c\u0443",
    "\u0437\u0430\u0447\u0435\u043c",
    "\u0441\u043a\u043e\u043b\u044c\u043a\u043e",
    "\u043c\u043e\u0436\u043d\u043e",
    "\u043c\u043e\u0436\u0435\u0448\u044c",
    "\u043f\u043e\u043c\u043e\u0433",
    "\u043f\u043e\u0434\u0441\u043a\u0430\u0436",
    "\u043d\u0435 \u043f\u043e\u043d\u044f\u043b",
    "\u043d\u0435\u043f\u043e\u043d\u044f\u0442\u043d\u043e",
    "\u043d\u0435 \u043f\u043e\u043d\u044f\u0442\u043d\u043e",
    "\u043d\u0435 \u043c\u043e\u0433\u0443",
    "\u043d\u0435 \u043f\u043e\u043b\u0443\u0447\u0430\u0435\u0442\u0441\u044f",
    "\u043e\u0448\u0438\u0431",
    "\u0441\u0441\u044b\u043b\u043a",
    "\u0437\u0430\u0440\u0435\u0433",
    "\u0440\u0435\u0433\u0438\u0441\u0442",
    "\u0430\u0439\u0434\u0438",
    "id",
    "trader",
    "\u0432\u0435\u0440\u0438\u0444",
    "\u043f\u0440\u043e\u0432\u0435\u0440",
    "\u0434\u0435\u043f\u043e\u0437",
    "\u043f\u043e\u043f\u043e\u043b",
    "\u0433\u043e\u0442\u043e\u0432",
    "\u0441\u0434\u0435\u043b\u0430\u043b",
    "\u0441\u0434\u0435\u043b\u0430\u043b\u0430",
    "\u0443\u0434\u0430\u043b",
)

YES_ACCOUNT_TOKENS = {
    "да",
    "ага",
    "угу",
    "есть",
    "имеется",
    "имею",
    "конечно",
    "yes",
    "yeah",
    "yep",
    "sure",
    "have",
    "got",
}

NO_ACCOUNT_TOKENS = {
    "нет",
    "нету",
    "неа",
    "никакого",
    "none",
    "no",
    "nope",
}


def extract_trader_id(text: str) -> str | None:
    if not text:
        return None
    stripped = text.strip()

    m = TRADER_ID_INLINE_REGEX.search(stripped)
    if m:
        return m.group(1)

    m = TRADER_ID_STANDALONE_REGEX.search(stripped)
    if m:
        return m.group(1)

    if stripped.isdigit() and len(stripped) >= 5:
        return stripped

    m = TRADER_ID_REGEX.search(stripped)
    if not m:
        return None
    return m.group(0)


def detect_platform_account_answer(text: str) -> str | None:
    raw_text = (text or "").strip().lower()
    if not raw_text:
        return None

    normalized = re.sub(r"[^\w\s]+", " ", raw_text, flags=re.UNICODE)
    tokens = [token for token in normalized.split() if token]
    if not tokens:
        return None

    if any(token in YES_ACCOUNT_TOKENS for token in tokens):
        return "yes"
    if any(token in NO_ACCOUNT_TOKENS for token in tokens):
        return "no"
    return None


def format_cross_project_user_label(match: dict) -> str:
    username = str(match.get("username") or "").strip()
    if username:
        return f"@{username}"
    first_name = str(match.get("first_name") or "").strip()
    if first_name:
        return first_name
    return f"TG ID {match.get('tg_user_id')}"


async def check_user_globally_via_affiliate(tg_user_id: int) -> list[dict]:
    payload = {
        "bot_id": AFFILIATE_BOT_ID,
        "tg_user_id": tg_user_id,
    }
    data = await call_affiliate_post("/affiliate/check-user-globally", payload)
    if not data or not data.get("success"):
        return []
    result = data.get("data") or {}
    matches = result.get("matches") or []
    return [match for match in matches if isinstance(match, dict)]


async def send_cross_project_hold_and_notify(
    tg_user_id: int,
    business_id: str,
    bot: Bot,
    match: dict,
):
    hold_text = "Брат, буквально пару минут и вернусь к тебе 🤝"
    try:
        sent = await bot.send_message(
            chat_id=tg_user_id,
            text=hold_text,
            business_connection_id=business_id,
        )
        await save_message(sent.chat.id, "out", hold_text, is_business=True)
    except Exception as exc:
        logging.warning("[cross_project] failed to send hold message to %s: %s", tg_user_id, exc)

    project_name = match.get("project_name") or match.get("bot_id") or "unknown"
    trader_id = match.get("trader_id") or "—"
    deposit_status = int(match.get("deposit_status") or 0)
    registration_status = int(match.get("registration_status") or 0)
    client_label = format_cross_project_user_label(match)

    text = (
        f"👤 Tgid: <code>{tg_user_id}</code>\n"
        f"👤 Пользователь: {escape(client_label)}\n\n"
        "<b>Пользователь уже найден в другом проекте.</b>\n\n"
        f"Проект: <b>{escape(str(project_name))}</b>\n"
        f"Trader ID: <code>{escape(str(trader_id))}</code>\n"
        f"Регистрация: <b>{'Да' if registration_status else 'Нет'}</b>\n"
        f"Депозит: <b>{'Да' if deposit_status else 'Нет'}</b>\n\n"
        "Бот для этого клиента автоматически остановлен."
    )
    try:
        await notify_admins(text, bot, tg_user_id=tg_user_id)
    except Exception as exc:
        logging.exception(
            "[cross_project] failed to notify admins for %s: %s",
            tg_user_id,
            exc,
        )

    try:
        await disable_bot_for_user(tg_user_id, "cross_project_registered")
    except Exception as exc:
        logging.exception(
            "[cross_project] failed to disable bot for %s: %s",
            tg_user_id,
            exc,
        )


async def send_platform_account_question(
    tg_user_id: int,
    business_id: str,
    bot: Bot,
):
    text = "Есть ли у тебя уже аккаунт на торговой площадке?"
    sent = await bot.send_message(
        chat_id=tg_user_id,
        business_connection_id=business_id,
        text=text,
    )
    await save_message(sent.chat.id, "out", text, is_business=True)
    await set_user_state(tg_user_id, STAGE_WAITING_PLATFORM_ACCOUNT, "Ждём ответ про наличие аккаунта")


async def send_existing_account_trader_id_request(
    tg_user_id: int,
    business_id: str,
    bot: Bot,
):
    text = "Супер, можешь пожалуйста выслать его, добавлю тебя в команду 🤝"
    sent = await bot.send_message(
        chat_id=tg_user_id,
        business_connection_id=business_id,
        text=text,
    )
    await save_message(sent.chat.id, "out", text, is_business=True)
    await set_user_state(
        tg_user_id,
        STAGE_WAITING_EXISTING_ACCOUNT_TRADER_ID,
        "Ожидаем Trader ID существующего аккаунта",
    )


async def send_registration_start_message(
    tg_user_id: int,
    business_id: str,
    bot: Bot,
):
    reg_link = build_register_link(tg_user_id)
    text = (
        "Отлично, тогда идём дальше.\n\n"
        "Для старта нужно пройти регистрацию по моей ссылке, а после этого прислать мне свой Trader ID 🤝"
    )
    reply_markup = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Зарегистрироваться по моей ссылке",
                url=reg_link,
            )
        ]]
    )
    sent = await bot.send_message(
        chat_id=tg_user_id,
        business_connection_id=business_id,
        text=text,
        reply_markup=reply_markup,
    )
    await save_message(sent.chat.id, "out", text, is_business=True)
    await set_user_state(
        tg_user_id,
        STAGE_REG_LINK_SENT,
        "Отправили ссылку на регистрацию после уточнения по наличию аккаунта",
    )
     
async def update_work_hours(new_start: time, new_end: time):
    """Обновляем рабочие часы в БД и в памяти."""
    global work_start, work_end
    assert db_pool is not None

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE settings
            SET work_start = %s, work_end = %s
            WHERE id = 1
            """,
            (new_start, new_end),
        )

    work_start = new_start
    work_end = new_end


async def save_user_from_message(msg: Message):
    """Обновляем/создаём пользователя по сообщению."""
    assert db_pool is not None
    tg_id = msg.chat.id
    first_name = msg.from_user.first_name if msg.from_user else None
    username = msg.from_user.username if msg.from_user else None

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (tg_user_id, first_name, username)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                first_name = COALESCE(NULLIF(VALUES(first_name), ''), first_name),
                username = COALESCE(NULLIF(VALUES(username), ''), username),
                last_message_at = CURRENT_TIMESTAMP
            """,
            (tg_id, first_name, username),
        )


async def ensure_user_exists(tg_user_id: int):
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (tg_user_id)
            VALUES (%s)
            ON DUPLICATE KEY UPDATE last_message_at = CURRENT_TIMESTAMP
            """,
            (tg_user_id,),
        )


def get_business_message_kind(msg: Message, bot: Bot | None = None) -> str:
    from_user = msg.from_user
    chat_id = getattr(msg.chat, "id", None)

    if getattr(msg, "sender_business_bot", None) is not None:
        return "bot_out"

    if bot and from_user and from_user.id == bot.id:
        return "bot_out"

    if from_user and chat_id is not None and from_user.id != chat_id:
        return "manual_out"

    return "incoming"

async def save_message(
    tg_user_id: int,
    direction: str,
    text: str,
    is_business: bool,
) -> bool:
    """Сохраняем одно сообщение в БД."""
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        if direction == "out" and is_business and text:
            await cur.execute(
                """
                SELECT 1
                FROM messages
                WHERE tg_user_id = %s
                  AND direction = 'out'
                  AND is_business = 1
                  AND text = %s
                  AND created_at >= (NOW() - INTERVAL 15 SECOND)
                LIMIT 1
                """,
                (tg_user_id, text),
            )
            if await cur.fetchone():
                return False

        await cur.execute(
            """
            INSERT INTO messages (tg_user_id, direction, is_business, text)
            VALUES (%s, %s, %s, %s)
            """,
            (tg_user_id, direction, 1 if is_business else 0, text),
        )
    return True


def contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in markers)


def should_skip_ack_reply(user_text: str, stage: str) -> bool:
    if stage not in SILENT_ACK_STAGES:
        return False

    raw_text = (user_text or "").strip()
    if not raw_text or len(raw_text) > 80:
        return False

    lowered = raw_text.lower().replace("\u0451", "\u0435")

    if extract_trader_id(raw_text):
        return False

    if any(blocker in lowered for blocker in SILENT_ACK_BLOCKERS):
        return False

    normalized = re.sub(r"[^\w\s]+", " ", lowered, flags=re.UNICODE)
    tokens = [token for token in normalized.split() if token]
    if not tokens or len(tokens) > 4:
        return False

    return all(token in SILENT_ACK_TOKENS for token in tokens)


async def has_recent_matching_outgoing_business_message(
    tg_user_id: int,
    text: str,
    within_seconds: int = 30,
) -> bool:
    if not text:
        return False

    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT 1
            FROM messages
            WHERE tg_user_id = %s
              AND direction = 'out'
              AND is_business = 1
              AND text = %s
              AND created_at >= (NOW() - INTERVAL {within_seconds} SECOND)
            LIMIT 1
            """,
            (tg_user_id, text),
        )
        return bool(await cur.fetchone())


def is_manual_takeover_active(tg_user_id: int) -> bool:
    until = manual_takeover_until.get(tg_user_id)
    if not until:
        return False
    if until <= datetime.now(MSK_TZ):
        manual_takeover_until.pop(tg_user_id, None)
        return False
    return True


def mark_manual_takeover(tg_user_id: int, seconds: int = 180):
    global pending_reply_tasks, pending_reply_buffers

    manual_takeover_until[tg_user_id] = datetime.now(MSK_TZ) + timedelta(seconds=seconds)

    task = pending_reply_tasks.pop(tg_user_id, None)
    if task and not task.done():
        task.cancel()

    pending_reply_buffers.pop(tg_user_id, None)

async def get_last_messages(
    tg_user_id: int,
    limit: int = 20,
) -> list[tuple[str, str | None, datetime]]:
    """
    Возвращает последние `limit` сообщений с пользователем.
    direction: 'in' / 'out'
    text: текст сообщения
    created_at: время отправки
    """
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT direction, text, created_at
            FROM messages
            WHERE tg_user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (tg_user_id, limit),
        )
        rows = await cur.fetchall()

    # rows идёт от новых к старым
    return rows

async def get_user_state(tg_user_id: int) -> tuple[str, str | None]:
    """
    Возвращает (stage, notes).
    Если записи нет – создаём со stage=new.
    """
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT stage, notes FROM user_state
            WHERE tg_user_id = %s
            """,
            (tg_user_id,),
        )
        row = await cur.fetchone()

        if row:
            return row[0], row[1]

        # если нет – создаём
        await cur.execute(
            """
            INSERT INTO user_state (tg_user_id, stage, notes)
            VALUES (%s, %s, %s)
            """,
            (tg_user_id, STAGE_NEW, None),
        )
        return STAGE_NEW, None
async def get_user_memory(tg_user_id: int) -> str | None:
    """Возвращает краткую сводку по пользователю (долгосрочная память) или None."""
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT memory FROM conversation_memory WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return row[0] or None
async def update_user_memory(tg_user_id: int):
    """
    Обновляет долгосрочную память по пользователю на основе
    прошлых сообщений и старой сводки.
    Делается отдельно от основного ответа, чтобы не тормозить диалог.
    """
    if not ai_client:
        return

    # Берём побольше контекста — допустим, последние 50 сообщений
    rows = await get_last_messages(tg_user_id, limit=50)
    if not rows:
        return

    # Собираем историю в текст (клиент/мы)
    # ВАЖНО: rows идут от новых к старым, разворачиваем:
    lines: list[str] = []
    for direction, text, created_at in reversed(rows):
        if not text:
            continue
        who = "КЛИЕНТ" if direction == "in" else "МЫ"
        ts = created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {who}: {text}")

    history_text = "\n".join(lines)

    old_memory = await get_user_memory(tg_user_id)
    if old_memory:
        user_prompt = (
            "Вот старая краткая сводка по клиенту и фрагмент истории диалога. "
            "Обнови сводку, сохранив важные факты, но сделай её максимально короткой "
            "(5-10 предложений максимум).\n\n"
            "СТАРАЯ СВОДКА:\n"
            f"{old_memory}\n\n"
            "ИСТОРИЯ СООБЩЕНИЙ:\n"
            f"{history_text}"
        )
    else:
        user_prompt = (
            "Сделай краткую сводку по этому клиенту на основе диалога. "
            "Укажи: опыт в трейдинге, страхи и сомнения, что уже объяснили, "
            "на каком он примерно этапе (до регистрации, после регистрации, депозит и т.п.), "
            "и любые важные договорённости.\n\n"
            "ИСТОРИЯ СООБЩЕНИЙ:\n"
            f"{history_text}"
        )

    try:
        resp = await call_chat_with_retry(
            model=ai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты помощник, который делает краткие сводки по диалогам. "
                        "Отвечай ТОЛЬКО сводкой, без пояснений, без маркдауна."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        new_memory = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logging.warning("Ошибка при обновлении памяти: %s", e)
        return

    if not new_memory:
        return

    # Сохраняем новую сводку в БД
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO conversation_memory (tg_user_id, memory)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE memory = VALUES(memory)
            """,
            (tg_user_id, new_memory),
        )
        
async def get_planner_prompt() -> str:
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT planner_system_prompt FROM ai_settings LIMIT 1")
        row = await cur.fetchone()
        return row[0] if row and row[0] else ""

async def plan_conversation(
    tg_user_id: int,
    user_text: str,
    stage: str,
    reg_status: int,
    dep_status: int,
    country: str | None,
    long_memory: str | None,
) -> dict:
    """
    Дополнительный ИИ-планировщик на gpt-4.1-mini.
    Он НЕ пишет текст клиенту, а только:
    - определяет intent
    - возвращает список actions
    - формирует main_prompt для основного ИИ
    """
    if not ai_client:
        return {
            "intent": "DEFAULT",
            "actions": [],
            "main_prompt": f"Клиент написал: {user_text}",
            "tone": "default",
        }

    # 1) диагностическое логирование входа
    logging.info(
        "[planner] вход: tg=%s | stage=%s | reg_status=%s | dep_status=%s | text='%s'",
        tg_user_id, stage, reg_status, dep_status, user_text
    )

    # 2) короткая история
    rows = await get_last_messages(tg_user_id, limit=10)
    lines: list[str] = []
    for direction, text, created_at in reversed(rows):
        if not text:
            continue
        who = "КЛИЕНТ" if direction == "in" else "МЫ"
        ts = created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {who}: {text}")
    history_text = "\n".join(lines) if lines else "(история пуста)"

    # 3) вычисляем наличие Trader ID (число из 5+ цифр) в истории/сообщении
    id_pattern = re.compile(r"\b\d{5,}\b")
    has_trader_id = bool(
        id_pattern.search(history_text) or id_pattern.search(user_text)
    )

    # 4) системный промт
    sys = await get_planner_prompt()

    # 5) user-message для планнер-модели
    user_content = (
        f"Имя менеджера: {bot_name}\n"
        f"Текущий этап воронки (stage): {stage}\n"
        f"registration_status: {reg_status}\n"
        f"deposit_status: {dep_status}\n"
        f"country: {country or 'не указана'}\n\n"
        f"Краткая сводка по клиенту:\n{long_memory or '(нет сводки)'}\n\n"
        f"История переписки:\n{history_text}\n\n"
        f"Текущее сообщение клиента:\n{user_text}\n\n"
        "Сформируй JSON по правилам."
    )

    try:
        resp = await call_chat_with_retry(
            model="gpt-4.1-mini",
            temperature=0.0,
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": user_content},
            ],
        )

        raw = (resp.choices[0].message.content or "").strip()
        logging.info("[planner raw JSON]: %s", raw)

        # 6) подстраховка: вырезаем JSON из сырого текста
        if not (raw.startswith("{") and raw.endswith("}")):
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw = raw[start : end + 1]

        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("planner returned non-dict JSON")

        # 7) дефолтные поля
        data.setdefault("intent", "DEFAULT")
        data.setdefault("actions", [])
        data.setdefault("main_prompt", f"Клиент написал: {user_text}")
        data.setdefault("tone", "default")

        # safety для actions
        if not isinstance(data["actions"], list):
            data["actions"] = []

        if reg_status == 0 and not has_trader_id:
            dangerous_intents = {
                "REG_CONFIRMED",
                "DEPOSIT_ALREADY_CONFIRMED",
                "VERIFICATION_DONE",
            }
            has_check_reg = "CHECK_REGISTRATION_API" in data["actions"]

            if data["intent"] in dangerous_intents or has_check_reg:
                logging.info(
                    "[planner guard] reg_status=0 и нет Trader ID, "
                    "переписываем intent=%s, actions=%s -> CLAIM_REG_NO_ID без action",
                    data.get("intent"),
                    data.get("actions"),
                )
                data["intent"] = "CLAIM_REG_NO_ID"
                data["actions"] = []
                data["main_prompt"] = (
                    "Клиент говорит, что всё сделал/зарегистрировался, "
                    "но registration_status=0 и в истории нет Trader ID. "
                    "Попроси вежливо прислать Trader ID кабинета, объясни, где его найти, "
                    "и не подтверждай регистрацию до проверки ID."
                )

        # 8.2. Если депозит уже подтверждён (`deposit_status = 1`) —
        # убираем любые CHECK_DEPOSIT_API.
        if dep_status == 1 and "CHECK_DEPOSIT_API" in data["actions"]:
            logging.info(
                "[planner guard] dep_status=1, удаляем CHECK_DEPOSIT_API из actions: %s",
                data["actions"],
            )
            data["actions"] = [
                a for a in data["actions"] if a != "CHECK_DEPOSIT_API"
            ]

        # 8.3. Защита от GREETING_FLOW, если stage != "new"
        if stage != "new" and data.get("intent") == "GREETING_FLOW":
            logging.info(
                "[planner guard] stage != 'new', но intent=GREETING_FLOW. "
                "Переводим в DEFAULT."
            )
            data["intent"] = "DEFAULT"
            # main_prompt оставляем как есть либо можно упростить:
            if not data.get("main_prompt"):
                data["main_prompt"] = f"Клиент написал: {user_text}"

        # 9) логируем распарсенный JSON
        logging.info(
            "[planner parsed] intent=%s | actions=%s | tone=%s",
            data.get("intent"),
            data.get("actions"),
            data.get("tone"),
        )

        return data

    except Exception as e:
        logging.warning("plan_conversation error: %s", e)
        return {
            "intent": "DEFAULT_ERROR_FALLBACK",
            "actions": [],
            "main_prompt": f"Клиент написал: {user_text}",
            "tone": "default",
        }
        
async def get_kv_value(key: str) -> str | None:
    """Вернуть значение из kv_settings по ключу skey или None."""
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT svalue FROM kv_settings WHERE skey = %s",
            (key,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return row[0]
async def load_kv_settings() -> dict[str, str]:
    """
    Грузим все настройки из kv_settings в память с простым TTL-кэшем.
    """
    global KV_CACHE, KV_CACHE_LOADED_AT

    # используем кэш, если не протух
    if KV_CACHE and KV_CACHE_LOADED_AT and datetime.now() - KV_CACHE_LOADED_AT < KV_CACHE_TTL:
        return KV_CACHE

    assert db_pool is not None  # пул уже создаётся в init_db()

    async with db_pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT skey, svalue FROM kv_settings")
            rows = await cur.fetchall()

    KV_CACHE = {row["skey"]: row["svalue"] for row in rows}
    KV_CACHE_LOADED_AT = datetime.now()
    return KV_CACHE



async def get_min_deposit_threshold() -> float:
    settings = await load_kv_settings()
    raw_value = settings.get("MIN_DEPOSIT_THRESHOLD", "5")

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 10.0        
async def get_user_status_flags(tg_user_id: int) -> tuple[int, int, str | None]:
    """
    Возвращает (registration_status, deposit_status, country) для пользователя.
    Если записи нет – считаем всё нулями.
    """
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT registration_status, deposit_status, country
            FROM users
            WHERE tg_user_id = %s
            """,
            (tg_user_id,),
        )
        row = await cur.fetchone()

    if not row:
        logging.warning(
            "[get_user_status_flags] user %s: записи в users нет, возвращаю (0,0,None)",
            tg_user_id,
        )
        return 0, 0, None

    reg_status = int(row[0] or 0)
    dep_status = int(row[1] or 0)
    country = row[2]

    logging.info(
        "[get_user_status_flags] user %s: reg=%s, dep=%s, country=%s",
        tg_user_id,
        reg_status,
        dep_status,
        country,
    )

    return reg_status, dep_status, country


async def get_funnel_routing_prompt() -> str:
    settings = await load_kv_settings()
    if settings.get("FUNNEL_MEDIA_ENABLED", "1") != "1":
        return "Отправка кружков сейчас отключена: не используй теги [SEND:id]."
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            """
            SELECT media_key, block_code, title, description
            FROM funnel_media
            WHERE enabled = 1
            ORDER BY sort_order, id
            """
        )
        rows = await cur.fetchall()
    if not rows:
        return "Отправка кружков сейчас отключена: не используй теги [SEND:id]."
    lines = [
        "Управляемая карта кружков из админцентра (порядок строк — порядок воронки):",
        "Используй только перечисленные ID, не перепрыгивай этапы без причины и не отправляй больше одного кружка за ответ.",
    ]
    for index, row in enumerate(rows, start=1):
        description = " ".join(str(row.get("description") or "").split())
        lines.append(
            f"{index}. [SEND:{row['media_key']}] · блок {row['block_code']} · "
            f"{row['title']}" + (f" — {description}" if description else "")
        )
    return "\n".join(lines)


async def get_next_unsent_funnel_media_key(tg_user_id: int, block_code: str) -> str | None:
    settings = await load_kv_settings()
    if settings.get("FUNNEL_MEDIA_ENABLED", "1") != "1":
        return None
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT fm.media_key
            FROM funnel_media fm
            LEFT JOIN funnel_media_sent fms
              ON fms.media_key = fm.media_key AND fms.tg_user_id = %s
            WHERE fm.enabled = 1
              AND fm.block_code = %s
              AND fms.media_key IS NULL
            ORDER BY fm.sort_order, fm.id
            LIMIT 1
            """,
            (tg_user_id, block_code),
        )
        row = await cur.fetchone()
    return str(row[0]) if row else None

async def is_user_bot_active(tg_user_id: int) -> bool:
    """
    Проверяем, не отключён ли автоответчик для этого пользователя.
    По умолчанию считаем, что включён.
    """
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT bot_active FROM users WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        row = await cur.fetchone()

    if not row or row[0] is None:
        return True
    return bool(row[0])


async def disable_bot_for_user(tg_user_id: int, reason: str):
    assert db_pool is not None
    short_reason = (reason or "")[:250]

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET bot_active = 0,
                bot_block_reason = %s,
                bot_blocked_at = NOW()
            WHERE tg_user_id = %s
            """,
            (short_reason, tg_user_id),
        )
        await cur.execute(
            """
            INSERT INTO bot_block_log (tg_user_id, reason)
            VALUES (%s, %s)
            """,
            (tg_user_id, short_reason),
        )
        
async def enable_bot_for_user(tg_user_id: int):
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET bot_active = 1,
                bot_block_reason = NULL,
                bot_blocked_at = NULL
            WHERE tg_user_id = %s
            """,
            (tg_user_id,),
        )
        
async def notify_admins(message: str, bot: Bot, tg_user_id: int | None = None):
    logging.info(
        "[notify_admins] call: tg_user_id=%s, msg_preview=%r",
        tg_user_id,
        (message or "")[:200],
    )

    if not RUNTIME_ADMIN_IDS and not LOG_CHANNEL_ID:
        logging.error(
            "[notify_admins] Нет ни ADMIN_IDS, ни LOG_CHANNEL_ID — уведомление некуда отправлять."
        )
        return

    final_msg = message
    if tg_user_id:
        final_msg = f"👤 tg_user_id: {tg_user_id}\n\n{message}"

    for admin_id in RUNTIME_ADMIN_IDS:
        try:
            await bot.send_message(admin_id, final_msg)
            logging.info("[notify_admins] отправлено админу %s", admin_id)
        except Exception as e:
            logging.warning(
                "[notify_admins] Не удалось отправить админу %s: %s",
                admin_id, e
            )

    if LOG_CHANNEL_ID:
        try:
            await bot.send_message(LOG_CHANNEL_ID, final_msg)
            logging.info(
                "[notify_admins] отправлено в LOG_CHANNEL_ID %s",
                LOG_CHANNEL_ID
            )
        except Exception as e:
            logging.warning(
                "[notify_admins] Ошибка отправки в LOG_CHANNEL_ID=%s: %s",
                LOG_CHANNEL_ID, e
            )

            
async def get_trader_id_for_user(tg_user_id: int) -> str | None:
    """Вернуть trader_id из таблицы users (если есть)."""
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT trader_id FROM users WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return row[0]


async def update_trader_id_and_reg_status(
    tg_user_id: int,
    trader_id: str | None = None,
    registration_status: int | None = None,
):
    """Обновить trader_id и/или registration_status в users."""
    assert db_pool is not None

    sets = []
    args: list = []
    if trader_id is not None:
        sets.append("trader_id = %s")
        args.append(trader_id)
    if registration_status is not None:
        sets.append("registration_status = %s")
        args.append(int(registration_status))

    if not sets:
        return

    args.append(tg_user_id)

    query = f"""
        UPDATE users
        SET {", ".join(sets)}
        WHERE tg_user_id = %s
    """

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(query, tuple(args))


async def update_deposit_status(tg_user_id: int, deposit_status: int):
    """Обновить deposit_status в users."""
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE users
            SET deposit_status = %s
            WHERE tg_user_id = %s
            """,
            (int(deposit_status), tg_user_id),
        )

async def set_user_state(
    tg_user_id: int,
    stage: str,
    notes: str | None = None,
):
    """Устанавливаем/обновляем этап воронки и заметку."""
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO user_state (tg_user_id, stage, notes)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                stage = VALUES(stage),
                notes = VALUES(notes)
            """,
            (tg_user_id, stage, notes),
        )


async def passive_sync_user_context(
    tg_user_id: int,
    incoming_text: str = "",
    outgoing_text: str = "",
):
    trader_id = extract_trader_id(incoming_text)
    if trader_id:
        await update_trader_id_and_reg_status(tg_user_id, trader_id=trader_id)

    if contains_any_marker(outgoing_text, REGISTRATION_CONFIRMED_MARKERS):
        await update_trader_id_and_reg_status(tg_user_id, registration_status=1)

    if contains_any_marker(outgoing_text, DEPOSIT_CONFIRMED_MARKERS):
        await update_trader_id_and_reg_status(tg_user_id, registration_status=1)
        await update_deposit_status(tg_user_id, 1)

    if incoming_text or outgoing_text:
        await update_user_stage_from_exchange(
            tg_user_id=tg_user_id,
            user_text=incoming_text,
            ai_reply=outgoing_text,
            get_user_state=get_user_state,
            get_user_status_flags=get_user_status_flags,
            set_user_state=set_user_state,
        )


async def backfill_missing_trader_ids_from_messages(
    limit_users: int = 1000,
    per_user_messages: int = 100,
):
    assert db_pool is not None

    updated = 0

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT tg_user_id
            FROM users
            WHERE trader_id IS NULL OR trader_id = ''
            ORDER BY last_message_at DESC
            LIMIT %s
            """,
            (limit_users,),
        )
        users = await cur.fetchall()

        for (tg_user_id,) in users:
            await cur.execute(
                """
                SELECT text
                FROM messages
                WHERE tg_user_id = %s
                  AND direction = 'in'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (tg_user_id, per_user_messages),
            )
            rows = await cur.fetchall()

            trader_id = None
            for (text,) in rows:
                trader_id = extract_trader_id(text or "")
                if trader_id:
                    break

            if trader_id:
                await update_trader_id_and_reg_status(tg_user_id, trader_id=trader_id)
                updated += 1

    logging.info(
        "[backfill_missing_trader_ids_from_messages] restored trader_id for %s users",
        updated,
    )
        
async def call_chat_with_retry(messages, model: str, temperature: float = 0.4,
                               max_retries: int = 4):
    """
    Обёртка для chat.completions с ретраями при rate_limit_exceeded (429).
    """
    last_err = None

    for attempt in range(1, max_retries + 1):
        try:
            request = {"model": model, "messages": messages}
            # GPT-5 reasoning-модели принимают только стандартную temperature=1.
            # Не передаём параметр, чтобы одна настройка модели работала для 4.x и 5.x.
            if not model.lower().startswith("gpt-5"):
                request["temperature"] = temperature
            resp = await ai_client.chat.completions.create(**request)
            return resp

        except Exception as e:
            text = str(e)
            # Проверяем, что это именно rate limit
            if "rate_limit_exceeded" in text or "Rate limit reached" in text:
                # Пытаемся достать "Please try again in Xs"
                wait_for = 10.0
                if "Please try again in" in text:
                    try:
                        part = text.split("Please try again in", 1)[1]
                        sec_str = part.split("s", 1)[0].strip()
                        wait_for = float(sec_str)
                    except Exception:
                        pass

                # небольшая защита
                wait_for = max(5.0, min(wait_for + 1.0, 30.0))

                logging.warning(
                    "Rate limit (attempt %s/%s). Жду %.1f c и пробую ещё раз",
                    attempt, max_retries, wait_for
                )
                last_err = e
                await asyncio.sleep(wait_for)
                continue

            # это уже не лимит — пробрасываем выше
            raise

    # если все попытки умерли на rate limit
    raise last_err if last_err else RuntimeError("OpenAI rate limit, retries exhausted")


async def ensure_english_reply(reply_text: str, model: str) -> str:
    """Гарантирует английский ответ даже при русской истории и инструкциях планировщика."""
    text = (reply_text or "").strip()
    if not re.search(r"[А-Яа-яЁё]", text):
        return text
    try:
        response = await call_chat_with_retry(
            model=model,
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the supplied Telegram reply into natural English only. "
                        "Preserve its meaning, paragraph structure, HTML, URLs, emojis, and every "
                        "[SEND:id] tag exactly. Return only the translated reply."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        translated = (response.choices[0].message.content or "").strip()
        if translated and not re.search(r"[А-Яа-яЁё]", translated):
            logging.info("[language] translated non-English AI reply to English")
            return translated
        logging.error("[language] translation still contains Cyrillic")
    except Exception as exc:
        logging.exception("[language] failed to translate AI reply: %s", exc)
    return "Thanks for your message! I’ll explain everything clearly in English. What would you like to know first?"
async def call_affiliate_post(endpoint: str, payload: dict) -> dict | None:
    """
    Общий POST в affiliate-сервис.
    Возвращает dict-ответ или None при жёсткой ошибке.
    """
    url = AFFILIATE_BASE_URL.rstrip("/") + endpoint
    try:
        headers = {"X-Affiliate-Secret": AFFILIATE_API_SECRET}
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logging.warning("Affiliate POST %s failed: %s", endpoint, e)
        return None


async def check_registration_via_affiliate(
    tg_user_id: int,
    trader_id: str,
    bot: Bot | None = None,
    business_id: str | None = None,
) -> tuple[str, dict]:
    payload = {
        "bot_id": AFFILIATE_BOT_ID,
        "tg_user_id": tg_user_id,
        "trader_id": str(trader_id),
    }
    data = await call_affiliate_post("/affiliate/check-registration", payload)
    if not data:
        if bot:
            # пробуем достать username из таблицы users (как в company_mismatch)
            username_link = "Не указан"
            try:
                assert db_pool is not None
                async with db_pool.acquire() as conn, conn.cursor() as cur:
                    await cur.execute(
                        "SELECT username FROM users WHERE tg_user_id = %s",
                        (tg_user_id,),
                    )
                    row = await cur.fetchone()
                if row and row[0]:
                    uname = row[0]
                    username_link = f'<a href="https://t.me/{uname}">@{uname}</a>'
            except Exception as e:
                logging.warning(
                    "[affiliate_error] Не удалось получить username для %s: %s",
                    tg_user_id, e
                )

            details = (
                f"Tgid: {tg_user_id}\n"
                f"Указал Trader_id: {trader_id}\n"
            )

            text = (
                "⚠️ Ошибка при проверке регистрации!\n\n"
                "<b>Api не отвечает или не доступно.</b>\n\n"
                f"Username: {username_link}\n\n"
                f"<pre>{escape(details)}</pre>"
            )

            await notify_admins(text, bot, tg_user_id=tg_user_id)

        return "affiliate_error", {}

    success = bool(data.get("success"))
    code = (data.get("code") or "").strip()
    info = data.get("data") or {}

    logging.info(
        "[affiliate reg] tg=%s trader_id=%s success=%s code=%s",
        tg_user_id,
        trader_id,
        success,
        code,
    )

    # ====== УСПЕШНАЯ РЕГИСТРАЦИЯ ======
    if success and code == "registered":
        await update_trader_id_and_reg_status(
            tg_user_id,
            trader_id=trader_id,
            registration_status=1,
        )
        stage, notes = await get_user_state(tg_user_id)
        if stage in {STAGE_REG_LINK_SENT, STAGE_WAITING_ACCOUNT_ID, STAGE_ACCOUNT_ID_SENT}:
            new_notes = (notes or "") + f"\nРегистрация подтверждена по trader_id={trader_id}"
            await set_user_state(tg_user_id, STAGE_ACCOUNT_ID_OK, new_notes)

        return code, data

    # ====== company_mismatch (как было) ======
    if code == "company_mismatch":
        # 1. Пытаемся объяснить клиенту, но не роняем функцию при ошибке
        if bot and business_id:
            txt = (
                "Сейчас все проверю и вернусь с ответом 🤝"
            )
            try:
                sent = await bot.send_message(
                    chat_id=tg_user_id,
                    text=txt,
                    business_connection_id=business_id,
                )
                await save_message(sent.chat.id, "out", txt, is_business=True)
            except Exception as e:
                logging.warning(
                    "[company_mismatch] Не удалось отправить сообщение клиенту "
                    "tg_user_id=%s: %s",
                    tg_user_id, e
                )

        # 2. Отключаем бота для пользователя, но тоже не даём этому сломать уведомление админам
        try:
            await disable_bot_for_user(tg_user_id, "company_mismatch")
        except Exception as e:
            logging.warning(
                "[company_mismatch] Не удалось отключить бота для tg_user_id=%s: %s",
                tg_user_id, e
            )

        # 3. Всегда уведомляем админов, даже если клиенту ничего не ушло
        if bot:
            reg_date = info.get("reg_date")
            company_required = info.get("company_required")
            company_actual = info.get("company_actual")
            registration_link = info.get("registration_link")

            # пробуем достать username из таблицы users
            username_link = "Не указан"
            try:
                assert db_pool is not None
                async with db_pool.acquire() as conn, conn.cursor() as cur:
                    await cur.execute(
                        "SELECT username FROM users WHERE tg_user_id = %s",
                        (tg_user_id,),
                    )
                    row = await cur.fetchone()
                if row and row[0]:
                    uname = row[0]
                    username_link = f'<a href="https://t.me/{uname}">@{uname}</a>'
            except Exception as e:
                logging.warning(
                    "[company_mismatch] Не удалось получить username для %s: %s",
                    tg_user_id, e
                )

            details = (
                f"Trader ID:              {trader_id}\n"
                f"Дата регистрации:       {reg_date}\n"
                f"Наша компания:          {company_required}\n"
                f"Фактическая компания:   {company_actual}\n"
                f"registration_link:     {registration_link}\n"
            )

            text = (
                f"👤 Tgid: <code>{tg_user_id}</code>\n"
                f"👤 Username: {username_link}\n\n"
                "<b>Пользователь зарегистрирован в другой компании!</b>\n\n"
                f"<pre>{escape(details)}</pre>\n\n"
                "Бот для этого клиента автоматически выключен."
            )

            await notify_admins(text, bot, tg_user_id=tg_user_id)

        return code, data

    # ====== НОВОЕ: user_not_found ======
    if code == "user_not_found":
        if bot and business_id:
            try:
                intro_text = (
                    "По этому ID кабинет не найден.\n\n"
                    "Скорее всего, аккаунт зарегистрирован не по моей ссылке. "
                    "Тогда давай сразу сделаем новый аккаунт по моей ссылке, а после регистрации ты пришлёшь мне свой Trader ID 🤝"
                )
                sent = await bot.send_message(
                    chat_id=tg_user_id,
                    text=intro_text,
                    business_connection_id=business_id,
                )
                await save_message(sent.chat.id, "out", intro_text, is_business=True)
                await send_registration_start_message(tg_user_id, business_id, bot)
            except Exception as e:
                logging.warning(
                    "[user_not_found] Не удалось отправить сообщение клиенту "
                    "tg_user_id=%s: %s",
                    tg_user_id, e
                )
        return code, data

    # ====== НОВОЕ: pocket_error / unknown_bot_id ======
    if code in ("unknown_bot_id", "pocket_error"):
        # 1) Пишем клиенту
        if bot and business_id:
            txt = "Спасибо, подожди пожалуйста, я проверю и вернусь"
            try:
                sent = await bot.send_message(
                    chat_id=tg_user_id,
                    text=txt,
                    business_connection_id=business_id,
                )
                await save_message(sent.chat.id, "out", txt, is_business=True)
            except Exception as e:
                logging.warning(
                    "[reg_error_msg] Не удалось отправить сообщение клиенту "
                    "tg_user_id=%s: %s",
                    tg_user_id, e
                )

        if bot:
            await notify_admins(
                "⚠️ Проблема при /affiliate/check-registration.\n"
                f"tg_user_id: {tg_user_id}\n"
                f"trader_id: {trader_id}\n"
                f"code: {code}\n"
                f"raw: {data}",
                bot,
            )

        return code, data

    if code == "trader_id_in_use" and bot:
        username_link = "Не указан"
        try:
            assert db_pool is not None
            async with db_pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute(
                    "SELECT username FROM users WHERE tg_user_id = %s",
                    (tg_user_id,),
                )
                row = await cur.fetchone()
            if row and row[0]:
                uname = row[0]
                username_link = f'<a href="https://t.me/{uname}">@{uname}</a>'
        except Exception as e:
            logging.warning(
                "[trader_id_in_use] Не удалось получить username для %s: %s",
                tg_user_id, e
            )

        other_tg_id = None
        raw_message = (data.get("message") or "").strip()
        marker = "tg_user_id="
        idx = raw_message.find(marker)
        if idx != -1:
            idx += len(marker)
            digits = []
            while idx < len(raw_message) and raw_message[idx].isdigit():
                digits.append(raw_message[idx])
                idx += 1
            if digits:
                try:
                    other_tg_id = int("".join(digits))
                except ValueError:
                    other_tg_id = None

        other_username_link = "Не указан"
        if other_tg_id:
            try:
                assert db_pool is not None
                async with db_pool.acquire() as conn, conn.cursor() as cur:
                    await cur.execute(
                        "SELECT username FROM users WHERE tg_user_id = %s",
                        (other_tg_id,),
                    )
                    row = await cur.fetchone()
                if row and row[0]:
                    uname2 = row[0]
                    other_username_link = f'<a href="https://t.me/{uname2}">@{uname2}</a>'
            except Exception as e:
                logging.warning(
                    "[trader_id_in_use] Не удалось получить username владельца %s: %s",
                    other_tg_id, e
                )

        details = (
            f"Tgid: {tg_user_id}\n"
            f"Trader_id: {trader_id}\n"
        )
        if other_tg_id:
            details += f"Привязан к: {other_tg_id}\n"

        text = (
            "⚠️ Ошибка при проверке регистрации!\n\n"
            "Trader ID уже привязан к другому пользователю. Похоже, пытаются обойти систему.\n\n"
            f"Username: {username_link}\n\n"
            f"<pre>{escape(details)}</pre>"
        )

        if other_tg_id:
            text += (
                f"Владелец: {other_username_link}"
            )

        await notify_admins(text, bot, tg_user_id=tg_user_id)

    elif code == "registration_not_confirmed" and bot:
        await notify_admins(
            "⚠️ Проблема при /affiliate/check-registration.\n"
            f"tg_user_id: {tg_user_id}\n"
            f"trader_id: {trader_id}\n"
            f"code: {code}\n"
            f"raw: {data}",
            bot,
        )

    return code or "unknown", data

async def check_deposit_via_affiliate(tg_user_id: int, bot: Bot) -> tuple[str, float, float]:
    payload = {
        "bot_id": AFFILIATE_BOT_ID,
        "tg_user_id": tg_user_id,
    }

    data = await call_affiliate_post("/affiliate/check-deposit", payload)
    if not data:
        return "error", 0.0, 0.0

    code = data.get("code", "error")
    d = data.get("data") or {}

    sum_deposits = float(d.get("sum_deposits") or 0.0)
    min_deposit = float(d.get("min_deposit") or 0.0)

    logging.info(
        "[affiliate dep] tg=%s code=%s sum=%.2f min=%.2f",
        tg_user_id, code, sum_deposits, min_deposit
    )

    # Депозит подтверждён
    if data.get("success") and code in ("confirmed", "already_confirmed"):
        await update_deposit_status(tg_user_id, 1)
        stage, notes = await get_user_state(tg_user_id)

        if stage in {STAGE_WAITING_DEPOSIT, STAGE_ACCOUNT_ID_OK, STAGE_DEPOSIT_DONE}:
            new_notes = (notes or "") + "\nДепозит подтверждён через affiliate API"
            await set_user_state(tg_user_id, STAGE_DEPOSIT_DONE, new_notes)

    # Ниже минимального порога — НИЧЕГО НЕ ОТПРАВЛЯЕМ КЛИЕНТУ
    elif code == "below_threshold":
        # просто возвращаем код, сумма и минималку,
        # чтобы основная логика могла передать это ИИ
        return "below_threshold", sum_deposits, min_deposit

    return code, sum_deposits, min_deposit

    
async def generate_ai_reply(
    tg_user_id: int,
    user_text: str,
    bot: Bot,
    plan: dict | None = None,
) -> str:

    global ai_system_prompt, ai_enabled, ai_model
    fallback_text = "Простите, сейчас большая нагрузка, вернусь к вам через пару минут 🙏"
    if not ai_client or not ai_enabled:
        # уведомляем админов
        for admin_id in RUNTIME_ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    (
                        "⚠️ ИИ не смог ответить клиенту.\n"
                        f"tg_user_id: {tg_user_id}\n"
                        f"Текст клиента: {user_text[:1000]}"
                    ),
                )
            except Exception as e:
                logging.warning("Ошибка отправки уведомления админу: %s", e)

        return fallback_text

    assert db_pool is not None

    try:
        # история сообщений (как и раньше)
        rows = await get_last_messages(tg_user_id, limit=20)
        history: list[dict] = []
        for direction, text, created_at in reversed(rows):
            if not text:
                continue
            role = "user" if direction == "in" else "assistant"
            history.append({"role": role, "content": text})

        # долгосрочная память + статусы
        long_memory = await get_user_memory(tg_user_id)
        stage, notes = await get_user_state(tg_user_id)
        reg_status, dep_status, country = await get_user_status_flags(tg_user_id)

        logging.info(
            "[generate_ai_reply] user=%s stage=%s reg=%s dep=%s country=%s text=%r",
            tg_user_id,
            stage,
            reg_status,
            dep_status,
            country,
            user_text,
        )

        # Короткая безопасная подсказка по текущему этапу.
        stage_hint_map = {
            STAGE_NEW: "Клиент только начал диалог. Можно использовать стартовое знакомство.",
            STAGE_NAME_KNOWN: "Имя клиента уже известно. Не начинай знакомство заново.",
            STAGE_REG_LINK_SENT: "Ссылка на регистрацию уже отправлялась. Уточняй прогресс.",
            STAGE_WAITING_ACCOUNT_ID: "Ранее уже просили Trader ID. Мягко напомни про него.",
            STAGE_ACCOUNT_ID_SENT: "Trader ID уже присылали. Дальше по логике идёт проверка аккаунта.",
            STAGE_ACCOUNT_ID_OK: "Trader ID подтверждён. Следующий шаг — депозит и сопровождение.",
            STAGE_WAITING_DEPOSIT: "Ждём депозит. Помогай довести клиента до пополнения.",
            STAGE_DEPOSIT_DONE: "Депозит подтверждён. Веди дальше как участника команды.",
        }
        stage_hint = stage_hint_map.get(stage, "Продолжай диалог по текущему этапу, не откатываясь к началу.")

        status_instructions = (
            f"Текущие статусы клиента:\n"
            f"- stage = {stage}\n"
            f"- registration_status = {reg_status}\n"
            f"- deposit_status = {dep_status}\n"
            f"- country = {country or 'не указана'}\n"
            "- денежные условия и точные суммы сообщает только личный менеджер\n\n"
            "Правила:\n"
            "- Не противоречь статусам из БД.\n"
            "- Если registration_status = 1, не говори, что регистрация не найдена.\n"
            "- Если registration_status = 0, можно вести к регистрации по ссылке.\n"
            "- Если deposit_status = 1, не говори, что депозит ещё не подтверждён.\n"
            "- Если deposit_status = 0, можно вести к пополнению, но не называй конкретных сумм.\n"
            "- По всем денежным условиям отправляй к личному менеджеру.\n"
            "- Если клиент спрашивает, из какой ты страны, отвечай, что ты из Беларуси.\n"
        )

        state_description = (
            f"Информация о клиенте:\n"
            f"- Имя бота: {bot_name}\n"
            f"- Этап воронки: {stage}\n"
            f"- Подсказка по этапу: {stage_hint}\n"
            f"- Заметки: {notes or 'нет заметок'}\n\n"
            f"{status_instructions}"
        )

        messages: list[dict] = [
            {"role": "system", "content": ai_system_prompt},
            {
                "role": "system",
                "content": (
                    f"Тебя зовут {bot_name}. Если клиент спрашивает, как тебя зовут или кто ты, "
                    "используй это имя и отвечай от первого лица."
                ),
            },
            {
                "role": "system",
                "content": (
                    "Если клиент спрашивает, из какой ты страны, откуда ты или где ты находишься, "
                    "отвечай коротко и уверенно, что ты из Беларуси."
                ),
            },
        ]

        messages.append({"role": "system", "content": await get_funnel_routing_prompt()})

        if long_memory:
            messages.append({
                "role": "system",
                "content": (
                    "Краткая сводка по этому клиенту из прошлых диалогов:\n"
                    f"{long_memory}\n\n"
                    "Учитывай эту информацию и не противоречь ей."
                ),
            })

        messages.append({"role": "system", "content": state_description})

        if plan:
            main_prompt = (plan.get("main_prompt") or "").strip()
            tone = (plan.get("tone") or "").strip()
            if main_prompt:
                messages.append({
                    "role": "system",
                    "content": f"Дополнительная задача от планировщика:\n{main_prompt}",
                })
            if tone:
                messages.append({
                    "role": "system",
                    "content": f"Желаемый тон ответа: {tone}.",
                })

        # история и текущий запрос
        messages.extend(history)
        messages.append({
            "role": "system",
            "content": (
                "FINAL OUTPUT LANGUAGE RULE: Reply only in natural English. "
                "Do not use Russian or any other language, even if the user or conversation history does."
            ),
        })
        messages.append({"role": "user", "content": user_text})

        resp = await call_chat_with_retry(
            messages=messages,
            model=ai_model,
            temperature=0.4,
        )

        reply = (resp.choices[0].message.content or "").strip()
        reply = await ensure_english_reply(reply, ai_model)

        selected_media_key, _, _ = split_funnel_reply(reply)
        if stage == STAGE_NEW and not selected_media_key:
            selected_media_key = await get_next_unsent_funnel_media_key(tg_user_id, "A")
            if selected_media_key:
                reply = f"[SEND:{selected_media_key}]\n\n{reply}"
                logging.info(
                    "[funnel media] inserted required cold-stage media %s for user %s",
                    selected_media_key,
                    tg_user_id,
                )

        # обновляем этап воронки на основе диалога
        try:
            await update_user_stage_from_exchange(
                tg_user_id=tg_user_id,
                user_text=user_text,
                ai_reply=reply,
                get_user_state=get_user_state,
                get_user_status_flags=get_user_status_flags,
                set_user_state=set_user_state,
            )
        except Exception as upd_err:
            logging.warning("Ошибка обновления user_state: %s", upd_err)

        return reply

    except Exception as e:
        logging.error("Ошибка при запросе к OpenAI: %s", e)

        for admin_id in RUNTIME_ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    (
                        "⚠️ Ошибка ИИ при ответе клиенту.\n"
                        f"tg_user_id: {tg_user_id}\n"
                        f"Текст клиента: {user_text[:1000]}\n"
                        f"Ошибка: {e}"
                    ),
                )
            except Exception as e2:
                logging.warning("Ошибка отправки уведомления админу: %s", e2)

        return fallback_text
        
# ================== ЛОГИКА ВРЕМЕНИ РАБОТЫ ==================


def is_bot_active_now() -> bool:
    if not work_enabled_manual:
        return False
    return is_in_schedule_now()

async def update_work_enabled(enabled: bool):
    global work_enabled_manual
    assert db_pool is not None

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE settings SET is_enabled = %s WHERE id = 1",
            (1 if enabled else 0,),
        )

    work_enabled_manual = enabled
    
async def work_monitor(bot: Bot):
    global is_working_flag, session_clients, session_out_messages

    while True:
        active = is_in_schedule_now() 

        if is_working_flag is None:
            # первый запуск
            is_working_flag = active
        elif active != is_working_flag:
            # смена статуса
            if not active and is_working_flag:
                # только что ЗАКОНЧИЛИ смену
                clients_count = len(session_clients)
                msgs_count = session_out_messages
                text = (
                    "⏱️ Смена завершена.\n"
                    f"Клиентов обработано: {clients_count}\n"
                    f"Отправлено сообщений: {msgs_count}"
                )
                for admin_id in RUNTIME_ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, text)
                    except Exception as e:
                        print("Error notifying admin:", e)
                session_clients.clear()
                session_out_messages = 0
            else:
                # только что НАЧАЛИ смену – просто сбрасываем счётчики
                session_clients.clear()
                session_out_messages = 0

            is_working_flag = active

        await asyncio.sleep(30)


async def runtime_settings_refresh_worker():
    global work_start, work_end, work_enabled_manual
    global ai_system_prompt, ai_enabled, ai_model, bot_name
    global KV_CACHE, KV_CACHE_LOADED_AT
    global ai_client, active_openai_api_key

    while True:
        await asyncio.sleep(10)
        if db_pool is None:
            continue
        try:
            async with db_pool.acquire() as conn, conn.cursor() as cur:
                await cur.execute("SELECT work_start, work_end, is_enabled FROM settings WHERE id = 1")
                settings_row = await cur.fetchone()
                await cur.execute(
                    "SELECT system_prompt, enabled, model, openai_api_key FROM ai_settings WHERE id = 1"
                )
                ai_row = await cur.fetchone()
                await cur.execute("SELECT svalue FROM kv_settings WHERE skey = 'BOT_NAME'")
                name_row = await cur.fetchone()

            if settings_row:
                work_start = to_time(settings_row[0]) if settings_row[0] is not None else None
                work_end = to_time(settings_row[1]) if settings_row[1] is not None else None
                work_enabled_manual = bool(settings_row[2])
            if ai_row:
                ai_system_prompt = ai_row[0] or ""
                ai_enabled = bool(ai_row[1])
                ai_model = ai_row[2] or "gpt-4.1"
                next_openai_api_key = (ai_row[3] or OPENAI_API_KEY or "").strip()
                if next_openai_api_key != active_openai_api_key:
                    ai_client = AsyncOpenAI(api_key=next_openai_api_key) if next_openai_api_key else None
                    active_openai_api_key = next_openai_api_key
                    logging.info(
                        "OpenAI client reconfigured from admin settings: configured=%s",
                        bool(next_openai_api_key),
                    )
            if name_row:
                bot_name = name_row[0] or "Elizabeth Vane"

            KV_CACHE = {}
            KV_CACHE_LOADED_AT = None
            await refresh_admin_ids_cache()
        except Exception as exc:
            logging.warning("Runtime settings refresh failed: %s", exc)


# ================== ОБРАБОТЧИКИ БИЗНЕС-СОБЫТИЙ ==================


async def mark_business_message_read(msg: Message, bot: Bot):
    business_id = msg.business_connection_id
    if not business_id:
        return
    try:
        await bot(
            ReadBusinessMessage(
                business_connection_id=business_id,
                chat_id=msg.chat.id,
                message_id=msg.message_id,
            )
        )
    except Exception as exc:
        logging.warning(
            "[business read] failed for chat=%s message=%s: %s",
            msg.chat.id,
            msg.message_id,
            exc,
        )


@router.business_connection()
async def on_business_connection(connection: BusinessConnection):
    print(
        f"[BUSINESS_CONNECTION] id={connection.id}, "
        f"user_chat_id={connection.user_chat_id}, "
        f"can_reply={connection.can_reply}"
    )


@router.business_message(F.text)
async def on_business_message(msg: Message, bot: Bot):
    if msg.text and msg.text.startswith("/"):
        return

    message_kind = get_business_message_kind(msg, bot)
    if message_kind == "bot_out":
        return

    if message_kind == "manual_out":
        mark_manual_takeover(msg.chat.id)
        await ensure_user_exists(msg.chat.id)
        saved = await save_message(msg.chat.id, "out", msg.text or "", is_business=True)
        if saved:
            await passive_sync_user_context(msg.chat.id, outgoing_text=msg.text or "")
        return

    if await has_recent_matching_outgoing_business_message(msg.chat.id, msg.text or ""):
        return

    await mark_business_message_read(msg, bot)
    await save_user_from_message(msg)
    await save_message(msg.chat.id, "in", msg.text or "", is_business=True)
    await passive_sync_user_context(msg.chat.id, incoming_text=msg.text or "")

    if not await is_user_bot_active(msg.chat.id):
        return

    if not is_bot_active_now():
        return

    if is_manual_takeover_active(msg.chat.id):
        return

    schedule_business_reply(msg, bot)
    
@router.business_message(F.voice)
async def on_business_voice(msg: Message, bot: Bot):
    tg_id = msg.chat.id
    business_id = msg.business_connection_id

    if not business_id:
        return

    message_kind = get_business_message_kind(msg, bot)
    if message_kind != "incoming":
        return

    await mark_business_message_read(msg, bot)

    if not await is_user_bot_active(tg_id):
        await save_message(
            tg_id,
            "in",
            "(голосовое сообщение, бот для пользователя отключён)",
            is_business=True,
        )
        return
        
    # Создаём/обновляем пользователя
    await save_user_from_message(msg)

    # Если бот "отдыхает" — ничего не транскрибируем и не отвечаем
    if not is_bot_active_now():
        await save_message(
            tg_id,
            "in",
            "(голосовое сообщение, получено вне рабочего времени)",
            is_business=True,
        )
        return

    # Пытаемся расшифровать голосовое
    text = await transcribe_voice_to_text(msg, bot)
    if not text:
        # Если не смогли — просто сохраняем факт голосового и молчим/или пишем ошибку
        await save_message(
            tg_id,
            "in",
            "(не удалось расшифровать голосовое сообщение)",
            is_business=True,
        )
        # Можно отправить клиенту ответ:
        # await bot.send_message(tg_id, "Не смог расшифровать голосовое, можешь написать текстом?")
        return

    # Сохраняем уже расшифрованное сообщение как входящее
    await save_message(
        tg_id,
        "in",
        f"(голосовое) {text}",
        is_business=True,
    )
    await passive_sync_user_context(tg_id, incoming_text=text)

    if is_manual_takeover_active(tg_id):
        return

    # И сразу отвечаем через ИИ, используя общий хелпер
    await send_business_ai_reply(tg_id, business_id, text, bot)

# ================== ОБЫЧНЫЕ СООБЩЕНИЯ БОТУ ==================


@router.message(F.text.regexp(r"(?i)^привет$"))
async def on_regular_message(msg: Message):
    global session_clients, session_out_messages

    await save_user_from_message(msg)
    await save_message(msg.chat.id, "in", msg.text or "", is_business=False)

    if not is_bot_active_now():
        return

    reply_text = "Привет (обычный чат, не бизнес)"
    sent = await msg.answer(reply_text)
    await save_message(sent.chat.id, "out", reply_text, is_business=False)

    session_clients.add(sent.chat.id)
    session_out_messages += 1


async def transcribe_voice_to_text(msg: Message, bot: Bot) -> str | None:
    if not ai_client:
        return None

    if not msg.voice:
        return None

    buf = BytesIO()
    try:
        await bot.download(msg.voice, buf)
    except Exception as e:
        logging.warning("Не удалось скачать голосовое: %s", e)
        return None

    buf.seek(0)
    # 👉 иногда полезно задать имя файла, чтобы SDK не ругался
    if not hasattr(buf, "name"):
        buf.name = "voice.ogg"

    try:
        tr = await ai_client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=buf,
        )
        text = (tr.text or "").strip()
        return text or None
    except Exception as e:
        logging.warning("Ошибка расшифровки голосового: %s", e)
        return None


async def get_funnel_media_for_user(tg_user_id: int, media_key: str) -> dict | None:
    settings = await load_kv_settings()
    if settings.get("FUNNEL_MEDIA_ENABLED", "1") != "1":
        return None
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute(
            """
            SELECT media_key, title, file_name, telegram_file_id
            FROM funnel_media
            WHERE media_key = %s AND enabled = 1
            LIMIT 1
            """,
            (media_key,),
        )
        row = await cur.fetchone()
        if not row:
            return None
        await cur.execute(
            "SELECT 1 FROM funnel_media_sent WHERE tg_user_id = %s AND media_key = %s LIMIT 1",
            (tg_user_id, media_key),
        )
        if await cur.fetchone():
            logging.info("[funnel media] skip repeated %s for user %s", media_key, tg_user_id)
            return None
    return row


async def mark_funnel_media_sent(tg_user_id: int, media_key: str, telegram_file_id: str | None):
    assert db_pool is not None
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT IGNORE INTO funnel_media_sent (tg_user_id, media_key) VALUES (%s, %s)",
            (tg_user_id, media_key),
        )
        if telegram_file_id:
            await cur.execute(
                "UPDATE funnel_media SET telegram_file_id = %s WHERE media_key = %s",
                (telegram_file_id, media_key),
            )


async def prepare_square_video_note(source_path: str) -> str | None:
    """Конвертирует исходный MP4 в квадратный H.264 для Telegram video note."""
    source_path = os.path.abspath(source_path)
    output_dir = os.path.join(os.path.dirname(source_path), ".video_notes")
    output_path = os.path.join(output_dir, os.path.basename(source_path))
    lock = video_note_prepare_locks.setdefault(output_path, asyncio.Lock())

    async with lock:
        try:
            if (
                os.path.isfile(output_path)
                and os.path.getsize(output_path) > 1024
                and os.path.getmtime(output_path) >= os.path.getmtime(source_path)
            ):
                return output_path
        except OSError:
            pass

        os.makedirs(output_dir, exist_ok=True)
        temp_path = f"{output_path}.tmp.mp4"
        filter_graph = (
            "crop=w='min(iw,ih)':h='min(iw,ih)':"
            "x='(iw-ow)/2':y='(ih-oh)*0.15',scale=512:512:flags=lanczos"
        )
        command = (
            "ffmpeg", "-y", "-v", "error", "-i", source_path,
            "-map", "0:v:0", "-map", "0:a?", "-t", "59",
            "-vf", filter_graph,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart", temp_path,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                logging.error(
                    "[funnel media] ffmpeg failed for %s: %s",
                    source_path,
                    stderr.decode("utf-8", "replace")[-2000:],
                )
                return None
            os.replace(temp_path, output_path)
            return output_path
        except FileNotFoundError:
            logging.error("[funnel media] ffmpeg is not installed")
            return None
        except Exception as exc:
            logging.exception("[funnel media] conversion failed for %s: %s", source_path, exc)
            return None
        finally:
            if os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass


async def send_funnel_video_note(
    tg_user_id: int,
    business_id: str,
    media_key: str,
    bot: Bot,
    reply_markup=None,
) -> Message | None:
    media = await get_funnel_media_for_user(tg_user_id, media_key)
    if not media:
        return None

    file_name = os.path.basename(str(media.get("file_name") or ""))
    media_root = os.path.abspath(FUNNEL_MEDIA_DIR)
    file_path = os.path.abspath(os.path.join(media_root, file_name))
    if os.path.commonpath((media_root, file_path)) != media_root or not os.path.isfile(file_path):
        logging.error("[funnel media] file missing for %s: %s", media_key, file_path)
        return None

    video_note_path = await prepare_square_video_note(file_path)
    if not video_note_path:
        return None

    async def send(video_note):
        return await bot.send_video_note(
            chat_id=tg_user_id,
            video_note=video_note,
            business_connection_id=business_id,
            reply_markup=reply_markup,
        )

    sent = None
    cached_file_id = str(media.get("telegram_file_id") or "").strip()
    if cached_file_id:
        try:
            sent = await send(cached_file_id)
            if not sent.video_note:
                logging.warning(
                    "[funnel media] cached file_id is not a video note for %s; uploading normalized file",
                    media_key,
                )
                sent = None
        except Exception as exc:
            logging.warning("[funnel media] cached file_id failed for %s: %s", media_key, exc)
    if sent is None:
        try:
            sent = await send(FSInputFile(video_note_path))
        except Exception as exc:
            logging.exception("[funnel media] upload failed for %s: %s", media_key, exc)
            return None

    telegram_file_id = sent.video_note.file_id if sent.video_note else None
    if not telegram_file_id:
        logging.error("[funnel media] Telegram returned no video_note for %s", media_key)
        return None
    await mark_funnel_media_sent(tg_user_id, media_key, telegram_file_id)
    await save_message(sent.chat.id, "out", f"[Кружок {media_key.upper()}]", is_business=True)
    return sent


async def send_ai_reply_with_funnel_media(
    tg_user_id: int,
    business_id: str,
    reply_text: str,
    bot: Bot,
    reply_markup=None,
) -> tuple[int | None, int]:
    media_key, before, after = split_funnel_reply(reply_text)
    if not media_key:
        sent = await bot.send_message(
            chat_id=tg_user_id,
            text=reply_text,
            business_connection_id=business_id,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
        await save_message(sent.chat.id, "out", reply_text, is_business=True)
        return sent.chat.id, 1

    sent_chat_id = None
    sent_count = 0

    if before:
        sent = await bot.send_message(
            chat_id=tg_user_id,
            text=before,
            business_connection_id=business_id,
            parse_mode=ParseMode.HTML,
        )
        await save_message(sent.chat.id, "out", before, is_business=True)
        sent_chat_id, sent_count = sent.chat.id, sent_count + 1

    if not is_manual_takeover_active(tg_user_id):
        sent_media = await send_funnel_video_note(
            tg_user_id,
            business_id,
            media_key,
            bot,
            reply_markup=reply_markup if not after else None,
        )
        if sent_media:
            sent_chat_id, sent_count = sent_media.chat.id, sent_count + 1

    if after and not is_manual_takeover_active(tg_user_id):
        sent = await bot.send_message(
            chat_id=tg_user_id,
            text=after,
            business_connection_id=business_id,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
        await save_message(sent.chat.id, "out", after, is_business=True)
        sent_chat_id, sent_count = sent.chat.id, sent_count + 1

    return sent_chat_id, sent_count
    
async def send_business_ai_reply(
    tg_user_id: int,
    business_id: str,
    user_text: str,
    bot: Bot,
):

    global session_clients, session_out_messages

    # 0. Если бот для этого пользователя уже отключён – ничего не делаем
    if not await is_user_bot_active(tg_user_id):
        return

    if is_manual_takeover_active(tg_user_id):
        return

    stage, _ = await get_user_state(tg_user_id)
    reg_status, dep_status, country = await get_user_status_flags(tg_user_id)

    if reg_status == 0:
        global_matches = await check_user_globally_via_affiliate(tg_user_id)
        registered_match = next(
            (match for match in global_matches if int(match.get("registration_status") or 0) == 1),
            None,
        )
        if registered_match:
            await send_cross_project_hold_and_notify(
                tg_user_id=tg_user_id,
                business_id=business_id,
                bot=bot,
                match=registered_match,
            )
            return

        has_pending_external_account = bool(global_matches)
    else:
        global_matches = []
        has_pending_external_account = False

    if stage == STAGE_WAITING_PLATFORM_ACCOUNT:
        trader_id = extract_trader_id(user_text)
        if trader_id:
            code, _ = await check_registration_via_affiliate(
                tg_user_id,
                trader_id,
                bot=bot,
                business_id=business_id,
            )
            if code in {
                "user_not_found",
                "unknown_bot_id",
                "pocket_error",
                "affiliate_error",
                "company_mismatch",
            }:
                asyncio.create_task(update_user_memory(tg_user_id))
                return

            if code == "registered":
                confirm_text = (
                    "Отлично, аккаунт вижу 🤝\n\nТеперь нужно пополнить баланс, "
                    "и после этого мы продолжим дальше. Точные условия и сумму подскажет твой личный менеджер."
                )
                sent = await bot.send_message(
                    chat_id=tg_user_id,
                    business_connection_id=business_id,
                    text=confirm_text,
                )
                await save_message(sent.chat.id, "out", confirm_text, is_business=True)
                _, notes = await get_user_state(tg_user_id)
                new_notes = (notes or "") + ("\n" if notes else "") + "Trader ID подтвержден сразу после вопроса про наличие аккаунта"
                await set_user_state(tg_user_id, STAGE_WAITING_DEPOSIT, new_notes)
                session_clients.add(tg_user_id)
                session_out_messages += 1
                asyncio.create_task(update_user_memory(tg_user_id))
                return

        answer = detect_platform_account_answer(user_text)
        if answer == "yes":
            await send_existing_account_trader_id_request(tg_user_id, business_id, bot)
            session_clients.add(tg_user_id)
            session_out_messages += 1
            asyncio.create_task(update_user_memory(tg_user_id))
            return
        if answer == "no":
            await send_registration_start_message(tg_user_id, business_id, bot)
            session_clients.add(tg_user_id)
            session_out_messages += 1
            asyncio.create_task(update_user_memory(tg_user_id))
            return

        clarify_text = "Напиши, пожалуйста, просто да или нет 🤝"
        sent = await bot.send_message(
            chat_id=tg_user_id,
            business_connection_id=business_id,
            text=clarify_text,
        )
        await save_message(sent.chat.id, "out", clarify_text, is_business=True)
        session_clients.add(tg_user_id)
        session_out_messages += 1
        return

    if stage == STAGE_WAITING_EXISTING_ACCOUNT_TRADER_ID:
        trader_id = extract_trader_id(user_text)
        if not trader_id:
            reminder_text = "Пришли, пожалуйста, только Trader ID без лишнего текста 🤝"
            sent = await bot.send_message(
                chat_id=tg_user_id,
                business_connection_id=business_id,
                text=reminder_text,
            )
            await save_message(sent.chat.id, "out", reminder_text, is_business=True)
            session_clients.add(tg_user_id)
            session_out_messages += 1
            return

        code, _ = await check_registration_via_affiliate(
            tg_user_id,
            trader_id,
            bot=bot,
            business_id=business_id,
        )
        if code in {
            "user_not_found",
            "unknown_bot_id",
            "pocket_error",
            "affiliate_error",
            "company_mismatch",
        }:
            asyncio.create_task(update_user_memory(tg_user_id))
            return

        if code == "registered":
            confirm_text = (
                "Отлично, аккаунт вижу 🤝\n\nТеперь нужно пополнить баланс, "
                "и после этого мы продолжим дальше. Точные условия и сумму подскажет твой личный менеджер."
            )
            sent = await bot.send_message(
                chat_id=tg_user_id,
                business_connection_id=business_id,
                text=confirm_text,
            )
            await save_message(sent.chat.id, "out", confirm_text, is_business=True)
            _, notes = await get_user_state(tg_user_id)
            new_notes = (notes or "") + ("\n" if notes else "") + "Trader ID подтвержден после кросс-проверки"
            await set_user_state(tg_user_id, STAGE_WAITING_DEPOSIT, new_notes)
            session_clients.add(tg_user_id)
            session_out_messages += 1
            asyncio.create_task(update_user_memory(tg_user_id))
            return

    if await handle_keyword_trigger(
        tg_user_id=tg_user_id,
        business_id=business_id,
        user_text=user_text,
        bot=bot,
        save_message=save_message,
        db_pool=db_pool,
        notify_admins=notify_admins,
        get_user_status_flags=get_user_status_flags,
        disable_bot_for_user=disable_bot_for_user,
        get_trader_id_for_user=get_trader_id_for_user,
        update_user_memory=update_user_memory,
    ):
        return
        
    # 1. Текущий статус + память – нужны планировщику
    long_memory = await get_user_memory(tg_user_id)

    if should_skip_ack_reply(user_text, stage):
        logging.info(
            "[silent_ack] skip auto-reply for user=%s stage=%s text=%r",
            tg_user_id,
            stage,
            user_text,
        )
        return

    plan = await plan_conversation(
        tg_user_id=tg_user_id,
        user_text=user_text,
        stage=stage,
        reg_status=reg_status,
        dep_status=dep_status,
        country=country,
        long_memory=long_memory,
    )

    if stage == STAGE_NAME_KNOWN and reg_status == 0:
        await send_platform_account_question(tg_user_id, business_id, bot)
        session_clients.add(tg_user_id)
        session_out_messages += 1
        asyncio.create_task(update_user_memory(tg_user_id))
        return

    original_intent = (plan.get("intent") or "").strip()

    logging.info(
        "[vip_check] user=%s intent=%s reg=%s dep=%s",
        tg_user_id,
        original_intent,
        reg_status,
        dep_status,
    )

    if original_intent == "VERIFICATION_DONE" and reg_status == 1 and dep_status == 1:
        logging.info("[vip_check] starting VIP onboarding on VERIFICATION_DONE for %s", tg_user_id)
        await send_vip_onboarding_flow(
            tg_user_id,
            business_id,
            bot,
            save_message,
            get_user_state,
            set_user_state,
        )
        asyncio.create_task(update_user_memory(tg_user_id))
        return

    if original_intent == "READY_TO_START" and reg_status == 1 and dep_status == 1:
        _, notes = await get_user_state(tg_user_id)
        if not notes or "VIP доступ выдан" not in (notes or ""):
            logging.info("[vip_check] starting VIP onboarding on READY_TO_START for %s", tg_user_id)
            await send_vip_onboarding_flow(
                tg_user_id,
                business_id,
                bot,
                save_message,
                get_user_state,
                set_user_state,
            )
            asyncio.create_task(update_user_memory(tg_user_id))
            return

    actions: list[str] = plan.get("actions") or []
    
    if original_intent == "GREETING_FLOW":
        await send_greeting_flow(
            tg_user_id=tg_user_id,
            business_id=business_id,
            bot=bot,
            save_message=save_message,
            set_user_state=set_user_state,
            stage_name_known=STAGE_NAME_KNOWN,
        )

        session_clients.add(tg_user_id)
        session_out_messages += 2

        asyncio.create_task(update_user_memory(tg_user_id))
        return

    actions: list[str] = plan.get("actions") or []
    
    actions = [str(a) for a in actions]

    add_register_button = False
    existing_flow_started = False
    skip_ai_reply = False  

    for action in actions:
        if action == "CHECK_REGISTRATION_API":
            trader_id = await get_trader_id_for_user(tg_user_id)

            if not trader_id:
                parsed_id = extract_trader_id(user_text)
                if parsed_id:
                    trader_id = parsed_id
                    logging.info(
                        "[plan] CHECK_REGISTRATION_API: trader_id взяли из текста (%s) для user %s",
                        trader_id, tg_user_id,
                    )

            if not trader_id:
                logging.info(
                    "[plan] CHECK_REGISTRATION_API, но trader_id у user %s не найден ни в БД, ни в тексте",
                    tg_user_id,
                )
            else:
                code, _ = await check_registration_via_affiliate(
                    tg_user_id,
                    trader_id,
                    bot=bot,
                    business_id=business_id,
                )

                # если уже отправили клиенту сервисное сообщение — второй раз не отвечаем
                if code in (
                    "user_not_found",
                    "unknown_bot_id",
                    "pocket_error",
                    "affiliate_error",
                    "company_mismatch",
                ):
                    skip_ai_reply = True

        elif action == "CHECK_DEPOSIT_API":
            code, _sum_deposits, _min_deposit = await check_deposit_via_affiliate(tg_user_id, bot)

            if code == "below_threshold":
                plan = {
                    "intent": "DEPOSIT_BELOW_THRESHOLD",
                    "actions": [],
                    "main_prompt": (
                        "Affiliate API показал, что депозит клиента найден, "
                        "но он пока ниже необходимого порога.\n\n"
                        "Основной ИИ должен сказать клиенту примерно так:\n"
                        "«Вижу твоё пополнение, но пока нужно пополнить ещё немного. "
                        "Точные условия и сумму подскажет твой личный менеджер 🙂»"
                    ),
                    "tone": "friendly_short",
                }

        elif action == "ADD_REGISTER_LINK_BUTTON":
            add_register_button = True

        elif action == "START_EXISTING_ACCOUNT_FLOW":
            await send_existing_account_flow(
                tg_user_id=tg_user_id,
                business_id=business_id,
                bot=bot,
                save_message=save_message,
                set_user_state=set_user_state,
                bad_stage=STAGE_ACCOUNT_ID_BAD,
                build_register_link=build_register_link,
            )
            existing_flow_started = True

        else:
            logging.info("[plan] неизвестный action=%s, игнорируем", action)

    if existing_flow_started:
        session_clients.add(tg_user_id)
        session_out_messages += 3
        asyncio.create_task(update_user_memory(tg_user_id))
        return

    # если affiliate уже отправил клиенту тех.сообщение — лишний ответ ИИ не нужен
    if skip_ai_reply:
        asyncio.create_task(update_user_memory(tg_user_id))
        return   
        
    # 3. Генерируем текст ответа через основной ИИ
    reply_text = await generate_ai_reply(tg_user_id, user_text, bot, plan)

    # 4. Кнопка + ссылка на регистрацию, если планировщик запросил
    reply_markup = None
    if add_register_button:
        reply_text = inject_register_link_into_text(reply_text, tg_user_id)
        reg_link = build_register_link(tg_user_id)
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔗 Регистрация на Pocket Option",
                    url=reg_link,
                )
            ]]
        )

    # 5. Имитируем набор текста (как раньше)
    total_typing = len(reply_text) / 40.0
    total_typing = max(1.0, min(8.0, total_typing))

    pre_delay = random.uniform(0.2, 0.8)
    await asyncio.sleep(pre_delay)

    remaining = total_typing
    while remaining > 0:
        if is_manual_takeover_active(tg_user_id):
            return
        try:
            await bot.send_chat_action(
                chat_id=tg_user_id,
                action=ChatAction.TYPING,
                business_connection_id=business_id,
            )
        except Exception:
            pass

        step = min(3.0, remaining)
        jitter = random.uniform(-0.3, 0.3)
        sleep_time = max(0.5, step + jitter)
        await asyncio.sleep(sleep_time)
        remaining -= step

    # 6. Отправляем сообщение
    if is_manual_takeover_active(tg_user_id):
        return

    sent_chat_id, sent_count = await send_ai_reply_with_funnel_media(
        tg_user_id=tg_user_id,
        business_id=business_id,
        reply_text=reply_text,
        bot=bot,
        reply_markup=reply_markup,
    )
    if sent_chat_id is not None:
        session_clients.add(sent_chat_id)
        session_out_messages += sent_count

    # 7. Обновляем долгосрочную память асинхронно
    asyncio.create_task(update_user_memory(tg_user_id))
    
def split_prompt_pages(prompt: str, page_size: int = PROMPT_PAGE_SIZE) -> list[str]:
    prompt = prompt or ""
    if not prompt:
        return ["(Промпт пока пустой)"]
    return [prompt[i:i + page_size] for i in range(0, len(prompt), page_size)]


async def delayed_business_reply(tg_user_id: int, bot: Bot, delay: float = 20.0):
    global pending_reply_tasks, pending_reply_buffers

    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return

    data = pending_reply_buffers.pop(tg_user_id, None)
    if not data:
        return

    texts: list[str] = data.get("texts", [])
    business_id = data.get("business_id")
    if not texts or not business_id:
        return

    if is_manual_takeover_active(tg_user_id):
        pending_reply_tasks.pop(tg_user_id, None)
        return

    user_text = "\n".join(texts)

    # Просто используем общий хелпер
    await send_business_ai_reply(tg_user_id, business_id, user_text, bot)

    # Таск уже отработал — можно удалить ссылку на него
    pending_reply_tasks.pop(tg_user_id, None)

    
def schedule_business_reply(msg: Message, bot: Bot):
    """
    Складывает текст сообщения в буфер и переинициализирует таймер ответа.
    """
    global pending_reply_tasks, pending_reply_buffers

    tg_id = msg.chat.id
    business_id = msg.business_connection_id
    text = msg.text or ""

    if not business_id:
        # На всякий случай — без business_connection_id не сможем ответить как бизнесу
        return

    buf = pending_reply_buffers.get(tg_id)
    if not buf:
        buf = {"texts": [], "business_id": business_id}
        pending_reply_buffers[tg_id] = buf

    buf["texts"].append(text)
    # если вдруг бизнес-коннект обновился — сохраняем актуальный
    buf["business_id"] = business_id

    # отменяем старый таск, если он ещё жив
    old_task = pending_reply_tasks.get(tg_id)
    if old_task and not old_task.done():
        old_task.cancel()

    # запускаем новый таймер на, например, 10 секунд
    pending_reply_tasks[tg_id] = asyncio.create_task(
        delayed_business_reply(tg_id, bot, delay=10.0)
    )
    
def is_in_schedule_now() -> bool:
    """Только проверка по времени (без ручного рубильника)."""
    if work_start is None or work_end is None:
        return True

    now = datetime.now(MSK_TZ).time()

    if work_start <= work_end:
        return work_start <= now < work_end
    else:
        return now >= work_start or now < work_end

    
# ================== ЗАПУСК ==================
async def main():
    global db_pool, work_start, work_end, work_enabled_manual
    global ai_system_prompt, ai_enabled, ai_model, bot_name

    if not API_TOKEN:
        raise RuntimeError("API_TOKEN is required")

    (
        db_pool,
        work_start,
        work_end,
        work_enabled_manual,
        ai_system_prompt,
        ai_enabled,
        ai_model,
        bot_name,
    ) = await init_db()

    bot = Bot(
        API_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # обычный роутер с бизнес-логикой
    dp.include_router(router)

    # функция, чтобы админка могла обновлять промпт в памяти
    def set_ai_system_prompt(new_value: str) -> None:
        global ai_system_prompt
        ai_system_prompt = new_value

    # прокидываем зависимости в admin-модуль
    setup_admin(
        get_db_pool=lambda: db_pool,
        is_bot_active_now=is_bot_active_now,
        get_work_start=lambda: work_start,
        get_work_end=lambda: work_end,
        get_work_enabled_manual=lambda: work_enabled_manual,
        update_work_hours=update_work_hours,
        update_work_enabled=update_work_enabled,
        get_user_state=get_user_state,
        split_prompt_pages=split_prompt_pages,
        get_ai_system_prompt=lambda: ai_system_prompt,
        set_ai_system_prompt=set_ai_system_prompt,
        disable_bot_for_user=disable_bot_for_user,
        enable_bot_for_user=enable_bot_for_user,
    )
    await refresh_admin_ids_cache()

    # подключаем админский роутер
    dp.include_router(admin_router)

    asyncio.create_task(work_monitor(bot))
    asyncio.create_task(backfill_missing_trader_ids_from_messages())
    asyncio.create_task(runtime_settings_refresh_worker())

    try:
        await dp.start_polling(bot)
    finally:
        if db_pool is not None:
            db_pool.close()
            await db_pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())


