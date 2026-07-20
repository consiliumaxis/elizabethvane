# flows/vip.py
import asyncio
import logging
from datetime import datetime
from typing import Callable, Awaitable

from aiogram import Bot
from aiogram.enums import ParseMode

from zoneinfo import ZoneInfo
from config import CHANNEL_URL, SUPPORT_URL
from service.telegram_context import business_connection_kwargs

MSK_TZ = ZoneInfo("Europe/Moscow")

SaveMessageFn = Callable[[int, str, str, bool], Awaitable[None]]
GetUserStateFn = Callable[[int], Awaitable[tuple[str, str | None]]]
SetUserStateFn = Callable[[int, str, str | None], Awaitable[None]]


async def send_vip_onboarding_flow(
    tg_user_id: int,
    business_id: str | None,
    bot: Bot,
    save_message: SaveMessageFn,
    get_user_state: GetUserStateFn,
    set_user_state: SetUserStateFn,
) -> int:

    sent_count = 0

    text1 = "All set, give me just a second."
    try:
        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=text1,
            parse_mode=ParseMode.HTML,
        )
        await save_message(tg_user_id, "out", text1, is_business=bool(business_id))
        sent_count += 1
    except Exception as e:
        logging.warning("[vip_flow] error sending msg1: %s", e)
        return sent_count

    await asyncio.sleep(2.0)

    text2 = (
        "<b>Congratulations! Your access to the Elizabeth Vane team is now open 🔥</b>\n\n"
        f"Channel: {CHANNEL_URL}"
    )
    try:
        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=text2,
            parse_mode=ParseMode.HTML,
        )
        await save_message(tg_user_id, "out", text2, is_business=bool(business_id))
        sent_count += 1
    except Exception as e:
        logging.warning("[vip_flow] error sending msg2: %s", e)

    await asyncio.sleep(1.0)

    text3 = f"If you need any help, contact support: {SUPPORT_URL}"
    try:
        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=text3,
            parse_mode=ParseMode.HTML,
        )
        await save_message(tg_user_id, "out", text3, is_business=bool(business_id))
        sent_count += 1
    except Exception as e:
        logging.warning("[vip_flow] error sending msg3: %s", e)

    await asyncio.sleep(1.0)

    text4 = "<b>All tools and analytics are available in the Elizabeth Vane app.</b>"
    try:
        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=text4,
            parse_mode=ParseMode.HTML,
        )
        await save_message(tg_user_id, "out", text4, is_business=bool(business_id))
        sent_count += 1
    except Exception as e:
        logging.warning("[vip_flow] error sending msg4: %s", e)

    try:
        stage, notes = await get_user_state(tg_user_id)

        timestamp = datetime.now(MSK_TZ).strftime("%Y-%m-%d %H:%M")
        marker = "VIP доступ выдан"

        if notes and marker in notes:
            new_notes = notes
        else:
            line = f"{marker} {timestamp}"
            new_notes = (notes + "\n" + line) if notes else line

        await set_user_state(tg_user_id, stage, new_notes)
    except Exception as e:
        logging.warning("[vip_flow] error updating user_state notes: %s", e)

    return sent_count
