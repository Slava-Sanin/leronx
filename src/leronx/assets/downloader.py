"""Download stock clips with a small on-disk cache."""
from __future__ import annotations
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("leronx.assets")


def _suffix_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".mp4", ".webm", ".mov", ".jpg", ".jpeg", ".png", ".webp"):
        if path.endswith(ext):
            return ext
    return ".mp4"


def download_file(url: str, dest_dir: Path, timeout: float = 60.0) -> Path | None:
    """Download url into dest_dir. Returns the local path or None."""
    if not url:
        return None
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    dest = dest_dir / f"{digest}{_suffix_from_url(url)}"
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    try:
        import httpx
    except ImportError:
        logger.error("httpx is required to download stock footage")
        return None
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            with client.stream("GET", url, headers={"User-Agent": "LeronX/1.1"}) as response:
                response.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with tmp.open("wb") as handle:
                    for chunk in response.iter_bytes(64 * 1024):
                        handle.write(chunk)
                tmp.replace(dest)
        if dest.stat().st_size < 1000:
            dest.unlink(missing_ok=True)
            return None
        logger.info("Downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
        return dest
    except Exception as exc:
        logger.warning("Download failed for %s: %s", url, exc)
        dest.unlink(missing_ok=True)
        return None
