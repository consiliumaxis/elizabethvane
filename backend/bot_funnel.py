import json
import re
from typing import Any, Dict, Optional
from urllib.parse import urlsplit


BOT_START_EVENT = "bot_start"
CHATTERFY_START_EVENT = "start_chatterfy"
CHATTERFY_BOT_START_EVENT = "start_bot_chatterfy"
QUIZ_COMPLETE_EVENT = "quiz_complete"
CHANNEL_SUBSCRIBE_EVENT = "channel_subscribe"
CHATTERFY_CHANNEL_SUBSCRIBE_EVENT = CHANNEL_SUBSCRIBE_EVENT

DEFAULT_CHANNEL_ID = -1003584421739
DEFAULT_CHANNEL_URL = "https://t.me/+sUmNRVpk63M1Y2E1"
DEFAULT_CHECK_SUBSCRIPTION_ENABLED = 1

QUIZ_STEPS = ("experience", "broker_experience", "capital")
QUIZ_AIO_FIELDS = {
    "experience": "tg_question1",
    "broker_experience": "tg_question2",
    "capital": "tg_question3",
}
QUIZ_QUESTIONS = {
    "experience": "What is your trading experience?",
    "broker_experience": "Have you worked with any of these brokers before?",
    "capital": (
        "What is your trading capital (deposit)?\n"
        "This helps us suggest a more relevant broker setup later.\n"
        "Trading involves risk."
    ),
}
QUIZ_OPTIONS = {
    "experience": (
        "I have no experience",
        "Less than 1 year",
        "1-2 years",
        "2-5 years",
        "More than 5 years",
        "Skip",
    ),
    "broker_experience": (
        "Broker 1",
        "Broker 2",
        "Broker 3",
        "Other broker",
        "I have not worked with a broker",
        "Skip",
    ),
    "capital": (
        "Up to $100",
        "$100-$1,000",
        "$1,000-$10,000",
        "$10,000-$100,000",
        "$100,000+",
        "Skip",
    ),
}
DEFAULT_QUIZ_CONFIG = {
    step: {
        "question": QUIZ_QUESTIONS[step],
        "options": list(QUIZ_OPTIONS[step]),
    }
    for step in QUIZ_STEPS
}
FINAL_MESSAGE_BUTTON_TYPES = ("url", "menu", "web_app")
FINAL_MESSAGE_MAX_BUTTONS = 8
FINAL_MESSAGE_TEXT_MAX_LENGTH = 3500
DEFAULT_FINAL_MESSAGE_CONFIG = {
    "enabled": 1,
    "trigger_button_text": "Go to trading",
    "message_text": "You're all set. Choose what you'd like to do next.",
    "buttons": [
        {
            "id": "open_menu",
            "type": "menu",
            "text": "Open Elizabeth Vane",
            "url": "",
        }
    ],
}
SKIP_PHRASES = {
    "skip",
    "later",
    "not now",
    "no thanks",
    "dont want",
    "don't want",
    "do not want",
    "just send link",
    "just send the link",
    "send link",
    "send the link",
    "channel",
}


def normalize_quiz_step(step: Optional[str]) -> str:
    normalized_step = str(step or "").strip().lower()
    return normalized_step if normalized_step in QUIZ_STEPS else QUIZ_STEPS[0]


def is_valid_quiz_step(step: Optional[str]) -> bool:
    return str(step or "").strip().lower() in QUIZ_STEPS


def normalize_quiz_config(value: Any = None) -> Dict[str, Dict[str, Any]]:
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    if not isinstance(value, dict):
        value = {}

    normalized: Dict[str, Dict[str, Any]] = {}
    for step in QUIZ_STEPS:
        default_item = DEFAULT_QUIZ_CONFIG[step]
        raw_item = value.get(step) if isinstance(value.get(step), dict) else {}
        question = str(raw_item.get("question") or "").strip() or default_item["question"]
        raw_options = raw_item.get("options")
        options = []
        if isinstance(raw_options, (list, tuple)):
            seen = set()
            for option in raw_options:
                text = str(option or "").strip()
                key = text.lower()
                if not text or key in seen:
                    continue
                seen.add(key)
                options.append(text[:64])
        if not options:
            options = list(default_item["options"])
        normalized[step] = {
            "question": question[:600],
            "options": options[:8],
        }
    return normalized


def _load_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, str) and value.strip():
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    return value if isinstance(value, dict) else {}


def normalize_final_button_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("@"):
        raw = f"https://t.me/{raw[1:].strip('/')}"
    elif raw.startswith("t.me/"):
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw[:1000]
    if parsed.scheme == "tg" and (parsed.netloc or parsed.path):
        return raw[:1000]
    return ""


