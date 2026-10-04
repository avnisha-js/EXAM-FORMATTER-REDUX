"""Format the real Math teacher exam and check the reference differences only."""

import shutil
import zipfile
from pathlib import Path

from lxml import etree

from subjects.math_10.reference.read import academic_text, content_signature, q, read_exam, resolved_labels
from subjects.math_10.service import format_exam

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "input" / "math_10" / "reference" / "Reference Exam Math Grade 10.docx"
TEACHER = ROOT / "input" / "math_10" / "exams" / "Teacher Exam Math Grade 10 - Formatting Errors.docx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def test_real_teacher_exam_matches_the_reference_choices(tmp_path):
    output = tmp_path / "formatted.docx"
    result = format_exam(REFERENCE, TEACHER, output)
    assert result.ok, result.message
    assert result.kind == "formatted"
    before = read_exam(TEACHER)
    after = read_exam(output)
    assert _choice_labels(after) == ["(a)", "(b)", "(c)", "(d)"] * 6
    assert _choice_words(after)[:4] == ["Rational", "Irrational", "Composite", "Prime"]
    assert all(not paragraph.text.startswith("1\t") for paragraph in after.paragraphs)
    assert after.page.width is None and after.page.height is None and after.page.margins == ()
    assert _unusual(academic_text(before)) == _unusual(academic_text(after))
    assert _texts_except_prefix(before, after)
    assert academic_text(after).count("[Image/graph in original examination]") == 1
    assert sum(paragraph.rule for paragraph in after.paragraphs) == 9
    assert _question_numbers(after) == list(range(1, 26))
    assert _kept_other_lists(after)
    section = _section_children(output)
    assert "pgSz" not in section and "pgMar" not in section
    assert "footnotePr" in section and "cols" in section


def test_formatted_exam_round_trips(tmp_path):
    first = tmp_path / "first.docx"
    second = tmp_path / "second.docx"
    assert format_exam(REFERENCE, TEACHER, first).ok
    again = format_exam(REFERENCE, first, second)
    assert again.ok, again.message
    assert content_signature(read_exam(first)) == content_signature(read_exam(second))
    assert resolved_labels(read_exam(first)) == resolved_labels(read_exam(second))
    assert read_exam(first).page == read_exam(second).page


def test_unsupported_objects_are_not_removed(tmp_path):
    output = tmp_path / "formatted.docx"
    omml = tmp_path / "omml.docx"
    _inject(TEACHER, omml, f'<m:oMath xmlns:m="{M}"><m:r><m:t>x</m:t></m:r></m:oMath>')
    drawing = tmp_path / "drawing.docx"
    _inject(TEACHER, drawing, f'<w:r xmlns:w="{W}"><w:drawing/></w:r>')
    for path, token in ((omml, "OMML"), (drawing, "drawing")):
        result = format_exam(REFERENCE, path, output)
        assert result.ok is False
        assert token in result.message
        assert "not removed" in result.message
        assert output.exists() is False


def test_unsafe_choice_group_is_a_note_not_a_guess(tmp_path):
    broken = tmp_path / "broken.docx"
    _drop_paragraph_containing(TEACHER, broken, "Prime")
    output = tmp_path / "Teacher Exam CORRECTIONS.docx"
    result = format_exam(REFERENCE, broken, output)
    assert result.ok
    assert result.kind == "corrections"
    text = academic_text(read_exam(output))
    assert "ERROR: Question 1 choices are not six groups of four." in text
    assert "FIX: Give each Question 1 stem four choices, then format the exam again." in text
    assert "Irrational" in text
    assert "x² − 49" in text


def _choice_labels(exam) -> list[str | None]:
    labels = resolved_labels(exam)
    words = []
    for index, paragraph in enumerate(exam.paragraphs):
        numbering = paragraph.numbering
        if numbering is not None and numbering.fmt == "lowerLetter" and numbering.level_text == "(%1)":
            words.append(labels[index])
    return words


def _choice_words(exam) -> list[str]:
    words = []
    for paragraph in exam.paragraphs:
        numbering = paragraph.numbering
        if numbering is not None and numbering.fmt == "lowerLetter" and numbering.level_text == "(%1)":
            words.append(paragraph.text.replace("\n", "").strip())
    return words


def _texts_except_prefix(before, after) -> bool:
    repairs = 0
    for left, right in zip(before.paragraphs, after.paragraphs):
        if left.text == right.text:
            continue
        if left.text.startswith("1\t") and right.text == left.text[2:]:
            repairs += 1
            continue
        return False
    return repairs == 1


def _question_numbers(exam) -> list[int]:
    import re

    found = []
    for paragraph in exam.paragraphs:
        match = re.match(r"Question\s+(\d+)\b", paragraph.text.strip())
        if match:
            found.append(int(match.group(1)))
    return found


def _kept_other_lists(exam) -> bool:
    labels = resolved_labels(exam)
    for index, paragraph in enumerate(exam.paragraphs):
        if paragraph.text.startswith("Real Numbers"):
            if labels[index] != "1.":
                return False
        if paragraph.text.startswith("x² − 3"):
            if labels[index] != "(i)":
                return False
        if paragraph.text.startswith("√13"):
            if labels[index] != "bullet":
                return False
    return True


def _unusual(text: str) -> tuple:
    counts = {}
    for character in text:
        if ord(character) > 127:
            counts[character] = counts.get(character, 0) + 1
    return tuple(sorted(counts.items()))


def _section_children(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    section = root.find(".//" + q("sectPr"))
    return [etree.QName(child).localname for child in section]


def _inject(source: Path, dest: Path, snippet: str) -> None:
    with zipfile.ZipFile(source) as package:
        root = etree.fromstring(package.read("word/document.xml"))
        payload = {name: package.read(name) for name in package.namelist()}
    paragraph = root.find(f".//{{{W}}}p")
    paragraph.append(etree.fromstring(snippet))
    payload["word/document.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(dest, "w") as package:
        for name, data in payload.items():
            package.writestr(name, data)


def _drop_paragraph_containing(source: Path, dest: Path, text: str) -> None:
    shutil.copyfile(source, dest)
    with zipfile.ZipFile(dest) as package:
        root = etree.fromstring(package.read("word/document.xml"))
        payload = {name: package.read(name) for name in package.namelist()}
    for paragraph in root.findall(f".//{{{W}}}p"):
        value = "".join(node.text or "" for node in paragraph.findall(f".//{{{W}}}t"))
        if value.strip() == text:
            paragraph.getparent().remove(paragraph)
            break
    payload["word/document.xml"] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    with zipfile.ZipFile(dest, "w") as package:
        for name, data in payload.items():
            package.writestr(name, data)
