"""Route a grade and subject to one isolated compartment.

The map names a module. It does not contain that module's formatting rules.
"""

from __future__ import annotations

import importlib
import re

COMPARTMENTS = {
    ("10", "english"): "subjects.english_10",
    ("10", "math"): "subjects.math_10",
}


def normalize(grade: str, subject: str) -> tuple[str, str]:
    grade_key = " ".join((grade or "").split()).casefold()
    grade_key = re.sub(r"^grade\s*[:\-]?\s*", "", grade_key).strip()
    subject_key = " ".join((subject or "").split()).casefold()
    return grade_key, subject_key


def display_pair(grade: str, subject: str) -> tuple[str, str]:
    grade_key, subject_key = normalize(grade, subject)
    return grade_key, subject_key.title()


def compartment_name(grade: str, subject: str) -> str | None:
    return COMPARTMENTS.get(normalize(grade, subject))


def load_compartment(grade: str, subject: str):
    """Import the compartment for this grade and subject, if one exists."""
    name = compartment_name(grade, subject)
    if not name:
        return None
    return importlib.import_module(name)


def handler_matches(grade: str, subject: str, handler: str) -> bool:
    expected = compartment_name(grade, subject)
    return bool(expected) and handler == expected
