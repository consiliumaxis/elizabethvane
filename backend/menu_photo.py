import os
import secrets
from typing import Any, Dict, Optional, Tuple


MAX_MENU_PHOTO_SIZE = 10 * 1024 * 1024
MENU_PHOTO_EXTENSIONS = (".jpg", ".png", ".webp")


def detect_menu_photo_format(payload: bytes) -> Optional[Tuple[str, str]]:
    """Return a safe extension/content type based on the actual file bytes."""
    if payload.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def find_custom_menu_photo(managed_dir: str) -> str:
    root = os.path.realpath(managed_dir)
    for extension in MENU_PHOTO_EXTENSIONS:
        candidate = os.path.realpath(os.path.join(root, f"active{extension}"))
        if os.path.dirname(candidate) == root and os.path.isfile(candidate):
            return candidate
    return ""


def resolve_menu_photo(default_path: str, managed_dir: str) -> Tuple[str, str]:
    custom_path = find_custom_menu_photo(managed_dir)
    if custom_path:
        return custom_path, "uploaded"
    return default_path, "default" if os.path.isfile(default_path) else "missing"


def describe_menu_photo(default_path: str, managed_dir: str) -> Dict[str, Any]:
    path, source = resolve_menu_photo(default_path, managed_dir)
    file_exists = bool(path and os.path.isfile(path))
    try:
        file_size = os.path.getsize(path) if file_exists else 0
        version = str(os.stat(path).st_mtime_ns) if file_exists else "missing"
    except OSError:
        file_size = 0
        version = "missing"
        file_exists = False
    return {
        "file_exists": file_exists,
        "file_name": os.path.basename(path) if path else "",
        "file_size": int(file_size),
        "source": source if file_exists else "missing",
        "max_size": MAX_MENU_PHOTO_SIZE,
        "preview_url": f"/api/assets/menu-photo?v={version}",
        "default_exists": os.path.isfile(default_path),
    }


def save_custom_menu_photo(payload: bytes, managed_dir: str) -> str:
    detected = detect_menu_photo_format(payload)
    if not detected:
        raise ValueError("Only JPEG, PNG or WebP images are supported")
    if len(payload) > MAX_MENU_PHOTO_SIZE:
        raise ValueError("The image is too large")

    extension, _content_type = detected
    os.makedirs(managed_dir, exist_ok=True)
    root = os.path.realpath(managed_dir)
    target_path = os.path.realpath(os.path.join(root, f"active{extension}"))
    if os.path.dirname(target_path) != root:
        raise ValueError("Invalid menu image storage path")
    temp_path = os.path.realpath(
        os.path.join(root, f".upload-{secrets.token_hex(8)}{extension}")
    )
    if os.path.dirname(temp_path) != root:
        raise ValueError("Invalid menu image temporary path")

    try:
        with open(temp_path, "wb") as target_file:
            target_file.write(payload)
            target_file.flush()
            os.fsync(target_file.fileno())
        os.replace(temp_path, target_path)
        for stale_extension in MENU_PHOTO_EXTENSIONS:
            stale_path = os.path.realpath(os.path.join(root, f"active{stale_extension}"))
            if stale_path != target_path and os.path.dirname(stale_path) == root and os.path.isfile(stale_path):
                os.remove(stale_path)
    finally:
        if os.path.isfile(temp_path):
            os.remove(temp_path)
    return target_path


def reset_custom_menu_photo(managed_dir: str) -> None:
    root = os.path.realpath(managed_dir)
    for extension in MENU_PHOTO_EXTENSIONS:
        candidate = os.path.realpath(os.path.join(root, f"active{extension}"))
        if os.path.dirname(candidate) == root and os.path.isfile(candidate):
            os.remove(candidate)
