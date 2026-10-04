"""Subject-neutral Word file helpers.

Opening and saving a DOCX lives here. Reading exam structure does not.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document


def load_document(path: str | Path):
    return Document(str(path))


def save_document(document, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(target))
    return target


def readable_docx(path: str | Path) -> tuple[bool, str]:
    try:
        load_document(path)
    except Exception as exc:
        return False, str(exc)
    return True, ""
