"""Live browser flow for English 10 certification, formatting, and round-trip."""

import io
import re
import zipfile
from pathlib import Path

import pytest
from docx import Document

from app.reference_registry import ReferenceRegistry
from app.web import create_app
from common.hashing import sha256_file

FIXTURES = Path(__file__).resolve().parents[1] / "subjects" / "english_10" / "tests" / "fixtures"
REFERENCE = FIXTURES / "good_reference.docx"
TEACHER = FIXTURES / "good_teacher.docx"
BAD_REFERENCE = FIXTURES / "bad_reference.docx"

_DOUBLE_LABEL = re.compile(r"Q\d+\)\s+Q\d+\)")


@pytest.fixture(scope="module")
def certified_client(tmp_path_factory):
    data = tmp_path_factory.mktemp("live")
    app = create_app(data)
    client = app.test_client()
    response = client.post(
        "/reference",
        data={
            "grade": "10",
            "subject": "English",
            "reference": (REFERENCE.open("rb"), "English Reference.docx"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Reference Certification Failed." not in body
    assert "Reference installed successfully." in body
    assert "Grade 10 / English" in body
    assert "Status: Certified" in body
    return client, data


@pytest.mark.live
def test_good_reference_certification_and_view(certified_client):
    client, data = certified_client
    page = client.get("/references")
    text = page.get_data(as_text=True)
    assert "10" in text
    assert "English" in text
    assert "English Reference.docx" in text
    assert "Certified" in text
    row = ReferenceRegistry(data).find("10", "English")
    assert row["handler"] == "subjects.english_10"
    assert row["certification_status"] == "certified"
    assert sha256_file(ReferenceRegistry(data).file_path(row)) == sha256_file(REFERENCE)


@pytest.mark.live
def test_duplicate_reference_leaves_certified_file(certified_client):
    client, data = certified_client
    before = sha256_file(ReferenceRegistry(data).file_path(ReferenceRegistry(data).find("10", "English")))
    response = client.post(
        "/reference",
        data={
            "grade": "10",
            "subject": "English",
            "reference": (BAD_REFERENCE.open("rb"), "bad_reference.docx"),
        },
        content_type="multipart/form-data",
    )
    text = response.get_data(as_text=True)
    assert "Reference already exists for Grade 10 / English." in text
    assert "Delete the existing Reference before adding another." in text
    after = ReferenceRegistry(data).find("10", "English")
    assert after["filename"] == "English Reference.docx"
    assert sha256_file(ReferenceRegistry(data).file_path(after)) == before


@pytest.mark.live
def test_good_english_exam_and_academic_integrity(certified_client):
    client, _data = certified_client
    response = _format(client, TEACHER, "good_teacher.docx")
    assert response.status_code == 200
    assert "formatted.docx" in response.headers["Content-Disposition"]
    formatted = response.data
    text = _text(formatted)
    teacher = _text(TEACHER.read_bytes())
    assert "Ashoka" in text
    assert "Section A" in text
    assert "Section B" in text
    assert "Section C" in text
    assert "Section D" in text
    assert _DOUBLE_LABEL.search(text) is None
    assert _image_count(formatted) == _image_count(TEACHER.read_bytes())
    assert "Emperor Ashoka was one of the earliest Indian monarchs" in text
    for mark in ("(1x5=5)",):
        if mark in teacher:
            assert mark in text


@pytest.mark.live
def test_bad_english_exam_error_fix(certified_client):
    client, _data = certified_client
    bad = FIXTURES / "bad_teacher.docx"
    response = _format(client, bad, "bad_teacher.docx")
    assert response.status_code == 200
    assert "CORRECTIONS.docx" in response.headers["Content-Disposition"]
    text = _text(response.data)
    assert "ERROR: Class header is missing." in text
    assert "ERROR: Section C is missing." in text
    assert "FIX:" in text
    assert "Section-D" in text.replace(" ", "")


@pytest.mark.live
def test_english_round_trip(certified_client, tmp_path):
    client, _data = certified_client
    first = _format(client, TEACHER, "good_teacher.docx")
    first_path = tmp_path / "once.docx"
    first_path.write_bytes(first.data)
    second = _format(client, first_path, "once.docx")
    assert second.status_code == 200
    assert "CORRECTIONS" not in second.headers.get("Content-Disposition", "")
    first_text = _paragraphs(first.data)
    second_text = _paragraphs(second.data)
    assert second_text == first_text
    assert _DOUBLE_LABEL.search("\n".join(second_text)) is None
    assert _image_count(second.data) == _image_count(first.data)
    joined = "\n".join(second_text)
    assert joined.count("Section A") == 1
    assert joined.count("Section D") == 1


def _format(client, path: Path, filename: str):
    return client.post(
        "/format",
        data={"grade": "10", "subject": "English", "teacher": (path.open("rb"), filename)},
        content_type="multipart/form-data",
    )


def _text(data: bytes) -> str:
    return "\n".join(_paragraphs(data))


def _paragraphs(data: bytes) -> list[str]:
    document = Document(io.BytesIO(data))
    return [paragraph.text for paragraph in document.paragraphs]


def _image_count(data: bytes) -> int:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return sum(1 for name in archive.namelist() if name.startswith("word/media/"))
