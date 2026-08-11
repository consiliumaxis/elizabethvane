import re
from datetime import datetime, timezone
from typing import Mapping, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_REQUIRED_TRACKING_KEYS = ("click_id", "sub_id2", "sub_id3")


def build_registration_url(
    template: str,
    click_id: int,
    *,
    aio_visit_uuid: object = "",
    chatterfy_lead_id: object = "",
    values: Optional[Mapping[str, object]] = None,
) -> str:
    """Build the same tracked URL as the main Elizabeth application."""
    parts = urlsplit(str(template or "").strip())
    replacements = {
        "click_id": str(click_id),
        "sub_id2": str(aio_visit_uuid or "").strip(),
        "sub_id3": str(chatterfy_lead_id or "").strip(),
        "date_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for key, value in (values or {}).items():
        normalized_key = str(key or "").strip()
        if normalized_key and normalized_key not in _REQUIRED_TRACKING_KEYS:
            replacements[normalized_key] = str(value or "").strip()

    query = []
    seen_required = set()
    for key, raw_value in parse_qsl(parts.query, keep_blank_values=True):
        if key in _REQUIRED_TRACKING_KEYS:
            if key in seen_required:
                continue
            value = replacements[key]
            seen_required.add(key)
        else:
            value = _PLACEHOLDER_RE.sub(lambda match: replacements.get(match.group(1), ""), raw_value)
        if not value and any(existing_key == key and existing_value for existing_key, existing_value in query):
            continue
        query.append((key, value))
    for key in _REQUIRED_TRACKING_KEYS:
        if key not in seen_required:
            query.append((key, replacements[key]))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
