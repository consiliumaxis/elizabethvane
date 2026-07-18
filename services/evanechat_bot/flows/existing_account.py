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

SaveMessageFn = Callable[[int, str, str, bool], Awaitable[None]]
SetUserStateFn = Callable[[int, str, str | None], Awaitable[None]]
BuildRegisterLinkFn = Callable[[int], str]

EXISTING_ACC_TEXT_1 = (
    "То что у тебя есть аккаунт — не проблема. "
    "Его можно удалить и создать новый за пару кликов, вот инструкция. "
    "Если на старом аккаунте есть баланс — его можно поставить на вывод. "
    "При этом верификацию можно пройти на те же документы, "
    "так как старый аккаунт уже будет удалён."
)

EXISTING_ACC_TEXT_2 = (
    "Для начала работы требуется создать аккаунт именно по моей ссылке, "
    "так как я получаю доход от оборота трейдеров, и обязательным условием "
    "для вступления является новый аккаунт."
)

EXISTING_ACC_TEXT_3 = (
    "Ссылка, по которой ты будешь регистрироваться, является реферальной — "
    "это значит, что ты пришёл «от меня». За счёт этого я получаю прибыль "
    "от твоего торгового оборота. Чем больше ты торгуешь и зарабатываешь, "
    "тем больше заработаю и я. В этом мой интерес тебя обучить и вести, "
    "а не работать за «спасибо»."
)

EXISTING_ACC_MEDIA_1 = os.getenv("EXISTING_ACC_MEDIA_1", "media/existing_acc_1.jpg")
EXISTING_ACC_MEDIA_2 = os.getenv("EXISTING_ACC_MEDIA_2", "media/existing_acc_2.jpg")
EXISTING_ACC_MEDIA_3 = os.getenv("EXISTING_ACC_MEDIA_3", "media/existing_acc_3.jpg")
EXISTING_ACC_MEDIA_4 = os.getenv("EXISTING_ACC_MEDIA_4", "media/existing_acc_4.jpg")


async def send_existing_account_flow(
    tg_user_id: int,
    business_id: str,
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
            business_connection_id=business_id,
            media=media_group,
        )

        await save_message(
            tg_user_id,
            "out",
            EXISTING_ACC_TEXT_1,
            is_business=True,
        )
    except Exception as e:
        logging.warning(
            "Ошибка отправки медиа-группы по старому аккаунту: %s", e
        )

    try:
        await bot.send_message(
            chat_id=tg_user_id,
            business_connection_id=business_id,
            text=EXISTING_ACC_TEXT_2,
            parse_mode=ParseMode.HTML,
        )
        await save_message(
            tg_user_id,
            "out",
            EXISTING_ACC_TEXT_2,
            is_business=True,
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
                        text="🔗 Зарегистрироваться по моей ссылке",
                        url=reg_link,
                    )
                ]
            ]
        )

        await bot.send_message(
            chat_id=tg_user_id,
            business_connection_id=business_id,
            text=EXISTING_ACC_TEXT_3,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        await save_message(
            tg_user_id,
            "out",
            EXISTING_ACC_TEXT_3,
            is_business=True,
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
