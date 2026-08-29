"""
Stock footage providers — Pexels, Pixabay API clients.

Register for API keys:
- Pexels: https://www.pexels.com/api/
- Pixabay: https://pixabay.com/api/docs/
"""
from __future__ import annotations
import json
import logging
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger("leronx.assets")


def _pick_video_file(files: list[dict[str, Any]], target_w: int = 1920) -> dict[str, Any] | None:
    if not files:
        return None
    mp4s = [
        item
        for item in files
        if "mp4" in str(item.get("file_type", "")).lower() or str(item.get("link", "")).endswith(".mp4")
    ]
    pool = mp4s or files
    bounded = [item for item in pool if 640 <= (item.get("width") or 0) <= target_w]
    pool = bounded or pool
    return max(pool, key=lambda item: item.get("width") or 0)


class StockProvider(ABC):
    """Abstract stock footage provider."""

    @abstractmethod
    def search(self, query: str, per_page: int = 5) -> list[dict[str, Any]]:
        ...


class PexelsProvider(StockProvider):
    """Pexels Video API client."""

    BASE_URL = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY", "")
        if not self.api_key:
            logger.debug("PEXELS_API_KEY not set — Pexels provider disabled")

    def search(self, query: str, per_page: int = 5) -> list[dict]:
        if not self.api_key or not query:
            return []
        params = urllib.parse.urlencode(
            {"query": query, "per_page": per_page, "orientation": "landscape"}
        )
        req = urllib.request.Request(
            f"{self.BASE_URL}?{params}",
            headers={"Authorization": self.api_key, "User-Agent": "LeronX/1.1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            logger.error("Pexels search failed: %s", exc)
            return []
        results = []
        for video in data.get("videos", []):
            chosen = _pick_video_file(video.get("video_files") or [])
            if not chosen:
                continue
            results.append(
                {
                    "url": chosen.get("link", ""),
                    "provider": "pexels",
                    "duration": video.get("duration", 0),
                    "width": chosen.get("width", 0),
                }
            )
        return results


class PixabayProvider(StockProvider):
    """Pixabay Video API client."""

    BASE_URL = "https://pixabay.com/api/videos/"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PIXABAY_API_KEY", "")
        if not self.api_key:
            logger.debug("PIXABAY_API_KEY not set — Pixabay provider disabled")

    def search(self, query: str, per_page: int = 5) -> list[dict]:
        if not self.api_key or not query:
            return []
        params = urllib.parse.urlencode(
            {"key": self.api_key, "q": query, "per_page": per_page, "video_type": "all"}
        )
        try:
            req = urllib.request.Request(
                f"{self.BASE_URL}?{params}",
                headers={"User-Agent": "LeronX/1.1"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as exc:
            logger.error("Pixabay search failed: %s", exc)
            return []
        results = []
        for hit in data.get("hits", []):
            videos = hit.get("videos") or {}
            chosen = videos.get("medium") or videos.get("large") or videos.get("small") or {}
            url = chosen.get("url", "")
            if not url:
                continue
            results.append(
                {
                    "url": url,
                    "provider": "pixabay",
                    "duration": hit.get("duration", 0),
                    "width": chosen.get("width", 0),
                }
            )
        return results
