"""Structural checks for an English 10 reference.

A shorter section list is valid. English does not require one fixed
sample shape such as Sections A, B, C, and D all being present.
"""

from __future__ import annotations

from subjects.english_10.reference.appearance import appearance_from_profile
from subjects.english_10.reference.headers import header_policy_from_profile
from subjects.english_10.reference.images import image_policy_from_profile
from subjects.english_10.reference.numbering import EnglishNumberingError, policy_from_profile
from subjects.english_10.reference.sections import ReferenceProfileError


def structural_problem(profile: dict) -> str | None:
    """Return a diagnostic when this profile is not an English 10 reference."""
    sections = (profile.get("structure") or {}).get("sections") or {}
    items = sections.get("items") or []
    headings = [item.get("heading") for item in items if isinstance(item, dict) and item.get("heading")]
    if sections.get("status") != "observed" or not headings:
        return (
            "Section headings could not be discovered. "
            "The reference needs recognizable section headings."
        )
    try:
        requirements = header_policy_from_profile(profile)
    except ReferenceProfileError as exc:
        return str(exc)
    if not any(item.role == "class_grade" for item in requirements):
        return "Expected Class header could not be discovered."
    try:
        policy_from_profile(profile)
    except EnglishNumberingError as exc:
        return str(exc)
    majors = (profile.get("structure") or {}).get("major_questions") or {}
    if majors.get("status") != "observed" or not majors.get("count"):
        return "Questions could not be identified."
    try:
        image_policy_from_profile(profile)
    except ReferenceProfileError as exc:
        return str(exc)
    try:
        appearance_from_profile(profile)
    except ReferenceProfileError as exc:
        return str(exc)
    return None
