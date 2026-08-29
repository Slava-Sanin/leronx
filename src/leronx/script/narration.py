"""Strip storyboard tags so TTS and subtitles get spoken text only."""
from __future__ import annotations
import re

_TAG = re.compile(r"^\s*\[[^\]]+\]\s*$")
_INLINE_SCENE = re.compile(r"\[Scene\s+\d+[^\]]*\]")
_INLINE_SECTION = re.compile(r"\[(?:HOOK|BODY|CTA)\]")


def extract_narration(script: str) -> str:
    """Return spoken lines from a tagged LeronX script."""
    if not script:
        return ""
    lines: list[str] = []
    for raw in script.splitlines():
        line = raw.strip()
        if not line or _TAG.match(line):
            continue
        line = _INLINE_SCENE.sub("", line)
        line = _INLINE_SECTION.sub("", line)
        line = line.strip()
        if line:
            lines.append(line)
    return " ".join(lines)


def extract_spoken_blocks(script: str) -> list[str]:
    """Return non-empty spoken paragraphs in order."""
    blocks: list[str] = []
    buf: list[str] = []
    for raw in script.splitlines():
        line = raw.strip()
        if _TAG.match(line) or not line:
            if buf:
                blocks.append(" ".join(buf))
                buf = []
            continue
        line = _INLINE_SCENE.sub("", line).strip()
        line = _INLINE_SECTION.sub("", line).strip()
        if line:
            buf.append(line)
    if buf:
        blocks.append(" ".join(buf))
    return blocks
