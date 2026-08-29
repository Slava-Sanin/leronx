"""
Asset Matcher — finds relevant stock footage for scenes.

Uses keyword extraction + provider APIs (Pexels, Pixabay, etc.)
"""
from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..scenes.graph import SceneGraph
from .cards import render_title_card
from .downloader import download_file
from .imagine import generate_still
from .motion import generate_clip
from .providers import PexelsProvider, PixabayProvider, StockProvider

logger = logging.getLogger("leronx.assets")


@dataclass
class AssetMatch:
    scene_index: int
    url: str = ""
    provider: str = "stock"
    relevance: float = 0.0
    keywords: list[str] = field(default_factory=list)
    path: Optional[str] = None


class AssetMatcher:
    """Matches scene descriptions to stock footage, with title-card fallback."""

    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "about", "and", "or", "but",
        "in", "on", "at", "to", "for", "of", "with", "by", "this", "that", "you",
        "your", "not", "just", "from", "will", "can", "how", "what", "when",
        "это", "как", "что", "для", "или", "при", "уже", "если", "все", "они",
        "его", "её", "без", "над", "под", "там", "тут", "чем", "кто", "где",
    }

    def __init__(self, providers: list[StockProvider] | None = None):
        self.providers = providers if providers is not None else self._default_providers()

    def _default_providers(self) -> list[StockProvider]:
        found: list[StockProvider] = []
        pexels = PexelsProvider()
        if pexels.api_key:
            found.append(pexels)
        pixabay = PixabayProvider()
        if pixabay.api_key:
            found.append(pixabay)
        return found

    def extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        words = re.findall(r"\b[a-zA-Zа-яА-ЯёЁ]{3,}\b", text.lower())
        keywords = [word for word in words if word not in self.STOP_WORDS]
        freq: dict[str, int] = {}
        for word in keywords:
            freq[word] = freq.get(word, 0) + 1
        return [key for key, _ in sorted(freq.items(), key=lambda item: -item[1])[:max_keywords]]

    def match(self, scenes: list[dict], max_per_scene: int = 3) -> list[AssetMatch]:
        """Match assets to scenes. Downloads when a provider is configured."""
        results: list[AssetMatch] = []
        for scene in scenes:
            keywords = self.extract_keywords(scene.get("narration", ""))
            url = ""
            provider_name = "stock"
            if self.providers and keywords:
                hits = self._search(" ".join(keywords[:3]), max_per_scene)
                if hits:
                    url = hits[0].get("url", "")
                    provider_name = hits[0].get("provider", "stock")
            results.append(
                AssetMatch(
                    scene_index=scene["index"],
                    keywords=keywords,
                    url=url,
                    provider=provider_name,
                    relevance=1.0 if url else 0.0,
                )
            )
        logger.info("Matched %d scenes", len(results))
        return results

    def enrich_graph(
        self,
        graph: SceneGraph,
        work_dir: Path,
        resolution: tuple[int, int] = (1920, 1080),
        topic: str = "",
        visual_style: str = "animation",
        generate_motion: bool = True,
    ) -> SceneGraph:
        """Attach animated clips, then stills, then stock. Text cards are last resort."""
        clips_dir = Path(work_dir) / "assets"
        clips_dir.mkdir(parents=True, exist_ok=True)
        used_urls: set[str] = set()
        for scene in graph.scenes:
            if scene.assets:
                continue
            if generate_motion:
                clip = generate_clip(
                    clips_dir / f"scene_{scene.index:03d}.mp4",
                    topic=topic,
                    narration=scene.narration,
                    shot_type=scene.shot_type,
                    style=visual_style,
                    duration=scene.duration,
                    resolution=resolution,
                )
                if clip:
                    scene.assets.append(str(clip))
                    time.sleep(2)
                    continue
            stills = self._generate_stills(scene, clips_dir, resolution, topic, visual_style)
            if stills:
                scene.assets.extend(str(path) for path in stills)
                continue
            keywords = self.extract_keywords(scene.narration or topic)
            query = " ".join(keywords[:3]) or topic
            local = self._download_stock(query, clips_dir, used_urls)
            if local:
                scene.assets.append(str(local))
                continue
            logger.warning("Falling back to a title card for scene %s", scene.index)
            card = clips_dir / f"card_{scene.index:03d}.png"
            spoken = (scene.narration or topic or "LeronX").strip()
            words = spoken.split()
            headline = spoken if len(words) <= 10 else " ".join(words[:10])
            render_title_card(
                headline,
                card,
                resolution=resolution,
                index=scene.index,
                kicker=topic[:42] if topic else f"Scene {scene.index + 1}",
            )
            scene.assets.append(str(card))
        return graph

    def _generate_stills(
        self,
        scene,
        dest_dir: Path,
        resolution: tuple[int, int],
        topic: str,
        visual_style: str,
    ) -> list[Path]:
        shots = [scene.shot_type or "medium"]
        if scene.duration >= 8:
            alt = "closeup" if scene.shot_type == "wide" else "wide"
            shots.append(alt)
        paths: list[Path] = []
        for variant, shot in enumerate(shots):
            dest = dest_dir / f"scene_{scene.index:03d}_{variant}.jpg"
            still = generate_still(
                dest,
                topic=topic,
                narration=scene.narration,
                shot_type=shot,
                style=visual_style,
                index=scene.index,
                variant=variant,
                resolution=resolution,
            )
            if still:
                paths.append(still)
                time.sleep(1.5)
        return paths

    def _search(self, query: str, per_page: int) -> list[dict]:
        for provider in self.providers:
            try:
                hits = provider.search(query, per_page=per_page)
            except Exception as exc:
                logger.warning("Provider %s failed: %s", type(provider).__name__, exc)
                continue
            if hits:
                return hits
        return []

    def _download_stock(self, query: str, dest_dir: Path, used_urls: set[str]) -> Path | None:
        if not query or not self.providers:
            return None
        hits = self._search(query, per_page=5)
        for hit in hits:
            url = hit.get("url") or ""
            if not url or url in used_urls:
                continue
            path = download_file(url, dest_dir)
            if path:
                used_urls.add(url)
                return path
        return None
