from pathlib import Path

from leronx import Pipeline, PipelineConfig
from leronx.script import ScriptConfig
from leronx.voice import VOICE_CATALOG, resolve_voice


TOPIC_FILE = Path("./topic.txt")
SCRIPT_FILE = Path("./script.txt")


def load_text(path: Path, *, required: bool) -> str:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"File not found: {path.resolve()}")
        return ""
    return path.read_text(encoding="utf-8").strip()


topic = load_text(TOPIC_FILE, required=True)
if not topic:
    raise ValueError(f"Topic file is empty: {TOPIC_FILE.resolve()}")

# Если script.txt заполнен — озвучивается он.
# Если пуст — сценарий генерируется по теме из topic.txt.
script = load_text(SCRIPT_FILE, required=False)

script_config = ScriptConfig(
    topic=topic,
    duration=45,
    tone="professional",
    language="en",
)

# Голос: короткое имя из каталога или полное edge-tts, например ru-RU-DmitryNeural.
# None — выбрать автоматически по language.
#   en: jenny, guy, aria, davis
#   ru: svetlana, dmitry
#   es: elvira, alvaro
#   de: katja, conrad
#   fr: denise, henri
VOICE = "jenny"

output_path = Path("./output/my_video.mp4")
voice_id = resolve_voice(VOICE, script_config.language)

pipeline = Pipeline(
    PipelineConfig(
        script=script_config,
        gpu_enabled=False,
        codec="h264",
        resolution=(1280, 720),
        fps=30,
        voice=voice_id,
    )
)

print(f"Topic:  {topic}")
print(f"Script: {SCRIPT_FILE.name} ({'custom' if script else 'generated from topic'})")
print(f"Voice:  {voice_id or 'auto'}  (options: {', '.join(VOICE_CATALOG)})")

video = pipeline.render(
    prompt=topic,
    script=script or None,
    output_path=output_path,
    tone=script_config.tone,
    duration=script_config.duration,
    language=script_config.language,
)

print(f"Video rendered: {video.path.resolve()}")
print(f"Duration: {video.duration:.1f}s")
print(f"Scenes: {len(video.scenes)}")
if video.subtitle_file:
    print(f"Subtitles: {video.subtitle_file}")
