"""Path and temporary-file helpers with no exam policy."""

from __future__ import annotations

import tempfile
from pathlib import Path


def is_docx_name(name: str | None) -> bool:
    return bool(name) and Path(name).name.lower().endswith(".docx")


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def temporary_docx(data: bytes) -> Path:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    try:
        handle.write(data)
    finally:
        handle.close()
    return Path(handle.name)
