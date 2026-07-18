# admin/admin.py
from __future__ import annotations

import logging
import re
from datetime import time, datetime, date
from html import escape
from typing import Callable, Awaitable, Optional, List, Tuple

import aiomysql
import httpx
from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import (
    ADMIN_IDS as CONFIG_ADMIN_IDS,
    STAGE_TITLES,
    PROMPT_PAGE_SIZE,
    AFFILIATE_BASE_URL,
    AFFILIATE_API_SECRET,
    AFFILIATE_BOT_ID,
    POSTBACK_BASE_URL,
)

router = Router()

ENV_ADMIN_IDS = {int(admin_id) for admin_id in CONFIG_ADMIN_IDS}
DB_ADMIN_IDS: set[int] = set()


class DynamicAdminIds:
    def __contains__(self, item) -> bool:
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            return False
        return user_id in ENV_ADMIN_IDS or user_id in DB_ADMIN_IDS

    def __iter__(self):
        return iter(sorted(ENV_ADMIN_IDS | DB_ADMIN_IDS))

    def __len__(self) -> int:
        return len(ENV_ADMIN_IDS | DB_ADMIN_IDS)


ADMIN_IDS = DynamicAdminIds()

class AISettingsStates(StatesGroup):
    waiting_for_prompt_edit = State()
    waiting_for_prompt_add = State()

class SettingsStates(StatesGroup):
    waiting_for_work_time = State()
    waiting_for_min_deposit = State()
    waiting_for_bot_name = State()
    waiting_for_company_code = State()
    waiting_for_postback_chat_id = State()
    waiting_for_statistics_commission_amount = State()
    waiting_for_statistics_commission_date = State()
    waiting_for_statistics_commission_edit_date = State()

class AdminCheckUserStates(StatesGroup):
    waiting_for_trader_id = State()

class AdminSearchUserStates(StatesGroup):
    waiting_for_search_input = State()
    
class TriggerStates(StatesGroup):
    waiting_for_add = State()
    waiting_for_delete = State()


class AdminManageStates(StatesGroup):
    waiting_for_add = State()
    
_get_db_pool: Callable[[], aiomysql.Pool] | None = None
_is_bot_active_now: Callable[[], bool] | None = None
_get_work_start: Callable[[], Optional[time]] | None = None
_get_work_end: Callable[[], Optional[time]] | None = None
_get_work_enabled_manual: Callable[[], bool] | None = None
_update_work_hours: Callable[[time, time], Awaitable[None]] | None = None
_update_work_enabled: Callable[[bool], Awaitable[None]] | None = None
_get_user_state: Callable[[int], Awaitable[Tuple[str, Optional[str]]]] | None = None
_split_prompt_pages: Callable[[str, int], List[str]] | None = None
_get_ai_system_prompt: Callable[[], str] | None = None
_set_ai_system_prompt: Callable[[str], None] | None = None
_disable_bot_for_user: Callable[[int, str], Awaitable[None]] | None = None
_enable_bot_for_user: Callable[[int], Awaitable[None]] | None = None

POSTBACK_EVENT_META = {
    "reg": {
        "title": "Регистрация",
        "path": "reg",
        "summary": "Подтверждение регистрации трейдера.",
        "params": [
            "click_id",
            "site_id",
            "trader_id",
            "cid",
            "ac",
            "country",
            "promo",
            "device_type",
        ],
    },
    "dep1": {
        "title": "Первый депозит",
        "path": "dep1",
        "summary": "Первое пополнение. Идет в FTD и в общую сумму депозитов.",
        "params": [
            "click_id",
            "site_id",
            "trader_id",
            "sumdep",
            "cid",
            "ac",
        ],
    },
    "dep": {
        "title": "Повторный депозит",
        "path": "dep",
        "summary": "Любое повторное пополнение после первого депозита.",
        "params": [
            "click_id",
            "site_id",
            "trader_id",
            "sumdep",
            "cid",
            "ac",
        ],
    },
    "wdr": {
        "title": "Вывод",
        "path": "wdr",
        "summary": "Событие вывода. Обновляет последнюю и общую сумму вывода.",
        "params": [
            "click_id",
            "site_id",
            "trader_id",
            "wdr_sum",
            "cid",
            "ac",
            "status",
        ],
    },
    "commission": {
        "title": "Комиссия",
        "path": "commission",
        "summary": "Партнерская комиссия. Может приходить массово по многим трейдерам.",
        "params": [
            "click_id",
            "site_id",
            "trader_id",
            "cid",
            "ac",
            "commission",
        ],
    },
}
def setup_admin(
    *,
    get_db_pool: Callable[[], aiomysql.Pool],
    is_bot_active_now: Callable[[], bool],
    get_work_start: Callable[[], Optional[time]],
    get_work_end: Callable[[], Optional[time]],
    get_work_enabled_manual: Callable[[], bool],
    update_work_hours: Callable[[time, time], Awaitable[None]],
    update_work_enabled: Callable[[bool], Awaitable[None]],
    get_user_state: Callable[[int], Awaitable[Tuple[str, Optional[str]]]],
    split_prompt_pages: Callable[[str, int], List[str]],
    get_ai_system_prompt: Callable[[], str],
    set_ai_system_prompt: Callable[[str], None],
    disable_bot_for_user: Callable[[int, str], Awaitable[None]],
    enable_bot_for_user: Callable[[int], Awaitable[None]],
) -> None:

    global _get_db_pool, _is_bot_active_now, _get_work_start, _get_work_end
    global _get_work_enabled_manual, _update_work_hours, _update_work_enabled
    global _get_user_state, _split_prompt_pages
    global _get_ai_system_prompt, _set_ai_system_prompt
    global _disable_bot_for_user, _enable_bot_for_user
    
    _get_db_pool = get_db_pool
    _is_bot_active_now = is_bot_active_now
    _get_work_start = get_work_start
    _get_work_end = get_work_end
    _get_work_enabled_manual = get_work_enabled_manual
    _update_work_hours = update_work_hours
    _update_work_enabled = update_work_enabled
    _get_user_state = get_user_state
    _split_prompt_pages = split_prompt_pages
    _get_ai_system_prompt = get_ai_system_prompt
    _set_ai_system_prompt = set_ai_system_prompt
    _disable_bot_for_user = disable_bot_for_user
    _enable_bot_for_user = enable_bot_for_user


async def refresh_admin_ids_cache() -> None:
    global DB_ADMIN_IDS

    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT tg_user_id FROM admin_users")
        rows = await cur.fetchall()

    DB_ADMIN_IDS = {int(row[0]) for row in rows if row and row[0] is not None}


async def get_admin_profiles() -> dict[int, tuple[str | None, str | None]]:
    assert _get_db_pool
    db_pool = _get_db_pool()

    admin_ids = sorted(ENV_ADMIN_IDS | DB_ADMIN_IDS)
    if not admin_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(admin_ids))
    query = (
        "SELECT tg_user_id, first_name, username "
        f"FROM users WHERE tg_user_id IN ({placeholders})"
    )

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(query, tuple(admin_ids))
        rows = await cur.fetchall()

    return {
        int(tg_user_id): (first_name, username)
        for tg_user_id, first_name, username in rows
    }


def format_admin_name(
    tg_user_id: int,
    profiles: dict[int, tuple[str | None, str | None]],
) -> str:
    first_name, username = profiles.get(tg_user_id, (None, None))
    if username:
        return f"@{username}"
    if first_name:
        return first_name
    return f"ID {tg_user_id}"


async def build_admin_home_text() -> str:
    assert _get_db_pool and _is_bot_active_now and _get_work_start and _get_work_end and _get_work_enabled_manual

    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) FROM messages "
            "WHERE created_at >= NOW() - INTERVAL 1 DAY"
        )
        total_msgs_24 = (await cur.fetchone())[0]

        await cur.execute(
            "SELECT COUNT(DISTINCT tg_user_id) FROM messages "
            "WHERE created_at >= NOW() - INTERVAL 1 DAY"
        )
        total_clients_24 = (await cur.fetchone())[0]

    status = "Работает" if _is_bot_active_now() else "Отдыхает"
    ws_time = _get_work_start()
    we_time = _get_work_end()
    ws = ws_time.strftime("%H:%M") if ws_time else "--:--"
    we = we_time.strftime("%H:%M") if we_time else "--:--"
    manual_status = "ВКЛ" if _get_work_enabled_manual() else "ВЫКЛ"

    return (
        "Админ-центр\n\n"
        "Коротко по системе:\n"
        f"• Сообщений за 24 часа: {total_msgs_24}\n"
        f"• Клиентов за 24 часа: {total_clients_24}\n"
        f"• Статус бота: {status}\n"
        f"• Рабочие часы: {ws}-{we} (МСК)\n"
        f"• Ручной режим: {manual_status}\n\n"
        "Разделы меню:\n"
        "• Пользователи — список диалогов, поиск и карточка клиента.\n"
        "• Настройки — часы работы, имя, компания, депозит и переключатели.\n"
        "• Постбеки — ссылки событий, параметры и лог-чат.\n"
        "• Промпт ИИ — редактирование системного промпта.\n"
        "• Триггеры — слова и фразы для остановки бота и вызова админа.\n"
        "• Администраторы — выдача доступа к админке.\n"
        "\n"
        "Выбери раздел:"
    )


