"""The real teacher file is inspected and not formatted."""

from pathlib import Path

from subjects.math_10.validator.compare import analyze_teacher

ROOT = Path(__file__).resolve().parents[3]
REFERENCE = ROOT / "input" / "math_10" / "reference" / "Reference Exam Math Grade 10.docx"
TEACHER = ROOT / "input" / "math_10" / "exams" / "Teacher Exam Math Grade 10 - Formatting Errors.docx"


def test_question_20_is_a_text_placeholder_and_numbering_differs():
    analysis = analyze_teacher(REFERENCE, TEACHER)
    assert analysis.ok
    assert analysis.unsupported == ()
    assert analysis.graph.startswith("C. text placeholder only")
    assert "[Image/graph in original examination]" in analysis.graph
    assert analysis.unicode_same
    assert analysis.numbering_semantics_same is False
    joined = "\n".join(analysis.differences)
    assert "Teacher 1\\tRational\\n" in joined
    assert "Ifa" not in joined
    assert "0and" not in joined
    assert "52x" not in joined
    assert "lowerLetter" in joined
    assert "page size and margins are not stored" in joined
    assert "12240" in joined
    assert "direct indent differs" in joined
    assert "Font or spacing differs" not in joined
    assert "alignment differs" not in joined
    assert "horizontal rule differs" not in joined
    assert "Objective-Type Questions" not in joined
    assert "Marks: 75" not in joined
