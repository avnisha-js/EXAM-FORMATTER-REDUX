"""One active reference for each grade and subject.

Lookup uses the normalized grade and subject, not the original filename.
"""

from __future__ import annotations

import json
from pathlib import Path

from common.files import ensure_dir
from common.hashing import sha256_bytes, sha256_file
from app.routing import display_pair, normalize


class ReferenceRegistry:
    def __init__(self, data_root: str | Path):
        self.root = Path(data_root)
        self.directory = ensure_dir(self.root / "references")
        self.files = ensure_dir(self.directory / "files")
        self.catalog_path = self.directory / "registry.json"

    def rows(self) -> list[dict]:
        if not self.catalog_path.is_file():
            return []
        try:
            data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def find(self, grade: str, subject: str) -> dict | None:
        grade_key, subject_key = normalize(grade, subject)
        for row in self.rows():
            if row.get("grade_key") == grade_key and row.get("subject_key") == subject_key:
                return row
        return None

    def file_path(self, row: dict) -> Path:
        return self.root / row["stored_path"]

    def install(
        self,
        grade: str,
        subject: str,
        filename: str,
        source: str | Path,
        handler: str,
    ) -> dict:
        """Copy a certified reference into storage. Caller has already certified it."""
        grade_key, subject_key = normalize(grade, subject)
        shown_grade, shown_subject = display_pair(grade, subject)
        if self.find(grade, subject):
            raise FileExistsError(f"{shown_grade}/{shown_subject}")
        data = Path(source).read_bytes()
        digest = sha256_bytes(data)
        stored_name = digest[:16] + ".docx"
        target = self.files / stored_name
        if not target.exists():
            target.write_bytes(data)
        if sha256_file(target) != digest:
            target.write_bytes(data)
        row = {
            "grade": shown_grade,
            "subject": shown_subject,
            "grade_key": grade_key,
            "subject_key": subject_key,
            "filename": Path(filename).name,
            "stored_path": target.relative_to(self.root).as_posix(),
            "source_hash": digest,
            "certification_status": "certified",
            "handler": handler,
        }
        rows = [item for item in self.rows() if not (item.get("grade_key") == grade_key and item.get("subject_key") == subject_key)]
        rows.append(row)
        self._write(rows)
        return row

    def delete(self, grade: str, subject: str) -> bool:
        grade_key, subject_key = normalize(grade, subject)
        rows = self.rows()
        kept = []
        removed = None
        for row in rows:
            if row.get("grade_key") == grade_key and row.get("subject_key") == subject_key:
                removed = row
            else:
                kept.append(row)
        if removed is None:
            return False
        self._write(kept)
        removed_path = self.file_path(removed)
        still_used = any(self.root / item.get("stored_path", "") == removed_path for item in kept)
        if removed_path.is_file() and not still_used:
            removed_path.unlink()
        return True

    def _write(self, rows: list[dict]) -> None:
        temporary = self.catalog_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(self.catalog_path)