def build_admin_home_keyboard() -> InlineKeyboardMarkup:
    assert _get_work_enabled_manual
    system_enabled = _get_work_enabled_manual()
    system_text = "🟢 Система ON" if system_enabled else "🔴 Система OFF"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔎 Проверить пользователя", callback_data="admin_check_user")],
            [InlineKeyboardButton(text=system_text, callback_data="system:toggle")],
            [
                InlineKeyboardButton(text="👥 Пользователи", callback_data="users:1"),
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"),
            ],
            [
                InlineKeyboardButton(text="🤖 Промпт ИИ", callback_data="settings:ai_prompt"),
                InlineKeyboardButton(text="🚨 Триггеры", callback_data="settings:triggers:1"),
            ],
            [
                InlineKeyboardButton(text="🔗 Постбеки", callback_data="postbacks"),
                InlineKeyboardButton(text="👮 Администраторы", callback_data="admins"),
            ],
        ]
    )

@router.message(Command("admin"))
async def admin_menu(msg: Message):
    if msg.from_user.id not in ADMIN_IDS:
        return

    text = await build_admin_home_text()
    await msg.answer(text, reply_markup=build_admin_home_keyboard())

async def get_kv_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT svalue FROM kv_settings WHERE skey = %s",
            (key,),
        )
        row = await cur.fetchone()

    if not row:
        return default
    return row[0]


async def set_kv_setting(key: str, value: str) -> None:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO kv_settings (skey, svalue)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE svalue = VALUES(svalue)
            """,
            (key, value),
        )


def build_postback_url(event_code: str) -> str:
    event = POSTBACK_EVENT_META[event_code]
    return f"{POSTBACK_BASE_URL.rstrip('/')}/postback/{AFFILIATE_BOT_ID}/{event['path']}"


async def build_postbacks_menu() -> tuple[str, InlineKeyboardMarkup]:
    company_code = await get_kv_setting("COMPANY_CODE", "-")
    log_chat_id = await get_kv_setting("POSTBACK_LOG_CHAT_ID", "—")

    text = (
        "🔗 <b>Постбеки</b>\n\n"
        "Здесь собраны ссылки и параметры для настройки postback через единый backend.\n\n"
        "<b>Как настроить в Pocket:</b>\n"
        "1. Выбери <b>Тип postback: Компания</b>.\n"
        f"2. Для этого проекта используй <b>компанию</b>: <code>{company_code or '-'}</code>.\n"
        "3. Ниже открой нужное <b>событие</b>.\n"
        "4. Скопируй ссылку из карточки события и вставь её в Pocket.\n\n"
        "<b>Инфо:</b>\n"
        f"• bot_id: <code>{AFFILIATE_BOT_ID}</code>\n"
        f"• Публичный адрес: <code>{POSTBACK_BASE_URL.rstrip('/')}</code>\n"
        f"• Chat ID логов: <code>{log_chat_id or '—'}</code>\n\n"
        "Выбери раздел ниже:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Регистрация", callback_data="postbacks:event:reg"),
                InlineKeyboardButton(text="💵 Первый депозит", callback_data="postbacks:event:dep1"),
            ],
            [
                InlineKeyboardButton(text="🔁 Повторный депозит", callback_data="postbacks:event:dep"),
                InlineKeyboardButton(text="💸 Вывод", callback_data="postbacks:event:wdr"),
            ],
            [
                InlineKeyboardButton(text="💼 Комиссия", callback_data="postbacks:event:commission"),
                InlineKeyboardButton(text="📝 Логи", callback_data="postbacks:logs"),
            ],
            [InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin")],
        ]
    )
    return text, kb

async def build_postback_event_text(event_code: str) -> str:
    company_code = await get_kv_setting("COMPANY_CODE", "-")
    event = POSTBACK_EVENT_META[event_code]
    params_block = "\n".join(f"• <code>{param}</code>" for param in event["params"])
    url = build_postback_url(event_code)

    return (
        f"🔗 <b>{event['title']}</b>\n\n"
        f"{event.get('summary', '')}\n\n"
        "<b>Настройка в Pocket:</b>\n"
        "• Тип postback: <b>Компания</b>\n"
        f"• Компания: <code>{company_code or '-'}</code>\n"
        f"• bot_id проекта: <code>{AFFILIATE_BOT_ID}</code>\n\n"
        "<b>Ссылка для события:</b>\n"
        f"<code>{url}</code>\n\n"
        "<b>Передавай параметры:</b>\n"
        f"{params_block}"
    )

async def build_postback_logs_menu() -> tuple[str, InlineKeyboardMarkup]:
    log_chat_id = await get_kv_setting("POSTBACK_LOG_CHAT_ID", "")
    log_regs = await get_kv_setting("LOG_REGISTRATIONS", "1")
    log_deps = await get_kv_setting("LOG_DEPOSITS", "1")
    log_wdr = await get_kv_setting("LOG_WITHDRAWALS", "1")
    log_comm = await get_kv_setting("LOG_COMMISSIONS", "1")
    log_sys = await get_kv_setting("LOG_SYSTEM_ERRORS", "0")

    def flag(value: str) -> str:
        return "✅" if value == "1" else "❌"

    text = (
        "📝 <b>Логи Postback</b>\n\n"
        f"<b>Chat ID для логов:</b> <code>{log_chat_id or '—'}</code>\n\n"
        "<b>Что здесь настраивается:</b>\n"
        "• куда backend отправляет сообщения о postback\n"
        "• какие типы событий логировать\n\n"
        "<b>Переключатели:</b>\n"
        f"• регистрации: {flag(log_regs)}\n"
        f"• депозиты: {flag(log_deps)}\n"
        f"• выводы: {flag(log_wdr)}\n"
        f"• комиссии: {flag(log_comm)}\n"
        f"• системные ошибки: {flag(log_sys)}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Chat ID логов", callback_data="postbacks:logs:chat")],
            [InlineKeyboardButton(text=f"Регистрации: {flag(log_regs)}", callback_data="postbacks:logs:toggle:LOG_REGISTRATIONS")],
            [InlineKeyboardButton(text=f"Депозиты: {flag(log_deps)}", callback_data="postbacks:logs:toggle:LOG_DEPOSITS")],
            [InlineKeyboardButton(text=f"Выводы: {flag(log_wdr)}", callback_data="postbacks:logs:toggle:LOG_WITHDRAWALS")],
            [InlineKeyboardButton(text=f"Комиссии: {flag(log_comm)}", callback_data="postbacks:logs:toggle:LOG_COMMISSIONS")],
            [InlineKeyboardButton(text=f"Системные: {flag(log_sys)}", callback_data="postbacks:logs:toggle:LOG_SYSTEM_ERRORS")],
            [InlineKeyboardButton(text="🔙 В постбеки", callback_data="postbacks")],
        ]
    )
    return text, kb

STATISTICS_PERIODS = {
    "today": ("Сегодня", 0, 0),
    "yesterday": ("Вчера", 1, 1),
    "day_before": ("Позавчера", 2, 2),
    "7d": ("За 7 дней", 6, 0),
    "14d": ("За 14 дней", 13, 0),
    "30d": ("За 30 дней", 29, 0),
}


def format_money(value) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def parse_manual_stat_date(raw: str) -> date | None:
    value = (raw or "").strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


AUTO_COMMISSION_RATIO = 0.2


async def get_statistics_commission_mode() -> str:
    mode = (await get_kv_setting("STATS_COMMISSION_MODE", "auto") or "auto").strip().lower()
    if mode == "manual":
        return "manual"
    if mode in {"auto_plus", "auto+"}:
        return "auto_plus"
    return "auto"


async def build_statistics_snapshot(period_key: str = "today") -> tuple[str, tuple[float, int, int]]:
    assert _get_db_pool
    db_pool = _get_db_pool()

    label, days_back_start, days_back_end = STATISTICS_PERIODS.get(
        period_key,
        STATISTICS_PERIODS["today"],
    )
    commission_mode = await get_statistics_commission_mode()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                COALESCE(SUM(registrations_count), 0),
                COALESCE(SUM(commission_total), 0)
            FROM postback_daily_stats
            WHERE stat_date BETWEEN CURDATE() - INTERVAL %s DAY AND CURDATE() - INTERVAL %s DAY
            """,
            (days_back_start, days_back_end),
        )
        row = await cur.fetchone()
        row = row or (0, 0)

        await cur.execute(
            """
            SELECT COUNT(*)
            FROM postback_events
            WHERE event_code = 'dep1'
              AND DATE(created_at) BETWEEN CURDATE() - INTERVAL %s DAY AND CURDATE() - INTERVAL %s DAY
            """,
            (days_back_start, days_back_end),
        )
        fd_row = await cur.fetchone()

        registrations = int(row[0] or 0)
        fd_count = int((fd_row[0] if fd_row else 0) or 0)
        commission_total = 0.0

        if commission_mode == "manual":
            commission_total = await get_manual_commission_total_between(days_back_start, days_back_end)
        elif commission_mode == "auto_plus":
            manual_cutoff = await get_manual_commission_last_date()
            commission_total = await get_manual_commission_total_between(days_back_start, days_back_end)

            if manual_cutoff:
                await cur.execute(
                    """
                    SELECT COALESCE(SUM(commission_total), 0)
                    FROM postback_daily_stats
                    WHERE stat_date BETWEEN CURDATE() - INTERVAL %s DAY AND CURDATE() - INTERVAL %s DAY
                      AND stat_date > %s
                    """,
                    (days_back_start, days_back_end, manual_cutoff),
                )
                auto_row = await cur.fetchone()
                commission_total += float((auto_row[0] if auto_row else 0) or 0) * AUTO_COMMISSION_RATIO
            else:
                commission_total = float(row[1] or 0) * AUTO_COMMISSION_RATIO
        else:
            commission_total = float(row[1] or 0) * AUTO_COMMISSION_RATIO

    return label, (commission_total, registrations, fd_count)


