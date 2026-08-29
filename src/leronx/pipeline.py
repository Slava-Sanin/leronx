"""
Pipeline Orchestrator — core video generation flow.
"""
from __future__ import annotations
import logging
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .assets.matcher import AssetMatcher
from .env import load_dotenv
from .plugins.base import Plugin
from .plugins.registry import PluginRegistry
from .render.ffmpeg_bin import find_ffmpeg, probe_duration
from .scenes.composition import CompositionPlanner
from .scenes.graph import SceneGraph
from .script.config import ScriptConfig, Tone, VideoFormat
from .script.generator import ScriptGenerator
from .script.narration import extract_narration
from .subtitles.generator import SubtitleGenerator
from .voice.emotions import EmotionMapper
from .voice.tts_base import TTSEngine

logger = logging.getLogger("leronx.pipeline")

FORMAT_SIZE = {
    VideoFormat.LANDSCAPE: (1920, 1080),
    VideoFormat.SHORT: (1080, 1920),
    VideoFormat.PORTRAIT: (1080, 1920),
    VideoFormat.SQUARE: (1080, 1080),
}


def _default_work_dir() -> Path:
    return Path(tempfile.gettempdir()) / "leronx"


@dataclass
class PipelineConfig:
    script: ScriptConfig = field(default_factory=ScriptConfig)
    gpu_enabled: bool = False
    codec: str = "h264"
    output_format: str = "mp4"
    resolution: tuple[int, int] = (1920, 1080)
    fps: int = 30
    plugins: list[Plugin] = field(default_factory=list)
    work_dir: Path = field(default_factory=_default_work_dir)
    burn_subtitles: bool = True
    voice: Optional[str] = None
    keep_work: bool = False
    visual_style: str = "animation"
    generate_motion: bool = True


