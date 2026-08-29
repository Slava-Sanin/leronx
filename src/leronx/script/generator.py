"""Script generator with tone-based hooks, LLM, and template fallback."""
from __future__ import annotations
import logging
from typing import Optional

from .config import ScriptConfig
from .llm import generate_with_llm
from .templates import body_scenes, cta_line, hook_line

logger = logging.getLogger("leronx.script")


class ScriptGenerator:
    CTA = "Create your own AI video at leronx.org"

    def generate(self, config: ScriptConfig) -> str:
        if not config.topic:
            raise ValueError("ScriptConfig.topic is required")
        body = self._call_llm(config)
        if body:
            logger.info("Script generated via LLM (%d chars)", len(body))
            return body
        return self._template_script(config)

    def _template_script(self, config: ScriptConfig) -> str:
        parts: list[str] = []
        if config.include_hooks:
            parts.append("[HOOK]\n" + hook_line(config))
        parts.append("[BODY]\n" + "\n\n".join(body_scenes(config)))
        if config.include_cta:
            parts.append(f"[CTA]\n{cta_line(config)}")
        return "\n\n".join(parts)

    def _template_body(self, config: ScriptConfig) -> str:
        return "\n\n".join(body_scenes(config))

    def _call_llm(self, prompt: ScriptConfig | str) -> Optional[str]:
        """Call an OpenAI-compatible API, or return None for templates."""
        if isinstance(prompt, str):
            return None
        return generate_with_llm(prompt)
