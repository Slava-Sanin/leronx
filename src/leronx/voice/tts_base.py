"""TTS abstraction layer — Edge, espeak, macOS say, and a silent fallback."""
from __future__ import annotations
import asyncio
import logging
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

logger = logging.getLogger("leronx.voice")

EDGE_VOICES = {
    "en": "en-US-JennyNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "es": "es-ES-ElviraNeural",
    "de": "de-DE-KatjaNeural",
    "fr": "fr-FR-DeniseNeural",
    "it": "it-IT-ElsaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ko": "ko-KR-SunHiNeural",
    "ar": "ar-SA-ZariyahNeural",
    "hi": "hi-IN-SwaraNeural",
    "uk": "uk-UA-PolinaNeural",
    "pl": "pl-PL-ZofiaNeural",
}

# Short names for run_video.py / CLI. Values are edge-tts neural voices.
VOICE_CATALOG = {
    "jenny": "en-US-JennyNeural",
    "guy": "en-US-GuyNeural",
    "aria": "en-US-AriaNeural",
    "davis": "en-US-DavisNeural",
    "svetlana": "ru-RU-SvetlanaNeural",
    "dmitry": "ru-RU-DmitryNeural",
    "elvira": "es-ES-ElviraNeural",
    "alvaro": "es-ES-AlvaroNeural",
    "katja": "de-DE-KatjaNeural",
    "conrad": "de-DE-ConradNeural",
    "denise": "fr-FR-DeniseNeural",
    "henri": "fr-FR-HenriNeural",
}


def resolve_voice(name: str | None, language: str = "en") -> str | None:
    """Map a short catalog key or a full edge-tts name to a voice id."""
    if not name:
        return None
    key = name.strip()
    if not key:
        return None
    return VOICE_CATALOG.get(key.lower(), key)


def _rate_percent(speed: float) -> str:
    delta = int(round((speed - 1.0) * 100))
    return f"{delta:+d}%"


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class TTSEngine(ABC):
    """Abstract TTS engine. Override synthesize() for custom providers."""

    @abstractmethod
    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        ...

    @classmethod
    def create_default(
        cls,
        language: str = "en",
        voice: str | None = None,
        speed: float = 1.0,
    ) -> "TTSEngine":
        """Auto-detect the best available TTS engine."""
        try:
            import edge_tts  # noqa: F401

            return EdgeTTS(language=language, voice=voice, speed=speed)
        except ImportError:
            logger.info("edge-tts is not installed")
        if shutil.which("espeak"):
            return EspeakTTS()
        if shutil.which("say"):
            return MacSayTTS()
        logger.warning("No TTS engine found. Install edge-tts: pip install edge-tts")
        return DummyTTS()


class EdgeTTS(TTSEngine):
    """Microsoft Edge neural voices via the edge-tts package."""

    def __init__(
        self,
        language: str = "en",
        voice: str | None = None,
        speed: float = 1.0,
    ):
        lang = (language or "en").lower()[:2]
        self.voice = resolve_voice(voice, language) or EDGE_VOICES.get(lang, EDGE_VOICES["en"])
        self.rate = _rate_percent(speed)

    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        spoken = (text or "").strip()
        if not spoken:
            return None
        out = output_path or Path(tempfile.gettempdir()) / "leronx_tts.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)

        async def _save() -> None:
            import edge_tts

            comm = edge_tts.Communicate(spoken, self.voice, rate=self.rate)
            await comm.save(str(out))

        try:
            _run_async(_save())
        except Exception as exc:
            logger.error("edge-tts failed: %s", exc)
            return None
        return out if out.exists() and out.stat().st_size > 0 else None


class EspeakTTS(TTSEngine):
    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        out = output_path or Path(tempfile.gettempdir()) / "leronx_tts.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["espeak", "-w", str(out), text[:2000]],
                check=True,
                capture_output=True,
            )
            return out
        except Exception as exc:
            logger.error("espeak failed: %s", exc)
            return None


class MacSayTTS(TTSEngine):
    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        out = output_path or Path(tempfile.gettempdir()) / "leronx_tts.aiff"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["say", "-o", str(out), text[:2000]],
                check=True,
                capture_output=True,
            )
            return out
        except Exception as exc:
            logger.error("macOS say failed: %s", exc)
            return None


class DummyTTS(TTSEngine):
    def synthesize(self, text: str, output_path: Path | None = None) -> Path | None:
        logger.info("DummyTTS: would synthesize %d chars", len(text))
        return None
