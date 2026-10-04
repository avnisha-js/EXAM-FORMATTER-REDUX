"""Browser GUI for reference management and exam formatting."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for

from app.reference_registry import ReferenceRegistry
from app.routing import display_pair, handler_matches, load_compartment
from common.files import is_docx_name, temporary_docx

LOGGER = logging.getLogger("exam_formatter")
ROOT = Path(__file__).resolve().parents[1]


def missing_reference_message(grade: str, subject: str) -> str:
    shown_grade, shown_subject = display_pair(grade, subject)
    return (
        f"No Reference Exam found for Grade {shown_grade} / {shown_subject}.\n"
        "Add the Reference Exam first."
    )


def unavailable_message(grade: str, subject: str) -> str:
    shown_grade, shown_subject = display_pair(grade, subject)
    return f"Grade {shown_grade} / {shown_subject} is not yet certified for formatting."


def duplicate_message(row: dict) -> str:
    return (
        f"Reference already exists for Grade {row['grade']} / {row['subject']}.\n"
        "Delete the existing Reference before adding another."
    )


def installed_message(row: dict) -> str:
    return (
        "Reference installed successfully.\n"
        f"Grade {row['grade']} / {row['subject']}\n"
        "Status: Certified"
    )


def create_app(data_root: str | Path | None = None) -> Flask:
    root = Path(data_root) if data_root is not None else ROOT / "data"
    root.mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "outputs").mkdir(parents=True, exist_ok=True)
    _configure_logging(root / "logs" / "app.log")

    app = Flask(__name__)
    app.config["DATA_ROOT"] = root
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    registry = ReferenceRegistry(root)

    @app.get("/")
    def home():
        return render_template("index.html", message=request.args.get("message", ""), error=request.args.get("error", ""))

    @app.get("/format")
    def format_form():
        return render_template("format.html", message=request.args.get("message", ""), error=request.args.get("error", ""))

    @app.post("/format")
    def format_exam():
        grade = request.form.get("grade", "")
        subject = request.form.get("subject", "")
        upload = request.files.get("teacher")
        shown_grade, shown_subject = display_pair(grade, subject)
        if not shown_grade or not shown_subject:
            return render_template("format.html", error="Enter a grade and a subject.")
        if upload is None or not is_docx_name(upload.filename):
            return render_template("format.html", error="Upload a Word exam (.docx).")
        row = registry.find(grade, subject)
        if row is None:
            LOGGER.info("format stopped: no reference grade=%s subject=%s", shown_grade, shown_subject)
            return render_template("format.html", error=missing_reference_message(grade, subject))
        if not handler_matches(row["grade"], row["subject"], row.get("handler", "")):
            LOGGER.info("format stopped: compartment unavailable grade=%s subject=%s", row["grade"], row["subject"])
            return render_template("format.html", error=unavailable_message(row["grade"], row["subject"]))
        module = load_compartment(row["grade"], row["subject"])
        if module is None:
            return render_template("format.html", error=unavailable_message(row["grade"], row["subject"]))
        data = upload.read()
        temporary = temporary_docx(data)
        stem = Path(upload.filename or "exam").stem
        try:
            reference = registry.file_path(row)
            probe = module.validate_exam(reference, temporary)
            suffix = " CORRECTIONS.docx" if probe.kind == "nonconformance" else " formatted.docx"
            output = root / "outputs" / _safe_stem(stem + suffix)
            result = module.format_exam(reference, temporary, output)
        except Exception:
            LOGGER.exception("format failed grade=%s subject=%s", shown_grade, shown_subject)
            return render_template("format.html", error="Formatting failed. The exam was not saved.")
        finally:
            temporary.unlink(missing_ok=True)
        if result.kind in {"formatted", "corrections"} and result.output_path:
            LOGGER.info("format delivered kind=%s grade=%s subject=%s", result.kind, shown_grade, shown_subject)
            return send_file(result.output_path, as_attachment=True, download_name=Path(result.output_path).name)
        LOGGER.info("format failed grade=%s subject=%s", shown_grade, shown_subject)
        return render_template("format.html", error=result.message)

    @app.get("/reference")
    def add_reference_form():
        return render_template("add_reference.html", message=request.args.get("message", ""), error=request.args.get("error", ""))

    @app.post("/reference")
    def add_reference():
        grade = request.form.get("grade", "")
        subject = request.form.get("subject", "")
        upload = request.files.get("reference")
        shown_grade, shown_subject = display_pair(grade, subject)
        if not shown_grade or not shown_subject:
            return render_template("add_reference.html", error="Enter a grade and a subject.")
        if upload is None or not is_docx_name(upload.filename):
            return render_template("add_reference.html", error="Upload a Word reference (.docx).")
        existing = registry.find(grade, subject)
        if existing:
            LOGGER.info("reference add refused: already exists grade=%s subject=%s", existing["grade"], existing["subject"])
            return render_template("add_reference.html", error=duplicate_message(existing))
        if load_compartment(grade, subject) is None:
            LOGGER.info("reference add refused: no compartment grade=%s subject=%s", shown_grade, shown_subject)
            return render_template("add_reference.html", error=unavailable_message(grade, subject))
        module = load_compartment(grade, subject)
        temporary = temporary_docx(upload.read())
        try:
            certified = module.certify_reference(temporary)
            if not certified.ok:
                LOGGER.info("reference certification rejected grade=%s subject=%s", shown_grade, shown_subject)
                return render_template("add_reference.html", error=certified.message)
            if not handler_matches(grade, subject, module.HANDLER_ID):
                return render_template("add_reference.html", error=unavailable_message(grade, subject))
            row = registry.install(grade, subject, upload.filename or "reference.docx", temporary, module.HANDLER_ID)
        except Exception:
            LOGGER.exception("reference add failed grade=%s subject=%s", shown_grade, shown_subject)
            return render_template("add_reference.html", error="Reference Certification Failed.\nThe reference could not be installed.")
        finally:
            temporary.unlink(missing_ok=True)
        LOGGER.info("reference installed grade=%s subject=%s handler=%s", row["grade"], row["subject"], row["handler"])
        return redirect(url_for("view_references", message=installed_message(row)))

    @app.get("/references")
    def view_references():
        return render_template(
            "references.html",
            rows=registry.rows(),
            message=request.args.get("message", ""),
            error=request.args.get("error", ""),
        )

    @app.post("/references/delete")
    def delete_reference():
        grade = request.form.get("grade", "")
        subject = request.form.get("subject", "")
        row = registry.find(grade, subject)
        if row is None:
            return redirect(url_for("view_references", error=missing_reference_message(grade, subject)))
        registry.delete(grade, subject)
        LOGGER.info("reference deleted grade=%s subject=%s", row["grade"], row["subject"])
        return redirect(url_for("view_references", message=f"Deleted Grade {row['grade']} / {row['subject']}."))

    return app


def _configure_logging(log_path: Path) -> None:
    LOGGER.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    if not any(type(handler) is logging.StreamHandler for handler in LOGGER.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        LOGGER.addHandler(stream)
    for handler in list(LOGGER.handlers):
        if isinstance(handler, logging.FileHandler):
            LOGGER.removeHandler(handler)
            handler.close()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    logging.getLogger("exam_formatter.english_10").setLevel(logging.INFO)
    logging.getLogger("exam_formatter.math_10").setLevel(logging.INFO)


def _safe_stem(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " ._-()" else "_" for ch in name).strip()
    return cleaned or "exam.docx"
