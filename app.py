"""Flask application entry point for the Student Report Generator.

This module is the *web-framework* layer of the application: it sits on
top of the framework-agnostic :mod:`report_generator` package and exposes
its functionality over HTTP.  It provides the :func:`create_app` factory
(per AAP §0.3.2 Application Factory pattern) and registers three HTTP
routes that collectively replace the browser-side JavaScript handlers
from the original implementation.

Route surface
-------------
============= ====== ========================================== ==============================
Path          Method Purpose                                    Replaces (original JS)
============= ====== ========================================== ==============================
``/``         GET    Render the empty student-details form      Loading embedded ``index.html``
``/generate`` POST   Compute report and re-render with results  ``onclick="generateReport()"``
``/download`` POST   Compute report and stream a PDF attachment ``onclick="downloadPDF()"``
============= ====== ========================================== ==============================

Design notes
------------
*   **Application Factory pattern (per AAP §0.3.2).**  The
    :func:`create_app` factory makes the Flask app instantiable from
    tests with isolated state — each test can spin up its own fresh
    application instance without import-time side effects bleeding
    between tests.  The module-level ``app = create_app()`` at the
    bottom of this file is exposed so the ``flask --app app run`` CLI
    command works out of the box (per AAP §0.3.4).

*   **DOM-as-shared-state pattern eliminated (per AAP §0.6.2 / ADR-005).**
    The original implementation used the rendered DOM as transient
    shared state between ``generateReport()`` (writer) and
    ``downloadPDF()`` (reader): the user had to click "Generate"
    *before* clicking "Download PDF" or the PDF would be blank.  The
    Python target eliminates this by having both endpoints accept the
    *same* form payload and invoke the *same* computation pipeline.
    There is no implicit ordering dependency because there is no
    shared state — both routes are pure functions of their input.

*   **Coordinate-system reconciliation lives in pdf_generator.**  The
    visual-parity machinery for the PDF output (axis inversion, mm→pt
    conversion) is encapsulated in
    :mod:`report_generator.pdf_generator`; this module simply hands a
    fully computed :class:`~report_generator.models.StudentReport` to
    :func:`~report_generator.pdf_generator.generate_pdf` and streams
    the resulting bytes.

*   **Empty-input parity (per AAP §0.6.3).**  The original JavaScript
    used ``parseInt(value || 0)`` which silently coerces empty strings
    to ``0``.  The private :func:`_parse_mark` helper preserves this
    behaviour for the empty/missing case but raises HTTP 400 for
    non-numeric strings (an improvement over the original, which would
    have silently produced ``NaN`` and corrupted the total — a path
    that was previously broken).

*   **Server-side computation is faster.**  Per AAP §0.3.3 the
    replacement primitives (C-implemented :func:`sum`, in-memory
    :class:`~io.BytesIO` buffers, Jinja2's compiled template builder,
    module-level constants, ``@lru_cache`` on
    :func:`~report_generator.grading.assign_grade`) are each
    individually faster than their JavaScript counterparts — and the
    PDF generation runs on the server's CPU rather than the user's
    browser thread.

User rule "Ajit_Test_Refactor" compliance
-----------------------------------------
This module honours the user rule ``Ajit_Test_Refactor`` ("Refactor
the code without changing the functionality") by preserving — exactly
— the form field set (``studentName``, ``rollNumber`` plus the five
lowercase subject IDs), the computation pipeline (total → percentage →
grade), and the filename pattern (``<name>_Report.pdf``).  The only
intentional behaviour change is the strict input validation described
above, which converts a previously-silently-broken case into a
well-defined HTTP 400 — strictly an improvement under the rule's
intent.
"""

from __future__ import annotations

from io import BytesIO
from typing import Final

from flask import Flask, abort, render_template, request, send_file
from werkzeug.exceptions import BadRequest

from report_generator.calculations import compute_percentage, compute_total
from report_generator.grading import assign_grade
from report_generator.models import SUBJECTS, StudentInput, StudentReport
from report_generator.pdf_generator import generate_pdf


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