def build_statistics_keyboard(selected_period: str = "today") -> InlineKeyboardMarkup:
    def button_text(key: str) -> str:
        label = STATISTICS_PERIODS[key][0]
        return f"• {label}" if key == selected_period else label

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=button_text("today"), callback_data="statistics:period:today"),
                InlineKeyboardButton(text=button_text("yesterday"), callback_data="statistics:period:yesterday"),
            ],
            [
                InlineKeyboardButton(text=button_text("day_before"), callback_data="statistics:period:day_before"),
                InlineKeyboardButton(text=button_text("7d"), callback_data="statistics:period:7d"),
            ],
            [InlineKeyboardButton(text=button_text("14d"), callback_data="statistics:period:14d")],
            [InlineKeyboardButton(text=button_text("30d"), callback_data="statistics:period:30d")],
            [
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="statistics:settings"),
                InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin"),
            ],
        ]
    )


async def build_statistics_text(period_key: str = "today") -> str:
    label, stats = await build_statistics_snapshot(period_key)
    return (
        "📊 <b>Статистика</b>\n\n"
        f"<b>{label}</b> по серверной дате:\n\n"
        f"💎 <b>Сумма комиссии:</b> {format_money(stats[0])}\n"
        f"👥 <b>Регистрации:</b> {int(stats[1] or 0)}\n"
        f"🆕 <b>Количество FD:</b> {int(stats[2] or 0)}"
    )


async def build_statistics_settings_text() -> str:
    mode = await get_statistics_commission_mode()
    if mode == "manual":
        mode_text = "Ручное"
    elif mode == "auto_plus":
        mode_text = "Авто+"
    else:
        mode_text = "Автообновление"

    return (
        "⚙️ <b>Настройки статистики</b>\n\n"
        f"<b>Режим комиссии:</b> {mode_text}\n\n"
        "Здесь настраивается источник суммы комиссии для статистики.\n"
        "В автоматическом режиме данные берутся из postback.\n"
        "В ручном режиме администратор указывает итоговую сумму комиссии по датам.\n"
        "Режим Авто+ берёт ручные суммы и после последней ручной даты автоматически продолжает по postback."
    )


async def build_statistics_settings_keyboard() -> InlineKeyboardMarkup:
    mode = await get_statistics_commission_mode()
    if mode == "manual":
        toggle_text = "✍️ Ручное"
    elif mode == "auto_plus":
        toggle_text = "🟡 Авто+"
    else:
        toggle_text = "🟢 Автообновление"

    rows = [[InlineKeyboardButton(text=toggle_text, callback_data="statistics:settings:toggle_mode")]]

    if mode == "manual":
        rows.extend(
            [
                [InlineKeyboardButton(text="💵 Указать сумму за сегодня", callback_data="statistics:settings:add_manual_commission")],
                [InlineKeyboardButton(text="📅 Указать за дату", callback_data="statistics:settings:add_manual_commission_for_date")],
                [InlineKeyboardButton(text="✏️ Редактировать сумму комиссии", callback_data="statistics:settings:edit_manual_commission")],
            ]
        )

    rows.append([InlineKeyboardButton(text="🔙 Вернуться", callback_data="statistics")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def get_manual_commission_total_for_date(target_date: date) -> float:
    exists, amount = await get_manual_commission_entry_for_date(target_date)
    return amount if exists else 0.0


async def get_manual_commission_entry_for_date(target_date: date) -> tuple[bool, float]:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT amount
            FROM stats_manual_commissions
            WHERE stat_date = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (target_date,),
        )
        row = await cur.fetchone()
    if not row:
        return False, 0.0
    return True, float((row[0] if row else 0) or 0)


async def get_manual_commission_total_between(days_back_start: int, days_back_end: int) -> float:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COALESCE(SUM(t.amount), 0)
            FROM (
                SELECT smc.stat_date, smc.amount
                FROM stats_manual_commissions smc
                INNER JOIN (
                    SELECT stat_date, MAX(id) AS max_id
                    FROM stats_manual_commissions
                    WHERE stat_date BETWEEN CURDATE() - INTERVAL %s DAY AND CURDATE() - INTERVAL %s DAY
                    GROUP BY stat_date
                ) latest ON latest.max_id = smc.id
            ) t
            """,
            (days_back_start, days_back_end),
        )
        row = await cur.fetchone()
    return float((row[0] if row else 0) or 0)


async def get_manual_commission_last_date() -> date | None:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT stat_date
            FROM stats_manual_commissions
            ORDER BY stat_date DESC, created_at DESC, id DESC
            LIMIT 1
            """
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def set_manual_commission_total_for_date(target_date: date, amount: float, added_by: int) -> None:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM stats_manual_commissions WHERE stat_date = %s",
            (target_date,),
        )
        await cur.execute(
            """
            INSERT INTO stats_manual_commissions (stat_date, amount, added_by)
            VALUES (%s, %s, %s)
            """,
            (target_date, amount, added_by),
        )

def short_admin_text(text: str | None, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "—"
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def looks_mojibake_text(text: str | None) -> bool:
    if not text:
        return False
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    return any(marker in cleaned for marker in ("пїЅ", "вЂ", "рџ", "Р’", "РЎ", "СЃ", "С‚", "СЏ"))


def clean_person_label(first_name: str | None, username: str | None, tg_user_id: int) -> str:
    first = (first_name or "").strip()
    user = (username or "").strip()

    if first and not looks_mojibake_text(first):
        return first
    if user and not looks_mojibake_text(user):
        return f"@{user}"
    return f"ID {tg_user_id}"


async def get_user_memory_summary(tg_user_id: int) -> str | None:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT memory FROM conversation_memory WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        row = await cur.fetchone()

    if not row:
        return None
    return row[0]


async def add_db_admin(tg_user_id: int, added_by: int | None = None) -> bool:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT IGNORE INTO admin_users (tg_user_id, added_by)
            VALUES (%s, %s)
            """,
            (tg_user_id, added_by),
        )
        inserted = cur.rowcount > 0

    await refresh_admin_ids_cache()
    return inserted


async def remove_db_admin(tg_user_id: int) -> bool:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM admin_users WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        deleted = cur.rowcount > 0

    await refresh_admin_ids_cache()
    return deleted


async def resolve_admin_input(raw: str) -> tuple[int | None, str | None]:
    value = (raw or "").strip()
    if not value:
        return None, None

    if value.isdigit():
        return int(value), None

    username = value.lstrip("@")
    if not username:
        return None, None

    assert _get_db_pool
    db_pool = _get_db_pool()
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT tg_user_id, first_name
            FROM users
            WHERE username = %s
            LIMIT 1
            """,
            (username,),
        )
        row = await cur.fetchone()

    if not row:
        return None, username

    return int(row[0]), username


