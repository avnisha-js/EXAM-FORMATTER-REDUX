"""External interface for the English 10 compartment.

The common application calls these functions. It does not inspect English
numbering, sections, or headers.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from docx import Document

from common.results import OperationResult
from subjects.english_10.certification.certify import certify_reference
from subjects.english_10.formatter.format_integrity import check_format
from subjects.english_10.formatter.word_formatter import format_exam as render_exam
from subjects.english_10.processor.pipeline import run_pipeline_stable
from subjects.english_10.reference.numbering import EnglishNumberingError
from subjects.english_10.reference.sections import ReferenceProfileError
from subjects.english_10.reference.session import prepared_reference
from subjects.english_10.validator.nonconformance import find_nonconformances, write_nonconformance_file

HANDLER_ID = "subjects.english_10"
GRADE_KEY = "10"
SUBJECT_KEY = "english"

LOGGER = logging.getLogger("exam_formatter.english_10")


def _error(message: str, diagnostics: list[str] | None = None) -> OperationResult:
    return OperationResult(ok=False, kind="error", message=message, diagnostics=diagnostics or [])


def format_exam(reference_docx: str | Path, teacher_docx: str | Path, output_docx: str | Path) -> OperationResult:
    reference = Path(reference_docx)
    teacher = Path(teacher_docx)
    output = Path(output_docx)
    if not reference.is_file():
        return _error("The English 10 reference file is missing.")
    if not teacher.is_file():
        return _error("The teacher exam file is missing.")
    try:
        Document(str(teacher))
    except Exception as exc:
        return _error(f"The teacher exam could not be read. {exc}")
    try:
        with prepared_reference(reference):
            errors = find_nonconformances(teacher, reference)
            if errors:
                output.parent.mkdir(parents=True, exist_ok=True)
                write_nonconformance_file(teacher, output, errors, reference)
                diagnostics = [f"ERROR: {item.error}\nFIX: {item.fix}" for item in errors]
                LOGGER.info("English 10 teacher exam returned %d correction(s)", len(errors))
                return OperationResult(
                    ok=True,
                    kind="corrections",
                    message="Teacher exam needs corrections.",
                    output_path=str(output),
                    diagnostics=diagnostics,
                )
            work = Path(tempfile.mkdtemp(prefix="english10-format-"))
            try:
                result = run_pipeline_stable(teacher, reference, work / "core", log_context="format:10/english")
                if not result["ok"]:
                    detail = "; ".join(str(item) for item in result["problems"]) or "validation failed"
                    return _error("Formatting failed.\n" + detail, [detail])
                output.parent.mkdir(parents=True, exist_ok=True)
                render_exam(result["blocks"], teacher, output, reference)
                problems = check_format(result["blocks"], teacher, output, reference)
                if problems:
                    output.unlink(missing_ok=True)
                    return _error(
                        "Academic content integrity check failed.\n" + problems[0],
                        problems,
                    )
            finally:
                shutil.rmtree(work, ignore_errors=True)
    except (ReferenceProfileError, EnglishNumberingError) as exc:
        return _error(str(exc))
    except Exception as exc:
        LOGGER.exception("English 10 formatting stopped")
        return _error(f"Formatting failed.\n{exc}")
    LOGGER.info("English 10 exam formatted output=%s", output.name)
    return OperationResult(ok=True, kind="formatted", message="Exam formatted.", output_path=str(output))


def validate_exam(reference_docx: str | Path, teacher_docx: str | Path) -> OperationResult:
    reference = Path(reference_docx)
    teacher = Path(teacher_docx)
    try:
        Document(str(teacher))
    except Exception as exc:
        return _error(f"The teacher exam could not be read. {exc}")
    try:
        with prepared_reference(reference):
            errors = find_nonconformances(teacher, reference)
    except (ReferenceProfileError, EnglishNumberingError) as exc:
        return _error(str(exc))
    if errors:
        diagnostics = [f"ERROR: {item.error}\nFIX: {item.fix}" for item in errors]
        return OperationResult(
            ok=False,
            kind="nonconformance",
            message=errors[0].error,
            diagnostics=diagnostics,
        )
    return OperationResult(ok=True, kind="valid", message="No reference nonconformance.")


__all__ = [
    "HANDLER_ID",
    "GRADE_KEY",
    "SUBJECT_KEY",
    "certify_reference",
    "format_exam",
    "validate_exam",
]
