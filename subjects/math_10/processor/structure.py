"""Hierarchy of the Math 10 reference.

These checks describe the reference that was actually read. They do not
describe another subject.
"""

from __future__ import annotations

import re

from subjects.math_10.reference.read import Exam, Paragraph, resolved_labels

_QUESTION = re.compile(r"^Question\s+(\d+)\b")
_SECTIONS = (
    "Objective-Type Questions",
    "Very Short-Answer Questions",
    "Short-Answer Questions",
    "Long-Answer Questions",
)
_REQUIRED_LINES = (
    "Math Grade 10 QE",
    "Chapters Covered",
    "BHAGINI NIVEDITA VIDYAPEETH",
    "Quarterly Examination 2026",
    "Subject: Mathematics",
    "Class: 10",
    "Marks: 75",
    "Time: 3 Hours",
    "Instructions",
    "6 × 5 = 30",
    "6 × 1 = 6",
    "12 × 2 = 24",
    "3 × 3 = 9",
    "Attempt any 3.",
    "3 × 4 = 12",
    "[Image/graph in original examination]",
)
_REQUIRED_CHARACTERS = ("−", "²", "₁", "₂", "×", "√", "–", "α", "β", "≠", "¼", "π")
_STEMS = ("(i)", "(ii)", "(iii)", "(iv)", "(v)", "(vi)")


def structure_problems(exam: Exam) -> list[str]:
    problems = []
    if not exam.paragraphs:
        return ["The document has no paragraphs."]
    if exam.unsupported:
        problems.append("Unsupported Word content: " + ", ".join(exam.unsupported))
    flat = "\n".join(paragraph.text for paragraph in exam.paragraphs)
    for line in _REQUIRED_LINES:
        if line not in flat:
            problems.append(f"Required reference text is missing: {line}")
    for character in _REQUIRED_CHARACTERS:
        if character not in flat:
            problems.append(f"Required mathematical character is missing: {character}")

    texts = [paragraph.text.strip() for paragraph in exam.paragraphs]
    section_at = [texts.index(name) for name in _SECTIONS if name in texts]
    if section_at != sorted(section_at) or len(section_at) != len(_SECTIONS):
        problems.append("The four Math section headings are missing or out of order.")

    questions = _questions(exam.paragraphs)
    numbers = [number for number, _index in questions]
    if numbers != list(range(1, 26)):
        problems.append(f"Questions 1–25 were not found in order. Found {numbers}.")

    labels = resolved_labels(exam)
    if any(paragraph.numbering is not None and label is None for paragraph, label in zip(exam.paragraphs, labels)):
        problems.append("A Word list label could not be reproduced.")

    if _questions_ok(numbers):
        problems.extend(_list_problems(exam.paragraphs, labels, questions))

    rules = [index for index, paragraph in enumerate(exam.paragraphs) if paragraph.rule]
    if len(rules) != 9:
        problems.append(f"Expected 9 horizontal rules. Found {len(rules)}.")
    return problems


def _questions(paragraphs: tuple[Paragraph, ...]) -> list[tuple[int, int]]:
    found = []
    for index, paragraph in enumerate(paragraphs):
        match = _QUESTION.match(paragraph.text.strip())
        if match:
            found.append((int(match.group(1)), index))
    return found


def _questions_ok(numbers: list[int]) -> bool:
    return numbers == list(range(1, 26))


