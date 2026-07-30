import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.video_note import prepare_square_video_note


class _FakeProcess:
    returncode = 0

    async def communicate(self):
        return b"", b""


class VideoNoteTests(unittest.IsolatedAsyncioTestCase):
    async def test_prepares_square_h264_video_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "portrait.mp4"
            source_path.write_bytes(b"source-video")
            commands = []

            async def fake_subprocess(*command, **kwargs):
                commands.append(command)
                Path(command[-1]).write_bytes(b"normalized" * 256)
                return _FakeProcess()

            with patch(
                "backend.video_note.asyncio.create_subprocess_exec",
                new=fake_subprocess,
            ):
                result = await prepare_square_video_note(str(source_path))

            self.assertTrue(result)
            self.assertTrue(os.path.isfile(result))
            self.assertIn(f"{os.sep}.video_notes{os.sep}", result)
            command = commands[0]
            self.assertIn("libx264", command)
            self.assertIn("yuv420p", command)
            self.assertIn("scale=512:512", " ".join(command))
            self.assertIn("59", command)

            create_process = AsyncMock()
            with patch(
                "backend.video_note.asyncio.create_subprocess_exec",
                new=create_process,
            ):
                cached_result = await prepare_square_video_note(str(source_path))

            self.assertEqual(cached_result, result)
            create_process.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
