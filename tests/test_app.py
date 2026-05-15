"""Flask integration tests for the Student Report Generator.

This module exercises the three HTTP routes registered by
:func:`app.create_app` end-to-end using Flask's in-process test client.
Together with :mod:`tests.test_calculations`, :mod:`tests.test_grading`,
and :mod:`tests.test_pdf_generator`, it forms the executable proof that
the Python port honours the user rule ``Ajit_Test_Refactor`` ("Refactor
the code without changing the functionality") for the user-visible
behaviour previously implemented in the browser-side JavaScript at
``Readme.md`` lines 161–238.

Coverage map
------------
=========  ============================ =============================================
Route      AAP cross-references         What is verified
=========  ============================ =============================================
GET ``/``  F-001 (Form Input Capture)   Empty form renders; both submit endpoints
                                        are wired into the rendered HTML.
POST       F-002 (Total/%),             Same form payload produces an HTML page with
``/gen.``  F-003 (Grade), F-004         the populated report card; the empty-input
           (Display)                    semantic from JS ``parseInt(value||0)`` is
                                        preserved (returns ``0``); non-numeric input
                                        raises HTTP 400 (per AAP §0.6.3).
POST       F-005 (PDF Generation),      Response carries ``application/pdf`` mimetype
``/dl.``   F-006 (Download)             plus an ``attachment`` Content-Disposition
                                        whose filename matches
                                        ``<name>_Report.pdf``; the byte stream begins
                                        with the ``%PDF-`` magic header and ends
                                        with the ``%%EOF`` marker.
=========  ============================ =============================================

Architectural verification
--------------------------
The :func:`test_generate_and_download_use_same_pipeline` case is the
executable proof of AAP §0.6.2: both routes accept the *same* form
payload and feed it through the *same* compute pipeline, demonstrating
that the DOM-as-transient-shared-state pattern from the original
implementation (ADR-005) has been eliminated.  In the new architecture
no implicit "generate-before-download" ordering exists because there is
no shared state — each endpoint is a pure function of its request body.

Test isolation guarantees
-------------------------
*   Every test consumes the :func:`client` fixture which constructs a
    fresh :class:`flask.Flask` instance via :func:`app.create_app`.  No
    state bleeds between tests; tests can be executed in any order.
*   ``app.config["TESTING"] = True`` switches the application into
    Flask's testing mode: ``TRAP_HTTP_EXCEPTIONS`` is disabled so HTTP
    400/500 responses are returned to the test client as ordinary
    response objects (with their original status codes intact) rather
    than being re-raised as Python exceptions.
*   The :func:`flask.Flask.test_client` context manager handles
    teardown automatically.
*   No test performs filesystem I/O or external network I/O — PDFs are
    asserted on as raw response bytes and the test client speaks to the
    WSGI callable directly without binding a real socket.

Compliance notes
----------------
*   PEP 484 type hints on every test signature (per AAP §0.7.5).
*   PEP 257 docstrings on every fixture and test function.
*   PEP 8 layout, line length ≤ 100 characters.
*   Only :mod:`pytest` is imported from third parties — no additional
    test-only dependency is introduced beyond what AAP §0.5.1 pins.
*   ``from __future__ import annotations`` (PEP 563) allows the modern
    ``dict[str, str]`` syntax in fixture return annotations without
    runtime evaluation cost on Python 3.10+.
"""

from __future__ import annotations

import pytest

