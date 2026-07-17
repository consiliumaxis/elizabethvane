import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import aiomysql
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel


_pool = None
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_KV_KEYS = (
    "BOT_NAME",
    "COMPANY_CODE",
    "MIN_DEPOSIT_THRESHOLD",
    "CHECK_COMPANY",
    "POSTBACK_LOG_CHAT_ID",
    "LOG_REGISTRATIONS",
    "LOG_DEPOSITS",
    "LOG_WITHDRAWALS",
    "LOG_COMMISSIONS",
    "LOG_SYSTEM_ERRORS",
    "STATS_COMMISSION_MODE",
    "FUNNEL_MEDIA_ENABLED",
)

_FUNNEL_DEFAULTS = (
    ("a1", "A", "Знакомство с Элизабет"),
    ("a2", "A", "Открытость системы"),
    ("a3", "A", "Доступно каждому"),
    ("a4", "A", "17 индикаторов и 10 стратегий"),
    ("a5", "A", "Канал видео-отзывов"),
    ("w1", "W", "Как работает AI-инструмент"),
    ("w2", "W", "Механика сигналов"),
    ("w2.5", "W", "Конфлюенс индикаторов"),
    ("w2.6", "W", "Порог сигнала 70%"),
    ("w3", "W", "Выбор актива"),
    ("w4", "W", "Запрос анализа"),
    ("w5", "W", "Ответ на сомнения"),
    ("w5.2", "W", "Проверка результата"),
    ("w5.3", "W", "Дисциплина"),
    ("w5.4", "W", "Не торговать на эмоциях"),
    ("w5.5", "W", "Доверие к системе"),
    ("w6", "W", "Регистрация у брокера"),
    ("e1", "E", "Зачем нужен депозит"),
    ("e2", "E", "Что открывается после депозита"),
    ("e3", "E", "Доверяй данным"),
    ("e4", "E", "Честно об убытках"),
    ("e5", "E", "Первые шаги"),
    ("e5.2", "E", "Работа с сомнениями"),
    ("e5.3", "E", "Дисциплина после пополнения"),
    ("e5.4", "E", "Переход к торговле"),
    ("r1", "R", "Онбординг и риск-менеджмент"),
    ("r2", "R", "Алгоритм открытия сделки"),
    ("r3", "R", "Нет сильного сигнала"),
    ("r3.2", "R", "Торговля на эмоциях"),
    ("r4", "R", "Убыточная сделка"),
    ("r5", "R", "Нет времени и VIP"),
    ("r6", "R", "Страх перед сделкой"),
    ("c1", "C", "Нет времени — копитрейдинг"),
    ("c2", "C", "Проверка по Trader ID"),
    ("c3", "C", "Условия копитрейдеров"),
    ("c4", "C", "Марафон и результаты"),
    ("c6", "C", "Как подключиться"),
)


class AichatterSettingsUpdate(BaseModel):
    system_enabled: Optional[bool] = None
    work_start: Optional[str] = None
    work_end: Optional[str] = None
    bot_name: Optional[str] = None
    company_code: Optional[str] = None
    min_deposit: Optional[float] = None
    check_company: Optional[bool] = None
    ai_enabled: Optional[bool] = None
    ai_model: Optional[str] = None
    openai_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    planner_system_prompt: Optional[str] = None
    postback_log_chat_id: Optional[str] = None
    log_registrations: Optional[bool] = None
    log_deposits: Optional[bool] = None
    log_withdrawals: Optional[bool] = None
    log_commissions: Optional[bool] = None
    log_system_errors: Optional[bool] = None
    commission_mode: Optional[str] = None
    funnel_media_enabled: Optional[bool] = None


class AichatterTriggersUpdate(BaseModel):
    phrases: list[str]


class AichatterUserUpdate(BaseModel):
    bot_active: bool
    reason: Optional[str] = None


class AichatterAdminUpdate(BaseModel):
    telegram_id: int


class AichatterManualCommissionUpdate(BaseModel):
    stat_date: date
    amount: float


class AichatterFunnelItemUpdate(BaseModel):
    media_key: str
    block_code: str
    title: str
    description: Optional[str] = None
    sort_order: int
    enabled: bool = True


class AichatterFunnelUpdate(BaseModel):
    items: list[AichatterFunnelItemUpdate]


