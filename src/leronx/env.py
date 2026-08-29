"""Load a local .env without adding a dependency."""
from __future__ import annotations
import os
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    candidate = Path(path) if path else Path.cwd() / ".env"
    if not candidate.exists():
        return
    for raw in candidate.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
