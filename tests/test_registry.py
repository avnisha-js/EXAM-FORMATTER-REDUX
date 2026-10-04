"""One certified reference per grade and subject."""

from pathlib import Path

from docx import Document

from app.reference_registry import ReferenceRegistry
from common.hashing import sha256_file


def test_lookup_is_case_insensitive_and_delete_is_isolated(tmp_path):
    registry = ReferenceRegistry(tmp_path)
    english = _docx(tmp_path / "english.docx", "English reference")
    math = _docx(tmp_path / "math.docx", "Math reference")
    registry.install("10", "English", "English10.docx", english, "subjects.english_10")
    registry.install("10", "Math", "Math10.docx", math, "subjects.math_10")

    found = registry.find("Grade 10", "ENGLISH")
    assert found is not None
    assert found["subject"] == "English"
    assert found["filename"] == "English10.docx"
    assert found["certification_status"] == "certified"
    assert found["handler"] == "subjects.english_10"
    english_hash = sha256_file(registry.file_path(found))

    assert registry.delete("10", "Math") is True
    assert registry.find("10", "Math") is None
    still = registry.find("10", "english")
    assert still is not None
    assert sha256_file(registry.file_path(still)) == english_hash


def test_second_install_for_same_key_is_refused(tmp_path):
    registry = ReferenceRegistry(tmp_path)
    first = _docx(tmp_path / "first.docx", "First")
    second = _docx(tmp_path / "second.docx", "Second")
    registry.install("10", "English", "English10.docx", first, "subjects.english_10")
    try:
        registry.install("10", "english", "Other.docx", second, "subjects.english_10")
        raised = False
    except FileExistsError:
        raised = True
    assert raised
    row = registry.find("10", "English")
    assert row["filename"] == "English10.docx"
    assert sha256_file(registry.file_path(row)) == sha256_file(first)


def _docx(path: Path, text: str) -> Path:
    document = Document()
    document.add_paragraph(text)
    document.save(str(path))
    return path