async def build_admins_panel() -> tuple[str, InlineKeyboardMarkup]:
    await refresh_admin_ids_cache()
    profiles = await get_admin_profiles()

    env_lines = []
    for tg_user_id in sorted(ENV_ADMIN_IDS):
        env_lines.append(f"• {format_admin_name(tg_user_id, profiles)} — {tg_user_id}")

    db_only_admin_ids = sorted(DB_ADMIN_IDS - ENV_ADMIN_IDS)

    db_lines = []
    for tg_user_id in db_only_admin_ids:
        db_lines.append(f"• {format_admin_name(tg_user_id, profiles)} — {tg_user_id}")

    text = (
        "👮 <b>Администраторы</b>\n\n"
        "Здесь выдается доступ к админке.\n"
        "• Админы из .env доступны всегда и здесь только для просмотра.\n"
        "• Админов из БД можно добавлять и удалять прямо из панели.\n\n"
        "ENV:\n"
        f"{chr(10).join(env_lines) if env_lines else '• Нет'}\n\n"
        "БД:\n"
        f"{chr(10).join(db_lines) if db_lines else '• Нет'}"
    )

    buttons = [
        [InlineKeyboardButton(text="➕ Добавить администратора", callback_data="admins:add")]
    ]

    for tg_user_id in db_only_admin_ids:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 Удалить {format_admin_name(tg_user_id, profiles)}",
                    callback_data=f"admins:remove:{tg_user_id}",
                )
            ]
        )

    buttons.append([InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin")])

    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


def _split_trigger_phrases(text: str) -> List[str]:
    return [p.strip() for p in (text or "").split(",") if p.strip()]


async def get_triggers() -> Tuple[Optional[int], List[str]]:
    assert _get_db_pool
    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id, phrases FROM keyword_triggers ORDER BY id LIMIT 1")
        row = await cur.fetchone()

    if not row:
        return None, []

    row_id, phrases_text = row
    phrases = _split_trigger_phrases(phrases_text)
    return row_id, phrases


async def save_triggers(row_id: Optional[int], phrases: List[str]) -> None:
    assert _get_db_pool
    db_pool = _get_db_pool()

    seen = set()
    cleaned: List[str] = []
    for p in phrases:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(p)

    text = ", ".join(cleaned)

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        if row_id is None:
            await cur.execute(
                "INSERT INTO keyword_triggers (phrases) VALUES (%s)",
                (text,),
            )
        else:
            await cur.execute(
                "UPDATE keyword_triggers SET phrases = %s WHERE id = %s",
                (text, row_id),
            )
            
@router.callback_query(F.data == "settings")
async def admin_settings_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_work_start and _get_work_end and _get_work_enabled_manual

    ws_time = _get_work_start()
    we_time = _get_work_end()
    ws = ws_time.strftime("%H:%M") if ws_time else "??"
    we = we_time.strftime("%H:%M") if we_time else "??"
    manual_status = "ВКЛ" if _get_work_enabled_manual() else "ВЫКЛ"
    bot_name = await get_kv_setting("BOT_NAME", "-")
    company_code = await get_kv_setting("COMPANY_CODE", "-")
    min_dep = await get_kv_setting("MIN_DEPOSIT_THRESHOLD", "0")
    check_company = await get_kv_setting("CHECK_COMPANY", "1")

    def flag(v: str) -> str:
        return "✅" if v == "1" else "❌"

    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"Рабочие часы: {ws}-{we} (МСК)\n"
        f"Ручной режим: {manual_status}\n\n"
        "Параметры воронки:\n"
        f"• Имя менеджера: {bot_name}\n"
        f"• Компания: {company_code}\n"
        f"• Мин. депозит: {min_dep} $\n"
        f"• Проверять компанию: {flag(check_company)}\n\n"
        "Логи и ссылки postback вынесены в раздел «Постбеки».\n\n"
        "Выбери, что настроить:"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🕒 Время работы", callback_data="settings:work_time")],
            [InlineKeyboardButton(text="✏️ Имя менеджера", callback_data="settings:edit:BOT_NAME")],
            [InlineKeyboardButton(text="✏️ Имя компании", callback_data="settings:edit:COMPANY_CODE")],
            [InlineKeyboardButton(text="✏️ Мин. депозит", callback_data="settings:edit:MIN_DEPOSIT_THRESHOLD")],
            [
                InlineKeyboardButton(
                    text=f"🏢 Проверять компанию: {flag(check_company)}",
                    callback_data="settings:toggle:CHECK_COMPANY",
                )
            ],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")],
        ]
    )

    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("settings:toggle:"))
async def settings_toggle_flag(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    key = parts[2]
    allowed = {
        "CHECK_COMPANY": "Проверка компании",
        "LOG_DEPOSITS": "Логи депозитов",
        "LOG_REGISTRATIONS": "Логи регистраций",
        "LOG_WITHDRAWALS": "Логи выводов",
        "LOG_COMMISSIONS": "Логи комиссий",
        "LOG_SYSTEM_ERRORS": "Системные ошибки",
    }
    if key not in allowed:
        await callback.answer("Неизвестный параметр.", show_alert=True)
        return

    current = await get_kv_setting(key, "0")
    new_val = "0" if current == "1" else "1"
    await set_kv_setting(key, new_val)

    status = "включено" if new_val == "1" else "выключено"
    await callback.answer(f"{allowed[key]}: {status}", show_alert=True)

    await admin_settings_menu(callback)
    
@router.callback_query(F.data.startswith("settings:edit:"))
async def settings_edit_param(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    key = parts[2]

    if key == "MIN_DEPOSIT_THRESHOLD":
        await state.set_state(SettingsStates.waiting_for_min_deposit)
        text = (
            "💵 Изменить минимальный депозит\n\n"
            "Укажи сумму минимального депозита в $.\n"
            "Если пользователь сделает депозит меньше, мы не пропустим его дальше по воронке.\n\n"
            "Отправь только число, например: <code>10</code>\n\n"
            "Чтобы отменить, нажми «Назад»."
        )
    elif key == "BOT_NAME":
        await state.set_state(SettingsStates.waiting_for_bot_name)
        text = (
            "✏️ Изменить имя менеджера\n\n"
            "Укажи новое имя менеджера.\n\n"
            "Например: <code>Elizabeth Vane</code>\n\n"
            "Чтобы отменить, нажми «Назад»."
        )
    elif key == "COMPANY_CODE":
        await state.set_state(SettingsStates.waiting_for_company_code)
        text = (
            "🏢 Изменить имя компании\n\n"
            "Укажи имя компании для отслеживания.\n\n"
            "⚠️ Внимание: не меняй этот параметр без согласования с тех. отделом.\n\n"
            "Чтобы отменить, нажми «Назад»."
        )
    else:
        await callback.answer("Неизвестный параметр.", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в настройки", callback_data="settings_back")]
        ]
    )

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()
    
@router.message(SettingsStates.waiting_for_min_deposit)
async def process_min_deposit_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    raw = (msg.text or "").strip().replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", raw):
        await msg.answer(
            "Нужно отправить только число в долларах, например: 10 или 15.5",
        )
        return

    await set_kv_setting("MIN_DEPOSIT_THRESHOLD", raw)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В настройки", callback_data="settings")]]
    )

    await msg.answer(f"✅ Минимальный депозит обновлён: {raw} $", reply_markup=kb)
    
@router.message(SettingsStates.waiting_for_company_code)
async def process_company_code_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    company = (msg.text or "").strip()
    if not company:
        await msg.answer("Имя компании не может быть пустым. Отправь ещё раз.")
        return

    await set_kv_setting("COMPANY_CODE", company)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В настройки", callback_data="settings")]]
    )

    await msg.answer(f"✅ Имя компании обновлено: {company}", reply_markup=kb)
    
@router.message(SettingsStates.waiting_for_bot_name)
async def process_bot_name_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    name = (msg.text or "").strip()
    if not name:
        await msg.answer("Имя менеджера не может быть пустым. Отправь ещё раз.")
        return

    await set_kv_setting("BOT_NAME", name)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 В настройки", callback_data="settings")]]
    )

    await msg.answer(f"✅ Имя менеджера обновлено: {name}", reply_markup=kb)
    
@router.callback_query(F.data == "settings_back")
async def settings_back(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    await admin_settings_menu(callback)

@router.callback_query(F.data == "admin_check_user")
async def admin_check_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminCheckUserStates.waiting_for_trader_id)
    await callback.message.edit_text(
        "Введите Trader ID пользователя, которого нужно проверить:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]]
        )
    )
    await callback.answer()


