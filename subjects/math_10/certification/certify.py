"""Certify the Math 10 reference before it may become active.

A failed certification returns an error. It does not write a registry entry
and it does not strip unsupported Word objects out of the file.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from common.results import OperationResult
from subjects.math_10.processor.structure import structure_problems
from subjects.math_10.reference.preserve import MathPreserveError, write_preserved
from subjects.math_10.reference.read import MathReadError, academic_text, content_signature, read_exam, resolved_labels

LOGGER = logging.getLogger("exam_formatter.math_10")


def _failed(detail: str) -> OperationResult:
    LOGGER.info("Math 10 reference certification failed: %s", detail)
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
        original = path.read_bytes()
        exam = read_exam(path)
    except MathReadError as exc:
        return _failed(str(exc))
    except Exception as exc:
        LOGGER.exception("Math 10 reference certification stopped while reading")
        return _failed(str(exc))
    if exam.unsupported:
        return _failed(
            "Unsupported Word content would be lost, so certification stopped: "
            + ", ".join(exam.unsupported)
            + ". Nothing was removed."
        )
    problems = structure_problems(exam)
    if problems:
        return _failed(problems[0])
    if path.read_bytes() != original:
        return _failed("Reading the reference changed the file.")
    work = Path(tempfile.mkdtemp(prefix="math10-cert-"))
    try:
        copied = work / "roundtrip.docx"
        try:
            write_preserved(path, copied, exam)
            again = read_exam(copied)
        except (MathReadError, MathPreserveError) as exc:
            return _failed(str(exc))
        if again.unsupported:
            return _failed("The certification copy gained unsupported content: " + ", ".join(again.unsupported))
        if content_signature(exam) != content_signature(again):
            return _failed("Certification processing changed the reference structure or text.")
        if academic_text(exam) != academic_text(again):
            return _failed("Certification processing changed academic text.")
        if resolved_labels(exam) != resolved_labels(again):
            return _failed("Certification processing changed Word list labels.")
        if path.read_bytes() != original:
            return _failed("Certification changed the original reference file.")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    LOGGER.info("Math 10 reference certification passed file=%s", path.name)
    return OperationResult(ok=True, kind="certified", message="Reference certified.")