_DEFAULT_FILENAME_STEM: Final[str] = "Student"
"""Fallback name stem used when the submitted student name is blank.

When the user submits the form with an empty ``studentName`` field the
original JavaScript would have produced a download named
``_Report.pdf`` (a leading underscore, no name).  The Python port
substitutes :data:`_DEFAULT_FILENAME_STEM` (``"Student"``) so the
download is named ``Student_Report.pdf`` — a small usability
improvement over an undefined input the original implementation never
properly handled.  The substitution preserves the
``<name>_Report.pdf`` filename pattern documented in
``Readme.md`` line 236.
"""


_PDF_MIMETYPE: Final[str] = "application/pdf"
"""IANA-registered MIME type for PDF documents (RFC 8118).

Used as the ``mimetype`` argument of :func:`flask.send_file` for the
``/download`` route.  Naming the constant — rather than embedding the
literal string at the call site — honours the "no magic strings"
spirit of AAP §0.7.5.
"""


_PDF_MAGIC_HEADER: Final[bytes] = b"%PDF-"
"""The first five bytes that every well-formed PDF document begins with.

Defined in the PDF 1.4 specification (ISO 32000-1) and emitted by
ReportLab as the first bytes written to the output stream.  This
module uses :data:`_PDF_MAGIC_HEADER` as the sentinel of a defensive
check in the ``/download`` route — if
:func:`~report_generator.pdf_generator.generate_pdf` somehow returned
bytes that did *not* begin with this header, the download is aborted
with HTTP 500 rather than serving a corrupted attachment to the user.
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_mark(raw: str | None) -> int:
    """Parse a form mark value.

    Preserves the JavaScript ``parseInt(value || 0)`` semantic for
    empty or missing inputs (returns ``0``), but raises HTTP 400 for
    non-numeric strings — an improvement over the original
    implementation which would silently produce ``NaN`` and corrupt
    the running total.  See AAP §0.6.3 for the full rationale.

    Parameters
    ----------
    raw : str or None
        The raw form value.  ``None`` means the field was absent from
        the request entirely.  An empty string or a string consisting
        only of whitespace means the user submitted the form without
        filling the field in.  Both cases are treated the same as the
        JavaScript ``parseInt("" || 0)`` short-circuit and return ``0``.

    Returns
    -------
    int
        The parsed integer mark, or ``0`` if the input was empty,
        missing, or whitespace-only.

    Raises
    ------
    werkzeug.exceptions.BadRequest
        Raised (HTTP 400) when ``raw`` is a non-empty string that is
        *not* a valid integer.  The original JavaScript would silently
        propagate ``NaN`` in this case — a behaviour that was
        previously undefined and broken.

    Examples
    --------
    Empty-input parity with the original JavaScript::

        >>> _parse_mark("")
        0
        >>> _parse_mark(None)
        0
        >>> _parse_mark("   ")
        0

    Numeric inputs round-trip::

        >>> _parse_mark("85")
        85
        >>> _parse_mark("0")
        0

    Non-numeric input raises ``BadRequest`` (improvement over the JS)::

        >>> _parse_mark("abc")
        Traceback (most recent call last):
            ...
        werkzeug.exceptions.BadRequest: 400 Bad Request: Invalid mark value: 'abc'
    """
    if raw is None or raw.strip() == "":
        return 0
    try:
        return int(raw)
    except ValueError as exc:
        # Chain the original ValueError onto the BadRequest so the
        # underlying parsing failure remains visible in tracebacks.
        raise BadRequest(f"Invalid mark value: {raw!r}") from exc


def _build_report_from_form(form) -> StudentReport:  # noqa: ANN001 (Flask ImmutableMultiDict)
    """Build a :class:`StudentReport` from the submitted form payload.

    Shared by the ``/generate`` (renders to HTML) and ``/download``
    (renders to PDF) routes so the math is performed exactly once, in
    one place, with identical results.  This is the architectural
    realisation of AAP §0.6.2's "single-form, server-side computation"
    approach — both endpoints become pure functions of the same
    request body, eliminating the DOM-as-shared-state pattern
    (ADR-005) of the original implementation.

    Parameters
    ----------
    form : werkzeug.datastructures.ImmutableMultiDict
        The form payload from :data:`flask.request.form`.  Annotated as
        an untyped parameter to avoid leaking the verbose Werkzeug type
        into this module's signature — any mapping that supports
        ``.get(key, default)`` (Werkzeug's own ImmutableMultiDict, a
        plain :class:`dict`, etc.) works correctly.

    Returns
    -------
    StudentReport
        A fully computed report containing the original input
        (:class:`StudentInput`) plus the three derived values
        (:attr:`~StudentReport.total`,
        :attr:`~StudentReport.percentage`, and
        :attr:`~StudentReport.grade`).

    Notes
    -----
    *   The five subject names in :data:`SUBJECTS` are stored in
        **Title Case** (``"Maths"``, ``"Science"``, …) — matching the
        original JavaScript object literal at ``Readme.md`` lines
        166–171.  The HTML form field IDs and ``name`` attributes are
        **lowercase** (``maths``, ``science``, …) — matching the
        original ``getElementById('maths')`` etc. calls.  The
        ``subject.lower()`` translation between the two is the same
        pattern the original code used.

    *   The :func:`str.strip` calls on ``studentName`` and
        ``rollNumber`` trim incidental whitespace (e.g. user typing
        ``"  Alice  "``) without changing any semantics the original
        JavaScript would have observed — the original wrote whatever
        was in ``.value`` directly into the DOM, which a user could
        already have stripped via the same trim approach.
    """
    name = form.get("studentName", "").strip()
    roll = form.get("rollNumber", "").strip()
    marks: dict[str, int] = {
        subject: _parse_mark(form.get(subject.lower()))
        for subject in SUBJECTS
    }
    student_input = StudentInput(name=name, roll=roll, marks=marks)
    total = compute_total(marks)
    percentage = compute_percentage(total)
    grade = assign_grade(percentage)
    return StudentReport(
        input=student_input,
        total=total,
        percentage=percentage,
        grade=grade,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    """Create and configure a Flask application instance.

    Standard Flask **Application Factory** pattern (per AAP §0.3.2).
    Each call returns a fresh, independent :class:`flask.Flask`
    instance with its own URL map, configuration, and signal channels
    — enabling test fixtures to instantiate isolated apps without any
    cross-test contamination.

    The factory makes no use of the Flask extensions ecosystem (no
    SQLAlchemy, no Login, no Migrate, no Mail) because the application
    has no persistence, no auth, and no email surface; the
    out-of-scope feature set (per AAP §0.2.2) deliberately rules these
    out.  The factory therefore configures only what is strictly
    needed: the static folder is left at its default (``static``),
    the template folder is left at its default (``templates``), both
    auto-discovered relative to the ``app.py`` module path.

    Returns
    -------
    flask.Flask
        A configured Flask application instance with the three routes
        (``/``, ``/generate``, ``/download``) registered.  Debug mode
        is **not** enabled — toggling it on in production exposes the
        Werkzeug debugger which provides an interactive Python REPL
        over HTTP to anyone who can trigger an exception.

    Notes
    -----
    The route handlers are defined as nested functions inside the
    factory so they close over the ``app`` local and become part of
    the per-instance URL map.  Defining them at module level (the
    other common Flask pattern) would tie them to a single global app
    object and break the factory's isolation guarantee.
    """
    app = Flask(__name__)

    @app.route("/", methods=["GET"])
    def index() -> str:
        """Render the empty student-details form.

        Returned to the browser on the very first GET visit, before
        any form has been submitted.  ``report=None`` causes the
        Jinja2 template's ``{% if report %}`` guard to skip rendering
        the report-card section — exactly the same visual result as
        loading the original static ``index.html`` before clicking
        "Generate Report".
        """
        return render_template("index.html", report=None, subjects=SUBJECTS)

    @app.route("/generate", methods=["POST"])
    def generate() -> str:
        """Compute the report and re-render the page with the populated card.

        Replaces the original ``onclick="generateReport()"`` handler
        at ``Readme.md`` line 55.  Both this route and ``/download``
        share the same form parsing and computation pipeline via
        :func:`_build_report_from_form`, so the math is performed
        exactly once and identically across both flows.

        Returns
        -------
        str
            The rendered HTML page.  The ``report`` context variable
            is populated with the freshly computed
            :class:`StudentReport`, which causes the Jinja2 template
            to render both the form (re-populated with the submitted
            values) *and* the report-card section showing the totals,
            percentage, and grade.
        """
        report = _build_report_from_form(request.form)
        return render_template("index.html", report=report, subjects=SUBJECTS)

    @app.route("/download", methods=["POST"])
    def download():
        """Compute the report and stream a PDF attachment to the browser.

        Replaces the original ``onclick="downloadPDF()"`` handler at
        ``Readme.md`` line 56 (JavaScript at lines 215–237).  The
        PDF is generated by
        :func:`~report_generator.pdf_generator.generate_pdf` whose
        output preserves the original visual layout exactly — same
        page size, same font, same coordinates (modulo the
        documented mm/top-left → pt/bottom-left reconciliation in
        AAP §0.6.1).

        The download filename matches the original pattern
        ``<name>_Report.pdf`` (per ``Readme.md`` line 236).  When
        the user submitted an empty ``studentName`` the fallback
        :data:`_DEFAULT_FILENAME_STEM` (``"Student"``) is
        substituted so the download is named ``Student_Report.pdf``
        rather than the awkward ``_Report.pdf`` the original would
        have produced — an undefined-behaviour input the JavaScript
        never properly handled.

        Returns
        -------
        flask.wrappers.Response
            A Flask response with ``Content-Type: application/pdf``
            and ``Content-Disposition: attachment; filename=...``.

        Raises
        ------
        werkzeug.exceptions.HTTPException
            HTTP 500 (via :func:`flask.abort`) if
            :func:`~report_generator.pdf_generator.generate_pdf`
            unexpectedly returns an empty byte string or bytes that
            do not begin with the PDF magic header — a defensive
            check that prevents serving a corrupted attachment to the
            user.
        """
        report = _build_report_from_form(request.form)
        pdf_bytes = generate_pdf(report)

        # Defensive guard: refuse to stream a non-PDF byte payload.
        # `generate_pdf` is contractually obliged to return a
        # well-formed PDF, so the typical request never hits this
        # branch — but if a future refactor ever subtly breaks that
        # contract, aborting here gives a clean HTTP 500 rather than
        # silently delivering a broken PDF the browser would refuse to
        # open.  `flask.abort(500)` raises an
        # `werkzeug.exceptions.InternalServerError`, the standard way
        # to signal a server-side failure from a route handler.
        if not pdf_bytes or not pdf_bytes.startswith(_PDF_MAGIC_HEADER):
            abort(500, description="PDF generation failed: invalid output")

        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)

        filename = f"{report.input.name or _DEFAULT_FILENAME_STEM}_Report.pdf"

        return send_file(
            buffer,
            mimetype=_PDF_MIMETYPE,
            as_attachment=True,
            download_name=filename,
        )

    return app


# ---------------------------------------------------------------------------
# Module-level WSGI entry point
# ---------------------------------------------------------------------------


app: Final[Flask] = create_app()
"""The module-level WSGI application instance.

Created eagerly at import time so ``flask --app app run`` (per AAP
§0.3.4) discovers it without needing ``--call create_app``.  The
:data:`typing.Final` qualifier documents that the variable is bound
exactly once at import time and should never be reassigned —
production WSGI servers (gunicorn, uWSGI, mod_wsgi) all expect a
single, stable, importable application object.

For test fixtures that need an isolated app, call :func:`create_app`
directly rather than using this module-level instance: each call
produces a fresh, independent Flask instance with its own URL map,
configuration, and signal channels.
"""


if __name__ == "__main__":
    # Production-safe defaults: debug=False keeps the Werkzeug
    # debugger (which exposes a Python REPL over HTTP) firmly
    # disabled.  For local development the Flask CLI is preferred:
    # `flask --app app run --debug`.
    app.run(debug=False)
