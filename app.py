"""Flask application for the Student Report Generator (Python 3 port).

Python 3 port of the original browser-side JavaScript Student Report
Generator, governed by the user rule ``Ajit_Test_Refactor`` (refactor
without changing functionality). See pages 1-7 of the repository file
``Student Report Generator Javascript Pdf.pdf`` for the authoritative
original implementation.
"""

import math
from io import BytesIO

from flask import Flask, render_template, request, send_file
from fpdf import FPDF


# Canonical, ORDERED subject display names. Order must remain
# Maths -> Science -> English -> History -> Computer to match the
# JavaScript object-literal iteration order from the original source
# (Student Report Generator Javascript Pdf.pdf pages 4-5). HTML form
# ``name`` attributes are the lowercased forms of these labels.
SUBJECT_FIELDS = ["Maths", "Science", "English", "History", "Computer"]


app = Flask(__name__)


def _parse_marks(raw_value):
    """Return marks for one subject; mirrors JS ``parseInt(value || 0)``.

    Empty / falsy input coerces to ``0``; a valid integer string returns
    the matching ``int``; any non-numeric bypass input returns
    ``float('nan')`` so NaN propagates through total / percentage just
    as ``parseInt('abc')`` did in the original page.
    """
    if not raw_value:
        return 0
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return float("nan")


def _display(value):
    """Render a numeric value as JavaScript ``innerText`` would.

    Maps Python NaN floats to the literal string ``"NaN"`` (matching
    ``String(NaN)`` and ``(NaN).toFixed(2)`` in JavaScript); leaves
    integer values untouched for natural Jinja2 / f-string interpolation.
    """
    if isinstance(value, float) and math.isnan(value):
        return "NaN"
    return value


def _safe_pdf_text(value):
    """Coerce text to a string safe for fpdf2 core Helvetica (Latin-1).

    fpdf2's built-in Helvetica supports only the Latin-1 / WinAnsi
    character set; characters outside that range raise
    ``FPDFUnicodeEncodingException``. Encoding through Latin-1 with
    ``errors='replace'`` substitutes unsupported code points with
    ``?``, matching jsPDF's lossy default-font behaviour.
    """
    return (
        str(value if value is not None else "")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )


def _safe_filename_base(value):
    """Sanitize a user string for use in a download filename.

    Strips ASCII control characters (0x00-0x1F and 0x7F) so CR / LF /
    NUL do not trigger Werkzeug's ``Header values must not contain
    newline characters`` rejection, and strips ``/`` and ``\\`` for
    filesystem safety. Non-ASCII characters pass through; Werkzeug
    renders them via RFC 5987 in the Content-Disposition header.
    """
    if not value:
        return ""
    return "".join(
        ch
        for ch in str(value)
        if not (0 <= ord(ch) < 32 or ord(ch) == 127)
        and ch not in ("/", "\\")
    )