def normalize_final_message_config(value: Any = None) -> Dict[str, Any]:
    source = _load_json_object(value)
    has_source = bool(source)
    defaults = DEFAULT_FINAL_MESSAGE_CONFIG
    enabled = normalize_bool_flag(source.get("enabled"), defaults["enabled"])
    trigger_button_text = (
        str(source.get("trigger_button_text") or "").strip()
        or defaults["trigger_button_text"]
    )[:64]
    message_text = (
        str(source.get("message_text") or "").strip()
        or defaults["message_text"]
    )[:FINAL_MESSAGE_TEXT_MAX_LENGTH]

    raw_buttons = source.get("buttons")
    if not isinstance(raw_buttons, (list, tuple)):
        raw_buttons = defaults["buttons"] if not has_source or raw_buttons is None else []

    buttons = []
    used_ids = set()
    singleton_types_added = set()
    for index, raw_button in enumerate(raw_buttons):
        if not isinstance(raw_button, dict):
            continue
        button_type = str(raw_button.get("type") or "url").strip().lower()
        if button_type not in FINAL_MESSAGE_BUTTON_TYPES:
            continue
        text = str(raw_button.get("text") or "").strip()[:64]
        if not text:
            continue
        url = ""
        if button_type == "url":
            url = normalize_final_button_url(raw_button.get("url"))
            if not url:
                continue
        elif button_type in singleton_types_added:
            continue
        else:
            singleton_types_added.add(button_type)

        raw_id = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(raw_button.get("id") or "").strip())[:48]
        button_id = raw_id or f"button_{index + 1}"
        suffix = 2
        unique_id = button_id
        while unique_id in used_ids:
            unique_id = f"{button_id}_{suffix}"[:48]
            suffix += 1
        used_ids.add(unique_id)
        buttons.append(
            {
                "id": unique_id,
                "type": button_type,
                "text": text,
                "url": url,
            }
        )
        if len(buttons) >= FINAL_MESSAGE_MAX_BUTTONS:
            break

    return {
        "enabled": enabled,
        "trigger_button_text": trigger_button_text,
        "message_text": message_text,
        "buttons": buttons,
    }


def validate_final_message_config(value: Any) -> Dict[str, Any]:
    source = _load_json_object(value)
    if not source:
        return normalize_final_message_config()
    raw_buttons = source.get("buttons")
    enabled = normalize_bool_flag(source.get("enabled"), DEFAULT_FINAL_MESSAGE_CONFIG["enabled"])
    message_text = str(source.get("message_text") or "").strip()
    trigger_button_text = str(source.get("trigger_button_text") or "").strip()

    if not trigger_button_text:
        raise ValueError("Укажите название кнопки перехода")
    if len(trigger_button_text) > 64:
        raise ValueError("Название кнопки перехода не должно превышать 64 символа")
    if enabled and not message_text:
        raise ValueError("Укажите текст финального сообщения")
    if len(message_text) > FINAL_MESSAGE_TEXT_MAX_LENGTH:
        raise ValueError(
            f"Финальное сообщение не должно превышать {FINAL_MESSAGE_TEXT_MAX_LENGTH} символов"
        )
    if not isinstance(raw_buttons, list):
        raise ValueError("Кнопки финального сообщения должны быть списком")
    if len(raw_buttons) > FINAL_MESSAGE_MAX_BUTTONS:
        raise ValueError(f"Можно добавить не более {FINAL_MESSAGE_MAX_BUTTONS} кнопок")

    singleton_counts = {"menu": 0, "web_app": 0}
    for index, button in enumerate(raw_buttons, start=1):
        if not isinstance(button, dict):
            raise ValueError(f"Некорректные данные кнопки {index}")
        button_type = str(button.get("type") or "").strip().lower()
        if button_type not in FINAL_MESSAGE_BUTTON_TYPES:
            raise ValueError(f"Выберите действие для кнопки {index}")
        text = str(button.get("text") or "").strip()
        if not text:
            raise ValueError(f"Укажите название кнопки {index}")
        if len(text) > 64:
            raise ValueError(f"Название кнопки {index} не должно превышать 64 символа")
        if button_type == "url" and not normalize_final_button_url(button.get("url")):
            raise ValueError(f"Укажите полную HTTP(S) или tg:// ссылку для кнопки {index}")
        if button_type in singleton_counts:
            singleton_counts[button_type] += 1
    if singleton_counts["menu"] > 1:
        raise ValueError("Можно добавить только одну кнопку открытия меню")
    if singleton_counts["web_app"] > 1:
        raise ValueError("Можно добавить только одну кнопку открытия мини-приложения")
    if enabled and not raw_buttons:
        raise ValueError("Добавьте хотя бы одну кнопку финального сообщения")
    return normalize_final_message_config(source)


def get_quiz_question(step: Optional[str], quiz_config: Any = None) -> str:
    config = normalize_quiz_config(quiz_config)
    return config[normalize_quiz_step(step)]["question"]


def get_quiz_options(step: Optional[str], quiz_config: Any = None) -> tuple[str, ...]:
    config = normalize_quiz_config(quiz_config)
    return tuple(config[normalize_quiz_step(step)]["options"])


