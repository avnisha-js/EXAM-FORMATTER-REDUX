"""Reference install, rejection, and view behavior in the common application."""

from pathlib import Path

from app.reference_registry import ReferenceRegistry
from app.web import create_app, duplicate_message
from common.hashing import sha256_file

FIXTURES = Path(__file__).resolve().parents[1] / "subjects" / "english_10" / "tests" / "fixtures"
GOOD = FIXTURES / "good_reference.docx"
BAD = FIXTURES / "bad_reference.docx"


def test_bad_reference_is_not_activated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "subjects.english_10.processor.discover._call_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("model called")),
    )
    app = create_app(tmp_path)
    client = app.test_client()
    response = client.post(
        "/reference",
        data={"grade": "10", "subject": "English", "reference": (BAD.open("rb"), "bad_reference.docx")},
        content_type="multipart/form-data",
    )
    assert "Reference Certification Failed." in response.get_data(as_text=True)
    assert ReferenceRegistry(tmp_path).rows() == []


def test_failed_add_does_not_replace_the_active_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "subjects.english_10.processor.discover._call_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("model called")),
    )
    registry = ReferenceRegistry(tmp_path)
    registry.install("10", "English", "English10.docx", GOOD, "subjects.english_10")
    original = sha256_file(registry.file_path(registry.find("10", "English")))
    app = create_app(tmp_path)
    client = app.test_client()
    response = client.post(
        "/reference",
        data={"grade": "10", "subject": "english", "reference": (BAD.open("rb"), "bad_reference.docx")},
        content_type="multipart/form-data",
    )
    assert duplicate_message(registry.find("10", "English")) in response.get_data(as_text=True)
    current = registry.find("10", "ENGLISH")
    assert current["filename"] == "English10.docx"
    assert current["certification_status"] == "certified"
    assert sha256_file(registry.file_path(current)) == original


def test_view_references_lists_the_certified_row(tmp_path):
    registry = ReferenceRegistry(tmp_path)
    registry.install("10", "English", "English10.docx", GOOD, "subjects.english_10")
    app = create_app(tmp_path)
    client = app.test_client()
    text = client.get("/references").get_data(as_text=True)
    assert "English" in text
    assert "English10.docx" in text
    assert "Certified" in text
    again = client.post(
        "/reference",
        data={"grade": "Grade 10", "subject": "ENGLISH", "reference": (GOOD.open("rb"), "other.docx")},
        content_type="multipart/form-data",
    )
    body = again.get_data(as_text=True)
    assert "Reference already exists for Grade 10 / English." in body
    assert "Delete the existing Reference before adding another." in body
