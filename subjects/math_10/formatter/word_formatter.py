"""Apply the Math 10 reference's page setup and Question 1 choice lists.

The teacher file is copied. Only the demonstrated differences are edited:
page size, page margins, Question 1 choice numbering, the typed "1" and tab
on the first choice, and the direct indents on those choices.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from subjects.math_10.reference.read import Exam, MathReadError, Paragraph, academic_text, q, read_exam

_STEM = re.compile(r"^\((?:iii|ii|iv|vi|v|i)\)")
_PLACEHOLDER = "[Image/graph in original examination]"


@dataclass(frozen=True)
class ChoiceIssue:
    error: str
    fix: str


@dataclass(frozen=True)
class Plan:
    issue: ChoiceIssue | None
    groups: tuple[tuple[int, ...], ...]
    scheme: tuple[str, str]


def prepare(reference_docx: str | Path, teacher: Exam) -> Plan | str:
    """Return a format plan, an error string, or a plan that names a correction."""
    if teacher.unsupported:
        return "Unsupported Word content was found and was not removed: " + ", ".join(teacher.unsupported)
    try:
        reference = read_exam(reference_docx)
    except MathReadError as exc:
        return str(exc)
    scheme = _reference_scheme(reference)
    if scheme is None:
        return "The Math reference does not show a single Question 1 choice list to follow."
    groups, issue = _choice_groups(teacher, scheme)
    return Plan(issue, tuple(tuple(group) for group in groups), scheme)


def format_document(source: str | Path, dest: str | Path, plan: Plan) -> None:
    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    if plan.issue is not None:
        _write_note(source, target, plan.issue)
        return
    with zipfile.ZipFile(source) as package:
        document = etree.fromstring(package.read("word/document.xml"))
        numbering = etree.fromstring(package.read("word/numbering.xml")) if "word/numbering.xml" in package.namelist() else None
        changed = _clear_page(document)
        if numbering is not None and plan.groups:
            changed = _apply_choices(document, numbering, plan) or changed
        if not changed:
            shutil.copyfile(source, target)
            return
        payload = {name: package.read(name) for name in package.namelist()}
    payload["word/document.xml"] = _xml(document)
    if numbering is not None:
        payload["word/numbering.xml"] = _xml(numbering)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as outgoing:
        for name, data in payload.items():
            outgoing.writestr(name, data)


def integrity_problem(before: Exam, after: Exam) -> str | None:
    if after.unsupported:
        return "Formatting produced unsupported Word content: " + ", ".join(after.unsupported)
    if len(before.paragraphs) != len(after.paragraphs):
        return "Formatting changed the number of paragraphs."
    repairs = 0
    for left, right in zip(before.paragraphs, after.paragraphs):
        if left.text == right.text and left.rule == right.rule:
            continue
        if repairs == 0 and left.text.startswith("1\t") and right.text == left.text[2:] and left.rule == right.rule:
            repairs += 1
            continue
        return "Formatting changed academic text."
    if _unusual(academic_text(before)) != _unusual(academic_text(after)):
        return "Formatting changed mathematical characters."
    if academic_text(before).count(_PLACEHOLDER) != academic_text(after).count(_PLACEHOLDER):
        return "Formatting changed the graph placeholder."
    if after.page.width or after.page.height or after.page.margins:
        return "Formatting left a page size or margins on the exam."
    return None


def _reference_scheme(reference: Exam) -> tuple[str, str] | None:
    groups, issue = _choice_groups(reference, ("lowerLetter", "(%1)"))
    if issue is not None or len(groups) != 6:
        return None
    schemes = set()
    for group in groups:
        for index in group:
            numbering = reference.paragraphs[index].numbering
            if numbering is None:
                return None
            schemes.add((numbering.fmt, numbering.level_text))
    if schemes != {("lowerLetter", "(%1)")}:
        return None
    return ("lowerLetter", "(%1)")


def _choice_groups(exam: Exam, scheme: tuple[str, str]) -> tuple[list[list[int]], ChoiceIssue | None]:
    start, end = _question_bounds(exam.paragraphs)
    if start is None or end is None:
        return [], None
    stems = [index for index in range(start + 1, end) if _STEM.match(exam.paragraphs[index].text.strip())]
    groups = []
    for position, stem in enumerate(stems):
        limit = stems[position + 1] if position + 1 < len(stems) else end
        groups.append(_group_after(exam.paragraphs, stem, limit, scheme))
    present = [group for group in groups if group]
    if not present:
        return [], None
    if [len(group) for group in present] != [4, 4, 4, 4, 4, 4]:
        return present, ChoiceIssue(
            "Question 1 choices are not six groups of four.",
            "Give each Question 1 stem four choices, then format the exam again.",
        )
    return present, None


def _group_after(paragraphs: tuple[Paragraph, ...], stem: int, limit: int, scheme: tuple[str, str]) -> list[int]:
    index = stem + 1
    while index < limit and not _is_choice(paragraphs[index], scheme) and not _is_prefix(paragraphs[index]):
        index += 1
    group = []
    if index < limit and _is_prefix(paragraphs[index]):
        group.append(index)
        index += 1
    while index < limit and _is_choice(paragraphs[index], scheme):
        group.append(index)
        index += 1
    return group


def _is_choice(paragraph: Paragraph, scheme: tuple[str, str]) -> bool:
    numbering = paragraph.numbering
    if numbering is None or numbering.ilvl != "0":
        return False
    if numbering.fmt == scheme[0] and numbering.level_text == scheme[1]:
        return True
    return numbering.fmt == "decimal" and numbering.level_text == "%1"


def _is_prefix(paragraph: Paragraph) -> bool:
    return paragraph.numbering is None and paragraph.text.startswith("1\t") and not paragraph.rule


def _question_bounds(paragraphs: tuple[Paragraph, ...]) -> tuple[int | None, int | None]:
    start = end = None
    for index, paragraph in enumerate(paragraphs):
        text = paragraph.text.strip()
        if start is None and text.startswith("Question 1:"):
            start = index
        elif start is not None and text.startswith("Question 2:"):
            end = index
            break
    return start, end


def _apply_choices(document, numbering, plan: Plan) -> bool:
    paragraphs = document.findall(".//" + q("p"))
    choice_indexes = {index for group in plan.groups for index in group}
    bindings = []
    for group in plan.groups:
        num_id = _shared_num_id(paragraphs, group)
        if num_id is None:
            raise MathFormatError("A Question 1 choice group has no single Word list.")
        abstract_id, number = _num_definition(numbering, num_id)
        if abstract_id is None or number is None:
            raise MathFormatError(f"Word list {num_id} has no definition.")
        if not _overrides_are_safe(number):
            raise MathFormatError(f"Word list {num_id} has a numbering override.")
        users = _abstract_users(paragraphs, numbering, abstract_id)
        if not set(users).issubset(choice_indexes):
            raise MathFormatError("A Question 1 choice list is shared with other exam text.")
        bindings.append((group, num_id, abstract_id))
    changed = False
    for abstract_id in {abstract_id for _group, _num_id, abstract_id in bindings}:
        changed = _set_choice_scheme(numbering, abstract_id, plan.scheme) or changed
    for group, num_id, _abstract_id in bindings:
        _abstract_id, number = _num_definition(numbering, num_id)
        changed = _restart_level_zero(number) or changed
        for index in group:
            if _strip_prefix(paragraphs[index]):
                changed = True
            if _clear_direct_indent(paragraphs[index]):
                changed = True
            if _paragraph_num_id(paragraphs[index]) != num_id:
                _set_num_pr(paragraphs[index], num_id)
                changed = True
    return changed


def _shared_num_id(paragraphs, group: tuple[int, ...]) -> str | None:
    found = []
    for index in group:
        num_id = _paragraph_num_id(paragraphs[index])
        if num_id:
            found.append(num_id)
    if not found or len(set(found)) != 1:
        return None
    return found[0]


def _paragraph_num_id(paragraph) -> str | None:
    properties = paragraph.find(q("pPr"))
    if properties is None:
        return None
    num_pr = properties.find(q("numPr"))
    if num_pr is None:
        return None
    node = num_pr.find(q("numId"))
    if node is None:
        return None
    value = node.get(q("val"))
    if not value or value == "0":
        return None
    return value


def _overrides_are_safe(number) -> bool:
    for override in number.findall(q("lvlOverride")):
        for child in override:
            if etree.QName(child).localname != "startOverride":
                return False
    return True


def _restart_level_zero(number) -> bool:
    changed = False
    for override in number.findall(q("lvlOverride")):
        if override.get(q("ilvl")) != "0":
            continue
        start = override.find(q("startOverride"))
        if start is not None and start.get(q("val")) != "1":
            start.set(q("val"), "1")
            changed = True
    return changed


def _num_definition(numbering, num_id: str):
    for number in numbering.findall(q("num")):
        if number.get(q("numId")) == num_id:
            node = number.find(q("abstractNumId"))
            abstract_id = node.get(q("val")) if node is not None else None
            return abstract_id, number
    return None, None


def _abstract_users(paragraphs, numbering, abstract_id: str) -> list[int]:
    num_ids = set()
    for number in numbering.findall(q("num")):
        node = number.find(q("abstractNumId"))
        if node is not None and node.get(q("val")) == abstract_id:
            num_ids.add(number.get(q("numId")))
    return [index for index, paragraph in enumerate(paragraphs) if _paragraph_num_id(paragraph) in num_ids]


def _set_choice_scheme(numbering, abstract_id: str, scheme: tuple[str, str]) -> bool:
    abstract = None
    for candidate in numbering.findall(q("abstractNum")):
        if candidate.get(q("abstractNumId")) == abstract_id:
            abstract = candidate
            break
    if abstract is None:
        raise MathFormatError(f"Numbering definition {abstract_id} is missing.")
    level = None
    for candidate in abstract.findall(q("lvl")):
        if candidate.get(q("ilvl")) == "0":
            level = candidate
            break
    if level is None:
        raise MathFormatError(f"Numbering definition {abstract_id} has no first level.")
    changed = False
    changed = _set_attr(level, "start", "1") or changed
    changed = _set_attr(level, "numFmt", scheme[0]) or changed
    changed = _set_attr(level, "lvlText", scheme[1]) or changed
    return changed


def _set_attr(parent, tag: str, value: str) -> bool:
    node = parent.find(q(tag))
    if node is None:
        raise MathFormatError(f"The Word list has no {tag}.")
    if node.get(q("val")) == value:
        return False
    node.set(q("val"), value)
    return True


def _strip_prefix(paragraph) -> bool:
    runs = [run for run in paragraph.findall(q("r")) if run.find(".//" + q("pict")) is None]
    if len(runs) < 2:
        return False
    if _run_text(runs[0]) != "1":
        return False
    if _run_text(runs[1]) or runs[1].find(q("tab")) is None:
        return False
    paragraph.remove(runs[0])
    paragraph.remove(runs[1])
    return True


def _run_text(run) -> str:
    return "".join(node.text or "" for node in run.findall(q("t")))


def _clear_direct_indent(paragraph) -> bool:
    properties = paragraph.find(q("pPr"))
    if properties is None:
        return False
    indent = properties.find(q("ind"))
    if indent is None:
        return False
    properties.remove(indent)
    return True


def _set_num_pr(paragraph, num_id: str) -> None:
    properties = paragraph.find(q("pPr"))
    if properties is None:
        properties = etree.Element(q("pPr"))
        paragraph.insert(0, properties)
    num_pr = properties.find(q("numPr"))
    if num_pr is None:
        num_pr = etree.Element(q("numPr"))
        style = properties.find(q("pStyle"))
        if style is not None:
            style.addnext(num_pr)
        else:
            properties.insert(0, num_pr)
    _set_child(num_pr, "ilvl", "0")
    _set_child(num_pr, "numId", num_id)


def _set_child(parent, tag: str, value: str) -> None:
    node = parent.find(q(tag))
    if node is None:
        node = etree.SubElement(parent, q(tag))
    node.set(q("val"), value)


def _clear_page(document) -> bool:
    section = document.find(".//" + q("sectPr"))
    if section is None:
        return False
    changed = False
    for tag in ("pgSz", "pgMar"):
        node = section.find(q(tag))
        if node is not None:
            section.remove(node)
            changed = True
    return changed


def _write_note(source: str | Path, dest: Path, issue: ChoiceIssue) -> None:
    with zipfile.ZipFile(source) as package:
        document = etree.fromstring(package.read("word/document.xml"))
        body = document.find(q("body"))
        if body is None:
            raise MathFormatError("The exam has no body.")
        body.insert(0, _note_paragraph(issue))
        payload = {name: package.read(name) for name in package.namelist()}
    payload["word/document.xml"] = _xml(document)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as outgoing:
        for name, data in payload.items():
            outgoing.writestr(name, data)


def _note_paragraph(issue: ChoiceIssue):
    paragraph = etree.Element(q("p"))
    paragraph.append(_note_run(f"ERROR: {issue.error}"))
    break_run = etree.SubElement(paragraph, q("r"))
    etree.SubElement(break_run, q("br"))
    paragraph.append(_note_run(f"FIX: {issue.fix}"))
    return paragraph


def _note_run(text: str):
    run = etree.Element(q("r"))
    properties = etree.SubElement(run, q("rPr"))
    etree.SubElement(properties, q("b"))
    highlight = etree.SubElement(properties, q("highlight"))
    highlight.set(q("val"), "yellow")
    node = etree.SubElement(run, q("t"))
    node.text = text
    return run


def _xml(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _unusual(text: str) -> tuple[tuple[str, int], ...]:
    counts = {}
    for character in text:
        if ord(character) > 127:
            counts[character] = counts.get(character, 0) + 1
    return tuple(sorted(counts.items()))


class MathFormatError(Exception):
    """The exam cannot be formatted without changing unrelated content."""
