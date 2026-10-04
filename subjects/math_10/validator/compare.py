"""Differences that the real Math teacher file actually shows.

This records formatting gaps. It does not rewrite the teacher file and it
does not invent a correction the two files do not demonstrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from subjects.math_10.reference.read import Exam, MathReadError, academic_text, graph_kind, read_exam, resolved_labels


@dataclass(frozen=True)
class TeacherAnalysis:
    ok: bool
    message: str
    graph: str
    unsupported: tuple[str, ...]
    differences: tuple[str, ...]
    unicode_same: bool
    numbering_semantics_same: bool


def analyze_teacher(reference_docx: str | Path, teacher_docx: str | Path) -> TeacherAnalysis:
    try:
        reference = read_exam(reference_docx)
        teacher = read_exam(teacher_docx)
    except MathReadError as exc:
        return TeacherAnalysis(False, str(exc), "D. the teacher file could not be read.", (), (), False, False)
    differences = tuple(_differences(reference, teacher))
    numbering_same = _numbering_pairs(reference) == _numbering_pairs(teacher)
    unicode_same = _unusual(academic_text(reference)) == _unusual(academic_text(teacher))
    graph = graph_kind(teacher)
    if teacher.unsupported:
        message = "Unsupported Word content was found and was not removed: " + ", ".join(teacher.unsupported)
        return TeacherAnalysis(False, message, graph, teacher.unsupported, differences, unicode_same, numbering_same)
    return TeacherAnalysis(True, "Teacher file read. No unsupported object.", graph, (), differences, unicode_same, numbering_same)


def _differences(reference: Exam, teacher: Exam) -> list[str]:
    found = []
    if reference.page != teacher.page:
        found.append(
            "Page setup differs. Reference: "
            + _page(reference)
            + ". Teacher: "
            + _page(teacher)
            + "."
        )
    if (reference.font_name, reference.font_size, reference.spacing_after, reference.heading_sizes) != (
        teacher.font_name,
        teacher.font_size,
        teacher.spacing_after,
        teacher.heading_sizes,
    ):
        found.append(
            "Font or spacing differs. "
            f"Reference font {reference.font_name} {reference.font_size}, spacing after {reference.spacing_after}, headings {reference.heading_sizes}. "
            f"Teacher font {teacher.font_name} {teacher.font_size}, spacing after {teacher.spacing_after}, headings {teacher.heading_sizes}."
        )
    if len(reference.paragraphs) != len(teacher.paragraphs):
        found.append(
            f"Paragraph count differs. Reference {len(reference.paragraphs)}. Teacher {len(teacher.paragraphs)}."
        )
    reference_labels = resolved_labels(reference)
    teacher_labels = resolved_labels(teacher)
    for index, (left, right) in enumerate(zip(reference.paragraphs, teacher.paragraphs), 1):
        if left.text != right.text:
            found.append(
                f"Paragraph {index} text differs. Reference {_show(left.text)}. Teacher {_show(right.text)}."
            )
        if _scheme(left) != _scheme(right) or reference_labels[index - 1] != teacher_labels[index - 1]:
            found.append(
                f"Paragraph {index} list label differs. "
                f"Reference {_label_phrase(left, reference_labels[index - 1])}. "
                f"Teacher {_label_phrase(right, teacher_labels[index - 1])}."
            )
        if left.indent != right.indent:
            found.append(f"Paragraph {index} direct indent differs. Reference {left.indent}. Teacher {right.indent}.")
        if left.alignment != right.alignment:
            found.append(f"Paragraph {index} alignment differs. Reference {left.alignment}. Teacher {right.alignment}.")
        if left.rule != right.rule:
            found.append(f"Paragraph {index} horizontal rule differs. Reference {left.rule}. Teacher {right.rule}.")
    return found


def _scheme(paragraph):
    if paragraph.numbering is None:
        return None
    return (paragraph.numbering.fmt, paragraph.numbering.level_text)


def _label_phrase(paragraph, label: str | None) -> str:
    if paragraph.numbering is None:
        return "typed text only, no Word list"
    kind = "Word list"
    return f"{kind} {paragraph.numbering.fmt} {paragraph.numbering.level_text!r} displaying {label!r}"


def _numbering_pairs(exam: Exam):
    return tuple(
        (
            paragraph.text,
            None if paragraph.numbering is None else (paragraph.numbering.fmt, paragraph.numbering.level_text),
            label,
        )
        for paragraph, label in zip(exam.paragraphs, resolved_labels(exam))
    )


def _unusual(text: str) -> tuple[tuple[str, int], ...]:
    counts = {}
    for character in text:
        if ord(character) > 127:
            counts[character] = counts.get(character, 0) + 1
    return tuple(sorted(counts.items()))


def _show(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


def _page(exam: Exam) -> str:
    page = exam.page
    if page.width is None and page.height is None and not page.margins:
        return "page size and margins are not stored"
    return f"{page.width} by {page.height} twips, margins {dict(page.margins)}"
