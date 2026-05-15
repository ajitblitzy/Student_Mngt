"""
Flask application module for the Student Report Generator.

This module is the Python 3 port of the original browser-side JavaScript
Student Report Generator (preserved verbatim inside
``Student Report Generator Javascript Pdf.pdf`` at the repository root and
mirrored in the original ``Readme.md``). The refactor is governed by the
user rule ``Ajit_Test_Refactor`` ("Refactor the code without changing the
functionality"), so every observable behaviour of the original
application is preserved here line-for-line:

* The HTML form continues to accept exactly the seven fields
  ``studentName``, ``rollNumber``, ``maths``, ``science``, ``english``,
  ``history``, ``computer``.
* The total is the sum of the five subject marks; the percentage is
  computed as ``(total / 500) * 100`` (two-decimal formatted); the grade
  is the same six-tier cascade ``A+`` / ``A`` / ``B`` / ``C`` / ``D`` /
  ``F`` with inclusive thresholds at 90, 80, 70, 60, 50.
* The downloaded PDF contains the title "Student Report Card" and the
  five labelled lines for name, roll number, total, percentage (with
  a trailing ``%``), and grade, drawn at the same millimetre
  coordinates and font sizes as the original jsPDF output. The
  filename is ``{name}_Report.pdf`` derived from the on-screen
  rendered name (not the raw form input), matching the original JS
  behaviour of reading ``document.getElementById('rName').innerText``.

The module exposes:

* :data:`app` -- the :class:`flask.Flask` application instance.
* :data:`SUBJECT_FIELDS` -- the canonical, ordered list of subject
  display names.
* :func:`compute_report` -- pure helper equivalent to the original JS
  ``generateReport()`` function; returns a dict that drives both the
  Jinja2 template and the PDF builder.
* :func:`build_report_pdf` -- pure helper equivalent to the original JS
  ``downloadPDF()`` function; returns a :class:`io.BytesIO` containing
  the rendered PDF bytes.
* :func:`index` / :func:`generate_report` / :func:`download_pdf` --
  the three Flask route handlers wiring HTTP requests to the helpers.

Run with ``flask --app app run`` or ``python app.py`` for the
default development server on ``http://127.0.0.1:5000``.
"""

from io import BytesIO

from flask import Flask, render_template, request, send_file
from fpdf import FPDF


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Canonical, ORDERED list of subject display names. The order MUST be
# Maths -> Science -> English -> History -> Computer to match the
# original JavaScript object literal iteration order
# (``for (let subject in subjects)`` in the source ``script.js``).
# ECMAScript guarantees insertion-ordered iteration for string keys and
# Python 3.7+ dicts/lists also guarantee insertion order, so this single
# constant pins the order for both the on-screen marks table (rendered
# by templates/index.html) and the per-subject row creation done by
# ``compute_report`` below.
#
# The HTML form field ``name`` attributes are the lowercased forms of
# these display names (``maths``, ``science``, ``english``, ``history``,
# ``computer``) -- ``compute_report`` derives the form key by calling
# ``.lower()`` on each entry of this list.
SUBJECT_FIELDS = ["Maths", "Science", "English", "History", "Computer"]


# ---------------------------------------------------------------------------
# Flask application instance
# ---------------------------------------------------------------------------

# ``Flask(__name__)`` autodiscovers the sibling ``templates/`` and
# ``static/`` directories. No additional configuration is required for
# the development server; production deployments are out of scope for
# this refactor (see AAP Section 0.3.2).
app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helper: compute_report
# ---------------------------------------------------------------------------

