# db.py
import logging
from datetime import time, timedelta
from typing import Optional, Tuple

import aiomysql

from config import DB_CONFIG


FUNNEL_MEDIA_DEFAULTS = (
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


def to_time(val) -> time:
    if isinstance(val, time):
        return val
    if isinstance(val, timedelta):
        total = int(val.total_seconds()) % (24 * 3600)
        h = total // 3600
        m = (total % 3600) // 60
        return time(h, m)
    raise TypeError(f"Unsupported type for time conversion: {type(val)}")


async def table_exists(cur, table_name: str) -> bool:
    await cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
          AND table_name = %s
        LIMIT 1
        """,
        (table_name,),
    )
    return bool(await cur.fetchone())


async def column_exists(cur, table_name: str, column_name: str) -> bool:
    await cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return bool(await cur.fetchone())


async def ensure_column(cur, table_name: str, column_name: str, definition_sql: str):
    if not await column_exists(cur, table_name, column_name):
        await cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {definition_sql}")


async def ensure_kv_setting(cur, key: str, value: str):
    await cur.execute(
        """
        INSERT INTO kv_settings (skey, svalue)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE svalue = svalue
        """,
        (key, value),
    )


async def init_db() -> Tuple[
    aiomysql.Pool,
    Optional[time],
    Optional[time],
    bool,
    str,
    bool,
    str,
    str,
]:
    
    db_pool = await aiomysql.create_pool(**DB_CONFIG)

    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INT PRIMARY KEY,
                work_start TIME DEFAULT NULL,
                work_end TIME DEFAULT NULL,
                is_enabled TINYINT(1) NOT NULL DEFAULT 1
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                tg_user_id BIGINT UNSIGNED NOT NULL UNIQUE,
                first_name VARCHAR(255),
                username VARCHAR(255),

                country VARCHAR(8) DEFAULT NULL,
                trader_id VARCHAR(64) DEFAULT NULL,
                registration_status TINYINT(1) NOT NULL DEFAULT 0,
                deposit_status TINYINT(1) NOT NULL DEFAULT 0,
                registered_at DATETIME DEFAULT NULL,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,

                bot_active TINYINT(1) NOT NULL DEFAULT 1,
                bot_blocked_at TIMESTAMP NULL DEFAULT NULL,
                bot_block_reason VARCHAR(255) DEFAULT NULL
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS keyword_triggers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                phrases TEXT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                tg_user_id BIGINT UNSIGNED PRIMARY KEY,
                added_by BIGINT UNSIGNED DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_block_log (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                tg_user_id BIGINT UNSIGNED NOT NULL,
                reason VARCHAR(255) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_bot_block_log_user (tg_user_id),
                INDEX idx_bot_block_log_created (created_at)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await ensure_column(cur, "settings", "is_enabled", "is_enabled TINYINT(1) NOT NULL DEFAULT 1")
        await ensure_column(cur, "users", "bot_active", "bot_active TINYINT(1) NOT NULL DEFAULT 1")
        await ensure_column(cur, "users", "bot_blocked_at", "bot_blocked_at TIMESTAMP NULL DEFAULT NULL")
        await ensure_column(cur, "users", "bot_block_reason", "bot_block_reason VARCHAR(255) DEFAULT NULL")
        await ensure_column(cur, "admin_users", "added_by", "added_by BIGINT UNSIGNED DEFAULT NULL")

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_memory (
                tg_user_id BIGINT UNSIGNED PRIMARY KEY,
                memory LONGTEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_conv_mem_user
                    FOREIGN KEY (tg_user_id) REFERENCES users(tg_user_id)
                    ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                tg_user_id BIGINT UNSIGNED NOT NULL,
                direction ENUM('in','out') NOT NULL,
                is_business TINYINT(1) NOT NULL DEFAULT 0,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_user_created (tg_user_id, created_at),
                CONSTRAINT fk_messages_users
                    FOREIGN KEY (tg_user_id) REFERENCES users(tg_user_id)
                    ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_state (
                tg_user_id BIGINT UNSIGNED PRIMARY KEY,
                stage VARCHAR(32) NOT NULL,
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                CONSTRAINT fk_user_state_user
                    FOREIGN KEY (tg_user_id) REFERENCES users(tg_user_id)
                    ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            INSERT INTO settings (id, work_start, work_end, is_enabled)
            VALUES (1, '22:00:00', '10:00:00', 1)
            ON DUPLICATE KEY UPDATE
                work_start = work_start,
                work_end   = work_end,
                is_enabled = is_enabled;
            """
        )

        await cur.execute(
            """
            INSERT INTO settings (id, work_start, work_end)
            VALUES (1, '22:00:00', '10:00:00')
            ON DUPLICATE KEY UPDATE
                work_start = work_start,
                work_end   = work_end;
            """
        )

        await cur.execute(
            "SELECT work_start, work_end, is_enabled FROM settings WHERE id = 1"
        )
        row = await cur.fetchone()
        work_start = to_time(row[0]) if row and row[0] is not None else None
        work_end = to_time(row[1]) if row and row[1] is not None else None
        work_enabled_manual = bool(row[2]) if row else True

        # kv_settings
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_settings (
                skey   VARCHAR(64) PRIMARY KEY,
                svalue TEXT
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        # ai_settings
        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_settings (
                id INT PRIMARY KEY,
                system_prompt LONGTEXT NOT NULL,
                enabled TINYINT(1) NOT NULL DEFAULT 1,
                model VARCHAR(64) NOT NULL DEFAULT 'gpt-4.1-mini'
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

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
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
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
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )
        for index, (media_key, block_code, title) in enumerate(FUNNEL_MEDIA_DEFAULTS, start=1):
            await cur.execute(
                """
                INSERT INTO funnel_media
                    (media_key, block_code, title, description, sort_order, file_name, enabled)
                VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE media_key = media_key
                """,
                (media_key, block_code, title, title, index * 10, f"{media_key.upper()}.MP4"),
            )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS postback_events (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                event_code VARCHAR(32) NOT NULL,
                tg_user_id BIGINT UNSIGNED DEFAULT NULL,
                click_id VARCHAR(128) DEFAULT NULL,
                trader_id VARCHAR(128) DEFAULT NULL,
                site_id VARCHAR(191) DEFAULT NULL,
                cid VARCHAR(255) DEFAULT NULL,
                ac VARCHAR(255) DEFAULT NULL,
                country VARCHAR(32) DEFAULT NULL,
                promo VARCHAR(128) DEFAULT NULL,
                device_type VARCHAR(64) DEFAULT NULL,
                sumdep DECIMAL(18,2) DEFAULT NULL,
                wdr_sum DECIMAL(18,2) DEFAULT NULL,
                commission DECIMAL(18,2) DEFAULT NULL,
                status VARCHAR(128) DEFAULT NULL,
                raw_payload LONGTEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_postback_events_trader (trader_id),
                INDEX idx_postback_events_click (click_id),
                INDEX idx_postback_events_code (event_code),
                INDEX idx_postback_events_created (created_at)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS postback_state (
                trader_id VARCHAR(128) PRIMARY KEY,
                tg_user_id BIGINT UNSIGNED DEFAULT NULL,
                click_id VARCHAR(128) DEFAULT NULL,
                site_id VARCHAR(191) DEFAULT NULL,
                cid VARCHAR(255) DEFAULT NULL,
                ac VARCHAR(255) DEFAULT NULL,
                country VARCHAR(32) DEFAULT NULL,
                promo VARCHAR(128) DEFAULT NULL,
                device_type VARCHAR(64) DEFAULT NULL,
                registration_received_at DATETIME DEFAULT NULL,
                first_deposit_sum DECIMAL(18,2) DEFAULT NULL,
                first_deposit_at DATETIME DEFAULT NULL,
                repeat_deposit_last_sum DECIMAL(18,2) DEFAULT NULL,
                repeat_deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                repeat_deposit_count INT NOT NULL DEFAULT 0,
                repeat_deposit_at DATETIME DEFAULT NULL,
                deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                withdrawal_last_sum DECIMAL(18,2) DEFAULT NULL,
                withdrawal_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                withdrawal_count INT NOT NULL DEFAULT 0,
                withdrawal_status VARCHAR(128) DEFAULT NULL,
                withdrawal_at DATETIME DEFAULT NULL,
                commission_last_amount DECIMAL(18,2) DEFAULT NULL,
                commission_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                commission_count INT NOT NULL DEFAULT 0,
                commission_at DATETIME DEFAULT NULL,
                last_event_code VARCHAR(32) DEFAULT NULL,
                last_event_at DATETIME DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_postback_state_tg (tg_user_id),
                INDEX idx_postback_state_click (click_id)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS postback_daily_stats (
                stat_date DATE PRIMARY KEY,
                registrations_count INT NOT NULL DEFAULT 0,
                first_deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                withdrawal_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                commission_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )

        await cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stats_manual_commissions (
                id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                stat_date DATE NOT NULL,
                amount DECIMAL(18,2) NOT NULL DEFAULT 0,
                added_by BIGINT UNSIGNED DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_stats_manual_commissions_date (stat_date),
                INDEX idx_stats_manual_commissions_added_by (added_by)
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
            """
        )
        await ensure_column(cur, "messages", "is_business", "is_business TINYINT(1) NOT NULL DEFAULT 0")
        await ensure_column(cur, "ai_settings", "planner_system_prompt", "planner_system_prompt LONGTEXT NULL")
        await ensure_column(cur, "ai_settings", "model", "model VARCHAR(64) NOT NULL DEFAULT 'gpt-4.1-mini'")
        await ensure_column(cur, "ai_settings", "openai_api_key", "openai_api_key TEXT NULL")
        await ensure_column(cur, "postback_events", "event_code", "event_code VARCHAR(32) NOT NULL DEFAULT 'unknown'")
        await ensure_column(cur, "postback_events", "tg_user_id", "tg_user_id BIGINT UNSIGNED DEFAULT NULL")
        await ensure_column(cur, "postback_events", "click_id", "click_id VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "trader_id", "trader_id VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "site_id", "site_id VARCHAR(191) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "cid", "cid VARCHAR(255) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "ac", "ac VARCHAR(255) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "country", "country VARCHAR(32) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "promo", "promo VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "device_type", "device_type VARCHAR(64) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "sumdep", "sumdep DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "wdr_sum", "wdr_sum DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "commission", "commission DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "status", "status VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_events", "raw_payload", "raw_payload LONGTEXT")
        await ensure_column(cur, "postback_state", "tg_user_id", "tg_user_id BIGINT UNSIGNED DEFAULT NULL")
        await ensure_column(cur, "postback_state", "click_id", "click_id VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "site_id", "site_id VARCHAR(191) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "cid", "cid VARCHAR(255) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "ac", "ac VARCHAR(255) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "country", "country VARCHAR(32) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "promo", "promo VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "device_type", "device_type VARCHAR(64) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "registration_received_at", "registration_received_at DATETIME DEFAULT NULL")
        await ensure_column(cur, "postback_state", "first_deposit_sum", "first_deposit_sum DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "first_deposit_at", "first_deposit_at DATETIME DEFAULT NULL")
        await ensure_column(cur, "postback_state", "repeat_deposit_last_sum", "repeat_deposit_last_sum DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "repeat_deposit_total", "repeat_deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "repeat_deposit_count", "repeat_deposit_count INT NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "repeat_deposit_at", "repeat_deposit_at DATETIME DEFAULT NULL")
        await ensure_column(cur, "postback_state", "deposit_total", "deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "withdrawal_last_sum", "withdrawal_last_sum DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "withdrawal_total", "withdrawal_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "withdrawal_count", "withdrawal_count INT NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "withdrawal_status", "withdrawal_status VARCHAR(128) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "withdrawal_at", "withdrawal_at DATETIME DEFAULT NULL")
        await ensure_column(cur, "postback_state", "commission_last_amount", "commission_last_amount DECIMAL(18,2) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "commission_total", "commission_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "commission_count", "commission_count INT NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_state", "commission_at", "commission_at DATETIME DEFAULT NULL")
        await ensure_column(cur, "postback_state", "last_event_code", "last_event_code VARCHAR(32) DEFAULT NULL")
        await ensure_column(cur, "postback_state", "last_event_at", "last_event_at DATETIME DEFAULT NULL")
        await ensure_column(cur, "postback_daily_stats", "registrations_count", "registrations_count INT NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_daily_stats", "first_deposit_total", "first_deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_daily_stats", "deposit_total", "deposit_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_daily_stats", "withdrawal_total", "withdrawal_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "postback_daily_stats", "commission_total", "commission_total DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "stats_manual_commissions", "amount", "amount DECIMAL(18,2) NOT NULL DEFAULT 0")
        await ensure_column(cur, "stats_manual_commissions", "added_by", "added_by BIGINT UNSIGNED DEFAULT NULL")
        await ensure_column(cur, "stats_manual_commissions", "created_at", "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        default_ai_prompt = """
Ты — Elizabeth Vane, менеджер трейдерской команды. Общайся с людьми в Telegram от первого лица.
Правила:
- Пиши по-дружески, но уверенно.
- Кратко и по делу, без воды.
- Отвечай на языке собеседника; если язык неясен — на русском.
- Не выдавай образовательную аналитику за гарантированную прибыль и не обещай доход.
- Всегда веди человека к вступлению в команду, регистрации на Pocket Option и выполнению шагов.
- Строго следуй скрипту, который будет в этом промпте (админ может его дополнять).
Если чего-то нет в скрипте — отвечай логично, но не меняй условия входа (регистрация, депозит и т.д.).
"""
        default_planner_prompt = """
Ты анализируешь переписку менеджера с клиентом и возвращаешь только JSON.
Определи intent, actions, tone и main_prompt.
Учитывай текущий этап воронки, registration_status, deposit_status, наличие Trader ID и историю диалога.
Не подтверждай регистрацию или депозит без достаточных оснований.
"""

        await cur.execute(
            """
            INSERT INTO ai_settings (id, system_prompt, planner_system_prompt, enabled, model)
            VALUES (1, %s, %s, 1, 'gpt-4.1-mini')
            ON DUPLICATE KEY UPDATE
                system_prompt = system_prompt,
                planner_system_prompt = COALESCE(planner_system_prompt, VALUES(planner_system_prompt))
            """,
            (default_ai_prompt, default_planner_prompt),
        )

        await cur.execute(
            "SELECT system_prompt, enabled, model FROM ai_settings WHERE id = 1"
        )
        row = await cur.fetchone()
        ai_system_prompt = row[0]
        ai_enabled = bool(row[1])
        ai_model = row[2]

        # Имя бота
        await cur.execute(
            """
            INSERT INTO kv_settings (skey, svalue)
            VALUES ('BOT_NAME', 'Elizabeth Vane')
            ON DUPLICATE KEY UPDATE svalue = svalue
            """
        )

        await ensure_kv_setting(cur, "CHECK_COMPANY", "1")
        await ensure_kv_setting(cur, "COMPANY_CODE", "")
        await ensure_kv_setting(cur, "MIN_DEPOSIT_THRESHOLD", "10")
        await ensure_kv_setting(cur, "LOG_DEPOSITS", "1")
        await ensure_kv_setting(cur, "LOG_REGISTRATIONS", "1")
        await ensure_kv_setting(cur, "LOG_WITHDRAWALS", "1")
        await ensure_kv_setting(cur, "LOG_COMMISSIONS", "1")
        await ensure_kv_setting(cur, "LOG_SYSTEM_ERRORS", "0")
        await ensure_kv_setting(cur, "POSTBACK_LOG_CHAT_ID", "")
        await ensure_kv_setting(cur, "STATS_COMMISSION_MODE", "auto")
        await ensure_kv_setting(cur, "FUNNEL_MEDIA_ENABLED", "1")

        await cur.execute(
            "SELECT svalue FROM kv_settings WHERE skey = 'BOT_NAME'"
        )
        row = await cur.fetchone()
        bot_name = (row[0] or "Elizabeth Vane") if row else "Elizabeth Vane"
        logging.info("[init_db] bot_name из kv_settings: %s", bot_name)

    return (
        db_pool,
        work_start,
        work_end,
        work_enabled_manual,
        ai_system_prompt,
        ai_enabled,
        ai_model,
        bot_name,
    )
    
async def get_keyword_triggers(db_pool) -> list[str]:
    async with db_pool.acquire() as conn, conn.cursor() as cur:
        await cur.execute("SELECT phrases FROM keyword_triggers LIMIT 1")
        row = await cur.fetchone()

    if not row or not row[0]:
        return []

    return [p.strip() for p in row[0].split(",") if p.strip()]
