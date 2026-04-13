import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException


class TelegramAuthError(HTTPException):
    def __init__(self, detail: str = "Unauthorized Telegram WebApp request"):
        super().__init__(status_code=401, detail=detail)


def _build_data_check_string(init_data: str) -> str:
    pairs = parse_qsl(init_data, keep_blank_values=True)
    filtered = [(k, v) for k, v in pairs if k != "hash"]
    filtered.sort(key=lambda item: item[0])
    return "\n".join(f"{k}={v}" for k, v in filtered)


def _extract_hash(init_data: str) -> str:
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = (pairs.get("hash") or "").strip()
    if not received_hash:
        raise TelegramAuthError("Telegram init data hash missing")
    return received_hash


def verify_telegram_init_data(init_data: str) -> Dict[str, Any]:
    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise HTTPException(status_code=500, detail="BOT_TOKEN is not configured")

    if not init_data or not init_data.strip():
        raise TelegramAuthError("Telegram init data header missing")

    received_hash = _extract_hash(init_data)
    data_check_string = _build_data_check_string(init_data)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramAuthError("Telegram init data is invalid")

    payload = dict(parse_qsl(init_data, keep_blank_values=True))
    auth_date_raw = (payload.get("auth_date") or "").strip()
    max_age = int((os.getenv("TG_INIT_DATA_MAX_AGE") or "86400").strip())
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError:
            raise TelegramAuthError("Telegram auth_date is invalid")
        if auth_date > int(time.time()) + 60:
            raise TelegramAuthError("Telegram auth_date is from the future")
        if int(time.time()) - auth_date > max_age:
            raise TelegramAuthError("Telegram init data is expired")

    user_raw = payload.get("user")
    if not user_raw:
        raise TelegramAuthError("Telegram user payload missing")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise TelegramAuthError("Telegram user payload is invalid")

    user_id = user.get("id")
    if not user_id:
        raise TelegramAuthError("Telegram user id missing")

    return {
        "init_data": init_data,
        "auth_date": auth_date_raw,
        "user": user,
        "user_id": int(user_id),
        "username": user.get("username") or "",
        "first_name": user.get("first_name") or "",
        "last_name": user.get("last_name") or "",
        "photo_url": user.get("photo_url") or "",
    }


async def get_telegram_user(x_tg_init_data: str = Header(default="", alias="X-TG-Init-Data")) -> Dict[str, Any]:
    return verify_telegram_init_data(x_tg_init_data)