@router.message(AdminCheckUserStates.waiting_for_trader_id)
async def process_check_user_input(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    trader_id = (message.text or "").strip()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                AFFILIATE_BASE_URL.rstrip("/") + "/affiliate/user-info",
                headers={"X-Affiliate-Secret": AFFILIATE_API_SECRET},
                params={"bot_id": AFFILIATE_BOT_ID, "trader_id": trader_id},
            )
        resp.raise_for_status()
        data = resp.json()
    except httpx.ConnectError:
        await message.answer(
            "❌ Не удалось подключиться к affiliate-сервису.\n"
            "Проверь, что он запущен и доступен.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]]
            ),
        )
        return
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при запросе к API:\n`{e}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]]
            ),
        )
        return

    if not data.get("success"):
        await message.answer(
            f"❌ Ошибка:\n`{data.get('message')}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]]
            ),
        )
        return

    user = data["data"]

    text = (
        "🧾 *Информация о пользователе*\n"
        "```\n"
        f"Trader ID:      {trader_id}\n"
        f"Баланс:         {user.get('balance')}\n\n"
        f"FTD сумма:      {user.get('first_deposit_sum')}\n"
        f"FTD дата:       {user.get('first_deposit_date')}\n"
        f"Кол-во депов:   {user.get('deposits_count')}\n"
        f"Все депозиты:   {user.get('deposits_sum')}\n\n"
        f"Регистрация:    {user.get('reg_date')}\n"
        f"Активность:     {user.get('activity_date')}\n"
        f"Страна:         {user.get('country')}\n"
        f"Верификация:    {user.get('is_verified')}\n\n"
        f"Компания:       {user.get('company')}\n"
        f"Рег. ссылка:    {user.get('registration_link')}\n"
        "```"
    )

    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]]
        ),
    )

    await state.clear()


@router.callback_query(F.data == "settings:work_toggle")
async def settings_work_toggle(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_work_enabled_manual and _update_work_enabled

    new_state = not _get_work_enabled_manual()
    await _update_work_enabled(new_state)

    await callback.answer(
        "Ручной режим: " + ("ВКЛ (бот отвечает)" if new_state else "ВЫКЛ (бот молчит)"),
        show_alert=True,
    )

    await admin_settings_menu(callback)


@router.callback_query(F.data == "system:toggle")
async def system_toggle_from_home(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_work_enabled_manual and _update_work_enabled

    new_state = not _get_work_enabled_manual()
    await _update_work_enabled(new_state)

    text = await build_admin_home_text()
    kb = build_admin_home_keyboard()

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer(
        "Система ON" if new_state else "Система OFF",
        show_alert=True,
    )


@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    text = await build_admin_home_text()
    kb = build_admin_home_keyboard()

    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
    return


@router.callback_query(F.data == "statistics")
async def statistics_placeholder(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    stats_text = await build_statistics_text("today")
    stats_kb = build_statistics_keyboard("today")
    if callback.message:
        await callback.message.edit_text(stats_text, parse_mode=ParseMode.HTML, reply_markup=stats_kb)
    await callback.answer()


@router.callback_query(F.data.startswith("statistics:period:"))
async def statistics_change_period(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    period_key = callback.data.split(":")[-1]
    if period_key not in STATISTICS_PERIODS:
        await callback.answer("Неизвестный период", show_alert=True)
        return

    stats_text = await build_statistics_text(period_key)
    stats_kb = build_statistics_keyboard(period_key)
    if callback.message:
        await callback.message.edit_text(stats_text, parse_mode=ParseMode.HTML, reply_markup=stats_kb)
    await callback.answer()


@router.callback_query(F.data == "statistics:settings")
async def statistics_settings_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    text = await build_statistics_settings_text()
    kb = await build_statistics_settings_keyboard()
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "statistics:settings:toggle_mode")
async def statistics_settings_toggle_mode(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    current = await get_statistics_commission_mode()
    if current == "auto":
        new_mode = "manual"
    elif current == "manual":
        new_mode = "auto_plus"
    else:
        new_mode = "auto"
    await set_kv_setting("STATS_COMMISSION_MODE", new_mode)

    text = await build_statistics_settings_text()
    kb = await build_statistics_settings_keyboard()
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer("Режим обновлён", show_alert=False)


@router.callback_query(F.data == "statistics:settings:add_manual_commission")
async def statistics_settings_add_manual_commission(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    if await get_statistics_commission_mode() != "manual":
        await callback.answer("Сначала переключи статистику в ручной режим", show_alert=True)
        return

    await state.update_data(statistics_manual_commission_date=date.today().isoformat())
    await state.set_state(SettingsStates.waiting_for_statistics_commission_amount)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В настройки статистики", callback_data="statistics:settings")]
        ]
    )
    text = (
        "💵 <b>Указать сумму комиссии за сегодня</b>\n\n"
        "Отправь итоговую сумму одним сообщением.\n"
        "Сумма будет сохранена за сегодняшнюю серверную дату."
    )
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "statistics:settings:add_manual_commission_for_date")
async def statistics_settings_add_manual_commission_for_date(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    if await get_statistics_commission_mode() != "manual":
        await callback.answer("Сначала переключи статистику в ручной режим", show_alert=True)
        return

    await state.clear()
    await state.set_state(SettingsStates.waiting_for_statistics_commission_date)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В настройки статистики", callback_data="statistics:settings")]
        ]
    )
    text = (
        "📅 <b>Указать сумму комиссии за дату</b>\n\n"
        "Отправь дату одним сообщением.\n"
        "Поддерживаются форматы: <code>2026-04-12</code> или <code>12.04.2026</code>."
    )
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "statistics:settings:edit_manual_commission")
async def statistics_settings_edit_manual_commission(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    if await get_statistics_commission_mode() != "manual":
        await callback.answer("Сначала переключи статистику в ручной режим", show_alert=True)
        return

    await state.clear()
    await state.set_state(SettingsStates.waiting_for_statistics_commission_edit_date)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В настройки статистики", callback_data="statistics:settings")]
        ]
    )
    text = (
        "✏️ <b>Редактировать сумму комиссии</b>\n\n"
        "Отправь дату, за которую нужно изменить сумму.\n"
        "Поддерживаются форматы: <code>2026-04-12</code> или <code>12.04.2026</code>."
    )
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.message(SettingsStates.waiting_for_statistics_commission_date)
async def process_statistics_commission_date_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    target_date = parse_manual_stat_date(msg.text or "")
    if not target_date:
        await msg.answer("Нужна дата в формате 2026-04-12 или 12.04.2026.")
        return

    await state.update_data(statistics_manual_commission_date=target_date.isoformat())
    await state.set_state(SettingsStates.waiting_for_statistics_commission_amount)
    await msg.answer(
        "💵 Отправь итоговую сумму комиссии за "
        f"<b>{target_date.strftime('%d.%m.%Y')}</b> одним сообщением.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В настройки статистики", callback_data="statistics:settings")]
            ]
        ),
    )


@router.message(SettingsStates.waiting_for_statistics_commission_edit_date)
async def process_statistics_commission_edit_date_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    target_date = parse_manual_stat_date(msg.text or "")
    if not target_date:
        await msg.answer("Нужна дата в формате 2026-04-12 или 12.04.2026.")
        return

    exists, current_amount = await get_manual_commission_entry_for_date(target_date)
    if not exists:
        await msg.answer(
            "За эту дату ручная сумма комиссии не найдена.\n"
            "Проверь дату или используй «Указать за дату»."
        )
        return

    await state.update_data(statistics_manual_commission_date=target_date.isoformat())
    await state.set_state(SettingsStates.waiting_for_statistics_commission_amount)
    await msg.answer(
        "✏️ Текущая сумма за "
        f"<b>{target_date.strftime('%d.%m.%Y')}</b>: <b>{format_money(current_amount)}</b>\n\n"
        "Отправь новую итоговую сумму одним сообщением.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В настройки статистики", callback_data="statistics:settings")]
            ]
        ),
    )


@router.message(SettingsStates.waiting_for_statistics_commission_amount)
async def process_statistics_commission_amount_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    raw = (msg.text or "").strip().replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        await msg.answer("Нужно отправить сумму числом. Пример: 20 или 15.50")
        return

    amount = float(raw)
    data = await state.get_data()
    target_date = parse_manual_stat_date(data.get("statistics_manual_commission_date", ""))
    if not target_date:
        target_date = date.today()

    await set_manual_commission_total_for_date(target_date, amount, msg.from_user.id)

    await state.clear()
    text = await build_statistics_settings_text()
    kb = await build_statistics_settings_keyboard()
    await msg.answer(
        f"Сумма комиссии за <b>{target_date.strftime('%d.%m.%Y')}</b> сохранена: "
        f"<b>{format_money(amount)}</b>",
        parse_mode=ParseMode.HTML,
    )
    await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "postbacks")
