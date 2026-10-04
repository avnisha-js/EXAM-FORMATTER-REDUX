"""Prepare one English 10 reference profile for the current call.

The profile is built from that reference file and kept in a temporary
directory. It is not a shared catalog and it is not reused for another
grade or subject.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from subjects.english_10.reference.preprocess import build_profile

_DIRECTORY: ContextVar[Path | None] = ContextVar("english10_profile_dir", default=None)
_PROFILE: ContextVar[dict | None] = ContextVar("english10_profile", default=None)


def current_profile_dir() -> Path | None:
    return _DIRECTORY.get()


def current_profile() -> dict | None:
    return _PROFILE.get()


@contextmanager
def prepared_reference(reference: str | Path):
    """Build this reference's profile, or reuse the profile already prepared."""
    if _DIRECTORY.get() is not None:
        yield _PROFILE.get()
        return
    path = Path(reference)
    profile = build_profile(path)
    temporary = tempfile.TemporaryDirectory(prefix="english10-profile-")
    directory = Path(temporary.name)
    digest = profile["source_hash"]["hex"]
    target = directory / f"english10-{digest[:12]}.json"
    target.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    dir_token = _DIRECTORY.set(directory)
    profile_token = _PROFILE.set(profile)
    try:
        yield profile
    finally:
        _PROFILE.reset(profile_token)
        _DIRECTORY.reset(dir_token)
        temporary.cleanup()
