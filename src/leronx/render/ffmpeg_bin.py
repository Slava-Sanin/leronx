"""Locate FFmpeg: system PATH first, then the imageio-ffmpeg binary."""
from __future__ import annotations
import logging
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("leronx.render")


@lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            logger.info("Using bundled FFmpeg: %s", exe)
            return exe
    except Exception as exc:
        logger.debug("imageio-ffmpeg unavailable: %s", exc)
    return None


def find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def probe_duration(path: Path, ffmpeg: str | None = None) -> float | None:
    """Read media duration from ffmpeg stderr. Works without ffprobe."""
    exe = ffmpeg or find_ffmpeg()
    if not exe or not Path(path).exists():
        return None
    try:
        result = subprocess.run(
            [exe, "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr or "")
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def ffmpeg_subtitles_path(path: Path) -> str:
    """Escape a filesystem path for FFmpeg ass=/subtitles= filters."""
    text = path.resolve().as_posix()
    return text.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
