import re


SEND_TAG_RE = re.compile(r"\[SEND:([a-z][a-z0-9]*(?:\.[0-9]+)?)\]", re.IGNORECASE)


def split_funnel_reply(reply_text: str) -> tuple[str | None, str, str]:
    text = reply_text or ""
    match = SEND_TAG_RE.search(text)
    if not match:
        return None, text, ""
    media_key = match.group(1).lower()
    before = SEND_TAG_RE.sub("", text[:match.start()]).strip()
    after = SEND_TAG_RE.sub("", text[match.end():]).strip()
    return media_key, before, after
