"""Grade 10 Math compartment.

Other subjects must not import this package to format their exams.
"""

from subjects.math_10.service import (
    GRADE_KEY,
    HANDLER_ID,
    SUBJECT_KEY,
    certify_reference,
    format_exam,
    validate_exam,
)

__all__ = [
    "GRADE_KEY",
    "HANDLER_ID",
    "SUBJECT_KEY",
    "certify_reference",
    "format_exam",
    "validate_exam",
]