def _config() -> Dict[str, Any]:
    return {
        "host": (os.getenv("AICHAT_DB_HOST") or os.getenv("DB_HOST") or "localhost").strip(),
        "port": int((os.getenv("AICHAT_DB_PORT") or "3306").strip()),
        "user": (os.getenv("AICHAT_DB_USER") or "").strip(),
        "password": os.getenv("AICHAT_DB_PASSWORD") or "",
        "db": (os.getenv("AICHAT_DB_NAME") or "aichat").strip(),
        "autocommit": True,
        "charset": "utf8mb4",
        "minsize": 1,
        "maxsize": 5,
    }


def _media_dir() -> Path:
    return Path(os.getenv("AICHAT_MEDIA_DIR") or "/root/evanechat/media/funnel").resolve()


async def _ensure_funnel_schema(pool):
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS funnel_media (
                id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                media_key VARCHAR(32) NOT NULL UNIQUE,
                block_code VARCHAR(16) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT NULL,
                sort_order INT NOT NULL,
                file_name VARCHAR(255) NOT NULL,
                telegram_file_id VARCHAR(255) NULL,
                enabled TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_funnel_media_order (sort_order)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS funnel_media_sent (
                tg_user_id BIGINT UNSIGNED NOT NULL,
                media_key VARCHAR(32) NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (tg_user_id, media_key),
                INDEX idx_funnel_media_sent_at (sent_at)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """
        )
        for index, (media_key, block_code, title) in enumerate(_FUNNEL_DEFAULTS, start=1):
            await cur.execute(
                """
                INSERT INTO funnel_media
                    (media_key, block_code, title, description, sort_order, file_name, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE media_key = media_key
                """,
                (media_key, block_code, title, title, index * 10, f"{media_key.upper()}.MP4"),
            )


async def _get_pool():
    global _pool
    if _pool is not None and not _pool.closed:
        return _pool
    config = _config()
    if not config["user"] or not config["password"]:
        raise HTTPException(status_code=503, detail="AIChatter database is not configured")
    try:
        _pool = await aiomysql.create_pool(**config)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AIChatter database is unavailable") from exc
    return _pool


async def _ensure_ai_settings_schema(pool):
    async with pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'ai_settings'
              AND COLUMN_NAME = 'openai_api_key'
            LIMIT 1
            """
        )
        if not await cur.fetchone():
            await cur.execute("ALTER TABLE ai_settings ADD COLUMN openai_api_key TEXT NULL")


def _time_text(value) -> Optional[str]:
    if value is None:
        return None
    return str(value)[:5]


def _split_phrases(raw: str) -> list[str]:
    result = []
    seen = set()
    for item in str(raw or "").split(","):
        phrase = " ".join(item.split()).strip()
        key = phrase.casefold()
        if phrase and key not in seen:
            seen.add(key)
            result.append(phrase[:255])
    return result


async def _load_settings(pool) -> Dict[str, Any]:
    await _ensure_ai_settings_schema(pool)
    async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
        await cur.execute("SELECT work_start, work_end, is_enabled FROM settings WHERE id = 1")
        settings = await cur.fetchone() or {}
        await cur.execute(
            "SELECT system_prompt, planner_system_prompt, enabled, model, openai_api_key FROM ai_settings WHERE id = 1"
        )
        ai = await cur.fetchone() or {}
        await cur.execute(
            f"SELECT skey, svalue FROM kv_settings WHERE skey IN ({','.join(['%s'] * len(_KV_KEYS))})",
            _KV_KEYS,
        )
        kv = {row["skey"]: row.get("svalue") or "" for row in await cur.fetchall()}
    return {
        "system_enabled": bool(settings.get("is_enabled", 1)),
        "work_start": _time_text(settings.get("work_start")),
        "work_end": _time_text(settings.get("work_end")),
        "bot_name": kv.get("BOT_NAME", "Elizabeth Vane"),
        "company_code": kv.get("COMPANY_CODE", ""),
        "min_deposit": float(kv.get("MIN_DEPOSIT_THRESHOLD") or 0),
        "check_company": kv.get("CHECK_COMPANY", "1") == "1",
        "postback_log_chat_id": kv.get("POSTBACK_LOG_CHAT_ID", ""),
        "log_registrations": kv.get("LOG_REGISTRATIONS", "1") == "1",
        "log_deposits": kv.get("LOG_DEPOSITS", "1") == "1",
        "log_withdrawals": kv.get("LOG_WITHDRAWALS", "1") == "1",
        "log_commissions": kv.get("LOG_COMMISSIONS", "1") == "1",
        "log_system_errors": kv.get("LOG_SYSTEM_ERRORS", "0") == "1",
        "commission_mode": kv.get("STATS_COMMISSION_MODE", "auto"),
        "funnel_media_enabled": kv.get("FUNNEL_MEDIA_ENABLED", "1") == "1",
        "ai_enabled": bool(ai.get("enabled", 1)),
        "ai_model": ai.get("model") or "gpt-4.1",
        "openai_api_key": "",
        "openai_key_configured": bool(str(ai.get("openai_api_key") or "").strip()),
        "system_prompt": ai.get("system_prompt") or "",
        "planner_system_prompt": ai.get("planner_system_prompt") or "",
    }


async def _set_kv(cur, key: str, value: Any):
    await cur.execute(
        "INSERT INTO kv_settings (skey, svalue) VALUES (%s, %s) ON DUPLICATE KEY UPDATE svalue = VALUES(svalue)",
        (key, str(value)),
    )


def create_aichatter_admin_router(admin_dependency) -> APIRouter:
    router = APIRouter(prefix="/api/admin/aichatter", tags=["admin-aichatter"])

    @router.get("/overview")
    async def overview(admin=Depends(admin_dependency)):
        pool = await _get_pool()
        settings = await _load_settings(pool)
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT COUNT(*) AS users_total,
                       COALESCE(SUM(bot_active = 1), 0) AS users_active,
                       COALESCE(SUM(registration_status = 1), 0) AS registrations,
                       COALESCE(SUM(deposit_status = 1), 0) AS deposits
                FROM users
                """
            )
            counts = await cur.fetchone() or {}
            await cur.execute("SELECT COUNT(*) AS messages_total FROM messages")
            counts.update(await cur.fetchone() or {})
            await cur.execute("SELECT COUNT(*) AS admins_total FROM admin_users")
            counts.update(await cur.fetchone() or {})
            await cur.execute("SELECT phrases FROM keyword_triggers ORDER BY id LIMIT 1")
            trigger_row = await cur.fetchone() or {}
        counts["triggers_total"] = len(_split_phrases(trigger_row.get("phrases") or ""))
        return {"status": "success", "settings": settings, "counts": counts}

    @router.put("/settings")
    async def update_settings(payload: AichatterSettingsUpdate, admin=Depends(admin_dependency)):
        pool = await _get_pool()
        await _ensure_ai_settings_schema(pool)
        data = payload.model_dump(exclude_unset=True)
        for key in ("work_start", "work_end"):
            if key in data and data[key] is not None and not _TIME_RE.fullmatch(data[key]):
                raise HTTPException(status_code=400, detail=f"{key} must use HH:MM format")
        if "min_deposit" in data and (data["min_deposit"] is None or data["min_deposit"] < 0):
            raise HTTPException(status_code=400, detail="Minimum deposit must be non-negative")
        if data.get("commission_mode") not in (None, "auto", "manual", "auto_plus"):
            raise HTTPException(status_code=400, detail="Invalid commission mode")
        if "ai_model" in data and not str(data["ai_model"] or "").strip():
            raise HTTPException(status_code=400, detail="AI model is required")
        if "openai_api_key" in data:
            openai_api_key = str(data["openai_api_key"] or "").strip()
            if openai_api_key and (not openai_api_key.startswith("sk-") or len(openai_api_key) < 20):
                raise HTTPException(status_code=400, detail="Invalid OpenAI API key")
            if not openai_api_key:
                data.pop("openai_api_key")

        async with pool.acquire() as conn, conn.cursor() as cur:
            setting_parts, setting_values = [], []
            for field, column in (("system_enabled", "is_enabled"), ("work_start", "work_start"), ("work_end", "work_end")):
                if field in data:
                    setting_parts.append(f"{column} = %s")
                    value = int(data[field]) if field == "system_enabled" else data[field]
                    setting_values.append(value)
            if setting_parts:
                await cur.execute(f"UPDATE settings SET {', '.join(setting_parts)} WHERE id = 1", setting_values)

            ai_parts, ai_values = [], []
            for field, column in (
                ("ai_enabled", "enabled"),
                ("ai_model", "model"),
                ("openai_api_key", "openai_api_key"),
                ("system_prompt", "system_prompt"),
                ("planner_system_prompt", "planner_system_prompt"),
            ):
                if field in data:
                    ai_parts.append(f"{column} = %s")
                    ai_values.append(int(data[field]) if field == "ai_enabled" else str(data[field]).strip())
            if ai_parts:
                await cur.execute(f"UPDATE ai_settings SET {', '.join(ai_parts)} WHERE id = 1", ai_values)

            kv_map = {
                "bot_name": "BOT_NAME",
                "company_code": "COMPANY_CODE",
                "min_deposit": "MIN_DEPOSIT_THRESHOLD",
                "check_company": "CHECK_COMPANY",
                "postback_log_chat_id": "POSTBACK_LOG_CHAT_ID",
                "log_registrations": "LOG_REGISTRATIONS",
                "log_deposits": "LOG_DEPOSITS",
                "log_withdrawals": "LOG_WITHDRAWALS",
                "log_commissions": "LOG_COMMISSIONS",
                "log_system_errors": "LOG_SYSTEM_ERRORS",
                "commission_mode": "STATS_COMMISSION_MODE",
                "funnel_media_enabled": "FUNNEL_MEDIA_ENABLED",
            }
            for field, key in kv_map.items():
                if field in data:
                    value = int(data[field]) if isinstance(data[field], bool) else data[field]
                    await _set_kv(cur, key, value)
        return {"status": "success", "settings": await _load_settings(pool)}

    @router.get("/users")
    async def users(
        search: str = "",
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=30, ge=1, le=100),
        admin=Depends(admin_dependency),
    ):
        pool = await _get_pool()
        where, params = "", []
        search = search.strip()
        if search:
            like = f"%{search}%"
            where = "WHERE CAST(u.tg_user_id AS CHAR) LIKE %s OR u.username LIKE %s OR u.first_name LIKE %s OR u.trader_id LIKE %s"
            params.extend((like, like, like, like))
        offset = (page - 1) * limit
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(f"SELECT COUNT(*) AS n FROM users u {where}", params)
            total = int((await cur.fetchone() or {}).get("n") or 0)
            await cur.execute(
                f"""
                SELECT u.tg_user_id, u.first_name, u.username, u.country, u.trader_id,
                       u.registration_status, u.deposit_status, u.bot_active,
                       u.bot_block_reason, u.created_at, u.last_message_at,
                       s.stage, s.notes, COUNT(m.id) AS messages_count
                FROM users u
                LEFT JOIN user_state s ON s.tg_user_id = u.tg_user_id
                LEFT JOIN messages m ON m.tg_user_id = u.tg_user_id
                {where}
                GROUP BY u.tg_user_id, s.stage, s.notes
                ORDER BY u.last_message_at DESC, u.created_at DESC
                LIMIT %s OFFSET %s
                """,
                tuple(params + [limit, offset]),
            )
            rows = await cur.fetchall()
        return {"status": "success", "users": rows, "total": total, "page": page, "limit": limit}

    @router.get("/users/{telegram_id}/messages")
    async def user_messages(
        telegram_id: int,
        limit: int = Query(default=100, ge=1, le=300),
        admin=Depends(admin_dependency),
    ):
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, direction, is_business, text, created_at FROM messages WHERE tg_user_id = %s ORDER BY id DESC LIMIT %s",
                (telegram_id, limit),
            )
            rows = list(reversed(await cur.fetchall()))
        return {"status": "success", "messages": rows}

    @router.patch("/users/{telegram_id}")
    async def update_user(telegram_id: int, payload: AichatterUserUpdate, admin=Depends(admin_dependency)):
        pool = await _get_pool()
        reason = None if payload.bot_active else (payload.reason or "Отключено из веб-админцентра")[:255]
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE users
                SET bot_active = %s,
                    bot_blocked_at = CASE WHEN %s = 1 THEN NULL ELSE NOW() END,
                    bot_block_reason = %s
                WHERE tg_user_id = %s
                """,
                (int(payload.bot_active), int(payload.bot_active), reason, telegram_id),
            )
            if not cur.rowcount:
                raise HTTPException(status_code=404, detail="User not found")
        return {"status": "success", "telegram_id": telegram_id, "bot_active": payload.bot_active}

    @router.get("/triggers")
    async def triggers(admin=Depends(admin_dependency)):
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT id, phrases FROM keyword_triggers ORDER BY id LIMIT 1")
            row = await cur.fetchone() or {}
        return {"status": "success", "phrases": _split_phrases(row.get("phrases") or "")}

    @router.put("/triggers")
    async def update_triggers(payload: AichatterTriggersUpdate, admin=Depends(admin_dependency)):
        phrases = _split_phrases(",".join(payload.phrases))
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("SELECT id FROM keyword_triggers ORDER BY id LIMIT 1")
            row = await cur.fetchone()
            if row:
                await cur.execute("UPDATE keyword_triggers SET phrases = %s WHERE id = %s", (", ".join(phrases), row[0]))
            else:
                await cur.execute("INSERT INTO keyword_triggers (phrases) VALUES (%s)", (", ".join(phrases),))
        return {"status": "success", "phrases": phrases}

    @router.get("/funnel")
    async def funnel(admin=Depends(admin_dependency)):
        pool = await _get_pool()
        await _ensure_funnel_schema(pool)
        media_dir = _media_dir()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT fm.id, fm.media_key, fm.block_code, fm.title, fm.description,
                       fm.sort_order, fm.file_name, fm.enabled, fm.updated_at,
                       COUNT(fms.tg_user_id) AS sent_count
                FROM funnel_media fm
                LEFT JOIN funnel_media_sent fms ON fms.media_key = fm.media_key
                GROUP BY fm.id
                ORDER BY fm.sort_order, fm.id
                """
            )
            rows = await cur.fetchall()
        for row in rows:
            file_path = (media_dir / Path(row["file_name"]).name).resolve()
            exists = file_path.parent == media_dir and file_path.is_file()
            row["file_exists"] = exists
            row["file_size"] = file_path.stat().st_size if exists else 0
        return {"status": "success", "items": rows, "media_dir": str(media_dir)}

    @router.put("/funnel")
    async def update_funnel(payload: AichatterFunnelUpdate, admin=Depends(admin_dependency)):
        if not payload.items:
            raise HTTPException(status_code=400, detail="Funnel must contain at least one item")
        keys = [item.media_key.strip().lower() for item in payload.items]
        if len(keys) != len(set(keys)):
            raise HTTPException(status_code=400, detail="Duplicate funnel media key")
        for item, media_key in zip(payload.items, keys):
            if not re.fullmatch(r"[a-z][a-z0-9]*(?:\.[0-9]+)?", media_key):
                raise HTTPException(status_code=400, detail=f"Invalid media key: {item.media_key}")
            if item.block_code.upper() not in {"A", "W", "E", "R", "C"}:
                raise HTTPException(status_code=400, detail=f"Invalid block: {item.block_code}")
            if not item.title.strip():
                raise HTTPException(status_code=400, detail=f"Title is required: {item.media_key}")

        pool = await _get_pool()
        await _ensure_funnel_schema(pool)
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT media_key FROM funnel_media")
            known = {row["media_key"] for row in await cur.fetchall()}
            unknown = sorted(set(keys) - known)
            if unknown:
                raise HTTPException(status_code=400, detail=f"Unknown media keys: {', '.join(unknown)}")
            for item, media_key in zip(payload.items, keys):
                await cur.execute(
                    """
                    UPDATE funnel_media
                    SET block_code = %s, title = %s, description = %s,
                        sort_order = %s, enabled = %s
                    WHERE media_key = %s
                    """,
                    (
                        item.block_code.upper(),
                        item.title.strip()[:255],
                        (item.description or "").strip(),
                        item.sort_order,
                        int(item.enabled),
                        media_key,
                    ),
                )
        return await funnel(admin)

    @router.put("/funnel/{media_key}/media")
    async def upload_funnel_media(media_key: str, request: Request, admin=Depends(admin_dependency)):
        media_key = media_key.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9]*(?:\.[0-9]+)?", media_key):
            raise HTTPException(status_code=400, detail="Invalid media key")
        declared_size = int(request.headers.get("content-length") or 0)
        max_size = 50 * 1024 * 1024
        if declared_size > max_size:
            raise HTTPException(status_code=413, detail="Video is larger than 50 MB")
        content_type = (request.headers.get("content-type") or "").lower()
        if content_type and "video/mp4" not in content_type and "application/octet-stream" not in content_type:
            raise HTTPException(status_code=415, detail="Only MP4 video is supported")
        payload_bytes = await request.body()
        if not payload_bytes or len(payload_bytes) > max_size:
            raise HTTPException(status_code=413, detail="Video must be between 1 byte and 50 MB")
        if b"ftyp" not in payload_bytes[:32]:
            raise HTTPException(status_code=400, detail="File is not a valid MP4 container")

        pool = await _get_pool()
        await _ensure_funnel_schema(pool)
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT media_key FROM funnel_media WHERE media_key = %s", (media_key,))
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Funnel item not found")

        media_dir = _media_dir()
        media_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{media_key.upper()}.MP4"
        file_path = (media_dir / file_name).resolve()
        if file_path.parent != media_dir:
            raise HTTPException(status_code=400, detail="Invalid media path")
        temp_path = file_path.with_suffix(".uploading")
        try:
            with temp_path.open("wb") as target:
                target.write(payload_bytes)
            os.replace(temp_path, file_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE funnel_media SET file_name = %s, telegram_file_id = NULL WHERE media_key = %s",
                (file_name, media_key),
            )
        return {"status": "success", "media_key": media_key, "file_name": file_name, "file_size": len(payload_bytes)}

    @router.get("/admins")
    async def admins(admin=Depends(admin_dependency)):
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT tg_user_id, added_by, created_at FROM admin_users ORDER BY created_at")
            rows = await cur.fetchall()
        return {"status": "success", "admins": rows}

    @router.post("/admins")
    async def add_admin(payload: AichatterAdminUpdate, admin=Depends(admin_dependency)):
        if payload.telegram_id <= 0:
            raise HTTPException(status_code=400, detail="Invalid Telegram ID")
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT IGNORE INTO admin_users (tg_user_id, added_by) VALUES (%s, %s)",
                (payload.telegram_id, int(admin["user_id"])),
            )
        return {"status": "success"}

    @router.delete("/admins/{telegram_id}")
    async def delete_admin(telegram_id: int, admin=Depends(admin_dependency)):
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM admin_users WHERE tg_user_id = %s", (telegram_id,))
        return {"status": "success"}

    @router.get("/postbacks")
    async def postbacks(
        event_code: str = "",
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=40, ge=1, le=100),
        admin=Depends(admin_dependency),
    ):
        pool = await _get_pool()
        where, params = "", []
        if event_code.strip():
            where, params = "WHERE event_code = %s", [event_code.strip()[:32]]
        offset = (page - 1) * limit
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(f"SELECT COUNT(*) AS n FROM postback_events {where}", params)
            total = int((await cur.fetchone() or {}).get("n") or 0)
            await cur.execute(
                f"""
                SELECT id, event_code, tg_user_id, trader_id, country, sumdep,
                       wdr_sum, commission, status, created_at
                FROM postback_events {where}
                ORDER BY id DESC LIMIT %s OFFSET %s
                """,
                tuple(params + [limit, offset]),
            )
            rows = await cur.fetchall()
        return {"status": "success", "events": rows, "total": total, "page": page}

    @router.get("/statistics")
    async def statistics(days: int = Query(default=7, ge=1, le=90), admin=Depends(admin_dependency)):
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT stat_date, registrations_count, first_deposit_total, deposit_total,
                       withdrawal_total, commission_total
                FROM postback_daily_stats
                WHERE stat_date >= CURDATE() - INTERVAL %s DAY
                ORDER BY stat_date
                """,
                (days - 1,),
            )
            daily = await cur.fetchall()
            await cur.execute(
                """
                SELECT smc.stat_date, smc.amount
                FROM stats_manual_commissions smc
                INNER JOIN (
                    SELECT stat_date, MAX(id) AS max_id FROM stats_manual_commissions
                    WHERE stat_date >= CURDATE() - INTERVAL %s DAY GROUP BY stat_date
                ) latest ON latest.max_id = smc.id
                ORDER BY smc.stat_date
                """,
                (days - 1,),
            )
            manual = await cur.fetchall()
        return {"status": "success", "daily": daily, "manual_commissions": manual}

    @router.put("/statistics/manual-commission")
    async def set_manual_commission(payload: AichatterManualCommissionUpdate, admin=Depends(admin_dependency)):
        if payload.amount < 0:
            raise HTTPException(status_code=400, detail="Amount must be non-negative")
        pool = await _get_pool()
        async with pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute("DELETE FROM stats_manual_commissions WHERE stat_date = %s", (payload.stat_date,))
            await cur.execute(
                "INSERT INTO stats_manual_commissions (stat_date, amount, added_by) VALUES (%s, %s, %s)",
                (payload.stat_date, payload.amount, int(admin["user_id"])),
            )
        return {"status": "success"}

    return router
