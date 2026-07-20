import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")


def build_registration_url(template: str, click_id: int) -> str:
    """Build a registration URL while preserving fixed and duplicate query parameters."""
    parts = urlsplit(str(template or "").strip())
    query = []
    has_click_id = False
    for key, raw_value in parse_qsl(parts.query, keep_blank_values=True):
        value = raw_value.replace("{click_id}", str(click_id))
        value = _PLACEHOLDER_RE.sub("", value)
        if key == "click_id":
            value = str(click_id)
            has_click_id = True
        query.append((key, value))
    if not has_click_id:
        query.append(("click_id", str(click_id)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
