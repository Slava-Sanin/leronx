"""Command-line interface: `leronx generate "topic"`."""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .env import load_dotenv
from .pipeline import Pipeline, PipelineConfig
from .render.ffmpeg_bin import find_ffmpeg
from .script.config import ScriptConfig, VideoFormat


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leronx",
        description="LeronX — generate a narrated video from a topic.",
    )
    parser.add_argument("--version", action="version", version=f"leronx {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="Generate a video from a topic")
    generate.add_argument("topic", help="What the video is about")
    generate.add_argument("-o", "--output", default="./output/video.mp4", help="Output MP4 path")
    generate.add_argument("-d", "--duration", type=int, default=45, help="Target length in seconds")
    generate.add_argument(
        "-t",
        "--tone",
        default="professional",
        choices=["professional", "casual", "educational", "dramatic", "humorous", "inspirational"],
    )
    generate.add_argument("-l", "--language", default="en", help="Spoken language code, e.g. en or ru")
    generate.add_argument(
        "--format",
        dest="video_format",
        default="landscape",
        choices=["landscape", "portrait", "square", "short"],
    )
    generate.add_argument("--fps", type=int, default=30)
    generate.add_argument("--codec", default="h264", choices=["h264", "h265", "vp9"])
    generate.add_argument("--gpu", action="store_true", help="Enable GPU hwaccel if available")
    generate.add_argument("--no-subs", action="store_true", help="Do not burn subtitles into the video")
    generate.add_argument("--voice", default=None, help="edge-tts voice name, e.g. ru-RU-DmitryNeural")
    generate.add_argument("--keep-work", action="store_true", help="Keep intermediate clips")
    generate.add_argument("-v", "--verbose", action="store_true")
    return parser


def _resolution_for(fmt: str) -> tuple[int, int]:
    return {
        "landscape": (1920, 1080),
        "portrait": (1080, 1920),
        "short": (1080, 1920),
        "square": (1080, 1080),
    }[fmt]


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.command != "generate":
        return 1

    try:
        from rich.console import Console

        console = Console()
    except ImportError:
        console = None

    def say(message: str) -> None:
        if console:
            console.print(message)
        else:
            print(message)

    if not find_ffmpeg():
        say(
            "[red]FFmpeg not found.[/red] Install it, or: pip install imageio-ffmpeg"
            if console
            else "FFmpeg not found. Install it, or: pip install imageio-ffmpeg"
        )
        return 2

    script_cfg = ScriptConfig(
        topic=args.topic,
        tone=args.tone,
        duration=args.duration,
        language=args.language,
        format=VideoFormat(args.video_format),
    )
    pipeline = Pipeline(
        PipelineConfig(
            script=script_cfg,
            gpu_enabled=args.gpu,
            codec=args.codec,
            resolution=_resolution_for(args.video_format),
            fps=args.fps,
            burn_subtitles=not args.no_subs,
            voice=args.voice,
            keep_work=args.keep_work,
        )
    )
    say(f"[bold]LeronX[/bold] · {args.topic}")
    try:
        result = pipeline.render(
            prompt=args.topic,
            output_path=Path(args.output),
            tone=args.tone,
            duration=args.duration,
            language=args.language,
        )
    except Exception as exc:
        say(f"[red]Render failed:[/red] {exc}" if console else f"Render failed: {exc}")
        logging.exception("Render failed")
        return 1

    say(f"[green]Video:[/green] {result.path.resolve()}")
    say(f"Duration: {result.duration:.1f}s · scenes: {len(result.scenes)} · render: {result.render_time:.1f}s")
    if result.subtitle_file:
        say(f"Subtitles: {result.subtitle_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
