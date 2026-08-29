"""Generate cartoon-film stills for each scene (Pollinations Flux, optional OpenAI)."""
from __future__ import annotations
import hashlib
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger("leronx.assets")

STYLE_SUFFIX = {
    "animation": (
        "2D animated feature-film still, Pixar and Cartoon Saloon look, "
        "clear character design, painted background, cel shading, "
        "vibrant colors, readable silhouette, cinematic framing, "
        "NOT photorealistic, NOT live action, NOT a photograph, NOT a slide"
    ),
    "cinematic": (
        "photoreal cinematic movie still, anamorphic lens, dramatic lighting, "
        "shallow depth of field, film grain, production design"
    ),
    "comic": (
        "graphic novel cinematic panel, bold ink, painted color, dramatic angle, "
        "no speech balloons"
    ),
}

SHOT_PHRASE = {
    "wide": "wide establishing shot",
    "medium": "medium shot",
    "closeup": "emotional close-up",
}


def visual_prompt(
    topic: str,
    narration: str,
    shot_type: str = "medium",
    style: str = "animation",
    variant: int = 0,
) -> str:
    """Turn spoken text into a film-frame prompt. Ban typography on purpose."""
    shot = SHOT_PHRASE.get(shot_type, SHOT_PHRASE["medium"])
    if variant:
        shot = "alternate camera angle, " + shot
    style_bit = STYLE_SUFFIX.get(style, STYLE_SUFFIX["animation"])
    scene = (narration or topic or "a turning point").strip()
    theme = (topic or scene).strip()
    return (
        f"still from an animated feature film about {theme}. {shot}. "
        f"Story moment: {scene}. "
        f"Show a vivid narrative image with characters or a symbolic situation. "
        f"{style_bit}. "
        "no text, no letters, no words, no subtitles, no caption, "
        "no title card, no watermark, no logo, no UI"
    )


def _seed(topic: str, index: int, variant: int) -> int:
    raw = f"{topic}|{index}|{variant}".encode("utf-8")
    return int(hashlib.sha1(raw).hexdigest()[:8], 16) % 1_000_000


def _is_image(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.verify()
        return path.stat().st_size > 4000
    except Exception:
        return False


def _headers() -> dict[str, str]:
    headers = {"User-Agent": "LeronX/1.1", "Accept": "image/*"}
    token = os.environ.get("POLLINATIONS_API_KEY") or os.environ.get("POLLINATIONS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _save_url(url: str, dest: Path, timeout: float, attempts: int = 4) -> Path | None:
    try:
        import httpx
    except ImportError:
        logger.error("httpx is required to generate scene images")
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(follow_redirects=True, timeout=timeout) as client:
                with client.stream("GET", url, headers=_headers()) as response:
                    if response.status_code == 429:
                        wait = min(8 * attempt, 24)
                        logger.info("Image API rate-limited, retry in %ss", wait)
                        time.sleep(wait)
                        continue
                    response.raise_for_status()
                    ctype = response.headers.get("content-type", "")
                    if ctype and "image" not in ctype and "octet-stream" not in ctype:
                        logger.warning("Image endpoint returned %s", ctype)
                        return None
                    with tmp.open("wb") as handle:
                        for chunk in response.iter_bytes(64 * 1024):
                            handle.write(chunk)
            tmp.replace(dest)
            if not _is_image(dest):
                dest.unlink(missing_ok=True)
                return None
            logger.info("Generated frame %s (%.1f KB)", dest.name, dest.stat().st_size / 1024)
            return dest
        except Exception as exc:
            last_error = exc
            logger.warning("Image generation attempt %s failed: %s", attempt, exc)
            tmp.unlink(missing_ok=True)
            dest.unlink(missing_ok=True)
            time.sleep(min(4 * attempt, 12))
    if last_error:
        logger.warning("Image generation failed: %s", last_error)
    return None


def _pollinations(
    prompt: str,
    dest: Path,
    size: tuple[int, int],
    seed: int,
) -> Path | None:
    width, height = size
    encoded = quote(prompt, safe="")
    for model in ("flux", "turbo"):
        query = (
            f"width={width}&height={height}&model={model}&nologo=true"
            f"&enhance=false&private=true&safe=true&seed={seed}"
        )
        url = f"https://image.pollinations.ai/prompt/{encoded}?{query}"
        path = _save_url(url, dest, timeout=120.0)
        if path:
            return path
    return None


def _openai_image(prompt: str, dest: Path, size: tuple[int, int]) -> Path | None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
    except ImportError:
        return None
    width, height = size
    dalle = "1792x1024" if width >= height else "1024x1792"
    if abs(width - height) < 80:
        dalle = "1024x1024"
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    try:
        with httpx.Client(timeout=90.0) as client:
            resp = client.post(
                f"{base}/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": "dall-e-3", "prompt": prompt[:3800], "size": dalle, "n": 1},
            )
            resp.raise_for_status()
            url = resp.json()["data"][0]["url"]
        return _save_url(url, dest, timeout=60.0)
    except Exception as exc:
        logger.warning("OpenAI image generation failed: %s", exc)
        return None


def generate_still(
    dest: Path,
    topic: str,
    narration: str,
    shot_type: str = "medium",
    style: str = "animation",
    index: int = 0,
    variant: int = 0,
    resolution: tuple[int, int] = (1280, 720),
) -> Path | None:
    """Create one film still. Prefers OpenAI if keyed, otherwise Pollinations."""
    if os.environ.get("LERONX_SKIP_IMAGES"):
        return None
    if dest.exists() and _is_image(dest):
        return dest
    width = min(max(resolution[0], 640), 1280)
    height = min(max(resolution[1], 360), 720)
    prompt = visual_prompt(topic, narration, shot_type, style, variant)
    seed = _seed(topic, index, variant)
    if os.environ.get("OPENAI_API_KEY"):
        path = _openai_image(prompt, dest, (width, height))
        if path:
            return path
    return _pollinations(prompt, dest, (width, height), seed)
