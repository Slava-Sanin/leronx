"""Optional OpenAI-compatible script writer. Falls back silently if unset."""
from __future__ import annotations
import logging
import os
from typing import Optional

from .config import ScriptConfig

logger = logging.getLogger("leronx.script.llm")

SYSTEM = (
    "You write spoken narration for short explainer videos. "
    "Return ONLY this exact structure, no markdown:\n"
    "[HOOK]\n"
    "one spoken sentence\n\n"
    "[BODY]\n"
    "[Scene 1: 0s-10s]\n"
    "two or three spoken sentences\n\n"
    "[Scene 2: 10s-20s]\n"
    "two or three spoken sentences\n\n"
    "[CTA]\n"
    "one short spoken call to action\n"
    "Do not write camera notes, shot lists, or brackets except those tags."
)


def generate_with_llm(config: ScriptConfig) -> Optional[str]:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LERONX_LLM_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
    except ImportError:
        logger.warning("httpx is required for LLM script generation")
        return None

    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LERONX_LLM_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    words = config.max_words or int((config.duration / 60) * 150)
    tone = config.tone.value if hasattr(config.tone, "value") else str(config.tone)
    user = (
        f"Topic: {config.topic}\n"
        f"Language: {config.language}\n"
        f"Tone: {tone}\n"
        f"Duration: {config.duration} seconds\n"
        f"Target spoken words: {words}\n"
        f"Audience: {config.target_audience or 'general'}\n"
        f"Keywords: {', '.join(config.keywords) or 'none'}\n"
        "Write enough scenes to fill the duration. Each scene is spoken aloud."
    )
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": min(max(config.creativity, 0.1), 1.2),
                    "messages": [
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            if "[BODY]" not in text:
                logger.warning("LLM response missing [BODY] — using templates")
                return None
            return text
    except Exception as exc:
        logger.warning("LLM script generation failed: %s", exc)
        return None
