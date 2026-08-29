"""
Render Engine — FFmpeg-based video rendering pipeline.

Builds one clip per scene, concatenates them, then mixes voice and subtitles.
"""
from __future__ import annotations
import logging
import subprocess
from pathlib import Path
from typing import Optional

from ..scenes.graph import Scene, SceneGraph
from .config import RenderConfig
from .ffmpeg_bin import ffmpeg_subtitles_path, find_ffmpeg, find_ffprobe

logger = logging.getLogger("leronx.render")

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class RenderEngine:
    def __init__(
        self,
        gpu: bool = True,
        codec: str = "h264",
        resolution: tuple[int, int] = (1920, 1080),
        fps: int = 30,
        config: RenderConfig | None = None,
    ):
        self.config = config or RenderConfig(gpu=gpu, codec=codec, resolution=resolution, fps=fps)
        self._ffmpeg = find_ffmpeg()
        if not self._ffmpeg:
            logger.warning("FFmpeg not found — rendering will be simulated")

    def render(
        self,
        graph: SceneGraph,
        voice_path: Path | None,
        output: Path,
        subtitle_path: Path | None = None,
        work_dir: Path | None = None,
    ) -> None:
        """Render a scene graph to a video file."""
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Rendering %d scenes → %s (%dx%d, %dfps, %s)",
            len(graph.scenes),
            output,
            *self.config.resolution,
            self.config.fps,
            self.config.codec,
        )
        if not self._ffmpeg:
            logger.warning("FFmpeg not installed — creating placeholder output")
            output.write_bytes(b"")
            return

        scratch = Path(work_dir) if work_dir else output.parent / f".leronx_{output.stem}"
        scratch.mkdir(parents=True, exist_ok=True)
        clips = self._render_scenes(graph, scratch)
        if not clips:
            raise RuntimeError("No scene clips were produced")
        silent = scratch / "video_silent.mp4"
        self._concat(clips, silent)
        self._mux(silent, voice_path, subtitle_path, output)
        if output.exists():
            logger.info("Render complete: %s (%.1f MB)", output, output.stat().st_size / 1e6)

    def _render_scenes(self, graph: SceneGraph, scratch: Path) -> list[Path]:
        clips: list[Path] = []
        scenes = graph.scenes or [Scene(index=0, start_time=0, end_time=graph.total_duration or 5)]
        for scene in scenes:
            clip = scratch / f"scene_{scene.index:03d}.mp4"
            self._render_scene(scene, clip)
            clips.append(clip)
        return clips

    def _image_assets(self, scene: Scene) -> list[Path]:
        found: list[Path] = []
        for item in scene.assets:
            path = Path(item)
            if path.exists() and path.suffix.lower() in _IMAGE_SUFFIXES:
                found.append(path)
        return found

    def _ken_burns(self, duration: float, move: int, shot: str) -> str:
        width, height = self.config.resolution
        fps = self.config.fps
        frames = max(int(duration * fps), 1)
        fade = min(0.28, duration / 5)
        fade_out = max(duration - fade, 0.0)
        if shot == "wide" or move % 3 == 1:
            zoom = "if(eq(on,1),1.16,max(zoom-0.0014,1.0))"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)-on*0.15"
        elif shot == "closeup" or move % 3 == 2:
            zoom = "min(zoom+0.0018,1.22)"
            x = "iw/2-(iw/zoom/2)+on*0.35"
            y = "ih/2-(ih/zoom/2)"
        else:
            zoom = "min(zoom+0.0013,1.14)"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)+on*0.2"
        return (
            f"zoompan=z='{zoom}':d={frames}:x='{x}':y='{y}':s={width}x{height}:fps={fps},"
            f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={fade_out:.3f}:d={fade:.3f},"
            f"format=yuv420p"
        )

    def _render_image_clip(self, source: Path, dest: Path, duration: float, move: int, shot: str) -> None:
        cmd = [
            self._ffmpeg, "-y", "-loop", "1", "-i", str(source),
            "-vf", self._ken_burns(duration, move, shot),
            "-t", f"{duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-an", str(dest),
        ]
        self._run(cmd, f"still {dest.stem}")

    def _render_scene(self, scene: Scene, clip: Path) -> None:
        width, height = self.config.resolution
        fps = self.config.fps
        duration = max(float(scene.duration or 0), 0.5)
        fade = min(0.35, duration / 4)
        fade_out_start = max(duration - fade, 0.0)
        images = self._image_assets(scene)
        source = Path(scene.assets[0]) if scene.assets else None

        if len(images) > 1:
            parts: list[Path] = []
            each = duration / len(images)
            for offset, image in enumerate(images):
                part = clip.with_name(f"{clip.stem}_shot{offset}.mp4")
                self._render_image_clip(image, part, each, offset, scene.shot_type)
                parts.append(part)
            self._concat(parts, clip)
            return

        if images:
            self._render_image_clip(images[0], clip, duration, scene.index, scene.shot_type)
            return

        if source and source.exists():
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},fps={fps},"
                f"fade=t=in:st=0:d={fade:.3f},fade=t=out:st={fade_out_start:.3f}:d={fade:.3f},"
                f"format=yuv420p"
            )
            cmd = [
                self._ffmpeg, "-y", "-stream_loop", "-1", "-i", str(source),
                "-vf", vf, "-t", f"{duration:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-an", str(clip),
            ]
        else:
            cmd = [
                self._ffmpeg, "-y", "-f", "lavfi",
                "-i", f"color=c=0x0b1220:s={width}x{height}:r={fps}:d={duration:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                "-an", str(clip),
            ]
        self._run(cmd, f"scene {scene.index}")

    def _concat(self, clips: list[Path], output: Path) -> None:
        listing = output.with_suffix(".txt")
        lines = []
        for clip in clips:
            posix = clip.resolve().as_posix().replace("'", r"'\''")
            lines.append(f"file '{posix}'")
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        copy_cmd = [
            self._ffmpeg, "-y", "-f", "concat", "-safe", "0",
            "-i", str(listing), "-c", "copy", str(output),
        ]
        try:
            self._run(copy_cmd, "concat")
            return
        except RuntimeError:
            logger.warning("Stream copy concat failed — re-encoding")
        encode_cmd = [
            self._ffmpeg, "-y", "-f", "concat", "-safe", "0",
            "-i", str(listing),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-an", str(output),
        ]
        self._run(encode_cmd, "concat-reencode")

    def _mux(
        self,
        video: Path,
        voice_path: Path | None,
        subtitle_path: Path | None,
        output: Path,
    ) -> None:
        cmd = [self._ffmpeg, "-y", "-i", str(video)]
        has_audio = bool(voice_path and Path(voice_path).exists())
        if has_audio:
            cmd.extend(["-i", str(voice_path)])

        filters: list[str] = ["eq=contrast=1.04:saturation=1.06"]
        if subtitle_path and Path(subtitle_path).exists():
            escaped = ffmpeg_subtitles_path(Path(subtitle_path))
            if Path(subtitle_path).suffix.lower() == ".ass":
                filters.append(f"ass='{escaped}'")
            else:
                filters.append(f"subtitles='{escaped}'")
        cmd.extend(["-vf", ",".join(filters)])
        cmd.extend(
            [
                "-c:v", self.config.get_ffmpeg_codec(),
                "-preset", self.config.preset,
                "-b:v", self.config.bitrate,
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
            ]
        )
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.append("-an")
        cmd.append(str(output))
        try:
            self._run(cmd, "mux")
        except RuntimeError:
            if subtitle_path:
                logger.warning("Subtitle burn-in failed — exporting without burned captions")
                self._mux(video, voice_path, None, output)
                return
            raise

    def _run(self, cmd: list[str], label: str) -> None:
        logger.debug("FFmpeg %s: %s", label, " ".join(cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out during %s", label)
            raise
        if result.returncode != 0:
            tail = (result.stderr or "")[-800:]
            logger.error("FFmpeg %s failed: %s", label, tail)
            raise RuntimeError(f"FFmpeg {label} failed: {result.returncode}")

    def _build_ffmpeg_cmd(
        self,
        graph: SceneGraph,
        voice_path: Path | None,
        output: Path,
    ) -> list[str]:
        """Kept for tests and simple color-bar fallback."""
        cmd = [self._ffmpeg or "ffmpeg", "-y"]
        cmd.extend(self.config.get_hwaccel_flags())
        width, height = self.config.resolution
        cmd.extend(
            [
                "-f", "lavfi",
                "-i", f"color=c=black:s={width}x{height}:r={self.config.fps}",
            ]
        )
        if voice_path and Path(voice_path).exists():
            cmd.extend(["-i", str(voice_path)])
        duration = graph.total_duration or 60.0
        cmd.extend(
            [
                "-t", str(duration),
                "-c:v", self.config.get_ffmpeg_codec(),
                "-preset", self.config.preset,
                "-b:v", self.config.bitrate,
                "-pix_fmt", "yuv420p",
            ]
        )
        if voice_path and Path(voice_path).exists():
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        cmd.append(str(output))
        return cmd

    def probe(self, video_path: Path) -> dict:
        """Get video metadata using ffprobe."""
        ffprobe = find_ffprobe()
        if not ffprobe:
            return {}
        try:
            result = subprocess.run(
                [
                    ffprobe, "-v", "quiet", "-print_format", "json",
                    "-show_format", "-show_streams", str(video_path),
                ],
                capture_output=True,
                text=True,
            )
            import json

            return json.loads(result.stdout) if result.returncode == 0 else {}
        except Exception:
            return {}
