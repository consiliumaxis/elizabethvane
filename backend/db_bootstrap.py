import os
import aiomysql

try:
    from backend.analysis_ai_service import DEFAULT_ANALYSIS_GPT_MODEL, DEFAULT_ANALYSIS_GPT_PROMPT
except ModuleNotFoundError:
    from analysis_ai_service import DEFAULT_ANALYSIS_GPT_MODEL, DEFAULT_ANALYSIS_GPT_PROMPT


async def _get_current_db_name(conn) -> str:
    async with conn.cursor() as cur:
        await cur.execute("SELECT DATABASE()")
        row = await cur.fetchone()
    if not row or not row[0]:
        raise RuntimeError("Database name is not selected")
    return str(row[0])


async def _column_exists(conn, db_name: str, table_name: str, column_name: str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT 1
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
            LIMIT 1
            """,
            (db_name, table_name, column_name),
        )
        row = await cur.fetchone()
    return bool(row)


async def _index_exists(conn, db_name: str, table_name: str, index_name: str) -> bool:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT 1
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
            LIMIT 1
            """,
            (db_name, table_name, index_name),
        )
        row = await cur.fetchone()
    return bool(row)


async def _ensure_column(conn, db_name: str, table_name: str, column_name: str, alter_sql: str) -> None:
    if not await _column_exists(conn, db_name, table_name, column_name):
        async with conn.cursor() as cur:
            await cur.execute(alter_sql)


async def _ensure_index(conn, db_name: str, table_name: str, index_name: str, create_sql: str) -> None:
    if not await _index_exists(conn, db_name, table_name, index_name):
        async with conn.cursor() as cur:
            await cur.execute(create_sql)