def compute_report(form_data):
    """Compute the student report from posted form data.

    Python equivalent of the original JavaScript ``generateReport()``
    function (see ``Readme.md`` lines 162-213 and pages 4-5 of
    ``Student Report Generator Javascript Pdf.pdf``).

    Args:
        form_data: A mapping (typically ``flask.request.form``, which is
            a :class:`werkzeug.datastructures.ImmutableMultiDict`) whose
            keys include ``studentName``, ``rollNumber``, ``maths``,
            ``science``, ``english``, ``history``, ``computer``. Missing
            keys are treated as empty strings, matching the browser-side
            behaviour where ``document.getElementById(...).value``
            returns ``""`` for an empty ``<input>``.

    Returns:
        dict: A dictionary with the following keys, suitable for passing
        directly to :func:`flask.render_template` or
        :func:`build_report_pdf`:

        * ``name`` (str) -- raw student name from the form.
        * ``roll`` (str) -- raw roll number from the form.
        * ``subjects`` (list of (str, int) tuples) -- one entry per
          subject in canonical order ``[Maths, Science, English,
          History, Computer]``.
        * ``total`` (int) -- sum of the five subject marks.
        * ``percentage`` (float) -- ``(total / 500) * 100`` using true
          division (Python 3 ``/`` operator).
        * ``percentage_str`` (str) -- ``percentage`` formatted with two
          decimal places (equivalent to JavaScript
          ``percentage.toFixed(2)``).
        * ``grade`` (str) -- one of ``'A+'``, ``'A'``, ``'B'``, ``'C'``,
          ``'D'``, ``'F'`` per the inclusive-threshold cascade.
    """
    # Raw text fields -- same default ("" for missing input) as the
    # browser-side reads via ``.value`` on a text input.
    name = form_data.get("studentName", "")
    roll = form_data.get("rollNumber", "")

    # Build the ordered list of (display_name, integer_marks) tuples.
    # The ``or 0`` idiom mirrors the original JS ``parseInt(value || 0)``
    # so that:
    #   - an empty string from a blank <input type="number"> coerces to 0
    #   - a missing key (form_data.get returns "") also coerces to 0
    # This preserves the original "no validation, blank means zero"
    # contract; do NOT replace with a stricter int() call (would raise
    # on empty inputs and break behaviour).
    subjects = []
    for subject_name in SUBJECT_FIELDS:
        # HTML <input> name attributes are lowercased subject names
        # (see templates/index.html: id="maths" name="maths", etc.).
        raw_value = form_data.get(subject_name.lower(), "")
        marks = int(raw_value or 0)
        subjects.append((subject_name, marks))

    # Total marks: a plain sum across the five tuples. The total is
    # always an int because every entry in ``subjects`` is int-typed
    # by the conversion above.
    total = sum(marks for _, marks in subjects)

    # Percentage: Python 3 ``/`` performs true division and yields a
    # float. The maximum possible total is hardcoded at 500 (five
    # subjects times 100) per the original source -- this is a fixed
    # divisor and MUST NOT be parameterised (AAP Section 0.1.3).
    percentage = (total / 500) * 100

    # Two-decimal string form. JavaScript's ``toFixed(2)`` rounds
    # half-away-from-zero for the positive doubles produced here;
    # Python's f-string ``:.2f`` format also rounds (banker's rounding
    # via ``format``) which is observationally equivalent for the
    # integer-total inputs in ``[0, 500]``.
    percentage_str = f"{percentage:.2f}"

    # Six-tier grade cascade: the order and the ``>=`` comparators are
    # preserved from the original ``if / else if`` chain. The default
    # 'F' is reached when percentage is strictly less than 50 (which
    # also covers the all-blanks "total == 0" case).
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
        "total": total,
        "percentage": percentage,
        "percentage_str": percentage_str,
        "grade": grade,
    }


# ---------------------------------------------------------------------------
# Helper: build_report_pdf
# ---------------------------------------------------------------------------