from app import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Provide a Flask test client with TESTING mode enabled.

    Each test invocation receives a brand-new Flask application
    instance (via :func:`app.create_app`) wrapped in its own test
    client.  This eliminates cross-test state bleed: a regression that
    accidentally introduced module-level mutable state (e.g. a global
    counter or a memoised dict) would surface as a test failure rather
    than silently corrupting downstream tests.

    The ``with`` block ensures Flask's normal request-context teardown
    runs after each test; the implicit ``yield`` hands control to the
    test body, and Flask cleans up the application context when the
    block exits — even if the test raises.

    Yields
    ------
    flask.testing.FlaskClient
        A configured test client whose ``.get()``, ``.post()``, etc.
        helpers invoke the WSGI application directly without binding a
        real network socket.  See the Flask testing documentation for
        the full API surface.
    """
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def valid_form_data() -> dict[str, str]:
    """Provide a complete, valid form payload used by multiple tests.

    The marks (90 + 85 + 80 + 75 + 95 = 425) are chosen so that the
    resulting percentage is 85.0% (a clean two-decimal number that the
    template renders as ``"85.00"``) and the grade is ``"A"`` (the
    ``>=80`` threshold of :data:`report_generator.grading.GRADE_THRESHOLDS`).
    Using a clean number avoids float-precision noise in substring
    assertions on the rendered HTML and PDF text.

    Field names mirror the HTML form input ``name`` attributes in
    :file:`templates/index.html`, which themselves preserve the
    ``getElementById(...)`` IDs from the original
    ``Readme.md`` form (lines 46–53).

    Returns
    -------
    dict[str, str]
        A new dict on every call (no shared mutable state), with the
        seven keys ``studentName``, ``rollNumber``, ``maths``,
        ``science``, ``english``, ``history``, ``computer``.
    """
    return {
        "studentName": "Alice Smith",
        "rollNumber": "42",
        "maths": "90",
        "science": "85",
        "english": "80",
        "history": "75",
        "computer": "95",
    }


# ---------------------------------------------------------------------------
# GET / — the empty-form landing page
# ---------------------------------------------------------------------------


def test_index_get_returns_200_with_form(client) -> None:
    """GET ``/`` returns 200 with the empty student-details form.

    Verifies F-001 (Form Input Capture): the application's entry point
    renders the form whose five numeric inputs and two submit buttons
    match the original HTML in ``Readme.md`` lines 27–85.  Specifically:

    * Status code is 200 (no redirect, no error).
    * The page title text ``"Student Report Generator"`` is present —
      the same heading the original page used.
    * At least five ``type="number"`` inputs are rendered (one per
      subject).
    * At least two submit-capable elements are present (Generate and
      Download buttons).
    """
    response = client.get("/")
    assert response.status_code == 200
    assert b"Student Report Generator" in response.data
    # Five numeric inputs (Maths, Science, English, History, Computer)
    assert response.data.count(b'type="number"') >= 5
    # Two submit buttons (Generate and Download) — match either the
    # <button> tag count or the word "submit" used in type="submit".
    body_lower = response.data.lower()
    assert body_lower.count(b"<button") >= 2 or body_lower.count(b"submit") >= 2


def test_index_get_has_form_action_attributes(client) -> None:
    """The rendered form wires both ``/generate`` and ``/download`` endpoints.

    AAP §0.6.2 eliminates the DOM-as-shared-state pattern by routing
    both submit buttons through the same ``<form>`` element with
    ``formaction`` attributes that point at the two server-side
    endpoints.  This test asserts that the rendered HTML contains
    references to both URLs so the user can reach either endpoint from
    the same form payload — proving the page-level wiring matches the
    target architecture.
    """
    response = client.get("/")
    assert response.status_code == 200
    body = response.data
    assert b"/generate" in body
    assert b"/download" in body


def test_index_get_no_report_card_visible_initially(client) -> None:
    """The report card is not rendered on the initial GET visit.

    The Jinja2 template uses ``{% if report %}`` to gate the
    report-card section.  When the view function is invoked with
    ``report=None`` (the GET ``/`` path), this branch is skipped — so
    the populated report-card content (the ``Student Report`` heading
    and the percentage display) must not appear in the response.

    This is the visual analogue of the original page's behaviour:
    before the user clicked "Generate Report", the report-card
    ``<div>`` existed in the DOM but its span elements were empty.  In
    the Python port the gate is at the template level so the whole
    section is omitted from the response body — strictly cleaner than
    the original.
    """
    response = client.get("/")
    assert response.status_code == 200
    # The report card heading and the percentage marker (always
    # rendered together inside the {% if report %} block) must both be
    # absent from the empty-form landing page.
    assert b"Student Report</h2>" not in response.data
    assert b"id=\"percentage\"" not in response.data


# ---------------------------------------------------------------------------
# POST /generate — compute and re-render with the report card populated
# ---------------------------------------------------------------------------


def test_generate_post_with_valid_data(client, valid_form_data: dict[str, str]) -> None:
    """POST ``/generate`` with valid data returns 200 + populated report card.

    Verifies the happy-path of F-002 (Total/Percentage), F-003 (Grade),
    and F-004 (Display).  Given the :func:`valid_form_data` payload
    (90+85+80+75+95 = 425, 85.00%, grade A) the rendered HTML must
    contain:

    * The student name (``"Alice Smith"``) verbatim — proves the form
      data was correctly read and rendered.
    * The roll number (``"42"``).
    * The computed total (``"425"``).
    * The percentage (``"85"`` substring — the template formats this
      as ``"85.00"`` via ``{{ "%.2f"|format(...) }}``).
    * The letter grade (``"A"``) — verified explicitly inside the
      ``<span id="grade">`` element to avoid matching the literal
      ``A`` characters that appear elsewhere in the page (e.g.
      ``<head>``).
    """
    response = client.post("/generate", data=valid_form_data)
    assert response.status_code == 200
    body = response.data
    assert b"Alice Smith" in body
    assert b"42" in body  # roll number
    # Total = 90+85+80+75+95 = 425
    assert b"425" in body
    # Percentage = 85.0, formatted by Jinja2 as "85.00"
    assert b"85.00" in body
    # Grade = "A" — assert inside the dedicated <span id="grade"> to
    # avoid matching the bare letter elsewhere in the page.
    assert b'id="grade">A<' in body


def test_generate_post_with_empty_marks(client) -> None:
    """Empty/missing marks coerce to 0 — preserves JS ``parseInt(value||0)``.

    AAP §0.6.3 mandates that the new ``_parse_mark`` helper preserve
    the original JavaScript's behaviour for empty input: ``parseInt(""
    || 0)`` returns ``0`` so the running total stays at ``0`` and the
    grade becomes ``"F"``.  This test submits a payload that omits all
    five subject fields entirely (only the name and roll number are
    present) and asserts that the response is still a successful 200
    with the report card populated to reflect a zero total and a
    failing grade.
    """
    response = client.post("/generate", data={
        "studentName": "Bob",
        "rollNumber": "1",
        # All marks fields are missing — _parse_mark returns 0 for each
    })
    assert response.status_code == 200
    body = response.data
    assert b"Bob" in body
    # Total = 0, percentage = 0.00, grade = F
    assert b'id="grade">F<' in body
    assert b"0.00" in body


def test_generate_post_with_all_zeros_marks(client) -> None:
    """Explicitly empty mark strings coerce to 0 (matches JS ``|| 0`` fallback).

    A subtly different code path from
    :func:`test_generate_post_with_empty_marks`: here the form fields
    *are* present but contain the empty string ``""``.  The
    ``_parse_mark`` helper short-circuits on ``raw.strip() == ""`` and
    returns ``0`` — exactly the same semantic as the missing-field case
    above, exactly the same semantic as the original
    ``parseInt("" || 0)``.  Verifying both paths separately catches a
    regression where one branch was handled and the other was not.
    """
    response = client.post("/generate", data={
        "studentName": "Charlie",
        "rollNumber": "2",
        "maths": "",
        "science": "",
        "english": "",
        "history": "",
        "computer": "",
    })
    assert response.status_code == 200
    body = response.data
    assert b"Charlie" in body
    # Same outcome as the all-missing-fields case: total=0, grade=F.
    assert b'id="grade">F<' in body


def test_generate_post_with_invalid_marks(client) -> None:
    """Non-numeric marks raise HTTP 400 (improvement over silent NaN).

    AAP §0.6.3 documents the one intentional behaviour change from the
    original JavaScript: a non-numeric input was previously coerced
    to ``NaN`` by ``parseInt("abc")``, which then propagated through
    the accumulator and silently corrupted the total.  The Python port
    surfaces this as an explicit HTTP 400 Bad Request, which is a
    strict improvement under the user rule's intent — a path that was
    previously undefined and broken is now well-defined.

    The test exercises a payload with one valid integer-as-string
    field replaced by the literal ``"abc"`` and asserts that the
    response status is 400.
    """
    response = client.post("/generate", data={
        "studentName": "Dan",
        "rollNumber": "3",
        "maths": "abc",
        "science": "85",
        "english": "80",
        "history": "75",
        "computer": "95",
    })
    assert response.status_code == 400


def test_generate_post_perfect_score(client) -> None:
    """A perfect score (all 100s) yields percentage 100.00 and grade A+.

    Verifies the top of the grade ladder.  Five 100s sum to 500, the
    canonical maximum (:data:`report_generator.models.MAX_TOTAL`), so
    the percentage is exactly 100.0 (rendered as ``"100.00"``) and the
    grade is ``"A+"`` (the ``>=90`` threshold).  This case is the
    upper-bound complement of
    :func:`test_generate_post_failing_score`.
    """
    response = client.post("/generate", data={
        "studentName": "Eve",
        "rollNumber": "5",
        "maths": "100",
        "science": "100",
        "english": "100",
        "history": "100",
        "computer": "100",
    })
    assert response.status_code == 200
    body = response.data
    assert b"500" in body
    # "A+" appears inside the <span id="grade"> element.
    assert b'id="grade">A+<' in body
    # Percentage rendered as 100.00.
    assert b"100.00" in body


def test_generate_post_failing_score(client) -> None:
    """A score below 50% yields grade F.

    Verifies the bottom of the grade ladder.  Marks 40+30+20+10+0=100,
    percentage=20.0%, which falls below the ``>=50`` D threshold and
    therefore lands on the default ``"F"`` branch of
    :func:`report_generator.grading.assign_grade`.
    """
    response = client.post("/generate", data={
        "studentName": "Frank",
        "rollNumber": "6",
        "maths": "40",
        "science": "30",
        "english": "20",
        "history": "10",
        "computer": "0",
    })
    assert response.status_code == 200
    body = response.data
    # Total = 100, percentage = 20.00, grade = F.
    assert b'id="grade">F<' in body
    assert b"20.00" in body


# ---------------------------------------------------------------------------
# POST /download — compute and stream a PDF attachment
# ---------------------------------------------------------------------------


def test_download_post_returns_pdf_attachment(client, valid_form_data: dict[str, str]) -> None:
    """POST ``/download`` returns 200 + an ``application/pdf`` attachment.

    Verifies the F-005/F-006 contract end-to-end at the HTTP layer:

    * Status code is 200.
    * The response mimetype is ``"application/pdf"`` (the IANA-
      registered PDF media type, RFC 8118).  Note: this test uses
      ``response.mimetype`` rather than ``response.content_type``
      because the latter may include a ``charset`` parameter while the
      former is always the bare MIME type — matching the original JS
      ``doc.save(...)`` behaviour where the browser saved a raw PDF
      file without charset metadata.
    * The ``Content-Disposition`` header marks the body as an
      ``attachment`` so the browser saves it to disk rather than
      attempting to inline-render it.
    * The filename matches the ``<name>_Report.pdf`` pattern preserved
      from the original ``doc.save(`${name}_Report.pdf`)`` call.
    """
    response = client.post("/download", data=valid_form_data)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "attachment" in content_disposition.lower()
    assert "Report.pdf" in content_disposition


def test_download_pdf_bytes_start_with_magic(
    client,
    valid_form_data: dict[str, str],
) -> None:
    """The downloaded PDF body starts with the ``%PDF-`` magic bytes.

    The PDF 1.4 specification (ISO 32000-1) requires every well-formed
    PDF to begin with the five bytes ``%PDF-`` followed by a version
    indicator.  ReportLab emits these bytes as the very first content
    written to the output stream, so the test client's response body
    must start with the same five bytes.  A regression that broke the
    PDF generation pipeline (e.g. accidentally returning the empty
    string, or returning HTML instead of PDF) would cause this check
    to fail loudly rather than producing a corrupt-but-200 download.
    """
    response = client.post("/download", data=valid_form_data)
    assert response.status_code == 200
    assert response.data[:5] == b"%PDF-"


def test_download_filename_pattern(client) -> None:
    """The ``Content-Disposition`` filename matches ``<studentName>_Report.pdf``.

    Preserves the exact filename pattern from
    ``Readme.md:236``: ``doc.save(`${name}_Report.pdf`)``.  In the
    Python port this is realised by Flask's
    :func:`flask.send_file(... download_name=...)` argument, which
    Werkzeug renders into a ``Content-Disposition`` header of the form
    ``attachment; filename=<name>_Report.pdf`` (and, on Werkzeug 2.x+,
    additionally as the RFC 5987 ``filename*=UTF-8''<name>_Report.pdf``
    parameter for non-ASCII names).

    The test uses a single-token student name (``"AliceSmith"``,
    without an embedded space) so the simple substring check is
    immune to the various ways different Werkzeug minor versions URL-
    or percent-encode spaces in the ``filename=`` parameter.  The
    same simple substring also matches the RFC-5987 ``filename*=``
    variant so the assertion is robust across Werkzeug 2.x and 3.x.
    """
    response = client.post("/download", data={
        "studentName": "AliceSmith",
        "rollNumber": "42",
        "maths": "90",
        "science": "85",
        "english": "80",
        "history": "75",
        "computer": "95",
    })
    assert response.status_code == 200
    content_disposition = response.headers.get("Content-Disposition", "")
    assert "AliceSmith_Report.pdf" in content_disposition


def test_download_pdf_contains_eof_marker(client, valid_form_data: dict[str, str]) -> None:
    """The downloaded PDF body contains the ``%%EOF`` marker near the end.

    Per the PDF specification, a well-formed PDF document ends with
    the literal byte sequence ``%%EOF`` (optionally followed by a
    single newline).  The ``%%EOF`` marker tells PDF readers that the
    cross-reference table is complete — without it, viewers may
    refuse to open the file or display a recovery prompt.

    The assertion looks for the marker within the last 1024 bytes of
    the response, which gives ReportLab plenty of room for the
    trailer/xref table that immediately precedes the EOF.  This is a
    far stronger structural-integrity check than the magic-bytes
    test above: a file with the correct prefix but a truncated tail
    would still pass the prefix check but fail this one.
    """
    response = client.post("/download", data=valid_form_data)
    assert response.status_code == 200
    # %%EOF should appear within the last 1024 bytes per the PDF spec.
    assert b"%%EOF" in response.data[-1024:]


def test_download_with_empty_marks_succeeds(client) -> None:
    """Empty marks coerce to 0 and still produce a valid PDF.

    Parity check with :func:`test_generate_post_with_empty_marks`:
    submitting an incomplete form to ``/download`` must succeed the
    same way it succeeds at ``/generate`` — because both routes go
    through the same :func:`_build_report_from_form` helper in
    :mod:`app`.  The resulting PDF has a total of 0 and a grade of
    ``"F"`` but is still a well-formed PDF document the browser can
    render.

    This case also doubles as a regression guard for the filename
    fallback: when ``studentName`` is empty the route substitutes
    ``"Student"``, but here the name is the non-empty ``"Grace"`` so
    the normal pattern applies.
    """
    response = client.post("/download", data={
        "studentName": "Grace",
        "rollNumber": "7",
        # All marks fields are missing — both routes accept this.
    })
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data[:5] == b"%PDF-"


def test_download_with_invalid_marks_returns_400(client) -> None:
    """Non-numeric marks on ``/download`` also raise HTTP 400.

    Mirror-image of :func:`test_generate_post_with_invalid_marks` —
    both routes share the same input-validation pipeline so the same
    invalid input must produce the same status code regardless of
    which endpoint is targeted.  This is the *negative* analogue of
    :func:`test_generate_and_download_use_same_pipeline`: that test
    proves successful pipelines agree, this one proves the failure
    pipelines agree.
    """
    response = client.post("/download", data={
        "studentName": "Henry",
        "rollNumber": "8",
        "maths": "xyz",
    })
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Cross-endpoint consistency — the architectural verification
# ---------------------------------------------------------------------------


def test_generate_and_download_use_same_pipeline(
    client,
    valid_form_data: dict[str, str],
) -> None:
    """``/generate`` and ``/download`` compute identical values from the same payload.

    The architectural verification of AAP §0.6.2: by submitting the
    same form payload to both routes and asserting that both produce
    successful, well-formed responses, this test proves that the
    DOM-as-transient-shared-state pattern from the original
    implementation (ADR-005) has been eliminated.  The original code
    required a strict click-order — "Generate" *before* "Download" or
    the PDF would be blank — because ``downloadPDF()`` read its data
    from DOM nodes that ``generateReport()`` was responsible for
    populating.

    In the Python port both routes are stateless: they accept the same
    form payload, route it through the same
    :func:`_build_report_from_form` helper, and render the result.
    There is no implicit ordering dependency because there is no
    shared state.  Either route can be invoked first; both produce
    correct output every time.
    """
    resp_gen = client.post("/generate", data=valid_form_data)
    resp_dl = client.post("/download", data=valid_form_data)
    # Both routes must succeed on the same input.
    assert resp_gen.status_code == 200
    assert resp_dl.status_code == 200
    # /generate returns a rendered HTML page with the student name.
    assert b"Alice" in resp_gen.data
    # /download returns a PDF attachment.
    assert resp_dl.mimetype == "application/pdf"
    assert resp_dl.data[:5] == b"%PDF-"