@dataclass
class PipelineResult:
    path: Path
    duration: float
    scenes: list[dict[str, Any]]
    script: str
    voice_track: Optional[Path] = None
    subtitle_file: Optional[Path] = None
    render_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class Pipeline:
    def __init__(self, config: PipelineConfig | ScriptConfig | None = None):
        load_dotenv()
        if config is None:
            config = PipelineConfig()
        elif isinstance(config, ScriptConfig):
            config = PipelineConfig(script=config)
            self._apply_format(config)
        self.config = config
        self.registry = PluginRegistry()
        for plugin in config.plugins:
            self.registry.register(plugin)
        self._script_gen = ScriptGenerator()
        self._scene_planner = CompositionPlanner()
        self._assets = AssetMatcher()
        logger.info(
            "Pipeline initialized (gpu=%s, codec=%s, plugins=%d)",
            config.gpu_enabled,
            config.codec,
            len(config.plugins),
        )

    def _apply_format(self, config: PipelineConfig) -> None:
        fmt = config.script.format
        if isinstance(fmt, str):
            fmt = VideoFormat(fmt)
        size = FORMAT_SIZE.get(fmt)
        if size:
            config.resolution = size

    def generate_script(
        self,
        prompt: str,
        *,
        tone: str = "professional",
        duration: int = 60,
        language: str = "en",
    ) -> str:
        config = ScriptConfig(topic=prompt, tone=tone, duration=duration, language=language)
        return self._script_gen.generate(config)

    def plan_scenes(self, script: str, target_duration: int | None = None) -> SceneGraph:
        duration = target_duration if target_duration is not None else self.config.script.duration
        return self._scene_planner.plan(script, target_duration=duration)

    def render(
        self,
        prompt: Optional[str] = None,
        *,
        script: Optional[str] = None,
        output_path: str | Path = "./output.mp4",
        tone: str | Tone | None = None,
        duration: int | None = None,
        language: str | None = None,
        burn_subtitles: bool | None = None,
    ) -> PipelineResult:
        if prompt is None and script is None:
            raise ValueError("Either 'prompt' or 'script' must be provided")
        start_time = time.monotonic()
        cfg = self.config.script
        tone_value = tone or (cfg.tone.value if isinstance(cfg.tone, Tone) else cfg.tone)
        duration_value = duration or cfg.duration
        language_value = language or cfg.language
        burn = self.config.burn_subtitles if burn_subtitles is None else burn_subtitles

        job_dir = Path(self.config.work_dir) / f"job_{uuid.uuid4().hex[:8]}"
        job_dir.mkdir(parents=True, exist_ok=True)

        if script is None:
            script = self.generate_script(
                prompt,
                tone=str(tone_value),
                duration=int(duration_value),
                language=language_value,
            )
        script = self.registry.run_stage("pre_scene", script, self.config)
        graph = self.plan_scenes(script, target_duration=int(duration_value))
        graph = self.registry.run_stage("pre_voice", graph, self.config)

        narration = extract_narration(script)
        voice_path = self._synthesize_voice(narration, language_value, job_dir)
        graph = self._align_to_voice(graph, voice_path)
        graph = self._assets.enrich_graph(
            graph,
            job_dir,
            resolution=self.config.resolution,
            topic=prompt or cfg.topic,
            visual_style=self.config.visual_style,
            generate_motion=self.config.generate_motion,
        )
        graph = self.registry.run_stage("pre_render", graph, self.config)

        subtitle_path = self._write_subtitles(narration, graph.total_duration, job_dir)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._render_video(graph, voice_path, output, subtitle_path if burn else None, job_dir)
        render_time = time.monotonic() - start_time
        post_ctx = {"video_path": output, "graph": graph, "config": self.config}
        self.registry.run_stage("post_render", post_ctx, self.config)
        if not self.config.keep_work:
            # Keep voice + subs next to the video; drop bulky scene clips.
            pass
        sidecar = None
        if subtitle_path and subtitle_path.exists():
            sidecar = output.with_suffix(".srt")
            if subtitle_path.suffix == ".srt":
                sidecar.write_text(subtitle_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                sidecar = subtitle_path
        return PipelineResult(
            path=output,
            duration=graph.total_duration,
            scenes=[scene.to_dict() for scene in graph.scenes],
            script=script,
            voice_track=voice_path,
            subtitle_file=sidecar,
            render_time=render_time,
            metadata={"work_dir": str(job_dir), "narration": narration},
        )

    def _synthesize_voice(self, script: str, language: str, job_dir: Path) -> Path | None:
        try:
            tone = self.config.script.tone
            tone_name = tone.value if isinstance(tone, Tone) else str(tone)
            profile = EmotionMapper().map_tone(tone_name)
            engine = TTSEngine.create_default(
                language=language,
                voice=self.config.voice,
                speed=profile.speed,
            )
            dest = job_dir / "voice.mp3"
            return engine.synthesize(script, dest)
        except Exception as exc:
            logger.warning("Voice synthesis skipped: %s", exc)
            return None

    def _align_to_voice(self, graph: SceneGraph, voice_path: Path | None) -> SceneGraph:
        if not voice_path or not graph.scenes or graph.total_duration <= 0:
            return graph
        audio_dur = probe_duration(voice_path)
        if not audio_dur or audio_dur < 0.5:
            return graph
        scale = audio_dur / graph.total_duration
        cursor = 0.0
        for scene in graph.scenes:
            length = max(scene.duration * scale, 0.5)
            scene.start_time = cursor
            scene.end_time = cursor + length
            cursor += length
        graph.total_duration = cursor
        logger.info("Aligned %d scenes to voice (%.1fs)", len(graph.scenes), cursor)
        return graph

    def _write_subtitles(self, narration: str, duration: float, job_dir: Path) -> Path | None:
        try:
            dest = job_dir / "captions.srt"
            return SubtitleGenerator().generate(narration, duration or 60.0, dest, fmt="srt")
        except Exception as exc:
            logger.warning("Subtitle generation skipped: %s", exc)
            return None

    def _render_video(
        self,
        graph: SceneGraph,
        voice_path: Path | None,
        output: Path,
        subtitle_path: Path | None = None,
        work_dir: Path | None = None,
    ) -> None:
        from .render.engine import RenderEngine

        if not find_ffmpeg():
            logger.warning("FFmpeg missing — install ffmpeg or imageio-ffmpeg")
        engine = RenderEngine(
            gpu=self.config.gpu_enabled,
            codec=self.config.codec,
            resolution=self.config.resolution,
            fps=self.config.fps,
        )
        engine.render(graph, voice_path, output, subtitle_path=subtitle_path, work_dir=work_dir)
