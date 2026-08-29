from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from leronx import Pipeline, PipelineConfig
from leronx.script import ScriptConfig
from leronx.voice import VOICE_CATALOG, resolve_voice
from leronx.voice.tts_base import EDGE_VOICES

ROOT = Path(__file__).resolve().parent
TOPIC_FILE = ROOT / "topic.txt"
SCRIPT_FILE = ROOT / "script.txt"
OUTPUT_PATH = ROOT / "output" / "video.mp4"

# None — голос по языку текста. Или ключ каталога: jenny, guy, svetlana, dmitry.
VOICE: str | None = None
TONE = "professional"
DURATION = 45


def load_text(path: Path, *, required: bool) -> str:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"File not found: {path.resolve()}")
        return ""
    return path.read_text(encoding="utf-8").strip()


def detect_language(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "en"
    cyrillic = sum(1 for char in letters if re.match(r"[а-яёА-ЯЁ]", char))
    return "ru" if cyrillic / len(letters) >= 0.25 else "en"


def estimate_duration(script: str, fallback: int) -> int:
    if not script:
        return fallback
    words = len(script.split())
    return max(15, min(180, round(words / 2.3)))


def pick_voice(name: str | None, language: str) -> str:
    resolved = resolve_voice(name, language)
    if resolved:
        return resolved
    return EDGE_VOICES.get(language[:2], EDGE_VOICES["en"])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    topic = load_text(TOPIC_FILE, required=True)
    if not topic:
        raise ValueError(f"Topic file is empty: {TOPIC_FILE.resolve()}")
    script = load_text(SCRIPT_FILE, required=False)
    language = detect_language(f"{topic}\n{script}")
    duration = estimate_duration(script, DURATION)
    voice_id = pick_voice(VOICE, language)

    print(f"Topic:    {topic}")
    print(f"Script:   {SCRIPT_FILE.name} ({'custom' if script else 'generated from topic'})")
    print(f"Language: {language}")
    print(f"Voice:    {voice_id}")
    print(f"Duration: {duration}s")
    print(f"Output:   {OUTPUT_PATH}")

    pipeline = Pipeline(
        PipelineConfig(
            script=ScriptConfig(
                topic=topic,
                duration=duration,
                tone=TONE,
                language=language,
            ),
            gpu_enabled=False,
            codec="h264",
            resolution=(1280, 720),
            fps=30,
            voice=voice_id,
        )
    )
    video = pipeline.render(
        prompt=topic,
        script=script or None,
        output_path=OUTPUT_PATH,
        tone=TONE,
        duration=duration,
        language=language,
    )
    print(f"Video:    {video.path.resolve()}")
    print(f"Ready:    {video.duration:.1f}s, {len(video.scenes)} scenes, {video.render_time:.1f}s render")
    if video.subtitle_file:
        print(f"Subs:     {video.subtitle_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Launch failed: {exc}", file=sys.stderr)
        raise
