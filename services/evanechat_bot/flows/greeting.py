# flows/greeting.py
import asyncio
import logging
import os
import random
from typing import Awaitable, Callable
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile

SaveMessageFn = Callable[[int, str, str, bool], Awaitable[None]]
SetUserStateFn = Callable[[int, str, str | None], Awaitable[None]]

async def send_greeting_flow(
    tg_user_id: int,
    business_id: str,
    bot: Bot,
    save_message: SaveMessageFn,
    set_user_state: SetUserStateFn,
    stage_name_known: str,
) -> None:
    voice_path = "media/greeting.ogg"
    if os.path.isfile(voice_path):
        voice = FSInputFile(voice_path)
        await bot.send_voice(
            chat_id=tg_user_id,
            business_connection_id=business_id,
            voice=voice,
        )
        await save_message(
            tg_user_id,
            "out",
            f"[voice] greeting: {voice_path}",
            is_business=True
        )
    else:
        logging.info("Greeting voice is not configured; continuing with text")

    # Пауза 1–2 секунды
    await asyncio.sleep(random.uniform(1.0, 2.0))

    # 2) Текстовый вопрос как раньше
    text2 = "Подскажи, пожалуйста, раньше уже был опыт в трейдинге?"
    await bot.send_message(
        chat_id=tg_user_id,
        business_connection_id=business_id,
        text=text2,
        parse_mode=ParseMode.HTML,
    )
    await save_message(tg_user_id, "out", text2, is_business=True)

    await set_user_state(tg_user_id, stage_name_known, "Ожидаем ответ об опыте")
