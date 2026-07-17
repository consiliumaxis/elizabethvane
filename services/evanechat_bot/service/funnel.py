# service/funnel.py
import re
from typing import Awaitable, Callable
from config import (
    STAGE_NEW,
    STAGE_NAME_KNOWN,
    STAGE_REG_LINK_SENT,
    STAGE_WAITING_ACCOUNT_ID,
    STAGE_ACCOUNT_ID_SENT,
    STAGE_ACCOUNT_ID_BAD,
    STAGE_ACCOUNT_ID_OK,
    STAGE_WAITING_DEPOSIT,
    STAGE_DEPOSIT_DONE,
)

GetUserStateFn = Callable[[int], Awaitable[tuple[str, str | None]]]
GetUserStatusFlagsFn = Callable[[int], Awaitable[tuple[int, int, str | None]]]
SetUserStateFn = Callable[[int, str, str | None], Awaitable[None]]


def _contains_any(text: str, patterns: list[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(p in t for p in patterns)


async def update_user_stage_from_exchange(
    tg_user_id: int,
    user_text: str,
    ai_reply: str,
    get_user_state: GetUserStateFn,
    get_user_status_flags: GetUserStatusFlagsFn,
    set_user_state: SetUserStateFn,
) -> None:
    
    stage, notes = await get_user_state(tg_user_id)
    u = (user_text or "").lower()
    a = (ai_reply or "").lower()

    new_stage = stage
    new_notes = notes

    if stage == STAGE_NEW:
        if "приятно познакомиться" in a:
            new_stage = STAGE_NAME_KNOWN

    if _contains_any(a, [
        "ссылка на регистрацию",
        "зарегистрируйся по моей ссылке",
        "вот ссылка для регистрации",
        "регистрация на pocket option",
    ]):
        new_stage = STAGE_REG_LINK_SENT

    if _contains_any(a, [
        "пришли свой айди",
        "отправь id торгового счета",
        "жду твой айди",
    ]):
        new_stage = STAGE_WAITING_ACCOUNT_ID
        
    if stage in {STAGE_REG_LINK_SENT, STAGE_WAITING_ACCOUNT_ID, STAGE_NAME_KNOWN}:
        if re.search(r"\b\d{5,}\b", u) or "id" in u:
            new_stage = STAGE_ACCOUNT_ID_SENT
            note_line = f"Последний ID от клиента: {user_text[:100]}"
            new_notes = (notes or "") + ("\n" if notes else "") + note_line

    if _contains_any(a, [
        "нужно удалить этот аккаунт",
        "удали этот аккаунт",
        "зарегистрироваться по новой по моей ссылке",
    ]):
        new_stage = STAGE_ACCOUNT_ID_BAD

    if _contains_any(a, [
        "id подходит",
        "ид подходит",
        "аккаунт подходит",
        "аккаунт подтвержден",
        "проверка прошла успешно",
    ]):
        new_stage = STAGE_ACCOUNT_ID_OK

    if _contains_any(a, [
        "теперь нужно пополнить",
        "сделай депозит",
        "внеси депозит",
        "пополни счет",
    ]):
        new_stage = STAGE_WAITING_DEPOSIT

    if _contains_any(u, [
        "сделал депозит",
        "депозит сделал",
        "пополнил",
        "зачислили деньги",
    ]):
        new_stage = STAGE_DEPOSIT_DONE

    reg_status, dep_status, _ = await get_user_status_flags(tg_user_id)

    if reg_status == 0:
        if new_stage in {STAGE_ACCOUNT_ID_OK, STAGE_WAITING_DEPOSIT, STAGE_DEPOSIT_DONE}:
            new_stage = STAGE_REG_LINK_SENT

    if dep_status == 0:
        if new_stage == STAGE_DEPOSIT_DONE:
            new_stage = STAGE_WAITING_DEPOSIT

    if new_stage != stage or new_notes != notes:
        await set_user_state(tg_user_id, new_stage, new_notes)
