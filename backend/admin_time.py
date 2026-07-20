import re
from datetime import time, timedelta
from typing import Optional


def time_text(value) -> Optional[str]:
    """Serialize MySQL TIME values for an HTML time input."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        hours, remainder = divmod(total_seconds, 60 * 60)
        minutes = remainder // 60
        return f"{hours:02d}:{minutes:02d}"
    if isinstance(value, time):
        return value.strftime("%H:%M")
    match = re.fullmatch(r"(\d{1,2}):([0-5]\d)(?::[0-5]\d(?:\.\d+)?)?", str(value).strip())
    if not match:
        return None
    hours = int(match.group(1))
    if hours > 23:
        return None
    return f"{hours:02d}:{match.group(2)}"
