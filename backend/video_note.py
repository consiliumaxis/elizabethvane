import asyncio
import os
from typing import Dict, Optional


_PREPARE_LOCKS: Dict[str, asyncio.Lock] = {}


async def prepare_square_video_note(source_path: str) -> Optional[str]:
    """Create a cached Telegram-compatible square H.264 video note."""
    source_path = os.path.abspath(str(source_path or ""))
    if not os.path.isfile(source_path):
        return None

    output_dir = os.path.join(os.path.dirname(source_path), ".video_notes")
    output_path = os.path.join(output_dir, os.path.basename(source_path))
    lock = _PREPARE_LOCKS.setdefault(output_path, asyncio.Lock())

    async with lock:
        try:
            if (
                os.path.isfile(output_path)
                and os.path.getsize(output_path) > 1024
                and os.path.getmtime(output_path) >= os.path.getmtime(source_path)
            ):
                return output_path
        except OSError:
            pass

        os.makedirs(output_dir, exist_ok=True)
        temp_path = f"{output_path}.tmp.mp4"
        filter_graph = (
            "crop=w='min(iw,ih)':h='min(iw,ih)':"
            "x='(iw-ow)/2':y='max(0,(ih-oh)*0.15)',"
            "scale=512:512:flags=lanczos"
        )
        command = (
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            source_path,
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-t",
            "59",
            "-vf",
            filter_graph,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            temp_path,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()
            if process.returncode != 0:
                error = stderr.decode("utf-8", "replace")[-2000:]
                print(f"[VideoNote] ffmpeg failed for {source_path}: {error}")
                return None
            os.replace(temp_path, output_path)
            return output_path
        except FileNotFoundError:
            print("[VideoNote] ffmpeg is not installed")
            return None
        except Exception as exc:
            print(f"[VideoNote] conversion failed for {source_path}: {exc}")
            return None
        finally:
            try:
                if os.path.isfile(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