def compute_report(form_data):
    """Build the report dict from submitted form data.

    Python equivalent of the original JavaScript ``generateReport()``
    function (see pages 4-5 of
    ``Student Report Generator Javascript Pdf.pdf``).

    Args:
        form_data: Mapping (e.g. ``flask.request.form``) with the seven
            keys ``studentName``, ``rollNumber``, ``maths``, ``science``,
            ``english``, ``history``, ``computer``. Missing keys default
            to ``""``.

    Returns:
        dict with keys ``name``, ``roll``, ``subjects`` (list of
        ``(label, marks)`` tuples in canonical order), ``total``,
        ``percentage`` (raw float, possibly NaN), ``percentage_str``,
        and ``grade``. Display fields render Python NaN as ``"NaN"``
        so on-screen output matches JavaScript ``innerText``.
    """
    name = form_data.get("studentName", "")
    roll = form_data.get("rollNumber", "")

    raw_marks = [
        _parse_marks(form_data.get(label.lower(), "")) for label in SUBJECT_FIELDS
    ]
    subjects = [
        (label, _display(marks)) for label, marks in zip(SUBJECT_FIELDS, raw_marks)
    ]

    # NaN propagates through sum() and division so a bypass non-numeric
    # mark renders as "NaN" everywhere, matching the JS source.
    total = sum(raw_marks)
    percentage = (total / 500) * 100
    if isinstance(percentage, float) and math.isnan(percentage):
        percentage_str = "NaN"
    else:
        percentage_str = f"{percentage:.2f}"

    # Six-tier grade cascade with inclusive thresholds. NaN comparisons
    # are False in both JS and Python so a NaN percentage falls through
    # to the default ``F`` (matching the original ``let grade = 'F'``).
    if percentage >= 90:
        grade = "A+"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 70:
        grade = "B"
    elif percentage >= 60:
        grade = "C"
    elif percentage >= 50:
        grade = "D"
    else:
        grade = "F"

    return {
        "name": name,
        "roll": roll,
        "subjects": subjects,
        "total": _display(total),
        "percentage": percentage,
        "percentage_str": percentage_str,
        "grade": grade,
    }


def build_report_pdf(report):
    """Build the downloadable PDF report from a computed report dict.

    Python equivalent of the original JavaScript ``downloadPDF()``
    function (see pages 5-6 of
    ``Student Report Generator Javascript Pdf.pdf``).

    Mirrors the jsPDF output exactly: A4 portrait in millimetres,
    Helvetica 18 title ``Student Report Card`` at (20, 20), Helvetica
    12 body lines for Student Name, Roll Number, Total Marks,
    Percentage (with trailing ``%``), and Grade at y = 40, 50, 60, 70,
    80 mm.

    Args:
        report: Dict with ``name``, ``roll``, ``total``,
            ``percentage_str``, and ``grade`` keys (native types or
            strings -- both interpolate cleanly).

    Returns:
        io.BytesIO: PDF bytes seeked to offset 0 for direct streaming
        through :func:`flask.send_file`.
    """
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_page()

    pdf.set_font("Helvetica", size=18)
    pdf.text(20, 20, _safe_pdf_text("Student Report Card"))

    pdf.set_font("Helvetica", size=12)
    pdf.text(20, 40, _safe_pdf_text(f"Student Name: {report['name']}"))
    pdf.text(20, 50, _safe_pdf_text(f"Roll Number: {report['roll']}"))
    pdf.text(20, 60, _safe_pdf_text(f"Total Marks: {report['total']}"))
    pdf.text(20, 70, _safe_pdf_text(f"Percentage: {report['percentage_str']}%"))
    pdf.text(20, 80, _safe_pdf_text(f"Grade: {report['grade']}"))

    buffer = BytesIO(bytes(pdf.output()))
    buffer.seek(0)
    return buffer


@app.route("/")
def index():
    """Render the empty form (no initial report)."""
    return render_template("index.html", report=None)


@app.route("/generate-report", methods=["POST"])
def generate_report():
    """Compute the report and re-render the populated page."""
    return render_template("index.html", report=compute_report(request.form))


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    """Build a PDF from the rendered report values and stream it back.

    Hidden ``#downloadForm`` fields carry the already-rendered values,
    matching the original ``document.getElementById('rName').innerText``
    read. The download filename uses a sanitized version of the
    rendered name so control characters do not trigger Werkzeug header
    rejection.
    """
    report = {
        "name": request.form.get("name", ""),
        "roll": request.form.get("roll", ""),
        "total": request.form.get("total", "0"),
        "percentage_str": request.form.get("percentage_str", "0.00"),
        "grade": request.form.get("grade", "F"),
    }
    filename = f"{_safe_filename_base(report['name'])}_Report.pdf"
    return send_file(
        build_report_pdf(report),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    # Local Flask development server on the default 127.0.0.1:5000
    # (only deployment mode in scope -- see AAP Section 0.8.3).
    app.run(debug=True)
