"""English 10 hierarchy pipeline.

Discovery, numbering, and integrity stay inside this compartment.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from subjects.english_10.processor.discover import discover, reference_convention_notes
from subjects.english_10.processor.extract import extract_document
from subjects.english_10.processor.integrity import integrity
from subjects.english_10.processor.models import clone_blocks
from subjects.english_10.processor.number import labels_are_stable
from subjects.english_10.processor.validate import validate
from subjects.english_10.reference.images import load_image_policy
from subjects.english_10.reference.numbering import load_numbering_policy
from subjects.english_10.reference.sections import required_section_headings
from subjects.english_10.reference.session import current_profile_dir, prepared_reference
from subjects.english_10.reference.syllabus import load_syllabus_policy

LOGGER = logging.getLogger("exam_formatter.english_10")


def _line(block) -> str:
    parent = block.parent_id or "-"
    label = block.final_label or "-"
    text = block.original_text.replace("\n", " ")
    return f"{block.source_id} | {block.block_type:<16} | {parent:<8} | {label:<16} | {text}"


def _tree_lines(blocks) -> list[str]:
    by_parent: dict[str | None, list] = {}
    ordered = sorted(
        blocks,
        key=lambda b: (b.source_order, 0 if b.source_id.startswith("p") else 1, b.source_id),
    )
    for block in ordered:
        by_parent.setdefault(block.parent_id, []).append(block)
    lines: list[str] = []

    def walk(node, depth: int) -> None:
        label = node.final_label if node.final_label and node.final_label != "-" else node.block_type
        text = node.original_text.replace("\n", " ")
        if len(text) > 140:
            text = text[:137] + "..."
        lines.append(f"{'  ' * depth}{node.source_id} {label} {text}".rstrip())
        for child in by_parent.get(node.source_id, []):
            walk(child, depth + 1)

    for root in [b for b in ordered if not b.parent_id]:
        walk(root, 0)
    return lines


def run_pipeline_stable(
    teacher: Path,
    reference: Path,
    out_dir: Path,
    log_context: str | None = None,
) -> dict:
    """Run discovery twice at most. The second pass is used only when validation fails."""
    result = run_pipeline(teacher, reference, out_dir, log_context)
    if result["ok"]:
        return result
    LOGGER.info("[%s] English 10 discovery did not validate; trying once more", log_context or teacher.name)
    return run_pipeline(teacher, reference, out_dir, log_context)


def run_pipeline(
    teacher: Path,
    reference: Path,
    out_dir: Path,
    log_context: str | None = None,
) -> dict:
    if current_profile_dir() is None:
        with prepared_reference(reference):
            return _run_pipeline(teacher, reference, out_dir, log_context)
    return _run_pipeline(teacher, reference, out_dir, log_context)


def _run_pipeline(teacher: Path, reference: Path, out_dir: Path, log_context: str | None) -> dict:
    context = log_context or teacher.name
    started = time.monotonic()
    LOGGER.info("[%s] English 10 pipeline started teacher=%s reference=%s", context, teacher.name, reference.name)

    source = extract_document(teacher)
    reference_blocks = extract_document(reference)
    section_headings = required_section_headings(reference)
    numbering_policy = load_numbering_policy(reference)
    syllabus_policy = load_syllabus_policy(reference)
    image_policy = load_image_policy(reference)
    notes = reference_convention_notes(reference_blocks, section_headings, numbering_policy)

    blocks = clone_blocks(source)
    LOGGER.info(
        "[%s] hierarchy discovery started model=%s blocks=%d",
        context,
        os.environ.get("EXAM_REDO_MODEL", "gpt-4.1"),
        len(blocks),
    )
    discover(blocks, notes, section_headings, numbering_policy, syllabus_policy.heading)
    stable = labels_are_stable(blocks, numbering_policy)
    problems = validate(blocks, stable, numbering_policy, image_policy)
    checks = integrity(source, blocks, image_policy)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "hierarchy.json").write_text(
        json.dumps([b.to_dict() for b in blocks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ordered = sorted(blocks, key=lambda b: (b.source_order, 0 if b.source_id.startswith("p") else 1, b.source_id))
    flat = ["SOURCE | TYPE | PARENT | FINAL LABEL | TEXT", *(_line(b) for b in ordered)]
    (out_dir / "hierarchy.txt").write_text("\n".join(flat + ["", "TREE", *_tree_lines(blocks)]) + "\n", encoding="utf-8")
    review = [b for b in blocks if b.review_required]
    integrity_lines = ["INTEGRITY"]
    for name, ok, detail in checks:
        integrity_lines.append(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    integrity_lines.append("")
    integrity_lines.append("VALIDATION")
    integrity_lines.extend(f"FAIL {item}" for item in problems) if problems else integrity_lines.append("PASS structural invariants")
    integrity_lines.append("")
    integrity_lines.append(f"NUMBERING_STABLE {'PASS' if stable else 'FAIL'}")
    integrity_lines.append(f"REVIEW_REQUIRED {len(review)}")
    (out_dir / "integrity.txt").write_text("\n".join(integrity_lines) + "\n", encoding="utf-8")

    ok = not problems and all(flag for _, flag, _ in checks)
    LOGGER.info("[%s] English 10 pipeline complete ok=%s elapsed=%.2fs", context, ok, time.monotonic() - started)
    if problems:
        LOGGER.error("[%s] validation problems: %s", context, problems)
    return {
        "ok": ok,
        "blocks": blocks,
        "problems": problems,
        "checks": checks,
        "review": review,
        "reference_notes": notes,
    }