def build_report_pdf(report):
    """Build the downloadable PDF report from a computed report dict.

    Python equivalent of the original JavaScript ``downloadPDF()``
    function (see ``Readme.md`` lines 215-237 and pages 5-6 of
    ``Student Report Generator Javascript Pdf.pdf``).

    The PDF layout mirrors the original jsPDF output exactly:

    * Page format A4 in millimetre units (jsPDF defaults).
    * Title "Student Report Card" in Helvetica 18 at (20, 20).
    * Five body lines in Helvetica 12 at x = 20 mm and y = 40, 50, 60,
      70, 80 mm, each carrying a literal label followed by the
      corresponding report field value. The percentage line ends in a
      literal ``%`` character matching the original
      ``Percentage: ${percentage}%`` template.

    The text is drawn via :meth:`fpdf.FPDF.text` which positions text
    at the baseline -- the same convention jsPDF uses for
    ``doc.text(text, x, y)`` -- so the y-coordinates do not need any
    adjustment between the two libraries.

    Args:
        report: A dict carrying the fields rendered on-screen by the
            report card region. Required keys are ``name``, ``roll``,
            ``total``, ``percentage_str``, ``grade``. The values may be
            either the native types returned by :func:`compute_report`
            (e.g. ``total`` as int) or string forms supplied by the
            hidden ``#downloadForm`` inputs (e.g. ``total`` as str).
            Both are handled because f-string interpolation calls
            ``str()`` on the value.

    Returns:
        io.BytesIO: A binary stream containing the rendered PDF
        document, with the read cursor positioned at byte 0 so the
        caller (typically :func:`flask.send_file`) can stream it to
        the response immediately.
    """
    # jsPDF defaults: ``new jsPDF()`` constructs a portrait A4 page in
    # millimetres. fpdf2's matching constructor call is explicit here.
    pdf = FPDF(unit="mm", format="A4")
    pdf.add_page()

    # Title -- Helvetica 18, drawn at (20, 20) just like the source.
    pdf.set_font("Helvetica", size=18)
    pdf.text(20, 20, "Student Report Card")

    # Body lines -- Helvetica 12, drawn at the same y-baselines
    # (40, 50, 60, 70, 80) as the original. The label strings and
    # punctuation must be byte-identical to the original; the
    # percentage line specifically retains the trailing ``%``.
    pdf.set_font("Helvetica", size=12)
    pdf.text(20, 40, f"Student Name: {report['name']}")
    pdf.text(20, 50, f"Roll Number: {report['roll']}")
    pdf.text(20, 60, f"Total Marks: {report['total']}")
    pdf.text(20, 70, f"Percentage: {report['percentage_str']}%")
    pdf.text(20, 80, f"Grade: {report['grade']}")

    # fpdf2 2.8.x's ``output()`` with no args returns a ``bytearray``.
    # Wrap in BytesIO so the caller can stream the bytes through
    # ``flask.send_file`` like any other file-like object.
    pdf_bytes = pdf.output()
    buffer = BytesIO(bytes(pdf_bytes))
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Render the empty form (no initial report).

    Equivalent to the original "open ``index.html`` in the browser"
    entry point. The Jinja2 template ``templates/index.html`` handles
    the ``report is None`` case by leaving the report card spans empty
    and the hidden ``#downloadForm`` inputs blank, so the page is in
    a known empty state until the user submits the form.
    """
    return render_template("index.html", report=None)


@app.route("/generate-report", methods=["POST"])
def generate_report():
    """Compute the report and re-render the full page populated.

    Replaces the original JavaScript ``generateReport()`` function. The
    response is a full HTML page rendered from the same template used
    by :func:`index`; ``static/js/script.js`` patches the populated
    ``#reportCard`` region and ``#downloadForm`` hidden inputs into
    the current page without a full reload, while a no-JavaScript
    browser still gets a usable full-page response.
    """
    report = compute_report(request.form)
    return render_template("index.html", report=report)


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    """Build a PDF from the rendered report values and stream it back.

    Replaces the original JavaScript ``downloadPDF()`` function. The
    hidden ``#downloadForm`` in ``templates/index.html`` carries the
    already-rendered values (name, roll, total, percentage_str, grade)
    so this endpoint does NOT recompute them -- it serialises whatever
    was last shown to the user on the report card. This preserves the
    original behaviour where ``downloadPDF()`` read the rendered DOM
    via ``document.getElementById('rName').innerText`` rather than the
    raw form inputs.

    The response carries ``Content-Disposition: attachment;
    filename="<name>_Report.pdf"`` so the browser presents a native
    file-save dialog matching the original ``doc.save(...)`` behaviour.
    """
    # Defensive defaults match the empty-form starting state for the
    # corresponding hidden fields in templates/index.html; missing
    # values yield a PDF with empty labels rather than a 500 error.
    report = {
        "name": request.form.get("name", ""),
        "roll": request.form.get("roll", ""),
        "total": request.form.get("total", "0"),
        "percentage_str": request.form.get("percentage_str", "0.00"),
        "grade": request.form.get("grade", "F"),
    }

    pdf_buffer = build_report_pdf(report)

    # Filename pattern preserved verbatim from the original
    # ``doc.save(`${name}_Report.pdf`)`` call. The ``name`` here comes
    # from the rendered (computed) span, not the raw form input,
    # because the hidden form carries the rendered values.
    filename = f"{report['name']}_Report.pdf"

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


# ---------------------------------------------------------------------------
# Run-time entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Plain Flask development server on the default host/port
    # (127.0.0.1:5000). ``debug=True`` enables the reloader and an
    # interactive traceback page; this is appropriate for local
    # development use, which is the only deployment mode in scope for
    # this refactor (see AAP Section 0.8.3).
    app.run(debug=True)