async def postbacks_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    text, kb = await build_postbacks_menu()
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("postbacks:event:"))
async def postback_event_details(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    event_code = callback.data.split(":")[-1]
    if event_code not in POSTBACK_EVENT_META:
        await callback.answer("Неизвестное событие", show_alert=True)
        return

    text = await build_postback_event_text(event_code)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В постбеки", callback_data="postbacks")]
        ]
    )
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "postbacks:logs")
async def postback_logs_menu(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    text, kb = await build_postback_logs_menu()
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("postbacks:logs:toggle:"))
async def postback_logs_toggle(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    key = callback.data.split(":")[-1]
    current = await get_kv_setting(key, "0")
    new_val = "0" if current == "1" else "1"
    await set_kv_setting(key, new_val)

    await callback.answer("Обновлено", show_alert=False)
    text, kb = await build_postback_logs_menu()
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "postbacks:logs:chat")
async def postback_logs_chat_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(SettingsStates.waiting_for_postback_chat_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В логи postback", callback_data="postbacks:logs")]
        ]
    )
    text = (
        "📝 Chat ID для логов postback\n\n"
        "Отправь Telegram chat id, куда backend будет слать логи событий.\n"
        "Можно указать канал или группу.\n\n"
        "Чтобы отключить отправку в чат, отправь: <code>0</code>"
    )
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.message(SettingsStates.waiting_for_postback_chat_id)
async def process_postback_chat_id_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    raw = (msg.text or "").strip()
    if raw == "0":
        await set_kv_setting("POSTBACK_LOG_CHAT_ID", "")
    elif not re.fullmatch(r"-?\d+", raw):
        await msg.answer("Нужно отправить только числовой chat id или 0 для отключения.")
        return
    else:
        await set_kv_setting("POSTBACK_LOG_CHAT_ID", raw)

    await state.clear()
    text, kb = await build_postback_logs_menu()
    await msg.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)


@router.callback_query(F.data == "admins")
async def admins_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    text, kb = await build_admins_panel()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admins:add")
async def admins_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminManageStates.waiting_for_add)
    text = (
        "👮 Добавить администратора\n\n"
        "Отправь TG ID нового администратора.\n"
        "Можно также отправить @username, если этот пользователь уже есть в таблице users."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к администраторам", callback_data="admins")]
        ]
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.message(AdminManageStates.waiting_for_add)
async def admins_add_finish(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    tg_user_id, username = await resolve_admin_input(message.text or "")
    if tg_user_id is None:
        hint = f"@{username}" if username else "указанное значение"
        await message.answer(
            f"❌ Не смог найти {hint}. Отправь TG ID или username пользователя, который уже есть в системе."
        )
        return

    if tg_user_id in ENV_ADMIN_IDS:
        await state.clear()
        await message.answer("ℹ️ Этот администратор уже задан через .env и доступ у него уже есть.")
        return

    inserted = await add_db_admin(tg_user_id, added_by=message.from_user.id)
    await state.clear()

    if inserted:
        profiles = await get_admin_profiles()
        admin_name = format_admin_name(tg_user_id, profiles)
        await message.answer(f"✅ Доступ выдан: {admin_name} ({tg_user_id})")
    else:
        await message.answer("ℹ️ Этот TG ID уже есть в списке администраторов.")


@router.callback_query(F.data.startswith("admins:remove:"))
async def admins_remove(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    try:
        _, _, tg_id_str = callback.data.split(":")
        tg_user_id = int(tg_id_str)
    except Exception:
        await callback.answer("Некорректный TG ID.", show_alert=True)
        return

    if tg_user_id in ENV_ADMIN_IDS:
        await callback.answer("Администратора из .env удалить отсюда нельзя.", show_alert=True)
        return

    removed = await remove_db_admin(tg_user_id)
    text, kb = await build_admins_panel()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer("Удалён." if removed else "Уже удалён.")


@router.callback_query(F.data == "settings:work_time")
async def settings_work_time(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_work_start and _get_work_end

    ws_time = _get_work_start()
    we_time = _get_work_end()
    ws = ws_time.strftime("%H:%M") if ws_time else "??"
    we = we_time.strftime("%H:%M") if we_time else "??"

    text = (
        "🕒 Настройка времени работы\n\n"
        f"Сейчас: {ws}-{we} (МСК)\n\n"
        "Отправь новое время в формате:\n"
        "<code>HH:MM-HH:MM</code>\n"
        "Например: <code>22:00-10:00</code>"
    )

    await state.set_state(SettingsStates.waiting_for_work_time)
    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.message(SettingsStates.waiting_for_work_time)
async def process_work_time_input(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    assert _update_work_hours

    text = (msg.text or "").strip()
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*", text)
    if not m:
        await msg.answer(
            "Неверный формат. Отправь в виде <code>HH:MM-HH:MM</code>, например <code>22:00-10:00</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    h1, m1, h2, m2 = map(int, m.groups())
    if not (0 <= h1 < 24 and 0 <= h2 < 24 and 0 <= m1 < 60 and 0 <= m2 < 60):
        await msg.answer("Некорректное время. Часы 0-23, минуты 0-59.")
        return

    new_start = time(h1, m1)
    new_end = time(h2, m2)

    await _update_work_hours(new_start, new_end)
    await state.clear()

    ws = new_start.strftime("%H:%M")
    we = new_end.strftime("%H:%M")
    await msg.answer(f"✅ Рабочие часы обновлены: {ws}-{we} (МСК)")

@router.callback_query(F.data.startswith("users:"))
async def admin_users_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_db_pool

    page_str = callback.data.split(":")[1]
    page = int(page_str) if page_str.isdigit() and int(page_str) > 0 else 1
    per_page = 10
    offset = (page - 1) * per_page

    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT COUNT(*) FROM users")
        total_users = (await cur.fetchone())[0]

        await cur.execute(
            """
            SELECT
                u.tg_user_id,
                u.first_name,
                u.username
            FROM users u
            LEFT JOIN (
                SELECT tg_user_id, MAX(created_at) AS last_activity_at
                FROM messages
                GROUP BY tg_user_id
            ) m ON m.tg_user_id = u.tg_user_id
            ORDER BY COALESCE(m.last_activity_at, u.last_message_at, u.created_at) DESC, u.tg_user_id DESC
            LIMIT %s OFFSET %s
            """,
            (per_page, offset),
        )
        rows = await cur.fetchall()

    buttons = []
    row_buttons: List[InlineKeyboardButton] = []
    for tg_user_id, first_name, username in rows:
        title = clean_person_label(first_name, username, tg_user_id)
        row_buttons.append(
            InlineKeyboardButton(
                text=title,
                callback_data=f"conv:{tg_user_id}:1",
            )
        )
        if len(row_buttons) == 2:
            buttons.append(row_buttons)
            row_buttons = []

    if row_buttons:
        buttons.append(row_buttons)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"users:{page-1}")
        )
    if offset + per_page < total_users:
        nav_buttons.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"users:{page+1}")
        )
    if nav_buttons:
        buttons.append(nav_buttons)
        
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔎 Проверить (TG/username)",
                callback_data="admin_search_user",
            )
        ]
    )

    buttons.append(
        [InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = f"👥 Пользователи\nСтраница {page}"

    if callback.message:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "admin_search_user")
async def admin_search_user_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(AdminSearchUserStates.waiting_for_search_input)

    text = (
        "🔎 Проверить пользователя\n\n"
        "Отправь <b>TG ID</b> пользователя или его <b>username</b>.\n"
        "Примеры:\n"
        "• <code>7097261848</code>\n"
        "• <code>@username</code>\n\n"
        "Чтобы вернуться, нажми кнопку ниже."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin")]
        ]
    )

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()
    
