"""Text-to-video clips for scenes: Pollinations, Luma, Replicate, Runway."""
from __future__ import annotations
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

from .imagine import visual_prompt

logger = logging.getLogger("leronx.assets")

def motion_prompt(
    topic: str,
    narration: str,
    shot_type: str = "medium",
    style: str = "animation",
) -> str:
    still = visual_prompt(topic, narration, shot_type, style)
    return (
        f"{still}. "
        "Animated movie shot with visible character motion, cloth and hair movement, "
        "parallax background, slow cinematic camera, continuous action, "
        "no jump cuts, no text on screen"
    )


def _is_video(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 20_000:
        return False
    head = path.read_bytes()[:32]
    return b"ftyp" in head


def _headers(accept: str) -> dict[str, str]:
    headers = {"User-Agent": "LeronX/1.1", "Accept": accept}
    token = os.environ.get("POLLINATIONS_API_KEY") or os.environ.get("POLLINATIONS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _download(url: str, dest: Path, headers: dict[str, str], timeout: float) -> Path | None:
    try:
        import httpx
    except ImportError:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            with client.stream("GET", url, headers=headers) as response:
                if response.status_code == 429:
                    return None
                response.raise_for_status()
                with tmp.open("wb") as handle:
                    for chunk in response.iter_bytes(64 * 1024):
                        handle.write(chunk)
        tmp.replace(dest)
        if not _is_video(dest):
            dest.unlink(missing_ok=True)
            return None
        logger.info("Video clip %s (%.1f MB)", dest.name, dest.stat().st_size / 1e6)
        return dest
    except Exception as exc:
        logger.warning("Video download failed: %s", exc)
        tmp.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        return None


def _aspect(resolution: tuple[int, int]) -> str:
    return "9:16" if resolution[1] > resolution[0] else "16:9"


def _clip_seconds(duration: float) -> int:
    return max(4, min(8, int(round(duration or 5))))


def _pollinations_video(prompt: str, dest: Path, seconds: int, aspect: str) -> Path | None:
    try:
        import httpx
    except ImportError:
        return None
    models = [
        os.environ.get("LERONX_VIDEO_MODEL", "").strip(),
        "wan-fast",
        "p-video",
        "wan",
    ]
    seen: set[str] = set()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    encoded = quote(prompt, safe="")
    for model in models:
        if not model or model in seen:
            continue
        seen.add(model)
        url = (
            f"https://gen.pollinations.ai/video/{encoded}"
            f"?model={model}&duration={seconds}&aspectRatio={aspect}&audio=false"
        )
        logger.info("Requesting %s clip (%ss, %s)", model, seconds, aspect)
        try:
            with httpx.Client(follow_redirects=True, timeout=300.0) as client:
                with client.stream("GET", url, headers=_headers("video/mp4,application/octet-stream")) as response:
                    if response.status_code in {401, 402, 403}:
                        logger.warning("Pollinations video needs a key/credits (%s)", response.status_code)
                        return None
                    if response.status_code == 429:
                        logger.info("Video API rate-limited on %s", model)
                        time.sleep(10)
                        continue
                    response.raise_for_status()
                    ctype = response.headers.get("content-type", "")
                    if "json" in ctype or "text/html" in ctype:
                        logger.warning("Pollinations video returned %s for %s", ctype, model)
                        continue
                    with tmp.open("wb") as handle:
                        for chunk in response.iter_bytes(64 * 1024):
                            handle.write(chunk)
            tmp.replace(dest)
            if _is_video(dest):
                logger.info("Pollinations/%s → %s", model, dest.name)
                return dest
            dest.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("Pollinations video %s failed: %s", model, exc)
            tmp.unlink(missing_ok=True)
            dest.unlink(missing_ok=True)
    return None


def _luma_video(prompt: str, dest: Path, seconds: int, aspect: str) -> Path | None:
    key = os.environ.get("LUMA_API_KEY") or os.environ.get("LUMA_API_TOKEN")
    if not key:
        return None
    try:
        import httpx
    except ImportError:
        return None
    duration = "9s" if seconds >= 8 else "5s"
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=60.0) as client:
            created = client.post(
                "https://api.lumalabs.ai/dream-machine/v1/generations",
                headers=headers,
                json={
                    "prompt": prompt[:2000],
                    "model": os.environ.get("LUMA_MODEL", "ray-2-flash"),
                    "resolution": "720p",
                    "duration": duration,
                    "aspect_ratio": aspect,
                },
            )
            if created.status_code == 429:
                logger.info("Luma rate-limited")
                return None
            if created.status_code >= 400:
                logger.warning("Luma rejected the job: %s", created.text[:300])
                return None
            payload = created.json()
            job_id = payload.get("id")
            if not job_id:
                return None
            for _ in range(40):
                time.sleep(6)
                poll = client.get(
                    f"https://api.lumalabs.ai/dream-machine/v1/generations/{job_id}",
                    headers=headers,
                )
                if poll.status_code != 200:
                    continue
                body = poll.json()
                state = (body.get("state") or "").lower()
                if state in {"failed", "error"}:
                    logger.warning("Luma job failed: %s", body)
                    return None
                url = ((body.get("assets") or {}).get("video")) or ""
                if state == "completed" and url:
                    return _download(url, dest, {"User-Agent": "LeronX/1.1"}, 90.0)
    except Exception as exc:
        logger.warning("Luma video failed: %s", exc)
        dest.unlink(missing_ok=True)
    return None


def _replicate_video(prompt: str, dest: Path, seconds: int, aspect: str) -> Path | None:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        return None
    try:
        import httpx
    except ImportError:
        return None
    model = os.environ.get("REPLICATE_VIDEO_MODEL", "wan-video/wan-2.2-t2v-fast")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait=60",
    }
    try:
        with httpx.Client(timeout=90.0) as client:
            created = client.post(
                f"https://api.replicate.com/v1/models/{model}/predictions",
                headers=headers,
                json={"input": {"prompt": prompt[:2000], "aspect_ratio": aspect, "duration": seconds}},
            )
            if created.status_code == 429:
                logger.info("Replicate rate-limited")
                return None
            if created.status_code >= 400:
                logger.warning("Replicate rejected the job: %s", created.text[:300])
                return None
            body = created.json()
            get_url = (body.get("urls") or {}).get("get")
            for _ in range(36):
                status = body.get("status")
                if status == "succeeded":
                    output = body.get("output")
                    url = output[0] if isinstance(output, list) and output else output
                    if isinstance(url, str) and url.startswith("http"):
                        return _download(url, dest, {"User-Agent": "LeronX/1.1"}, 90.0)
                    return None
                if status in {"failed", "canceled"}:
                    logger.warning("Replicate job %s", status)
                    return None
                if not get_url:
                    return None
                time.sleep(5)
                poll = client.get(get_url, headers={"Authorization": f"Bearer {token}"})
                if poll.status_code == 200:
                    body = poll.json()
    except Exception as exc:
        logger.warning("Replicate video failed: %s", exc)
        dest.unlink(missing_ok=True)
    return None


