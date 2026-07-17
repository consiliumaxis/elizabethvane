import os
from datetime import timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

ADMIN_IDS_ENV = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {
    int(x.strip())
    for x in ADMIN_IDS_ENV.split(",")
    if x.strip().isdigit()
}

DB_CONFIG: dict = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "db": os.getenv("DB_NAME", "aichat"),
    "autocommit": True,
    "charset": "utf8mb4",
}

MSK_TZ = ZoneInfo(os.getenv("MSK_TZ", "Europe/Moscow"))

REGISTER_BASE_URL = os.getenv(
    "REGISTER_BASE_URL",
    "https://app.elizabethvane.online/",
)

CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/VBerin")
SUPPORT_URL = os.getenv("SUPPORT_URL", CHANNEL_URL)
FUNNEL_MEDIA_DIR = os.path.abspath(
    os.getenv("FUNNEL_MEDIA_DIR", "/root/evanechat/media/funnel")
)

PROMPT_PAGE_SIZE = int(os.getenv("PROMPT_PAGE_SIZE", "800"))
KV_CACHE_TTL = timedelta(minutes=5)

STAGE_NEW = "new"
STAGE_NAME_KNOWN = "name_known"
STAGE_WAITING_PLATFORM_ACCOUNT = "waiting_platform_account"
STAGE_WAITING_EXISTING_ACCOUNT_TRADER_ID = "waiting_existing_account_trader_id"
STAGE_REG_LINK_SENT = "reg_link_sent"
STAGE_WAITING_ACCOUNT_ID = "waiting_account_id"
STAGE_ACCOUNT_ID_SENT = "account_id_sent"
STAGE_ACCOUNT_ID_BAD = "account_id_bad"
STAGE_ACCOUNT_ID_OK = "account_id_ok"
STAGE_WAITING_DEPOSIT = "waiting_deposit"
STAGE_DEPOSIT_DONE = "deposit_done"

STAGE_TITLES = {
    STAGE_NEW: "Новый",
    STAGE_NAME_KNOWN: "Имя известно / знакомство",
    STAGE_WAITING_PLATFORM_ACCOUNT: "Ждём ответ про наличие аккаунта",
    STAGE_WAITING_EXISTING_ACCOUNT_TRADER_ID: "Ждём Trader ID существующего аккаунта",
    STAGE_REG_LINK_SENT: "Ссылка на регистрацию отправлена",
    STAGE_WAITING_ACCOUNT_ID: "Ждём ID торгового счёта",
    STAGE_ACCOUNT_ID_SENT: "Клиент отправил ID",
    STAGE_ACCOUNT_ID_BAD: "ID не подходит, нужно удалить аккаунт",
    STAGE_ACCOUNT_ID_OK: "ID подтверждён",
    STAGE_WAITING_DEPOSIT: "Ждём депозит",
    STAGE_DEPOSIT_DONE: "Депозит сделан",
}

AFFILIATE_BASE_URL = os.getenv("AFFILIATE_BASE_URL", "http://127.0.0.1:8000")
AFFILIATE_API_SECRET = os.getenv("AFFILIATE_API_SECRET", "")
POSTBACK_BASE_URL = os.getenv("POSTBACK_BASE_URL", "https://app.elizabethvane.online")
AFFILIATE_BOT_ID = os.getenv("AFFILIATE_BOT_ID", "elizabethvane")