@router.message(AdminSearchUserStates.waiting_for_search_input)
async def process_admin_search_user(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    assert _get_db_pool

    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Пустой запрос. Отправь TG ID или username пользователя.")
        return

    db_pool = _get_db_pool()

    is_tg_id = raw.lstrip("@").isdigit()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        if is_tg_id:
            tg_user_id = int(raw.lstrip("@"))
            await cur.execute(
                """
                SELECT 
                    tg_user_id,
                    first_name,
                    username,
                    country,
                    trader_id,
                    registration_status,
                    deposit_status,
                    last_message_at,
                    bot_active
                FROM users
                WHERE tg_user_id = %s
                """,
                (tg_user_id,),
            )
        else:
            username = raw.lstrip("@")
            await cur.execute(
                """
                SELECT 
                    tg_user_id,
                    first_name,
                    username,
                    country,
                    trader_id,
                    registration_status,
                    deposit_status,
                    last_message_at,
                    bot_active
                FROM users
                WHERE username = %s
                LIMIT 1
                """,
                (username,),
            )

        row = await cur.fetchone()

    if not row:
        await message.answer("❌ Пользователь не найден в системе!")
        return

    (
        tg_user_id,
        first_name,
        username,
        country,
        trader_id,
        reg_status,
        dep_status,
        last_message_at,
        bot_active,
    ) = row

    reg_icon = "✅" if reg_status else "❌"
    dep_icon = "✅" if dep_status else "❌"
    bot_icon = "✅" if bot_active else "❌"
    memory_summary = short_admin_text(await get_user_memory_summary(tg_user_id), 140)

    if username:
        uname_link = f"https://t.me/{username} (@{username})"
    else:
        uname_link = "—"

    last_msg_str = last_message_at.strftime("%Y-%m-%d %H:%M:%S") if last_message_at else "—"

    sys_text = (
        "ℹ️ *Информация о пользователе (система)*\n"
        "```\n"
        f"TgID:              {tg_user_id}\n"
        f"Имя:               {first_name or '-'}\n"
        f"Username:          {username or '-'}\n"
        f"Ссылка:            {uname_link}\n"
        f"Страна:            {country or '-'}\n"
        f"Регистрация:       {reg_icon}\n"
        f"Депозит:           {dep_icon}\n"
        f"Бот активен:       {bot_icon}\n"
        f"Последнее сообщение: {last_msg_str}\n"
        f"Trader ID (из БД): {trader_id or '-'}\n"
        f"Сводка:            {memory_summary}\n"
        "```"
    )

    pocket_block = ""
    if trader_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    AFFILIATE_BASE_URL.rstrip("/") + "/affiliate/user-info",
                    headers={"X-Affiliate-Secret": AFFILIATE_API_SECRET},
                    params={"bot_id": AFFILIATE_BOT_ID, "trader_id": str(trader_id)},
                )
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            pocket_block = (
                "\n❌ Не удалось подключиться к affiliate-сервису "
                "для получения данных по Trader ID."
            )
        except Exception as e:
            pocket_block = f"\n❌ Ошибка при запросе к API:\n`{e}`"
        else:
            if not data.get("success"):
                pocket_block = f"\n❌ Ошибка affiliate:\n`{data.get('message')}`"
            else:
                user = data["data"]
                pocket_block = (
                    "\n🧾 *Информация из Pocket Option*\n"
                    "```\n"
                    f"Trader ID:      {trader_id}\n"
                    f"Баланс:         {user.get('balance')}\n\n"
                    f"FTD сумма:      {user.get('first_deposit_sum')}\n"
                    f"FTD дата:       {user.get('first_deposit_date')}\n"
                    f"Кол-во депов:   {user.get('deposits_count')}\n"
                    f"Все депозиты:   {user.get('deposits_sum')}\n\n"
                    f"Регистрация:    {user.get('reg_date')}\n"
                    f"Активность:     {user.get('activity_date')}\n"
                    f"Страна:         {user.get('country')}\n"
                    f"Верификация:    {user.get('is_verified')}\n\n"
                    f"Компания:       {user.get('company')}\n"
                    f"Рег. ссылка:    {user.get('registration_link')}\n"
                    "```"
                )
    else:
        pocket_block = "\nℹ️ Trader ID в БД не указан — запрос к Pocket Option не выполнялся."

    toggle_text = "🔴 Выключить бота пользователю" if bot_active else "🟢 Включить бота пользователю"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin_toggle_bot:{tg_user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Вернуться",
                    callback_data="back_to_admin",
                )
            ],
        ]
    )

    await state.clear()
    await message.answer(
        sys_text + pocket_block,
        parse_mode="Markdown",
        reply_markup=kb,
    )
    
@router.callback_query(F.data.startswith("admin_toggle_bot:"))
async def admin_toggle_bot(callback: CallbackQuery):

    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_db_pool and _disable_bot_for_user and _enable_bot_for_user

    try:
        _, tg_id_str = callback.data.split(":")
        tg_user_id = int(tg_id_str)
    except Exception:
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    db_pool = _get_db_pool()

    # Узнаём текущий статус bot_active
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT bot_active FROM users WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        row = await cur.fetchone()

    if not row:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    (bot_active,) = row

    if bot_active:
        await _disable_bot_for_user(tg_user_id, "Выключил админ")
        msg = "Бот выключен для пользователя."
    else:
        await _enable_bot_for_user(tg_user_id)
        msg = "Бот включён для пользователя."

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT 
                tg_user_id,
                first_name,
                username,
                country,
                trader_id,
                registration_status,
                deposit_status,
                last_message_at,
                bot_active
            FROM users
            WHERE tg_user_id = %s
            """,
            (tg_user_id,),
        )
        row = await cur.fetchone()

    if not row:
        await callback.answer(msg, show_alert=True)
        return

    (
        tg_user_id,
        first_name,
        username,
        country,
        trader_id,
        reg_status,
        dep_status,
        last_message_at,
        bot_active,
    ) = row

    reg_icon = "✅" if reg_status else "❌"
    dep_icon = "✅" if dep_status else "❌"
    bot_icon = "✅" if bot_active else "❌"
    memory_summary = short_admin_text(await get_user_memory_summary(tg_user_id), 140)

    if username:
        uname_link = f"https://t.me/{username} (@{username})"
    else:
        uname_link = "—"

    last_msg_str = last_message_at.strftime("%Y-%m-%d %H:%M:%S") if last_message_at else "—"

    sys_text = (
        "ℹ️ *Информация о пользователе (система)*\n"
        "```\n"
        f"TgID:              {tg_user_id}\n"
        f"Имя:               {first_name or '-'}\n"
        f"Username:          {username or '-'}\n"
        f"Ссылка:            {uname_link}\n"
        f"Страна:            {country or '-'}\n"
        f"Регистрация:       {reg_icon}\n"
        f"Депозит:           {dep_icon}\n"
        f"Бот активен:       {bot_icon}\n"
        f"Последнее сообщение: {last_msg_str}\n"
        f"Trader ID (из БД): {trader_id or '-'}\n"
        f"Сводка:            {memory_summary}\n"
        "```"
    )

    pocket_block = ""

    toggle_text = "🔴 Выключить бота пользователю" if bot_active else "🟢 Включить бота пользователю"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"admin_toggle_bot:{tg_user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Вернуться",
                    callback_data="back_to_admin",
                )
            ],
        ]
    )

    if callback.message:
        await callback.message.edit_text(
            sys_text + pocket_block,
            parse_mode="Markdown",
            reply_markup=kb,
        )

    await callback.answer(msg, show_alert=True)
    
@router.callback_query(F.data.startswith("conv:"))
async def admin_user_conversation(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    assert _get_db_pool and _get_user_state

    _, tg_id_str, page_str = callback.data.split(":")
    tg_user_id = int(tg_id_str)
    page = int(page_str) if page_str.isdigit() and int(page_str) > 0 else 1
    per_page = 10
    offset = (page - 1) * per_page

    db_pool = _get_db_pool()

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT first_name, username FROM users WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        user_row = await cur.fetchone()
        if user_row:
            first_name, username = user_row
        else:
            first_name, username = None, None

        await cur.execute(
            "SELECT COUNT(*) FROM messages WHERE tg_user_id = %s",
            (tg_user_id,),
        )
        total_msgs = (await cur.fetchone())[0]

        await cur.execute(
            """
            SELECT direction, text, created_at, is_business
            FROM messages
            WHERE tg_user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (tg_user_id, per_page, offset),
        )
        rows = await cur.fetchall()

    rows = list(reversed(rows))

    lines = []
    for direction, text, created_at, is_business in rows:
        who = "КЛИЕНТ" if direction == "in" else "МЫ"
        if is_business:
            who += " (BIZ)"
        ts = created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"[{ts}] {who}: {text or ''}")

    history_text = "\n".join(lines) if lines else "История пуста."

    display_name = (first_name or "").strip() or f"ID {tg_user_id}"

    if username:
        user_link_line = f'<a href="https://t.me/{username}">@{username}</a>\n'
    else:
        user_link_line = ""

    try:
        stage, notes = await _get_user_state(tg_user_id)
    except Exception:
        stage, notes = "new", None

    stage_title = STAGE_TITLES.get(stage, stage)
    notes_safe = escape(notes) if notes else "—"
    memory_summary = escape(short_admin_text(await get_user_memory_summary(tg_user_id), 220))

    header = (
        f"Диалог с {escape(str(display_name))}\n"
        f"{user_link_line}"
        f"Воронка: {escape(stage_title)}\n"
        f"Заметки: {notes_safe}\n"
        f"Сводка: {memory_summary}\n"
        f"Стр. {page}\n\n"
    )

    body = "<pre>" + escape(history_text) + "</pre>"

    buttons = []
    nav = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"conv:{tg_user_id}:{page-1}"
            )
        )
    if offset + per_page < total_msgs:
        nav.append(
            InlineKeyboardButton(
                text="Вперёд ➡️", callback_data=f"conv:{tg_user_id}:{page+1}"
            )
        )
    if nav:
        buttons.append(nav)

    buttons.append(
        [
                InlineKeyboardButton(
                    text="🔙 К пользователям", callback_data="users:1"
                )
            ]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if callback.message:
        await callback.message.edit_text(
            header + body,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )
    await callback.answer()

TRIGGERS_PER_PAGE = 25 

@router.callback_query(F.data.startswith("settings:triggers"))
async def settings_triggers_menu(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    page = 1
    if len(parts) == 3 and parts[2].isdigit():
        page = max(1, int(parts[2]))

    row_id, phrases = await get_triggers()
    total = len(phrases)
    total_pages = max(1, (total - 1) // TRIGGERS_PER_PAGE + 1) if total > 0 else 1
    page = min(page, total_pages)

    start = (page - 1) * TRIGGERS_PER_PAGE
    end = start + TRIGGERS_PER_PAGE
    chunk = phrases[start:end]

    if chunk:
        text_block = ", ".join(chunk)
    else:
        text_block = "(список пока пуст)"

    text = (
        "🚨 Триггеры ключевых слов\n\n"
        f"Страница {page}/{total_pages}\n\n"
        f"<pre>{escape(text_block)}</pre>\n\n"
        "При упоминании любого из этих слов или фраз бот остановит работу и уведомит админов.\n\n"
        "Выбери действие:\n"
        "• ➕ Добавить триггер — добавить новые слова или фразы через запятую\n"
        "• 🗑 Удалить триггер — удалить существующие слова или фразы\n"
    )

    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"settings:triggers:{page-1}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data=f"settings:triggers:{page}",
        )
    )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"settings:triggers:{page+1}",
            )
        )

    buttons: List[List[InlineKeyboardButton]] = []
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [InlineKeyboardButton(text="➕ Добавить триггер", callback_data="triggers:add")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🗑 Удалить триггер", callback_data="triggers:delete")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "triggers:add")
async def triggers_add_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(TriggerStates.waiting_for_add)

    text = (
        "➕ Добавить триггеры\n\n"
        "Отправь слова или фразы, разделённые запятыми.\n"
        "Пример:\n"
        "<code>промокод, трейдинг, pocket option</code>\n\n"
        "Все указанные фразы будут добавлены к существующему списку.\n\n"
        "Чтобы отменить, нажми «Назад»."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к триггерам", callback_data="triggers:back")]
        ]
    )

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.message(TriggerStates.waiting_for_add)
async def process_triggers_add(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    raw = (msg.text or "").strip()
    new_phrases = _split_trigger_phrases(raw)
    if not new_phrases:
        await msg.answer(
            "Нужно отправить хотя бы одно слово или фразу, разделив несколько значений запятыми."
        )
        return

    row_id, phrases = await get_triggers()
    existing_lower = {p.lower() for p in phrases}

    added = 0
    for p in new_phrases:
        if p.lower() in existing_lower:
            continue
        phrases.append(p)
        existing_lower.add(p.lower())
        added += 1

    await save_triggers(row_id, phrases)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К триггерам", callback_data="settings:triggers:1")]
        ]
    )

    await msg.answer(f"✅ Добавлено триггеров: {added}", reply_markup=kb)

