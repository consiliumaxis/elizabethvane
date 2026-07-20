# flows/existing_account.py
import logging
import os
from typing import Callable, Awaitable
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    FSInputFile,
)
from service.telegram_context import business_connection_kwargs

SaveMessageFn = Callable[[int, str, str, bool], Awaitable[None]]
SetUserStateFn = Callable[[int, str, str | None], Awaitable[None]]
BuildRegisterLinkFn = Callable[[int], str]

EXISTING_ACC_TEXT_1 = (
    "Having an existing account is not a problem. "
    "You can delete it and create a new one in just a few clicks; here are the instructions. "
    "If the old account has a balance, you can withdraw it first. "
    "You can then complete verification using the same documents, "
    "because the old account will already have been deleted."
)

EXISTING_ACC_TEXT_2 = (
    "To get started, you need to create an account using my link. "
    "I earn from traders' turnover, so a new account created through "
    "my link is a required condition for joining."
)

EXISTING_ACC_TEXT_3 = (
    "The registration link is a referral link, which means you are joining through me. "
    "This allows me to earn from your trading turnover. The more you trade and earn, "
    "the more I earn as well. That is why I am genuinely interested in teaching and "
    "supporting you throughout the process."
)

EXISTING_ACC_MEDIA_1 = os.getenv("EXISTING_ACC_MEDIA_1", "media/existing_acc_1.jpg")
EXISTING_ACC_MEDIA_2 = os.getenv("EXISTING_ACC_MEDIA_2", "media/existing_acc_2.jpg")
EXISTING_ACC_MEDIA_3 = os.getenv("EXISTING_ACC_MEDIA_3", "media/existing_acc_3.jpg")
EXISTING_ACC_MEDIA_4 = os.getenv("EXISTING_ACC_MEDIA_4", "media/existing_acc_4.jpg")


async def send_existing_account_flow(
    tg_user_id: int,
    business_id: str | None,
    bot: Bot,
    save_message: SaveMessageFn,
    set_user_state: SetUserStateFn,
    bad_stage: str,
    build_register_link: BuildRegisterLinkFn,
):

    try:
        media_group = [
            InputMediaPhoto(
                media=FSInputFile(EXISTING_ACC_MEDIA_1),
                caption=EXISTING_ACC_TEXT_1,
                parse_mode=ParseMode.HTML,
            ),
            InputMediaPhoto(
                media=FSInputFile(EXISTING_ACC_MEDIA_2),
            ),
            InputMediaPhoto(
                media=FSInputFile(EXISTING_ACC_MEDIA_3),
            ),
            InputMediaPhoto(
                media=FSInputFile(EXISTING_ACC_MEDIA_4),
            ),
        ]

        await bot.send_media_group(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            media=media_group,
        )

        await save_message(
            tg_user_id,
            "out",
            EXISTING_ACC_TEXT_1,
            is_business=bool(business_id),
        )
    except Exception as e:
        logging.warning(
            "Ошибка отправки медиа-группы по старому аккаунту: %s", e
        )

    try:
        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=EXISTING_ACC_TEXT_2,
            parse_mode=ParseMode.HTML,
        )
        await save_message(
            tg_user_id,
            "out",
            EXISTING_ACC_TEXT_2,
            is_business=bool(business_id),
        )
    except Exception as e:
        logging.warning(
            "Ошибка отправки 2-го текстового сообщения по старому аккаунту: %s", e
        )

    try:
        reg_link = build_register_link(tg_user_id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Register using my link",
                        url=reg_link,
                    )
                ]
            ]
        )

        await bot.send_message(
            chat_id=tg_user_id,
            **business_connection_kwargs(business_id),
            text=EXISTING_ACC_TEXT_3,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        await save_message(
            tg_user_id,
            "out",
            EXISTING_ACC_TEXT_3,
            is_business=bool(business_id),
        )
    except Exception as e:
        logging.warning(
            "Ошибка отправки 3-го сообщения (текст + кнопка) по старому аккаунту: %s", e
        )

    try:
        notes = (
            "У клиента уже был старый аккаунт, отправлена инструкция по удалению "
            "и новой регистрации (медиа-группа + текстовые сообщения)."
        )
        await set_user_state(tg_user_id, bad_stage, notes)
    except Exception as e:
        logging.warning(
            "Не удалось обновить user_state для старого аккаунта: %s", e
        )
