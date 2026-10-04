"""English 10 reference certification. This file does not use the GUI."""

from pathlib import Path

from subjects.english_10.certification.checks import structural_problem
from subjects.english_10.processor.discover import (
    enforce_english_question_heads,
    enforce_english_sections,
    settle_english_other_blocks,
)
from subjects.english_10.processor.models import Block
from subjects.english_10.processor.validate import _leading_int
from subjects.english_10.reference.session import prepared_reference
from subjects.english_10.service import certify_reference

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOD = FIXTURES / "good_reference.docx"
BAD = FIXTURES / "bad_reference.docx"


def test_q9_branch_still_counts_as_question_nine():
    policy = type("Policy", (), {"source": "compatibility", "major": "Q{n})"})()
    assert _leading_int("Q1. Read the following passage", policy) == 1
    assert _leading_int("Q9(a). Read the extract carefully", policy) == 9
    assert _leading_int("Q16. Answer the following question", policy) == 16


def test_q9_heads_stay_on_question_nine():
    carrier = Block("p0072", 72, "Q9(a). Read the extract", block_type="branch", parent_id="p0061")
    sibling = Block("p0089", 89, "Q9(b). Another extract", block_type="major_question")
    enforce_english_question_heads([carrier, sibling])
    assert carrier.block_type == "major_question"
    assert carrier.parent_id is None
    assert carrier.branch_carrier is True
    assert carrier.original_text.startswith("Q9(a).")
    assert sibling.block_type == "branch"
    assert sibling.parent_id == "p0072"


def test_a_false_major_does_not_replace_q_questions():
    real = Block("p0020", 20, "Q1. Read the passage", block_type="other")
    false_major = Block("p0017", 17, "READING", block_type="major_question")
    blank = Block("p0018", 18, "", block_type="other", parent_id="p0020")
    enforce_english_question_heads([real, false_major, blank])
    settle_english_other_blocks([real, false_major, blank])
    assert real.block_type == "major_question"
    assert false_major.block_type == "other"
    assert false_major.parent_id is None
    assert blank.parent_id is None
    assert false_major.original_text == "READING"


def test_a_written_section_heading_is_not_dropped():
    heading = Block("p0022", 22, "Section - C", block_type="other", parent_id="p0020")
    enforce_english_sections([heading], ["Section A", "Section B", "Section C", "Section D"])
    assert heading.block_type == "section"
    assert heading.parent_id is None
    assert heading.original_text == "Section - C"


def test_good_reference_structure_is_recognized():
    with prepared_reference(GOOD) as profile:
        assert structural_problem(profile) is None


def test_bad_reference_is_rejected_before_discovery(monkeypatch):
    monkeypatch.setattr(
        "subjects.english_10.processor.discover._call_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("model called")),
    )
    result = certify_reference(BAD)
    assert result.ok is False
    assert result.kind == "rejected"
    assert result.message.startswith("Reference Certification Failed.")
    assert "Section headings could not be discovered." in result.message