async def ensure_database_schema(db_pool: aiomysql.Pool) -> None:
    async with db_pool.acquire() as conn:
        db_name = await _get_current_db_name(conn)

        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT NOT NULL PRIMARY KEY,
                    username VARCHAR(255) NULL,
                    first_name VARCHAR(255) NULL,
                    avatar_url TEXT NULL,
                    aio_visit_uuid VARCHAR(64) NULL,
                    trader_id VARCHAR(64) NULL,
                    pocket_click_id VARCHAR(64) NULL,
                    pocket_site_id VARCHAR(128) NULL,
                    pocket_cid VARCHAR(128) NULL,
                    pocket_sub_id1 VARCHAR(255) NULL,
                    pocket_sub_id2 VARCHAR(255) NULL,
                    pocket_registered TINYINT(1) NOT NULL DEFAULT 0,
                    pocket_deposited TINYINT(1) NOT NULL DEFAULT 0,
                    pocket_registered_at VARCHAR(64) NULL,
                    pocket_deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00,
                    pocket_checked_at TIMESTAMP NULL DEFAULT NULL,
                    balance DECIMAL(18,2) NOT NULL DEFAULT 0.00,
                    balance_sync_enabled TINYINT(1) NOT NULL DEFAULT 0,
                    balance_synced_at TIMESTAMP NULL DEFAULT NULL,
                    balance_sync_error TEXT NULL,
                    lang VARCHAR(16) NOT NULL DEFAULT 'ru',
                    mode VARCHAR(16) NOT NULL DEFAULT 'forex',
                    strategy_id BIGINT NULL,
                    is_blocked TINYINT(1) NOT NULL DEFAULT 0,
                    blocked_by BIGINT NULL,
                    blocked_at TIMESTAMP NULL DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS presets (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    is_system TINYINT(1) NOT NULL DEFAULT 0,
                    icon VARCHAR(64) NULL DEFAULT '⚡',
                    allowed_timeframes VARCHAR(255) NULL DEFAULT '5m,15m,30m,1h,4h,1d',
                    public_winrate DECIMAL(6,2) NULL DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS indicators (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    `key` VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_indicators_key (`key`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS preset_indicators (
                    preset_id BIGINT NOT NULL,
                    indicator_id BIGINT NOT NULL,
                    PRIMARY KEY (preset_id, indicator_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_presets (
                    user_id BIGINT NOT NULL,
                    preset_id BIGINT NOT NULL,
                    PRIMARY KEY (user_id, preset_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_analyses (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    pair VARCHAR(64) NOT NULL,
                    timeframe VARCHAR(16) NOT NULL,
                    strategy_id BIGINT NULL,
                    analysis_type VARCHAR(16) NOT NULL DEFAULT 'forex',
                    market_kind VARCHAR(32) NULL,
                    entry_price DOUBLE NULL,
                    exit_price DOUBLE NULL,
                    raw_data LONGTEXT NULL,
                    news_data LONGTEXT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    closed_at TIMESTAMP NULL DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_chats (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_messages (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    role VARCHAR(32) NOT NULL,
                    content LONGTEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_settings (
                    id INT NOT NULL PRIMARY KEY,
                    system_prompt LONGTEXT NOT NULL,
                    model VARCHAR(64) NOT NULL DEFAULT 'gpt-4o-mini',
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    user_id BIGINT NOT NULL PRIMARY KEY,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    granted_by BIGINT NULL,
                    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_stream_settings (
                    id INT NOT NULL PRIMARY KEY,
                    is_enabled TINYINT(1) NOT NULL DEFAULT 0,
                    scope VARCHAR(16) NOT NULL DEFAULT 'all',
                    strategy_id BIGINT NULL,
                    forced_signal VARCHAR(8) NOT NULL DEFAULT 'BUY',
                    levels_mode VARCHAR(16) NOT NULL DEFAULT 'auto',
                    manual_conservative_sl DOUBLE NULL,
                    manual_take_profit DOUBLE NULL,
                    indicator_mode VARCHAR(16) NOT NULL DEFAULT 'auto',
                    indicator_overrides LONGTEXT NULL,
                    message TEXT NULL,
                    emulation_analysis_type VARCHAR(16) NOT NULL DEFAULT 'forex',
                    emulation_market VARCHAR(32) NULL,
                    emulation_symbol VARCHAR(128) NULL,
                    emulation_price DOUBLE NULL,
                    emulation_strategy_id BIGINT NULL,
                    updated_by BIGINT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_analysis_settings (
                    strategy_id BIGINT NOT NULL PRIMARY KEY,
                    engine VARCHAR(16) NOT NULL DEFAULT 'backend',
                    gpt_api_key TEXT NULL,
                    gpt_model VARCHAR(64) NOT NULL DEFAULT 'gpt-4o-mini',
                    gpt_prompt LONGTEXT NOT NULL,
                    updated_by BIGINT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_analysis_settings (
                    id INT NOT NULL PRIMARY KEY,
                    engine VARCHAR(16) NOT NULL DEFAULT 'backend',
                    gpt_api_key TEXT NULL,
                    gpt_model VARCHAR(64) NOT NULL DEFAULT 'gpt-4o-mini',
                    gpt_prompt LONGTEXT NOT NULL,
                    updated_by BIGINT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_support_links (
                    id INT NOT NULL PRIMARY KEY,
                    channel_url TEXT NULL,
                    support_url TEXT NULL,
                    updated_by BIGINT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_pocket_api_settings (
                    id INT NOT NULL PRIMARY KEY,
                    partner_id VARCHAR(64) NULL,
                    api_token TEXT NULL,
                    updated_by BIGINT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS aio_postback_events (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    aio_visit_uuid VARCHAR(64) CHARACTER SET ascii NOT NULL,
                    event_slug VARCHAR(64) CHARACTER SET ascii NOT NULL,
                    unique_key VARCHAR(128) CHARACTER SET utf8mb4 NOT NULL,
                    revenue DECIMAL(18,2) NOT NULL DEFAULT 0.00,
                    currency VARCHAR(8) NULL,
                    request_url TEXT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    response_status INT NULL,
                    response_body LONGTEXT NULL,
                    error TEXT NULL,
                    sent_at TIMESTAMP NULL DEFAULT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_aio_postback_once (aio_visit_uuid, event_slug, unique_key),
                    KEY idx_aio_postback_events_user (user_id, created_at),
                    KEY idx_aio_postback_events_status (status, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pocket_postback_events (
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    event_slug VARCHAR(64) NOT NULL,
                    unique_key VARCHAR(191) NOT NULL,
                    user_id BIGINT NULL,
                    click_id VARCHAR(128) NULL,
                    trader_id VARCHAR(64) NULL,
                    deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00,
                    site_id VARCHAR(128) NULL,
                    cid VARCHAR(128) NULL,
                    sub_id1 VARCHAR(255) NULL,
                    sub_id2 VARCHAR(255) NULL,
                    raw_payload LONGTEXT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'received',
                    reason VARCHAR(255) NULL,
                    chatterfy_request_url TEXT NULL,
                    chatterfy_status VARCHAR(32) NULL,
                    chatterfy_response_status INT NULL,
                    chatterfy_response_body LONGTEXT NULL,
                    chatterfy_error TEXT NULL,
                    chatterfy_sent_at TIMESTAMP NULL DEFAULT NULL,
                    source_ip VARCHAR(64) NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_pocket_postback_unique_key (unique_key),
                    KEY idx_pocket_postback_user_event (user_id, event_slug),
                    KEY idx_pocket_postback_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_modes (
                    mode VARCHAR(16) NOT NULL PRIMARY KEY,
                    title VARCHAR(64) NOT NULL,
                    is_enabled TINYINT(1) NOT NULL DEFAULT 1,
                    sort_order INT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_mode_access (
                    user_id BIGINT NOT NULL,
                    mode VARCHAR(16) NOT NULL,
                    is_enabled TINYINT(1) NOT NULL DEFAULT 1,
                    updated_by BIGINT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, mode)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

        await _ensure_column(conn, db_name, "users", "trader_id", "ALTER TABLE users ADD COLUMN trader_id VARCHAR(64) NULL")
        await _ensure_column(conn, db_name, "users", "aio_visit_uuid", "ALTER TABLE users ADD COLUMN aio_visit_uuid VARCHAR(64) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_click_id", "ALTER TABLE users ADD COLUMN pocket_click_id VARCHAR(64) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_site_id", "ALTER TABLE users ADD COLUMN pocket_site_id VARCHAR(128) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_cid", "ALTER TABLE users ADD COLUMN pocket_cid VARCHAR(128) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_sub_id1", "ALTER TABLE users ADD COLUMN pocket_sub_id1 VARCHAR(255) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_sub_id2", "ALTER TABLE users ADD COLUMN pocket_sub_id2 VARCHAR(255) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_registered", "ALTER TABLE users ADD COLUMN pocket_registered TINYINT(1) NOT NULL DEFAULT 0")
        await _ensure_column(conn, db_name, "users", "pocket_deposited", "ALTER TABLE users ADD COLUMN pocket_deposited TINYINT(1) NOT NULL DEFAULT 0")
        await _ensure_column(conn, db_name, "users", "pocket_registered_at", "ALTER TABLE users ADD COLUMN pocket_registered_at VARCHAR(64) NULL")
        await _ensure_column(conn, db_name, "users", "pocket_deposit_amount", "ALTER TABLE users ADD COLUMN pocket_deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00")
        await _ensure_column(conn, db_name, "users", "pocket_checked_at", "ALTER TABLE users ADD COLUMN pocket_checked_at TIMESTAMP NULL DEFAULT NULL")
        await _ensure_column(conn, db_name, "users", "balance", "ALTER TABLE users ADD COLUMN balance DECIMAL(18,2) NOT NULL DEFAULT 0.00")
        await _ensure_column(conn, db_name, "users", "balance_sync_enabled", "ALTER TABLE users ADD COLUMN balance_sync_enabled TINYINT(1) NOT NULL DEFAULT 0")
        await _ensure_column(conn, db_name, "users", "balance_synced_at", "ALTER TABLE users ADD COLUMN balance_synced_at TIMESTAMP NULL DEFAULT NULL")
        await _ensure_column(conn, db_name, "users", "balance_sync_error", "ALTER TABLE users ADD COLUMN balance_sync_error TEXT NULL")
        await _ensure_column(conn, db_name, "users", "strategy_id", "ALTER TABLE users ADD COLUMN strategy_id BIGINT NULL")
        await _ensure_column(conn, db_name, "users", "lang", "ALTER TABLE users ADD COLUMN lang VARCHAR(16) NOT NULL DEFAULT 'ru'")
        await _ensure_column(conn, db_name, "users", "mode", "ALTER TABLE users ADD COLUMN mode VARCHAR(16) NOT NULL DEFAULT 'forex'")
        await _ensure_column(conn, db_name, "users", "is_blocked", "ALTER TABLE users ADD COLUMN is_blocked TINYINT(1) NOT NULL DEFAULT 0")
        await _ensure_column(conn, db_name, "users", "blocked_by", "ALTER TABLE users ADD COLUMN blocked_by BIGINT NULL")
        await _ensure_column(conn, db_name, "users", "blocked_at", "ALTER TABLE users ADD COLUMN blocked_at TIMESTAMP NULL DEFAULT NULL")
        await _ensure_column(
            conn,
            db_name,
            "users",
            "created_at",
            "ALTER TABLE users ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        )
        await _ensure_column(
            conn,
            db_name,
            "users",
            "updated_at",
            "ALTER TABLE users ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )

        await _ensure_column(conn, db_name, "presets", "icon", "ALTER TABLE presets ADD COLUMN icon VARCHAR(64) NULL DEFAULT '⚡'")
        await _ensure_column(
            conn,
            db_name,
            "presets",
            "allowed_timeframes",
            "ALTER TABLE presets ADD COLUMN allowed_timeframes VARCHAR(255) NULL DEFAULT '5m,15m,30m,1h,4h,1d'",
        )
        await _ensure_column(
            conn,
            db_name,
            "presets",
            "public_winrate",
            "ALTER TABLE presets ADD COLUMN public_winrate DECIMAL(6,2) NULL DEFAULT NULL",
        )

        await _ensure_column(conn, db_name, "user_analyses", "news_data", "ALTER TABLE user_analyses ADD COLUMN news_data LONGTEXT NULL")
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "analysis_type",
            "ALTER TABLE user_analyses ADD COLUMN analysis_type VARCHAR(16) NOT NULL DEFAULT 'forex'",
        )
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "market_kind",
            "ALTER TABLE user_analyses ADD COLUMN market_kind VARCHAR(32) NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "entry_price",
            "ALTER TABLE user_analyses ADD COLUMN entry_price DOUBLE NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "exit_price",
            "ALTER TABLE user_analyses ADD COLUMN exit_price DOUBLE NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "status",
            "ALTER TABLE user_analyses ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active'",
        )
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "updated_at",
            "ALTER TABLE user_analyses ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )
        await _ensure_column(
            conn,
            db_name,
            "user_analyses",
            "closed_at",
            "ALTER TABLE user_analyses ADD COLUMN closed_at TIMESTAMP NULL DEFAULT NULL",
        )

        await _ensure_column(conn, db_name, "ai_chats", "title", "ALTER TABLE ai_chats ADD COLUMN title VARCHAR(255) NOT NULL DEFAULT 'New Chat'")
        await _ensure_column(conn, db_name, "ai_chats", "status", "ALTER TABLE ai_chats ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'active'")
        await _ensure_column(
            conn,
            db_name,
            "ai_chats",
            "updated_at",
            "ALTER TABLE ai_chats ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )

        await _ensure_column(
            conn,
            db_name,
            "admin_users",
            "is_active",
            "ALTER TABLE admin_users ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1",
        )
        await _ensure_column(conn, db_name, "admin_users", "granted_by", "ALTER TABLE admin_users ADD COLUMN granted_by BIGINT NULL")
        await _ensure_column(
            conn,
            db_name,
            "admin_users",
            "granted_at",
            "ALTER TABLE admin_users ADD COLUMN granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "is_enabled",
            "ALTER TABLE admin_stream_settings ADD COLUMN is_enabled TINYINT(1) NOT NULL DEFAULT 0",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "scope",
            "ALTER TABLE admin_stream_settings ADD COLUMN scope VARCHAR(16) NOT NULL DEFAULT 'all'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "strategy_id",
            "ALTER TABLE admin_stream_settings ADD COLUMN strategy_id BIGINT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "forced_signal",
            "ALTER TABLE admin_stream_settings ADD COLUMN forced_signal VARCHAR(8) NOT NULL DEFAULT 'BUY'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "levels_mode",
            "ALTER TABLE admin_stream_settings ADD COLUMN levels_mode VARCHAR(16) NOT NULL DEFAULT 'auto'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "manual_conservative_sl",
            "ALTER TABLE admin_stream_settings ADD COLUMN manual_conservative_sl DOUBLE NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "manual_take_profit",
            "ALTER TABLE admin_stream_settings ADD COLUMN manual_take_profit DOUBLE NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "indicator_mode",
            "ALTER TABLE admin_stream_settings ADD COLUMN indicator_mode VARCHAR(16) NOT NULL DEFAULT 'auto'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "indicator_overrides",
            "ALTER TABLE admin_stream_settings ADD COLUMN indicator_overrides LONGTEXT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "message",
            "ALTER TABLE admin_stream_settings ADD COLUMN message TEXT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "emulation_analysis_type",
            "ALTER TABLE admin_stream_settings ADD COLUMN emulation_analysis_type VARCHAR(16) NOT NULL DEFAULT 'forex'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "emulation_market",
            "ALTER TABLE admin_stream_settings ADD COLUMN emulation_market VARCHAR(32) NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "emulation_symbol",
            "ALTER TABLE admin_stream_settings ADD COLUMN emulation_symbol VARCHAR(128) NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "emulation_price",
            "ALTER TABLE admin_stream_settings ADD COLUMN emulation_price DOUBLE NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "emulation_strategy_id",
            "ALTER TABLE admin_stream_settings ADD COLUMN emulation_strategy_id BIGINT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "updated_by",
            "ALTER TABLE admin_stream_settings ADD COLUMN updated_by BIGINT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_stream_settings",
            "updated_at",
            "ALTER TABLE admin_stream_settings ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )

        await _ensure_index(conn, db_name, "users", "idx_users_strategy_id", "CREATE INDEX idx_users_strategy_id ON users(strategy_id)")
        await _ensure_index(conn, db_name, "users", "idx_users_balance_sync", "CREATE INDEX idx_users_balance_sync ON users(balance_sync_enabled, balance_synced_at)")
        await _ensure_index(conn, db_name, "admin_users", "idx_admin_users_active", "CREATE INDEX idx_admin_users_active ON admin_users(is_active)")
        await _ensure_index(
            conn,
            db_name,
            "user_analyses",
            "idx_user_analyses_user_status_created",
            "CREATE INDEX idx_user_analyses_user_status_created ON user_analyses(user_id, status, created_at)",
        )
        await _ensure_index(
            conn,
            db_name,
            "user_analyses",
            "idx_user_analyses_type_status_created",
            "CREATE INDEX idx_user_analyses_type_status_created ON user_analyses(analysis_type, status, created_at)",
        )
        await _ensure_index(
            conn,
            db_name,
            "ai_chats",
            "idx_ai_chats_user_status_updated",
            "CREATE INDEX idx_ai_chats_user_status_updated ON ai_chats(user_id, status, updated_at)",
        )
        await _ensure_index(conn, db_name, "ai_messages", "idx_ai_messages_chat_id", "CREATE INDEX idx_ai_messages_chat_id ON ai_messages(chat_id)")
        await _ensure_index(
            conn,
            db_name,
            "ai_messages",
            "idx_ai_messages_chat_created",
            "CREATE INDEX idx_ai_messages_chat_created ON ai_messages(chat_id, created_at)",
        )
        await _ensure_index(conn, db_name, "user_presets", "idx_user_presets_preset_id", "CREATE INDEX idx_user_presets_preset_id ON user_presets(preset_id)")
        await _ensure_index(conn, db_name, "user_mode_access", "idx_user_mode_access_mode", "CREATE INDEX idx_user_mode_access_mode ON user_mode_access(mode)")
        await _ensure_index(conn, db_name, "users", "idx_users_aio_visit_uuid", "CREATE INDEX idx_users_aio_visit_uuid ON users(aio_visit_uuid)")
        await _ensure_index(conn, db_name, "users", "idx_users_pocket_click_id", "CREATE INDEX idx_users_pocket_click_id ON users(pocket_click_id)")
        await _ensure_index(conn, db_name, "users", "idx_users_signal_gate", "CREATE INDEX idx_users_signal_gate ON users(pocket_registered, pocket_deposited)")
        await _ensure_column(conn, db_name, "pocket_postback_events", "sub_id2", "ALTER TABLE pocket_postback_events ADD COLUMN sub_id2 VARCHAR(255) NULL AFTER sub_id1")
        await _ensure_column(conn, db_name, "pocket_postback_events", "deposit_amount", "ALTER TABLE pocket_postback_events ADD COLUMN deposit_amount DECIMAL(18,2) NOT NULL DEFAULT 0.00 AFTER trader_id")
        await _ensure_column(conn, db_name, "pocket_postback_events", "chatterfy_request_url", "ALTER TABLE pocket_postback_events ADD COLUMN chatterfy_request_url TEXT NULL")
        await _ensure_column(conn, db_name, "pocket_postback_events", "chatterfy_status", "ALTER TABLE pocket_postback_events ADD COLUMN chatterfy_status VARCHAR(32) NULL")
        await _ensure_column(conn, db_name, "pocket_postback_events", "chatterfy_response_status", "ALTER TABLE pocket_postback_events ADD COLUMN chatterfy_response_status INT NULL")
        await _ensure_column(conn, db_name, "pocket_postback_events", "chatterfy_response_body", "ALTER TABLE pocket_postback_events ADD COLUMN chatterfy_response_body LONGTEXT NULL")
        await _ensure_column(conn, db_name, "pocket_postback_events", "chatterfy_error", "ALTER TABLE pocket_postback_events ADD COLUMN chatterfy_error TEXT NULL")
        await _ensure_column(conn, db_name, "pocket_postback_events", "chatterfy_sent_at", "ALTER TABLE pocket_postback_events ADD COLUMN chatterfy_sent_at TIMESTAMP NULL DEFAULT NULL")
        await _ensure_index(conn, db_name, "aio_postback_events", "idx_aio_postback_events_user", "CREATE INDEX idx_aio_postback_events_user ON aio_postback_events(user_id, created_at)")
        await _ensure_index(conn, db_name, "aio_postback_events", "idx_aio_postback_events_status", "CREATE INDEX idx_aio_postback_events_status ON aio_postback_events(status, created_at)")
        await _ensure_index(conn, db_name, "pocket_postback_events", "idx_pocket_postback_events_user", "CREATE INDEX idx_pocket_postback_events_user ON pocket_postback_events(user_id, created_at)")
        await _ensure_index(conn, db_name, "pocket_postback_events", "idx_pocket_postback_events_status", "CREATE INDEX idx_pocket_postback_events_status ON pocket_postback_events(status, created_at)")
        await _ensure_index(
            conn,
            db_name,
            "preset_indicators",
            "idx_preset_indicators_indicator_id",
            "CREATE INDEX idx_preset_indicators_indicator_id ON preset_indicators(indicator_id)",
        )

        await _ensure_column(
            conn,
            db_name,
            "strategy_analysis_settings",
            "engine",
            "ALTER TABLE strategy_analysis_settings ADD COLUMN engine VARCHAR(16) NOT NULL DEFAULT 'backend'",
        )
        await _ensure_column(
            conn,
            db_name,
            "strategy_analysis_settings",
            "gpt_api_key",
            "ALTER TABLE strategy_analysis_settings ADD COLUMN gpt_api_key TEXT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "strategy_analysis_settings",
            "gpt_model",
            "ALTER TABLE strategy_analysis_settings ADD COLUMN gpt_model VARCHAR(64) NOT NULL DEFAULT 'gpt-4o-mini'",
        )
        await _ensure_column(
            conn,
            db_name,
            "strategy_analysis_settings",
            "gpt_prompt",
            "ALTER TABLE strategy_analysis_settings ADD COLUMN gpt_prompt LONGTEXT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "strategy_analysis_settings",
            "updated_by",
            "ALTER TABLE strategy_analysis_settings ADD COLUMN updated_by BIGINT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "strategy_analysis_settings",
            "updated_at",
            "ALTER TABLE strategy_analysis_settings ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_analysis_settings",
            "engine",
            "ALTER TABLE admin_analysis_settings ADD COLUMN engine VARCHAR(16) NOT NULL DEFAULT 'backend'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_analysis_settings",
            "gpt_api_key",
            "ALTER TABLE admin_analysis_settings ADD COLUMN gpt_api_key TEXT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_analysis_settings",
            "gpt_model",
            "ALTER TABLE admin_analysis_settings ADD COLUMN gpt_model VARCHAR(64) NOT NULL DEFAULT 'gpt-4o-mini'",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_analysis_settings",
            "gpt_prompt",
            "ALTER TABLE admin_analysis_settings ADD COLUMN gpt_prompt LONGTEXT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_analysis_settings",
            "updated_by",
            "ALTER TABLE admin_analysis_settings ADD COLUMN updated_by BIGINT NULL",
        )
        await _ensure_column(
            conn,
            db_name,
            "admin_analysis_settings",
            "updated_at",
            "ALTER TABLE admin_analysis_settings ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
        )

        indicators_seed = [
            ("RSI", "RSI"),
            ("MACD", "MACD"),
            ("EMA50", "EMA50"),
            ("EMA200", "EMA200"),
            ("ADX", "ADX"),
            ("DMI", "DMI"),
            ("ICHIMOKU", "ICHIMOKU"),
            ("EMA9_21", "EMA9_21"),
        ]

        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT INTO indicators (name, `key`)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE name = VALUES(name)
                """,
                indicators_seed,
            )

            await cur.execute(
                """
                INSERT INTO presets (id, name, is_system, icon, allowed_timeframes)
                VALUES (1, 'Balanced Core', 1, '⚡', '5m,15m,30m,1h,4h,1d')
                ON DUPLICATE KEY UPDATE id = id
                """
            )
            await cur.execute("UPDATE presets SET is_system = 1 WHERE id = 1")

            await cur.execute("SELECT id, `key` FROM indicators")
            rows = await cur.fetchall()
            key_to_id = {row[1]: int(row[0]) for row in rows}
            default_keys = ["RSI", "MACD", "EMA50", "ADX", "DMI", "ICHIMOKU"]
            preset_links = [(1, key_to_id[k]) for k in default_keys if k in key_to_id]
            if preset_links:
                await cur.executemany(
                    """
                    INSERT IGNORE INTO preset_indicators (preset_id, indicator_id)
                    VALUES (%s, %s)
                    """,
                    preset_links,
                )

            await cur.execute(
                """
                INSERT INTO ai_settings (id, system_prompt, model)
                VALUES (1, 'You are a helpful trading assistant.', 'gpt-4o-mini')
                ON DUPLICATE KEY UPDATE id = id
                """
            )

            await cur.execute(
                """
                INSERT INTO admin_stream_settings (
                    id,
                    is_enabled,
                    scope,
                    strategy_id,
                    forced_signal,
                    levels_mode,
                    manual_conservative_sl,
                    manual_take_profit,
                    indicator_mode,
                    indicator_overrides,
                    message,
                    emulation_analysis_type,
                    emulation_market,
                    emulation_symbol,
                    emulation_price,
                    emulation_strategy_id,
                    updated_by
                )
                VALUES (1, 0, 'all', NULL, 'BUY', 'auto', NULL, NULL, 'auto', '{}', '', 'forex', NULL, NULL, NULL, NULL, NULL)
                ON DUPLICATE KEY UPDATE id = id
                """
            )

            await cur.execute(
                """
                UPDATE strategy_analysis_settings
                SET gpt_prompt = %s
                WHERE gpt_prompt IS NULL OR TRIM(gpt_prompt) = ''
                """,
                (DEFAULT_ANALYSIS_GPT_PROMPT,),
            )
            await cur.execute(
                """
                UPDATE strategy_analysis_settings
                SET gpt_model = %s
                WHERE gpt_model IS NULL OR TRIM(gpt_model) = ''
                """,
                (DEFAULT_ANALYSIS_GPT_MODEL,),
            )
            await cur.execute(
                """
                INSERT INTO admin_analysis_settings (id, engine, gpt_api_key, gpt_model, gpt_prompt, updated_by)
                VALUES (1, 'backend', NULL, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE id = id
                """,
                (DEFAULT_ANALYSIS_GPT_MODEL, DEFAULT_ANALYSIS_GPT_PROMPT),
            )
            await cur.execute(
                """
                UPDATE admin_analysis_settings
                SET gpt_prompt = %s
                WHERE gpt_prompt IS NULL OR TRIM(gpt_prompt) = ''
                """,
                (DEFAULT_ANALYSIS_GPT_PROMPT,),
            )
            await cur.execute(
                """
                UPDATE admin_analysis_settings
                SET gpt_model = %s
                WHERE gpt_model IS NULL OR TRIM(gpt_model) = ''
                """,
                (DEFAULT_ANALYSIS_GPT_MODEL,),
            )

            await cur.execute(
                """
                INSERT INTO admin_support_links (id, channel_url, support_url, updated_by)
                VALUES (1, %s, %s, NULL)
                ON DUPLICATE KEY UPDATE
                    channel_url = COALESCE(NULLIF(channel_url, ''), VALUES(channel_url)),
                    support_url = COALESCE(NULLIF(support_url, ''), VALUES(support_url))
                """,
                (
                    (os.getenv("CHANNEL_URL") or "").strip(),
                    (os.getenv("SUPPORT_URL") or "").strip(),
                ),
            )

            await cur.execute(
                """
                INSERT INTO admin_pocket_api_settings (id, partner_id, api_token, updated_by)
                VALUES (1, NULL, NULL, NULL)
                ON DUPLICATE KEY UPDATE id = id
                """
            )

            await cur.executemany(
                """
                INSERT INTO app_modes (mode, title, is_enabled, sort_order)
                VALUES (%s, %s, 1, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    sort_order = VALUES(sort_order)
                """,
                [
                    ("forex", "Forex", 10),
                    ("binary", "Binary", 20),
                    ("demo", "Demo", 30),
                ],
            )

            await cur.execute(
                """
                INSERT IGNORE INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                SELECT user_id, 'forex', 1, NULL FROM users
                """
            )
            await cur.execute(
                """
                INSERT IGNORE INTO user_mode_access (user_id, mode, is_enabled, updated_by)
                SELECT user_id, 'binary', 1, NULL FROM users
                """
            )

            raw_default_admin_id = (os.getenv("ADMIN_DEFAULT_USER_ID") or "7097261848").strip()
            try:
                default_admin_user_id = int(raw_default_admin_id)
            except (TypeError, ValueError):
                default_admin_user_id = 7097261848
            await cur.execute(
                """
                INSERT INTO admin_users (user_id, is_active, granted_by)
                VALUES (%s, 1, %s)
                ON DUPLICATE KEY UPDATE is_active = 1
                """,
                (default_admin_user_id, default_admin_user_id),
            )

