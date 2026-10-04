"""External interface for the Math 10 compartment.

The common application calls these functions. It does not inspect Math
numbering, page setup, or choice labels.
"""

from __future__ import annotations

import logging
from pathlib import Path

from common.results import OperationResult
from subjects.math_10.certification.certify import certify_reference
from subjects.math_10.formatter.word_formatter import (
    MathFormatError,
    Plan,
    format_document,
    integrity_problem,
    prepare,
)
from subjects.math_10.reference.read import MathReadError, read_exam, resolved_labels

HANDLER_ID = "subjects.math_10"
GRADE_KEY = "10"
SUBJECT_KEY = "math"

LOGGER = logging.getLogger("exam_formatter.math_10")


def _error(message: str) -> OperationResult:
    return OperationResult(ok=False, kind="error", message=message, diagnostics=[message])


def format_exam(reference_docx: str | Path, teacher_docx: str | Path, output_docx: str | Path) -> OperationResult:
    teacher_path = Path(teacher_docx)
    output = Path(output_docx)
    try:
        teacher = read_exam(teacher_path)
    except MathReadError as exc:
        return _error(str(exc))
    planned = prepare(reference_docx, teacher)
    if isinstance(planned, str):
        return _error(planned)
    if planned.issue is not None:
        try:
            format_document(teacher_path, output, planned)
        except MathFormatError as exc:
            output.unlink(missing_ok=True)
            return _error(str(exc))
        note = f"ERROR: {planned.issue.error}\nFIX: {planned.issue.fix}"
        LOGGER.info("Math 10 teacher exam returned a correction")
        return OperationResult(
            ok=True,
            kind="corrections",
            message="Teacher exam needs corrections.",
            output_path=str(output),
            diagnostics=[note],
        )
    try:
        format_document(teacher_path, output, planned)
        formatted = read_exam(output)
    except (MathReadError, MathFormatError) as exc:
        output.unlink(missing_ok=True)
        return _error(str(exc))
    problem = integrity_problem(teacher, formatted)
    if problem:
        output.unlink(missing_ok=True)
        return _error(problem + " The formatted file was not kept.")
    if not _choices_match(formatted, planned):
        output.unlink(missing_ok=True)
        return _error("Question 1 choices did not become the reference list. The formatted file was not kept.")
    LOGGER.info("Math 10 exam formatted output=%s", output.name)
    return OperationResult(ok=True, kind="formatted", message="Exam formatted.", output_path=str(output))


def validate_exam(reference_docx: str | Path, teacher_docx: str | Path) -> OperationResult:
    try:
        teacher = read_exam(teacher_docx)
    except MathReadError as exc:
        return _error(str(exc))
    planned = prepare(reference_docx, teacher)
    if isinstance(planned, str):
        return _error(planned)
    if planned.issue is not None:
        note = f"ERROR: {planned.issue.error}\nFIX: {planned.issue.fix}"
        return OperationResult(ok=False, kind="nonconformance", message=planned.issue.error, diagnostics=[note])
    return OperationResult(ok=True, kind="valid", message="Math teacher file can be formatted.")


def _choices_match(exam, plan: Plan) -> bool:
    if not plan.groups:
        return True
    labels = resolved_labels(exam)
    for group in plan.groups:
        if [labels[index] for index in group] != ["(a)", "(b)", "(c)", "(d)"]:
            return False
        for index in group:
            paragraph = exam.paragraphs[index]
            if paragraph.indent is not None:
                return False
            if paragraph.text.startswith("1\t"):
                return False
    return True


__all__ = [
    "HANDLER_ID",
    "GRADE_KEY",
    "SUBJECT_KEY",
    "certify_reference",
    "format_exam",
    "validate_exam",
]