def _list_problems(paragraphs, labels, questions) -> list[str]:
    problems = []
    located = dict(questions)
    problems.extend(_expect_group(paragraphs, labels, _after(paragraphs, "Chapters Covered"), "decimal", "%1.", 4, "(chapters)"))
    problems.extend(_expect_group(paragraphs, labels, _after(paragraphs, "Instructions"), "decimal", "%1.", 5, "(instructions)"))
    between_1_and_2 = paragraphs[located[1] + 1 : located[2]]
    stems = [paragraph.text.strip() for paragraph in between_1_and_2 if paragraph.text.strip().startswith(_STEMS)]
    stem_marks = [text[: text.find(")") + 1] if ")" in text else text for text in stems]
    if tuple(stem_marks) != _STEMS:
        problems.append(f"Question 1 stems are {stem_marks}, not (i) through (vi).")
    choice_groups = _groups(between_1_and_2, "lowerLetter", "(%1)")
    if [len(group) for group in choice_groups] != [4, 4, 4, 4, 4, 4]:
        problems.append("Question 1 does not have six groups of four (a) (b) (c) (d) choices.")
    else:
        for group in choice_groups:
            group_labels = [_label_at(paragraphs, labels, item) for item in group]
            if group_labels != ["(a)", "(b)", "(c)", "(d)"]:
                problems.append(f"A Question 1 choice list resolved to {group_labels}.")
    for start, end, fmt, level, count, name in (
        (2, 3, "decimal", "%1.", 6, "Question 2"),
        (3, 4, "decimal", "%1.", 6, "Question 3"),
        (18, 19, "lowerRoman", "(%1)", 2, "Question 18"),
        (19, 20, "lowerRoman", "(%1)", 2, "Question 19"),
        (22, 23, "lowerRoman", "(%1)", 2, "Question 22"),
        (23, 24, "lowerRoman", "(%1)", 2, "Question 23"),
    ):
        span = paragraphs[located[start] + 1 : located[end]]
        groups = _groups(span, fmt, level)
        if [len(group) for group in groups] != [count]:
            problems.append(f"{name} list shape is {[len(group) for group in groups]}, not [{count}].")
        elif fmt == "lowerRoman":
            group_labels = [_label_at(paragraphs, labels, item) for item in groups[0]]
            if group_labels != ["(i)", "(ii)"]:
                problems.append(f"{name} parts resolved to {group_labels}.")
    column_a = _between_headings(paragraphs, "A", "B", located[4], located[5])
    column_b = _between_headings(paragraphs, "B", None, located[4], located[5])
    if [len(group) for group in _groups(column_a, "decimal", "%1.")] != [6]:
        problems.append("Match column A is not six decimal items.")
    if [len(group) for group in _groups(column_b, "bullet", None)] != [6]:
        problems.append("Match column B is not six bullet items.")
    return problems


def _label_at(paragraphs, labels, item: Paragraph):
    for index, paragraph in enumerate(paragraphs):
        if paragraph is item:
            return labels[index]
    return None


def _after(paragraphs, text: str) -> list[Paragraph]:
    for index, paragraph in enumerate(paragraphs):
        if paragraph.text.strip() == text:
            return list(paragraphs[index + 1 :])
    return []


def _between_headings(paragraphs, start_text: str, end_text: str | None, begin: int, end: int) -> list[Paragraph]:
    span = list(paragraphs[begin + 1 : end])
    start = next((index for index, paragraph in enumerate(span) if paragraph.text.strip() == start_text), None)
    if start is None:
        return []
    if end_text is None:
        return span[start + 1 :]
    stop = next((index for index, paragraph in enumerate(span[start + 1 :], start + 1) if paragraph.text.strip() == end_text), None)
    if stop is None:
        return []
    return span[start + 1 : stop]


def _groups(span: list[Paragraph], fmt: str, level_text: str | None) -> list[list[Paragraph]]:
    groups: list[list[Paragraph]] = []
    current: list[Paragraph] = []
    for paragraph in span:
        numbering = paragraph.numbering
        matches = numbering is not None and numbering.fmt == fmt and (level_text is None or numbering.level_text == level_text)
        if matches:
            current.append(paragraph)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _expect_group(paragraphs, labels, span, fmt, level_text, count, name) -> list[str]:
    groups = _groups(span, fmt, level_text)
    if not groups or len(groups[0]) != count:
        return [f"{name} is not {count} decimal items."]
    expected = [f"{number}." for number in range(1, count + 1)]
    got = [_label_at(paragraphs, labels, item) for item in groups[0]]
    if got != expected:
        return [f"{name} resolved to {got}."]
    return []
