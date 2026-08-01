import os
from typing import Iterable, List


def env_int_list(name: str, defaults: Iterable[int]) -> List[int]:
    fallback = list(defaults)
    raw_value = str(os.getenv(name) or "").strip()
    values = raw_value.replace(";", ",").split(",") if raw_value else fallback
    result = []
    for value in values:
        try:
            normalized = int(str(value).strip())
        except (TypeError, ValueError):
            continue
        if normalized > 0 and normalized not in result:
            result.append(normalized)
    return result or fallback
