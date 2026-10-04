"""Routing uses grade and subject, and does not borrow another compartment."""

from pathlib import Path

from docx import Document

from app.reference_registry import ReferenceRegistry
from app.routing import compartment_name, display_pair, handler_matches, normalize
from app.web import create_app, missing_reference_message, unavailable_message


def test_grade_and_subject_are_the_routing_key():
    assert normalize("10", "English") == normalize("Grade 10", "ENGLISH")
    assert normalize("10", "english") == ("10", "english")
    assert display_pair("grade 10", "ENGLISH") == ("10", "English")
    assert compartment_name("10", "English") == "subjects.english_10"
    assert compartment_name("10", "Math") == "subjects.math_10"
    assert compartment_name("10", "Mathematics") is None
    assert handler_matches("10", "English", "subjects.english_10")
    assert handler_matches("10", "Math", "subjects.english_10") is False
    assert handler_matches("10", "Math", "subjects.math_10")


def test_missing_reference_stops_before_formatting(tmp_path):
    app = create_app(tmp_path)
    client = app.test_client()
    upload = _docx(tmp_path / "teacher.docx", "A teacher exam.")
    response = client.post(
        "/format",
        data={"grade": "8", "subject": "Science", "teacher": (upload.open("rb"), "teacher.docx")},
        content_type="multipart/form-data",
    )
    assert missing_reference_message("8", "Science") in response.get_data(as_text=True)
    assert response.status_code == 200


def test_math_reference_does_not_use_english(tmp_path, monkeypatch):
    registry_root = tmp_path / "data"
    app = create_app(registry_root)
    registry = app.config["DATA_ROOT"]
    store = ReferenceRegistry(registry)
    math_file = _docx(tmp_path / "math.docx", "Math reference.")
    store.install("10", "Math", "Math10.docx", math_file, "subjects.math_10")

    def explode(*_args, **_kwargs):
        raise AssertionError("English formatter was called for Math")

    monkeypatch.setattr("subjects.english_10.service.format_exam", explode)
    client = app.test_client()
    teacher = _docx(tmp_path / "teacher.docx", "A teacher exam.")
    response = client.post(
        "/format",
        data={"grade": "10", "subject": "Math", "teacher": (teacher.open("rb"), "teacher.docx")},
        content_type="multipart/form-data",
    )
    body = response.get_data()
    assert response.status_code == 200
    assert unavailable_message("10", "Math").encode() not in body
    assert b"subjects.english_10" not in body
    assert (Path(registry) / "references" / "registry.json").is_file()


def _docx(path: Path, text: str) -> Path:
    document = Document()
    document.add_paragraph(text)
    document.save(str(path))
    return path