def _runway_video(prompt: str, dest: Path, seconds: int, aspect: str) -> Path | None:
    key = os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY")
    if not key:
        return None
    try:
        import httpx
    except ImportError:
        return None
    ratio = "1280:720" if aspect == "16:9" else "720:1280"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            created = client.post(
                "https://api.dev.runwayml.com/v1/text_to_video",
                headers=headers,
                json={
                    "model": os.environ.get("RUNWAY_MODEL", "gen3a_turbo"),
                    "promptText": prompt[:1000],
                    "duration": 5 if seconds < 8 else 10,
                    "ratio": ratio,
                },
            )
            if created.status_code == 429:
                return None
            if created.status_code >= 400:
                logger.warning("Runway rejected the job: %s", created.text[:300])
                return None
            task_id = created.json().get("id")
            if not task_id:
                return None
            for _ in range(40):
                time.sleep(6)
                poll = client.get(f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers)
                if poll.status_code != 200:
                    continue
                body = poll.json()
                status = (body.get("status") or "").upper()
                if status in {"FAILED", "CANCELLED"}:
                    return None
                if status == "SUCCEEDED":
                    output = body.get("output") or []
                    url = output[0] if output else ""
                    if url:
                        return _download(url, dest, {"User-Agent": "LeronX/1.1"}, 90.0)
                    return None
    except Exception as exc:
        logger.warning("Runway video failed: %s", exc)
        dest.unlink(missing_ok=True)
    return None


def _provider_order() -> list[str]:
    forced = (os.environ.get("LERONX_VIDEO_PROVIDER") or "auto").strip().lower()
    if forced != "auto":
        return [forced]
    order = []
    if os.environ.get("LUMA_API_KEY") or os.environ.get("LUMA_API_TOKEN"):
        order.append("luma")
    if os.environ.get("RUNWAYML_API_SECRET") or os.environ.get("RUNWAY_API_KEY"):
        order.append("runway")
    if os.environ.get("REPLICATE_API_TOKEN"):
        order.append("replicate")
    order.append("pollinations")
    return order


def generate_clip(
    dest: Path,
    topic: str,
    narration: str,
    shot_type: str = "medium",
    style: str = "animation",
    duration: float = 5.0,
    resolution: tuple[int, int] = (1280, 720),
) -> Path | None:
    """Generate one animated shot. Returns an mp4 or None."""
    if os.environ.get("LERONX_SKIP_VIDEO"):
        return None
    dest = Path(dest)
    if _is_video(dest):
        return dest
    prompt = motion_prompt(topic, narration, shot_type, style)
    seconds = _clip_seconds(duration)
    aspect = _aspect(resolution)
    providers = {
        "pollinations": lambda: _pollinations_video(prompt, dest, seconds, aspect),
        "luma": lambda: _luma_video(prompt, dest, seconds, aspect),
        "replicate": lambda: _replicate_video(prompt, dest, seconds, aspect),
        "runway": lambda: _runway_video(prompt, dest, seconds, aspect),
    }
    for name in _provider_order():
        factory = providers.get(name)
        if not factory:
            continue
        logger.info("Animating scene with %s", name)
        path = factory()
        if path:
            return path
    return None
