import re
from datetime import datetime, timezone
from typing import Mapping, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_REGISTRATION_URL = (
    "https://u3.shortink.io/register?utm_campaign=836376&utm_source=affiliate"
    "&utm_medium=sr&a=vlWoz5KLjybBQD&al=1773166&ac=elizabeth_vane_rev1"
    "&cid=962430&code=WELCOME50"
)

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_REQUIRED_TRACKING_KEYS = ("click_id", "sub_id2", "sub_id3")
_TELEGRAM_USERNAME_RE = re.compile(r"[A-Za-z0-9_]{5,32}")
_CHATTERFY_LEAD_ID_RE = re.compile(r"[A-Za-z0-9._:@-]{1,255}")


def _clean(value: object, max_length: int = 512) -> str:
    return str(value if value is not None else "").strip()[:max_length]


def parse_registration_link_target(message_text: object) -> Tuple[Optional[str], Optional[str]]:
    """Parse ``/link`` argument as a Telegram username or Chatterfy lead id."""

    parts = str(message_text or "").strip().split(maxsplit=1)
    if len(parts) != 2 or not parts[0].lower().startswith("/link"):
        return None, None
    raw_target = parts[1].strip()
    if not raw_target or any(character.isspace() for character in raw_target):
        return None, None
    if raw_target.startswith("@"):
        username = raw_target[1:]
        if not _TELEGRAM_USERNAME_RE.fullmatch(username):
            return None, None
        return "username", username.lower()
    if not _CHATTERFY_LEAD_ID_RE.fullmatch(raw_target):
        return None, None
    return "lead_id", raw_target


def build_registration_url(
    template: str,
    *,
    click_id: object,
    aio_visit_uuid: object = "",
    tracker_click_id: object = None,
    chatterfy_lead_id: object = "",
    values: Optional[Mapping[str, object]] = None,
) -> str:
    """Build one Pocket registration URL without exposing data outside the URL.

    The three tracking fields are always present. ``tracker_click_id`` is the
    Chatterfy tracker value written to ``sub_id2``; the older
    ``aio_visit_uuid`` argument remains as a backwards-compatible fallback.
    Missing tracker or Chatterfy values intentionally stay empty so a single
    admin template works for every client.
    Fixed campaign values already present in the template take precedence over an
    empty duplicate placeholder (for example ``ac=fixed&ac={ac}``).
    """

    source = _clean(template, 8192) or DEFAULT_REGISTRATION_URL
    parts = urlsplit(source)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Registration URL must be a full HTTP(S) URL")

    replacements = {
        "click_id": _clean(click_id, 64),
        "sub_id2": _clean(
            tracker_click_id if tracker_click_id is not None else aio_visit_uuid,
            255,
        ),
        "sub_id3": _clean(chatterfy_lead_id, 255),
        "date_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for key, value in (values or {}).items():
        normalized_key = _clean(key, 64)
        if normalized_key and normalized_key not in _REQUIRED_TRACKING_KEYS:
            replacements[normalized_key] = _clean(value)

    query = []
    seen_required = set()
    for raw_key, raw_value in parse_qsl(parts.query, keep_blank_values=True):
        key = _clean(raw_key, 128)
        if not key:
            continue

        if key in _REQUIRED_TRACKING_KEYS:
            if key in seen_required:
                continue
            value = replacements[key]
            seen_required.add(key)
        else:
            value = _PLACEHOLDER_RE.sub(
                lambda match: replacements.get(match.group(1), ""),
                raw_value,
            )

        if not value and any(existing_key == key and existing_value for existing_key, existing_value in query):
            continue
        query.append((key, value))

    for key in _REQUIRED_TRACKING_KEYS:
        if key not in seen_required:
            query.append((key, replacements[key]))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
