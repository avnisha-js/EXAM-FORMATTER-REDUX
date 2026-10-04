"""Write parsed Math text back into a copy of the same DOCX.

The numbering part, horizontal rules, and section properties are copied.
Only the text runs are rewritten from the parsed pieces, so a later read
can prove the academic characters and list definitions survived.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from lxml import etree

from subjects.math_10.reference.read import Exam, MathReadError, Piece, q


class MathPreserveError(MathReadError):
    """The parsed exam could not be written back without dropping content."""


def write_preserved(source: str | Path, dest: str | Path, exam: Exam) -> Path:
    if exam.unsupported:
        raise MathPreserveError(
            "Unsupported Word content was not written and was not removed: " + ", ".join(exam.unsupported)
        )
    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as incoming:
        rebuilt = _rebuild_document(incoming.read("word/document.xml"), exam)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as outgoing:
            for item in incoming.infolist():
                payload = rebuilt if item.filename == "word/document.xml" else incoming.read(item.filename)
                outgoing.writestr(item, payload)
    return target


def _rebuild_document(payload: bytes, exam: Exam) -> bytes:
    root = etree.fromstring(payload)
    paragraphs = root.findall(".//" + q("p"))
    if len(paragraphs) != len(exam.paragraphs):
        raise MathPreserveError("The paragraph count changed before the text could be written back.")
    for para, parsed in zip(paragraphs, exam.paragraphs):
        _replace_text_runs(para, parsed.pieces)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _replace_text_runs(para, pieces: tuple[Piece, ...]) -> None:
    for child in list(para):
        if child.tag == q("r") and child.find(".//" + q("pict")) is None:
            para.remove(child)
    anchor = None
    for child in para:
        if child.tag == q("r") and child.find(".//" + q("pict")) is not None:
            anchor = child
            break
    for piece in pieces:
        run = _run(piece)
        if anchor is not None:
            anchor.addprevious(run)
        else:
            para.append(run)


def _run(piece: Piece):
    run = etree.Element(q("r"))
    if piece.bold:
        properties = etree.SubElement(run, q("rPr"))
        etree.SubElement(properties, q("b"))
        etree.SubElement(properties, q("bCs"))
    if piece.kind == "text":
        text = etree.SubElement(run, q("t"))
        if piece.text[:1].isspace() or piece.text[-1:].isspace():
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        text.text = piece.text
    elif piece.kind == "break":
        etree.SubElement(run, q("br"))
    elif piece.kind == "tab":
        etree.SubElement(run, q("tab"))
    else:
        raise MathPreserveError(f"Unknown text piece {piece.kind}.")
    return run
