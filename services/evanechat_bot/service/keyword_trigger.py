# service/keyword_trigger.py
import logging
import httpx
import asyncio
import re
from typing import Optional, List
from aiogram import Bot
from config import AFFILIATE_API_SECRET, AFFILIATE_BASE_URL, AFFILIATE_BOT_ID
from db import get_keyword_triggers
from service.telegram_context import business_connection_kwargs


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def find_keyword_trigger(user_text: str, phrases: List[str]) -> Optional[str]:
    text = normalize(user_text)
    for phrase in phrases:
        p = normalize(phrase)
        if p and p in text:
            return phrase
    return None

async def handle_keyword_trigger(
    *,
    tg_user_id: int,
    business_id: str | None,
    user_text: str,
    bot: Bot,
    save_message,
    db_pool,
    notify_admins,
    get_user_status_flags,
    disable_bot_for_user,
    get_trader_id_for_user,
    update_user_memory,
    delivery_scope: str = "business",
) -> bool:

    reg_status, dep_status, _ = await get_user_status_flags(tg_user_id)

    if not (reg_status == 1 and dep_status == 1):
        return False

    phrases = await get_keyword_triggers(db_pool, delivery_scope)
    hit = find_keyword_trigger(user_text, phrases)
    if not hit:
        return False

    reason = f"keyword_trigger: {hit}"
    await disable_bot_for_user(tg_user_id, reason)

    try:
        text = "I’ll get back to you with an answer shortly 🔥"
        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=text,
        )
        await save_message(tg_user_id, "out", text, is_business=bool(business_id))
    except Exception as e:
        logging.warning("[keyword_trigger] reply failed: %s", e)

    # 5. Trader ID
    trader_id = await get_trader_id_for_user(tg_user_id)

    affiliate_block = "Trader ID отсутствует"

    if trader_id:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    AFFILIATE_BASE_URL.rstrip("/") + "/affiliate/user-info",
                    headers={"X-Affiliate-Secret": AFFILIATE_API_SECRET},
                    params={
                        "bot_id": AFFILIATE_BOT_ID,
                        "trader_id": trader_id,
                    },
                )
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                u = data["data"]
                affiliate_block = (
                    "<pre>"
                    f"Trader ID:   {trader_id}\n"
                    f"Баланс:      {u.get('balance')}\n"
                    f"Сумма депов: {u.get('deposits_sum')}\n"
                    f"Регистрация: {u.get('reg_date')}"
                    "</pre>"
                )
            else:
                affiliate_block = f"Ошибка API: {data.get('message')}"
        except Exception as e:
            affiliate_block = f"Ошибка affiliate API: {e}"

    username_line = "Username: не указан"
    try:
        async with db_pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM users WHERE tg_user_id = %s",
                (tg_user_id,),
            )
            row = await cur.fetchone()
        if row and row[0]:
            username_line = f'<a href="https://t.me/{row[0]}">@{row[0]}</a>'
    except Exception as e:
        logging.warning("[keyword_trigger] username fetch failed: %s", e)

    notify_text = (
        "🔥 <b>Клиент задел ключевое слово</b>\n\n"
        f"<b>Ключевое слово:</b> <b>{hit}</b>\n\n"
        f"Tgid: <code>{tg_user_id}</code>\n"
        f"{username_line}\n\n"
        f"{affiliate_block}\n\n"
        "<b>Сообщение клиента:</b>\n"
        f"{user_text[:1000]}\n\n"
        f"<b>Чат с клиентом остановлен!</b>"
    )

    await notify_admins(notify_text, bot, tg_user_id=tg_user_id)

    asyncio.create_task(update_user_memory(tg_user_id))
    return True
