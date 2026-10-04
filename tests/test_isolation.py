"""Common code and English code stay on their own sides of the boundary."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_IN_COMMON = (
    "Section A",
    "Section B",
    "Q{n}",
    "major_question",
    "class_grade",
    "branch_carrier",
)
_APP_IMPORT = re.compile(r"^\s*(?:import|from)\s+app(?:\.|\s)", re.MULTILINE)
_OTHER_SUBJECT = re.compile(r"subjects\.(?!english_10\b)[a-z0-9_]+")


def test_common_and_app_do_not_contain_english_rules():
    roots = [ROOT / "common", ROOT / "app"]
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_IN_COMMON:
                if token in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {token}")
    assert offenders == []


def test_english_does_not_import_another_subject_or_the_gui():
    compartment = ROOT / "subjects" / "english_10"
    offenders = []
    for path in compartment.rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if _APP_IMPORT.search(text) or _OTHER_SUBJECT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_subject_imports_another_subject():
    subjects = ROOT / "subjects"
    packages = sorted(path.name for path in subjects.iterdir() if path.is_dir() and path.name != "__pycache__")
    assert packages == ["english_10", "math_10"]
    offenders = []
    for package in packages:
        for path in (subjects / package).rglob("*.py"):
            if "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if _APP_IMPORT.search(text):
                offenders.append(str(path.relative_to(ROOT)))
            for other in packages:
                if other != package and re.search(rf"subjects\.{other}\b", text):
                    offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
