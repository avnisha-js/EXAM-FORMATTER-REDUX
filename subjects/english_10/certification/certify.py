"""Certify an English 10 reference before it may become active.

The uploaded file is only read. Formatting runs on a temporary copy.
A failed certification does not write a registry entry.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from docx import Document

from common.results import OperationResult
from subjects.english_10.certification.checks import structural_problem
from subjects.english_10.formatter.format_integrity import check_format
from subjects.english_10.formatter.word_formatter import format_exam as render_exam
from subjects.english_10.processor.pipeline import run_pipeline_stable
from subjects.english_10.reference.numbering import EnglishNumberingError
from subjects.english_10.reference.sections import ReferenceProfileError
from subjects.english_10.reference.session import prepared_reference
from subjects.english_10.validator.nonconformance import find_nonconformances

LOGGER = logging.getLogger("exam_formatter.english_10")


def _failed(detail: str) -> OperationResult:
    LOGGER.info("English 10 reference certification failed: %s", detail)
    return OperationResult(
        ok=False,
        kind="rejected",
        message="Reference Certification Failed.\n" + detail,
        diagnostics=[detail],
    )


def certify_reference(reference_docx: str | Path) -> OperationResult:
    path = Path(reference_docx)
    if not path.is_file():
        return _failed("The reference file is missing.")
    try:
        Document(str(path))
    except Exception as exc:
        return _failed(f"The Word file could not be read. {exc}")
    try:
        with prepared_reference(path) as profile:
            problem = structural_problem(profile or {})
            if problem:
                return _failed(problem)
            problem = _self_test(path)
            if problem:
                return _failed(problem)
    except (ReferenceProfileError, EnglishNumberingError) as exc:
        return _failed(str(exc))
    except Exception as exc:
        LOGGER.exception("English 10 reference certification stopped")
        return _failed(str(exc))
    LOGGER.info("English 10 reference certification passed file=%s", path.name)
    return OperationResult(ok=True, kind="certified", message="Reference certified.")


def _self_test(master: Path) -> str | None:
    original = master.read_bytes()
    work = Path(tempfile.mkdtemp(prefix="english10-cert-"))
    try:
        copy = work / "copy.docx"
        formatted = work / "formatted.docx"
        shutil.copyfile(master, copy)
        errors = find_nonconformances(copy, master)
        if errors:
            item = errors[0]
            return f"{item.error} {item.fix}"
        result = run_pipeline_stable(copy, master, work / "core", log_context="certify:10/english")
        if not result["ok"]:
            observed = "; ".join(str(item) for item in result["problems"])
            failed = [detail for _name, flag, detail in result["checks"] if not flag]
            if not observed and failed:
                observed = "; ".join(str(item) for item in failed)
            return "The English formatter could not process this reference. " + (observed or "validation failed")
        render_exam(result["blocks"], copy, formatted, master)
        problems = check_format(result["blocks"], copy, formatted, master)
        if problems:
            return "Integrity check failed. " + problems[0]
        if master.read_bytes() != original:
            master.write_bytes(original)
            return "The reference file changed during certification and was restored."
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