@router.callback_query(F.data == "triggers:delete")
async def triggers_delete_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.set_state(TriggerStates.waiting_for_delete)

    text = (
        "🗑 Удалить триггеры\n\n"
        "Отправь слова или фразы, которые нужно удалить, через запятую.\n"
        "Пример:\n"
        "<code>промокод, трейдинг</code>\n\n"
        "Если указанных фраз нет в списке, они будут просто проигнорированы.\n\n"
        "Чтобы отменить, нажми «Назад»."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад к триггерам", callback_data="triggers:back")]
        ]
    )

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.message(TriggerStates.waiting_for_delete)
async def process_triggers_delete(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    raw = (msg.text or "").strip()
    to_delete = _split_trigger_phrases(raw)
    if not to_delete:
        await msg.answer(
            "Нужно отправить хотя бы одно слово или фразу, разделив несколько значений запятыми."
        )
        return

    row_id, phrases = await get_triggers()
    if not phrases:
        await state.clear()
        await msg.answer("Список триггеров и так пуст.")
        return

    delete_set = {p.lower() for p in to_delete}

    new_phrases: List[str] = []
    removed = 0
    for p in phrases:
        if p.lower() in delete_set:
            removed += 1
            continue
        new_phrases.append(p)

    await save_triggers(row_id, new_phrases)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К триггерам", callback_data="settings:triggers:1")]
        ]
    )

    await msg.answer(f"✅ Удалено триггеров: {removed}", reply_markup=kb)
    
@router.callback_query(F.data == "triggers:back")
async def triggers_back(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    callback.data = "settings:triggers:1"
    await settings_triggers_menu(callback, state)    

def _require_prompt_deps():
    assert _split_prompt_pages and _get_ai_system_prompt and _set_ai_system_prompt and _get_db_pool


@router.callback_query(F.data.startswith("settings:ai_prompt"))
async def settings_ai_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    _require_prompt_deps()

    parts = callback.data.split(":")
    page = 1
    if len(parts) == 3 and parts[2].isdigit():
        page = max(1, int(parts[2]))

    pages = _split_prompt_pages(_get_ai_system_prompt(), PROMPT_PAGE_SIZE)
    total_pages = len(pages) or 1
    page = min(page, total_pages)
    current_text = pages[page - 1] if pages else "(Промпт пока пустой)"

    text = (
        "🤖 Промпт ИИ\n\n"
        f"Страница {page}/{total_pages}:\n\n"
        f"<pre>{escape(current_text)}</pre>\n\n"
        "Выбери действие с промптом:\n"
        "• ➕ Добавить — дописать текст в конец текущего промпта\n"
        "• ✏️ Заменить — полностью заменить текущий промпт\n"
        "• 🗑 Удалить — очистить промпт\n"
    )

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"settings:ai_prompt:{page-1}",
            )
        )
    nav_row.append(
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data=f"settings:ai_prompt:{page}",
        )
    )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"settings:ai_prompt:{page+1}",
            )
        )

    buttons: list[list[InlineKeyboardButton]] = []
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [InlineKeyboardButton(text="➕ Добавить к промпту", callback_data="settings:ai_add")]
    )
    buttons.append(
        [InlineKeyboardButton(text="✏️ Заменить промпт", callback_data="settings:ai_edit")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🗑 Удалить промпт", callback_data="settings:ai_delete")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 В админку", callback_data="back_to_admin")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    if callback.message:
        await callback.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "settings:ai_add")
async def settings_ai_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    text = (
        "➕ Добавить к промпту\n\n"
        "Отправь текст, который нужно добавить в конец текущего промпта.\n\n"
        "После отправки он будет сохранён и применён для следующих ответов ИИ."
    )

    await state.set_state(AISettingsStates.waiting_for_prompt_add)
    if callback.message:
        await callback.message.edit_text(text)
    await callback.answer()


@router.message(AISettingsStates.waiting_for_prompt_add)
async def process_ai_prompt_add(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    _require_prompt_deps()
    db_pool = _get_db_pool()

    add_text = (msg.text or "").strip()
    if not add_text:
        await msg.answer("Текст не может быть пустым. Отправь, что нужно добавить к промпту.")
        return

    new_prompt = (_get_ai_system_prompt() or "").rstrip() + "\n\n" + add_text

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE ai_settings SET system_prompt = %s WHERE id = 1",
            (new_prompt,),
        )

    _set_ai_system_prompt(new_prompt)

    await state.clear()
    await msg.answer("✅ Текст добавлен к промпту ИИ.")


@router.callback_query(F.data == "settings:ai_edit")
async def settings_ai_edit(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    text = (
        "✏️ Заменить промпт\n\n"
        "Отправь новый полный промпт одним сообщением.\n"
        "Текущий текст будет полностью заменён."
    )

    await state.set_state(AISettingsStates.waiting_for_prompt_edit)
    if callback.message:
        await callback.message.edit_text(text)
    await callback.answer()


@router.message(AISettingsStates.waiting_for_prompt_edit)
async def process_ai_prompt_edit(msg: Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        return

    _require_prompt_deps()
    db_pool = _get_db_pool()

    new_prompt = (msg.text or "").strip()
    if not new_prompt:
        await msg.answer("Промпт не может быть пустым. Отправь текст ещё раз.")
        return

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE ai_settings SET system_prompt = %s WHERE id = 1",
            (new_prompt,),
        )

    _set_ai_system_prompt(new_prompt)

    await state.clear()
    await msg.answer("✅ Промпт ИИ обновлён (полностью заменён).")


@router.callback_query(F.data == "settings:ai_delete")
async def settings_ai_delete(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    _require_prompt_deps()
    db_pool = _get_db_pool()

    empty_prompt = ""

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE ai_settings SET system_prompt = %s WHERE id = 1",
            (empty_prompt,),
        )

    _set_ai_system_prompt(empty_prompt)

    await callback.answer("Промпт очищен.", show_alert=True)

    callback.data = "settings:ai_prompt:1"
    await settings_ai_prompt(callback, state)





