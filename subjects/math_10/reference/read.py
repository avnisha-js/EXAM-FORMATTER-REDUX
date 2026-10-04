"""Read a Math 10 DOCX without changing it.

Mathematical characters stay in the text nodes where Word stored them.
List labels are read from numbering definitions. They are not guessed
from English question marks.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"

_RUN_SKIP = {"rPr", "proofErr", "lastRenderedPageBreak"}
_KNOWN_FORMATS = {"decimal", "lowerLetter", "upperLetter", "lowerRoman", "upperRoman", "bullet"}


class MathReadError(Exception):
    """The file could not be read as a Math 10 Word document."""


@dataclass(frozen=True)
class Piece:
    kind: str
    text: str = ""
    bold: bool = False


@dataclass(frozen=True)
class ListNumbering:
    num_id: str
    ilvl: str
    fmt: str
    level_text: str
    start: int


@dataclass(frozen=True)
class Paragraph:
    style: str | None
    pieces: tuple[Piece, ...]
    numbering: ListNumbering | None
    indent: tuple[tuple[str, str], ...] | None
    alignment: str | None
    rule: bool

    @property
    def text(self) -> str:
        parts = []
        for piece in self.pieces:
            if piece.kind == "break":
                parts.append("\n")
            else:
                parts.append(piece.text)
        return "".join(parts)


@dataclass(frozen=True)
class PageSetup:
    width: str | None
    height: str | None
    margins: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Exam:
    paragraphs: tuple[Paragraph, ...]
    unsupported: tuple[str, ...]
    page: PageSetup
    font_name: str | None
    font_size: str | None
    spacing_after: str | None
    heading_sizes: tuple[tuple[str, str | None], ...]


def q(tag: str) -> str:
    return f"{{{W}}}{tag}"


def read_exam(path: str | Path) -> Exam:
    source = Path(path)
    if not source.is_file():
        raise MathReadError("The Word file is missing.")
    try:
        with zipfile.ZipFile(source) as package:
            names = package.namelist()
            if "word/document.xml" not in names:
                raise MathReadError("The file has no Word document body.")
            root = etree.fromstring(package.read("word/document.xml"))
            numbering = etree.fromstring(package.read("word/numbering.xml")) if "word/numbering.xml" in names else None
            styles = etree.fromstring(package.read("word/styles.xml")) if "word/styles.xml" in names else None
            theme = etree.fromstring(package.read("word/theme/theme1.xml")) if "word/theme/theme1.xml" in names else None
            media = [name for name in names if name.startswith("word/media/") or "/embeddings/" in name]
    except MathReadError:
        raise
    except Exception as exc:
        raise MathReadError(f"The Word file could not be read. {exc}") from exc

    unsupported: list[str] = []
    if root.find(".//" + f"{{{M}}}oMath") is not None or root.find(".//" + f"{{{M}}}oMathPara") is not None:
        unsupported.append("OMML equation")
    if root.find(".//" + q("tbl")) is not None:
        unsupported.append("table")
    if root.find(".//" + q("drawing")) is not None or root.find(".//" + f"{{{A}}}blip") is not None:
        unsupported.append("drawing or image")
    if root.find(".//" + q("object")) is not None or media:
        unsupported.append("embedded object")
    if root.find(".//" + q("txbxContent")) is not None:
        unsupported.append("text box")

    abstracts, numbers = _numbering_maps(numbering)
    paragraphs = []
    for para in root.findall(".//" + q("p")):
        paragraphs.append(_paragraph(para, abstracts, numbers, unsupported))
    page = _page(root)
    font_name, font_size, spacing_after, heading_sizes = _appearance(styles, theme)
    unique = tuple(dict.fromkeys(unsupported))
    return Exam(
        paragraphs=tuple(paragraphs),
        unsupported=unique,
        page=page,
        font_name=font_name,
        font_size=font_size,
        spacing_after=spacing_after,
        heading_sizes=tuple(heading_sizes.items()),
    )


def academic_text(exam: Exam) -> str:
    return "\n".join(paragraph.text for paragraph in exam.paragraphs)


def content_signature(exam: Exam) -> tuple:
    rows = []
    for paragraph in exam.paragraphs:
        numbering = None
        if paragraph.numbering is not None:
            numbering = (
                paragraph.numbering.num_id,
                paragraph.numbering.ilvl,
                paragraph.numbering.fmt,
                paragraph.numbering.level_text,
                paragraph.numbering.start,
            )
        pieces = tuple((piece.kind, piece.text, piece.bold) for piece in paragraph.pieces)
        rows.append((paragraph.style, pieces, numbering, paragraph.indent, paragraph.alignment, paragraph.rule))
    return tuple(rows)


def resolved_labels(exam: Exam) -> tuple[str | None, ...]:
    counters: dict[str, int] = {}
    labels = []
    for paragraph in exam.paragraphs:
        numbering = paragraph.numbering
        if numbering is None:
            labels.append(None)
            continue
        if numbering.fmt not in _KNOWN_FORMATS:
            labels.append(None)
            continue
        current = counters.get(numbering.num_id, numbering.start - 1) + 1
        counters[numbering.num_id] = current
        labels.append(render_label(numbering.fmt, numbering.level_text, current))
    return tuple(labels)


def render_label(fmt: str, level_text: str, number: int) -> str | None:
    if fmt == "bullet":
        return "bullet"
    if number < 1:
        return None
    if fmt == "decimal":
        token = str(number)
    elif fmt == "lowerLetter":
        if number > 26:
            return None
        token = chr(ord("a") + number - 1)
    elif fmt == "upperLetter":
        if number > 26:
            return None
        token = chr(ord("A") + number - 1)
    elif fmt in {"lowerRoman", "upperRoman"}:
        token = _roman(number)
        if token is None:
            return None
        if fmt == "lowerRoman":
            token = token.lower()
    else:
        return None
    if "%1" not in level_text:
        return token
    return level_text.replace("%1", token).replace("%2", token)


def graph_kind(exam: Exam) -> str:
    placeholder = "[Image/graph in original examination]"
    has_placeholder = any(placeholder in paragraph.text for paragraph in exam.paragraphs)
    has_picture = any(item in exam.unsupported for item in ("drawing or image", "embedded object", "text box"))
    rules = sum(1 for paragraph in exam.paragraphs if paragraph.rule)
    if has_placeholder and not has_picture:
        return (
            "C. text placeholder only. Question 20 stores the bold sentence "
            f"{placeholder!r}. No image part, drawing, blip, shape text, or embedded object "
            f"is attached to it. The file has {rules} VML horizontal rules, and those rules are separators."
        )
    if has_picture and not has_placeholder:
        return "A. real embedded image or drawing. No text placeholder was found."
    if has_picture and has_placeholder:
        return "A. real embedded image or drawing, together with a text placeholder."
    return "D. Question 20 has neither a graph image nor the text placeholder."


def _paragraph(para, abstracts, numbers, unsupported: list[str]) -> Paragraph:
    properties = para.find(q("pPr"))
    style = _val(properties, "pStyle")
    alignment = _val(properties, "jc")
    indent = None
    if properties is not None and properties.find(q("ind")) is not None:
        node = properties.find(q("ind"))
        indent = tuple(sorted((key.split("}")[-1], node.get(key)) for key in node.attrib))
    numbering = _paragraph_numbering(properties, abstracts, numbers, unsupported)
    pieces = []
    rule = False
    for run in para.findall(q("r")):
        if run.find(".//" + q("pict")) is not None:
            if _is_horizontal_rule(run):
                rule = True
            else:
                unsupported.append("pict that is not a horizontal rule")
            if _run_text(run):
                unsupported.append("horizontal rule mixed with text")
            continue
        bold = _bold(run.find(q("rPr")))
        for child in run:
            name = etree.QName(child).localname
            if name in _RUN_SKIP:
                continue
            if name == "t":
                pieces.append(Piece("text", child.text or "", bold))
            elif name == "br":
                pieces.append(Piece("break", "", bold))
            elif name == "tab":
                pieces.append(Piece("tab", "\t", bold))
            else:
                unsupported.append(f"unrecognized run content: {name}")
    return Paragraph(style, tuple(pieces), numbering, indent, alignment, rule)


def _paragraph_numbering(properties, abstracts, numbers, unsupported: list[str]) -> ListNumbering | None:
    if properties is None:
        return None
    num_pr = properties.find(q("numPr"))
    if num_pr is None:
        return None
    num_id = _val(num_pr, "numId")
    ilvl = _val(num_pr, "ilvl") or "0"
    if not num_id or num_id == "0":
        return None
    if num_id not in numbers:
        unsupported.append(f"numbering id {num_id} has no definition")
        return None
    abstract_id, overrides = numbers[num_id]
    if ilvl in overrides:
        fmt, level_text, start = overrides[ilvl]
    else:
        level = abstracts.get(abstract_id, {}).get(ilvl)
        if level is None:
            unsupported.append(f"numbering id {num_id} has no level {ilvl}")
            return None
        fmt, level_text, start = level
    if fmt not in _KNOWN_FORMATS:
        unsupported.append(f"unsupported list format: {fmt}")
    return ListNumbering(num_id, ilvl, fmt, level_text, start)


def _numbering_maps(numbering):
    abstracts: dict[str, dict[str, tuple[str, str, int]]] = {}
    numbers: dict[str, tuple[str, dict[str, tuple[str, str, int]]]] = {}
    if numbering is None:
        return abstracts, numbers
    for abstract in numbering.findall(q("abstractNum")):
        abstract_id = abstract.get(q("abstractNumId"))
        levels = {}
        for level in abstract.findall(q("lvl")):
            ilvl = level.get(q("ilvl"))
            fmt = _val(level, "numFmt") or ""
            level_text = _val(level, "lvlText") or ""
            start = int(_val(level, "start") or "1")
            levels[ilvl] = (fmt, level_text, start)
        abstracts[abstract_id] = levels
    for number in numbering.findall(q("num")):
        num_id = number.get(q("numId"))
        abstract_id = _val(number, "abstractNumId")
        overrides = {}
        for override in number.findall(q("lvlOverride")):
            ilvl = override.get(q("ilvl"))
            base = abstracts.get(abstract_id, {}).get(ilvl, ("", "", 1))
            fmt, level_text, start = base
            start_node = override.find(q("startOverride"))
            if start_node is not None and start_node.get(q("val")):
                start = int(start_node.get(q("val")))
            level = override.find(q("lvl"))
            if level is not None:
                fmt = _val(level, "numFmt") or fmt
                level_text = _val(level, "lvlText") or level_text
                if _val(level, "start"):
                    start = int(_val(level, "start"))
            overrides[ilvl] = (fmt, level_text, start)
        numbers[num_id] = (abstract_id, overrides)
    return abstracts, numbers


def _is_horizontal_rule(run) -> bool:
    for element in run.iter():
        for key, value in element.attrib.items():
            if key == "hr" or key.endswith("}hr"):
                return value in {"t", "true", "1"}
    return False


def _run_text(run) -> str:
    return "".join(node.text or "" for node in run.findall(".//" + q("t")))


def _bold(properties) -> bool:
    if properties is None:
        return False
    node = properties.find(q("b"))
    if node is None:
        return False
    return node.get(q("val")) not in {"0", "false", "off"}


def _val(parent, tag: str) -> str | None:
    if parent is None:
        return None
    node = parent.find(q(tag))
    if node is None:
        return None
    return node.get(q("val"))


def _page(root) -> PageSetup:
    section = root.find(".//" + q("sectPr"))
    width = height = None
    margins: list[tuple[str, str]] = []
    if section is not None:
        size = section.find(q("pgSz"))
        if size is not None:
            width = size.get(q("w"))
            height = size.get(q("h"))
        margin = section.find(q("pgMar"))
        if margin is not None:
            margins = sorted((key.split("}")[-1], margin.get(key)) for key in margin.attrib)
    return PageSetup(width, height, tuple(margins))


def _appearance(styles, theme):
    font_name = None
    font_size = None
    spacing_after = None
    heading_sizes = {}
    if theme is not None:
        for element in theme.iter(f"{{{A}}}latin"):
            parent = etree.QName(element.getparent()).localname
            if parent == "minorFont":
                font_name = element.get("typeface")
    if styles is not None:
        defaults = styles.find(q("docDefaults"))
        if defaults is not None:
            font_size = _val(defaults.find(".//" + q("rPr")), "sz")
            spacing = defaults.find(".//" + q("spacing"))
            if spacing is not None:
                spacing_after = spacing.get(q("after"))
        for style in styles.findall(q("style")):
            style_id = style.get(q("styleId"))
            if style_id in {"Heading1", "Heading2", "Heading3"}:
                heading_sizes[style_id] = _val(style.find(q("rPr")), "sz")
    return font_name, font_size, spacing_after, dict(sorted(heading_sizes.items()))


def _roman(number: int) -> str | None:
    if number > 40:
        return None
    values = (
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result = []
    remaining = number
    for value, glyph in values:
        while remaining >= value:
            result.append(glyph)
            remaining -= value
    return "".join(result)