def get_aio_question_field(step: Optional[str]) -> str:
    return QUIZ_AIO_FIELDS[normalize_quiz_step(step)]


def get_next_quiz_step(step: Optional[str]) -> Optional[str]:
    normalized_step = normalize_quiz_step(step)
    index = QUIZ_STEPS.index(normalized_step)
    if index + 1 >= len(QUIZ_STEPS):
        return None
    return QUIZ_STEPS[index + 1]


def get_quiz_steps_to_complete(step: Optional[str], skip_flow: bool = False) -> tuple[str, ...]:
    normalized_step = normalize_quiz_step(step)
    if not skip_flow:
        return (normalized_step,)
    index = QUIZ_STEPS.index(normalized_step)
    return QUIZ_STEPS[index:]


def is_skip_answer(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized in SKIP_PHRASES:
        return True
    return any(phrase in normalized for phrase in ("just send", "send me the channel", "give me the link"))


def normalize_quiz_answer(step: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("answer is required")
    if is_skip_answer(text):
        return "Skip"
    for option in get_quiz_options(step):
        if option.lower() == text.lower():
            return option
    return text[:255]


def _extract_amount(text: str) -> Optional[float]:
    match = re.search(r"(\d[\d\s,.]*)", text)
    if not match:
        return None
    raw = match.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def map_quiz_answer_locally(step: str, value: Any) -> Optional[str]:
    normalized_step = normalize_quiz_step(step)
    text = str(value or "").strip()
    lowered = text.lower()
    if not text:
        return None
    if is_skip_answer(text):
        return "Skip"

    if normalized_step == "experience":
        if any(token in lowered for token in ("no experience", "beginner", "newbie", "novice", "never traded")):
            return "I have no experience"
        if "less" in lowered or "under" in lowered or "few month" in lowered:
            return "Less than 1 year"
        if ("1" in lowered and "2" in lowered) or "one" in lowered or "two" in lowered:
            return "1-2 years"
        if "2" in lowered and "5" in lowered:
            return "2-5 years"
        if any(token in lowered for token in ("more than 5", "over 5", "5+", "six", "seven", "expert")):
            return "More than 5 years"

    if normalized_step == "broker_experience":
        if any(token in lowered for token in ("no broker", "not worked", "never", "none", "haven't", "have not")):
            return "I have not worked with a broker"
        for option in ("Broker 1", "Broker 2", "Broker 3"):
            if option.lower() in lowered:
                return option
        if "other" in lowered or "another" in lowered:
            return "Other broker"

    if normalized_step == "capital":
        amount = _extract_amount(lowered)
        if amount is not None:
            if amount <= 100:
                return "Up to $100"
            if amount <= 1000:
                return "$100-$1,000"
            if amount <= 10000:
                return "$1,000-$10,000"
            if amount <= 100000:
                return "$10,000-$100,000"
            return "$100,000+"

    for option in get_quiz_options(normalized_step):
        if option.lower() == lowered:
            return option
    return None


def normalize_channel_id(value: Any) -> int:
    try:
        channel_id = int(str(value or "").strip())
    except (TypeError, ValueError):
        return DEFAULT_CHANNEL_ID
    # Telegram supergroups/channels use the signed ``-100...`` Bot API form.
    # Admins sometimes paste the same identifier without its leading minus;
    # accepting that form here prevents every membership check from targeting
    # a non-existent positive chat.
    if channel_id > 0 and str(channel_id).startswith("100"):
        channel_id = -channel_id
    return channel_id or DEFAULT_CHANNEL_ID


def normalize_bool_flag(value: Any, default: int = 0) -> int:
    if value is None:
        return 1 if default else 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "on", "да"):
            return 1
        if lowered in ("0", "false", "no", "off", "нет"):
            return 0
    return 1 if bool(value) else 0


def normalize_telegram_url(value: Any, default: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return default
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:].strip('/')}"
    if raw.startswith("t.me/"):
        return f"https://{raw}"
    return raw


def normalize_channel_settings(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    source = row or {}
    channel_url = normalize_telegram_url(source.get("channel_url"), DEFAULT_CHANNEL_URL)
    support_url = normalize_telegram_url(source.get("support_url"))
    return {
        "channel_id": normalize_channel_id(source.get("channel_id")),
        "channel_url": channel_url,
        "support_url": support_url,
        "check_subscription_enabled": normalize_bool_flag(
            source.get("check_subscription_enabled"),
            DEFAULT_CHECK_SUBSCRIPTION_ENABLED,
        ),
    }


def is_active_channel_member(status: Any, is_member: Any = None) -> bool:
    raw_status = getattr(status, "value", status)
    normalized_status = str(raw_status or "").strip().lower()
    if normalized_status in {"member", "administrator", "creator"}:
        return True
    if normalized_status == "restricted":
        return bool(is_member)
    return False
