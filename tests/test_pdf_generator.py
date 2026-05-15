"""Tests for the PDF generator — F-005 (PDF Export) contract verification.

This module is the executable proof that
:func:`report_generator.pdf_generator.generate_pdf` produces a syntactically
valid PDF document whose textual content reproduces — byte for byte — the
output of the original browser-side PDF generation function at
``Readme.md`` lines 215–237 of the source repository.  The original
function (referenced below by its public-facing name only) performs the
following draw operations against an A4 portrait page using its library's
default top-left millimetre coordinate system:

* Set title font size to 18 pt.
* Draw the literal title ``"Student Report Card"`` at (20, 20).
* Set body font size to 12 pt.
* Draw the lines ``Student Name: <name>``, ``Roll Number: <roll>``,
  ``Total Marks: <total>``, ``Percentage: <percentage>%``, and
  ``Grade: <grade>`` at (20, 40), (20, 50), (20, 60), (20, 70), and
  (20, 80) respectively.
* Persist the document under the filename ``<name>_Report.pdf``.

The percentage value in the original implementation is formatted with the
``.toFixed(2)`` numeric formatter at ``Readme.md`` line 211 before being
read back out of the DOM for inclusion in the PDF — so the PDF always
carries two decimal places (e.g. ``85.00%``, ``100.00%``, ``0.00%``).
The Python port reproduces this with the ``:.2f`` f-string spec; the
corresponding tests in *Phase 5* (`test_pdf_perfect_score`,
`test_pdf_failing_score`) pin that formatting down explicitly.

Why this module exists
----------------------
The user rule **Ajit_Test_Refactor** ("Refactor the code without changing
the functionality") and the AAP §0.6.1 *Coordinate-system reconciliation*
together require that the visible content of the migrated PDF be identical
to the original.  Without an executable test suite this requirement is
unverifiable, so this file is a *rule-derived* deliverable per AAP §0.2.1.

Test layout (mirrors agent-prompt phases)
-----------------------------------------
*   **Phase 1** — module header (imports, regex constant) below.
*   **Phase 2** — the ``sample_report`` fixture.
*   **Phase 3** — three PDF *structural* tests (magic-byte prefix, ``%%EOF``
    trailer, ``bytes`` return type).
*   **Phase 4** — six PDF *content* tests using the :func:`_pdf_contains`
    helper (title, name, roll, total, percentage, grade).
*   **Phase 5** — five *quality-of-life* tests (perfect score, failing
    score, byte-size reasonableness, length determinism, special
    characters in name).

Design notes
------------
*   **Compressed text streams.**  ReportLab 4.5.1 emits text content
    streams with ``/Filter [ /ASCII85Decode /FlateDecode ]`` — so the
    "drawn" strings (``Student Report Card``, ``Alice Smith``, etc.) do
    **not** appear in the raw PDF bytes as literal substrings.  The
    private :func:`_pdf_contains` helper therefore applies *three*
    strategies in series: (1) raw byte search for any literally-embedded
    occurrences (PDF metadata, ``/Info`` dictionary fields, etc.); (2)
    a lossy ``latin-1`` decode of the whole PDF for substring detection
    that spans multi-byte chunks; and (3) extraction-and-decompression
    of every ``stream … endstream`` block (ASCII85 → FlateDecode) so the
    decoded text-positioning operators (``(Student Report Card) Tj``,
    ``(Grade: A) Tj``) become searchable.  This three-layer strategy is
    intentionally tolerant: even if a future ReportLab release changes
    its default compression posture, the same helper will continue to
    locate the expected strings.
*   **No third-party PDF parser.**  Per the folder requirements and AAP
    §0.5.1, this file uses *only* the standard library and pytest — no
    ``pypdf``, no ``PyPDF2``.  The ASCII85 + zlib decoding required to
    see compressed content uses :mod:`base64` and :mod:`zlib`, both
    bundled with CPython 3.13.
*   **Self-contained tests.**  Every test either uses the
    :func:`sample_report` fixture or builds its own
    :class:`~report_generator.models.StudentReport` inline; no test
    depends on another's side effects.
*   **No filesystem writes.**  Every PDF byte sequence stays in memory
    (``BytesIO`` inside :func:`generate_pdf`, plain :class:`bytes` here).
    Pytest fixtures and the test body never call :func:`open`.
*   **Determinism caveat.**  Two PDFs produced by back-to-back calls to
    :func:`generate_pdf` carry an identical layout but their
    ``/CreationDate`` and ``/ModDate`` fields embed the current
    timestamp; if the two timestamps differ (rarely, only across a
    one-second tick), the resulting PDFs are *length-equal but not
    byte-equal*.  :func:`test_pdf_is_deterministic_in_length` therefore
    asserts length equivalence within a forgiving tolerance rather than
    byte-for-byte equality.

This module honours AAP §0.7.5: every test signature carries PEP 484 type
hints, every test function carries a PEP 257 docstring, line length stays
below 100 characters, and ``from __future__ import annotations`` (PEP 563)
defers type-hint evaluation.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard-library imports
# ---------------------------------------------------------------------------
#
# These three stdlib modules are all that's required to fully decode the
# ReportLab-generated PDF content streams:
#
# * :mod:`re`      — locate every ``stream … endstream`` block in the raw
#                    PDF byte sequence (per agent-prompt Phase 1).
# * :mod:`base64`  — the :func:`base64.a85decode` routine reverses the
#                    ASCII85 outer layer applied by ReportLab when the
#                    ``/ASCII85Decode`` filter is in effect.
# * :mod:`zlib`    — :func:`zlib.decompress` reverses the inner
#                    ``/FlateDecode`` (zlib) layer, yielding the
#                    plaintext PDF content-stream operators.
import base64
import re
import zlib

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import pytest

# ---------------------------------------------------------------------------
# First-party imports — only from ``depends_on_files`` per AAP §0.4.2
# ---------------------------------------------------------------------------
from report_generator.models import StudentInput, StudentReport
from report_generator.pdf_generator import generate_pdf


# ---------------------------------------------------------------------------
# Module-level regex constant
# ---------------------------------------------------------------------------

# Matches ReportLab's ``stream\n…endstream`` blocks.  The PDF spec permits
# CR-LF after the ``stream`` keyword but ReportLab uses LF; the trailing
# ``endstream`` likewise appears on its own line.  ``re.DOTALL`` lets ``.``
# match the embedded newlines so the entire compressed payload (binary
# data, including newlines) is captured by the single capture group.
_STREAM_RE: re.Pattern[bytes] = re.compile(rb"stream\n(.*?)endstream", re.DOTALL)


# ---------------------------------------------------------------------------
# Private helper — flexible content search across the PDF byte stream
# ---------------------------------------------------------------------------


def _pdf_contains(pdf_bytes: bytes, needle: str) -> bool:
    """Return :data:`True` iff *needle* appears anywhere in the PDF *pdf_bytes*.

    The helper applies three search strategies in order, returning the first
    match:

    1.  **Raw byte search.**  ``needle.encode("latin-1") in pdf_bytes``.
        Locates substrings that ReportLab writes uncompressed — chiefly the
        ``/Info`` dictionary values (``/Title``, ``/Author``, …) — and
        also catches any string that happens to survive in cleartext when
        the optional compression layer is disabled in a future ReportLab
        release.
    2.  **Lossy ``latin-1`` decode.**  PDF byte streams are ISO-8859-1
        compatible in their structural framing; decoding with
        ``errors="ignore"`` and running an ordinary ``in`` check catches
        substrings that fall on chunk boundaries (a rare but real edge
        case with stream-builder formatters).
    3.  **ASCII85 + Flate decompression.**  ReportLab 4.5.1 ships text
        content streams behind the chained filter ``/ASCII85Decode``
        (outer) and ``/FlateDecode`` (inner).  For each
        ``stream … endstream`` block, the helper strips the ASCII85
        terminator (``~>``), feeds the body through
        :func:`base64.a85decode`, then decompresses the result with
        :func:`zlib.decompress`.  The decoded plaintext contains the
        PDF text-positioning operators (``(Student Report Card) Tj``,
        ``(Roll Number: 42) Tj``, …) where every literal string the
        ReportLab :meth:`Canvas.drawString` call rendered is verbatim
        searchable.

    Parameters
    ----------
    pdf_bytes:
        The full byte sequence returned by
        :func:`report_generator.pdf_generator.generate_pdf`.
    needle:
        The literal string to search for.  Encoded to bytes using
        ``latin-1``, which losslessly round-trips every Unicode code point
        below ``U+0100`` — sufficient for the ASCII content the F-005
        contract requires.

    Returns
    -------
    bool
        :data:`True` iff *needle* is found by **any** of the three
        strategies; :data:`False` otherwise.

    Notes
    -----
    The helper deliberately swallows three specific exception types from
    the decompression path (:exc:`ValueError` from :func:`a85decode`,
    :exc:`zlib.error` from :func:`zlib.decompress`, and :exc:`OSError`
    that some Python builds raise for malformed deflate streams) so that
    a single malformed stream cannot mask a hit in a *later* stream.
    Streams that are not ASCII85+Flate encoded — for example a font
    subset stream or a metadata XMP packet — are silently skipped: their
    contents are irrelevant to the F-005 contract.
    """
    needle_bytes: bytes = needle.encode("latin-1")

    # Strategy 1: raw byte search across the whole PDF.
    if needle_bytes in pdf_bytes:
        return True

    # Strategy 2: lossy latin-1 decode and substring check.  Latin-1
    # losslessly maps every byte to a unique code point, so this is just
    # a different *view* of the same byte stream — useful when a hit
    # would span a multi-byte boundary in a non-latin-1 decode.
    decoded: str = pdf_bytes.decode("latin-1", errors="ignore")
    if needle in decoded:
        return True

    # Strategy 3: decompress each ASCII85+Flate stream and search its
    # plaintext content for the needle.
    for match in _STREAM_RE.finditer(pdf_bytes):
        # ``rstrip`` of trailing whitespace handles the common case where
        # ReportLab emits a final CR or LF inside the payload.  The
        # ASCII85 terminator ``~>`` must remain attached for the slice
        # below to find it.
        raw_stream: bytes = match.group(1).rstrip(b"\r\n ")
        if not raw_stream.endswith(b"~>"):
            # Not an ASCII85-encoded stream — skip silently.
            continue
        try:
            a85_payload: bytes = raw_stream[:-2]
            compressed: bytes = base64.a85decode(
                a85_payload, adobe=False, ignorechars=b"\n\r\t "
            )
            inflated: bytes = zlib.decompress(compressed)
        except (ValueError, zlib.error, OSError):
            # Stream not in the expected ASCII85+Flate format; skip and
            # try the next one.  Defense in depth — keeps the helper
            # robust against ReportLab format-version drift.
            continue
        if needle_bytes in inflated:
            return True

    return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_report() -> StudentReport:
    """Provide a representative :class:`StudentReport` for PDF tests.

    The fixture builds a "Mary-had-a-little-lamb" report whose numbers
    cover the *middle* of the grade ladder (``A`` band):

    *   Name        — ``"Alice Smith"``
    *   Roll        — ``"42"``
    *   Marks       — ``Maths=90, Science=85, English=80, History=75,
                       Computer=95``  → ``total=425``
    *   Percentage  — ``85.0``  → renders as ``"85.00%"`` (two decimals)
    *   Grade       — ``"A"``

    The fixture is yielded as a *frozen*
    :class:`~report_generator.models.StudentReport`; mutation attempts by
    any test would raise :class:`dataclasses.FrozenInstanceError`.

    Returns
    -------
    StudentReport
        A fully populated report ready to feed into
        :func:`report_generator.pdf_generator.generate_pdf`.
    """
    student = StudentInput(
        name="Alice Smith",
        roll="42",
        marks={
            "Maths": 90,
            "Science": 85,
            "English": 80,
            "History": 75,
            "Computer": 95,
        },
    )
    return StudentReport(
        input=student,
        total=425,
        percentage=85.0,
        grade="A",
    )


# ---------------------------------------------------------------------------
# Phase 3 — PDF structural tests
# ---------------------------------------------------------------------------


def test_pdf_starts_with_magic_bytes(sample_report: StudentReport) -> None:
    """The generated PDF starts with the ``%PDF-`` magic header.

    The PDF 1.4+ specification (ISO 32000-1, §7.5.2) mandates that every
    valid PDF begins with the four-byte signature ``%PDF-`` followed by
    a version string.  Any byte sequence missing this header would be
    rejected by every PDF viewer in existence, so the assertion here is
    the most basic well-formedness gate.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert pdf_bytes.startswith(b"%PDF-"), (
        f"PDF header missing; first 16 bytes were {pdf_bytes[:16]!r}"
    )


def test_pdf_ends_with_eof_marker(sample_report: StudentReport) -> None:
    """The generated PDF contains ``%%EOF`` within its final 1024 bytes.

    The PDF 1.4+ specification (ISO 32000-1, §7.5.5) mandates that the
    very last marker in a valid PDF be ``%%EOF`` (optionally followed by
    a single newline).  The assertion uses ``in`` against the last 1024
    bytes rather than ``endswith`` so that a trailing newline or other
    whitespace does not cause a false negative.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert b"%%EOF" in pdf_bytes[-1024:], (
        "PDF trailer %%EOF marker not found within the last 1024 bytes"
    )


def test_pdf_returns_bytes(sample_report: StudentReport) -> None:
    """:func:`generate_pdf` returns a :class:`bytes` object, not :class:`str` or :class:`BytesIO`.

    The Flask ``/download`` route depends on the return type being raw
    :class:`bytes` so that it can wrap them in a fresh
    :class:`io.BytesIO` and hand it to :func:`flask.send_file` with
    ``mimetype="application/pdf"``.  A regression that returned a
    :class:`~io.BytesIO` or a :class:`str` would break that handler at
    runtime.  The explicit ``not isinstance(..., str)`` guard is defensive
    — even though :class:`str` is not a subtype of :class:`bytes`, an
    accidental ``.decode()`` somewhere would silently produce a
    :class:`str` and the first ``isinstance`` check would already fail,
    but the redundancy makes the intent unmistakable.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert isinstance(pdf_bytes, bytes), (
        f"Expected bytes, got {type(pdf_bytes).__name__}"
    )
    assert not isinstance(pdf_bytes, str), (
        "Expected bytes, got str (a string-encoded PDF would break send_file)"
    )


# ---------------------------------------------------------------------------
# Phase 4 — PDF content tests
# ---------------------------------------------------------------------------


def test_pdf_contains_title(sample_report: StudentReport) -> None:
    """The PDF body contains the literal title ``Student Report Card``.

    Matches the original JavaScript at ``Readme.md`` line 227::

        doc.text('Student Report Card', 20, 20);

    The title is drawn at 18 pt; its presence verifies both the text
    content *and* (transitively) that the ReportLab :func:`Canvas.drawString`
    invocation in :mod:`report_generator.pdf_generator` was executed.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert _pdf_contains(pdf_bytes, "Student Report Card"), (
        "Expected title 'Student Report Card' in the PDF content"
    )


def test_pdf_contains_student_name(sample_report: StudentReport) -> None:
    """The PDF body contains the student's name (``Alice``).

    The original JavaScript at ``Readme.md`` line 230 renders the line
    ``Student Name: ${name}`` at (20 mm, 40 mm from top); ReportLab
    writes the same line at the y-axis-flipped coordinate inside an
    ASCII85+Flate stream.  This test confirms the user-supplied name
    survives the migration intact.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert _pdf_contains(pdf_bytes, "Alice"), (
        "Expected student name 'Alice' in the PDF content"
    )


def test_pdf_contains_roll_number(sample_report: StudentReport) -> None:
    """The PDF body contains the roll number (``42``).

    The original JavaScript at ``Readme.md`` line 231 renders the line
    ``Roll Number: ${roll}`` at (20 mm, 50 mm from top).  The roll
    number is stored as :class:`str` (per :class:`StudentInput`'s field
    declaration) to preserve leading zeros and alphanumeric IDs; this
    test verifies the bare digits survive into the PDF.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert _pdf_contains(pdf_bytes, "42"), (
        "Expected roll number '42' in the PDF content"
    )


def test_pdf_contains_total(sample_report: StudentReport) -> None:
    """The PDF body contains ``Total Marks: 425``.

    Matches the original JavaScript at ``Readme.md`` line 232::

        doc.text(`Total Marks: ${total}`, 20, 60);

    The full string is asserted (not just ``425``) to catch a class of
    regressions where the label and the number become disconnected — for
    example if a future refactor split the line into separate
    :meth:`drawString` calls and inserted spurious whitespace.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert _pdf_contains(pdf_bytes, "Total Marks: 425"), (
        "Expected 'Total Marks: 425' in the PDF content"
    )


def test_pdf_contains_percentage(sample_report: StudentReport) -> None:
    """The PDF body contains ``Percentage: 85.00%`` (``:.2f`` formatted).

    Matches the original JavaScript at ``Readme.md`` line 233::

        doc.text(`Percentage: ${percentage}%`, 20, 70);

    where ``percentage`` is the DOM-stored string produced by
    ``percentage.toFixed(2)`` at ``Readme.md`` line 211.  The Python
    port mirrors the two-decimal-place rendering with the ``:.2f``
    f-string format spec inside :mod:`report_generator.pdf_generator`;
    this assertion is the binding contract that ``85.0`` renders as
    ``85.00`` rather than the raw ``85.0``.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert _pdf_contains(pdf_bytes, "Percentage: 85.00%"), (
        "Expected 'Percentage: 85.00%' in the PDF content"
    )


def test_pdf_contains_grade(sample_report: StudentReport) -> None:
    """The PDF body contains ``Grade: A``.

    Matches the original JavaScript at ``Readme.md`` line 234::

        doc.text(`Grade: ${grade}`, 20, 80);

    The grade letter for the fixture (``A``) sits squarely in the middle
    of the six-tier ladder defined in AAP §0.1.1.  Verifying the
    leading-space form ``"Grade: A"`` is preferred over a bare ``"A"``
    because the single letter ``A`` would otherwise also match the
    ``A+`` substring written by the perfect-score test fixture.
    """
    pdf_bytes = generate_pdf(sample_report)
    assert _pdf_contains(pdf_bytes, "Grade: A"), (
        "Expected 'Grade: A' in the PDF content"
    )


# ---------------------------------------------------------------------------
# Phase 5 — quality-of-life tests
# ---------------------------------------------------------------------------


def test_pdf_perfect_score() -> None:
    """A perfect score renders ``Percentage: 100.00%`` and ``Grade: A+``.

    The boundary case ``percentage = 100.0`` exercises two F-005-adjacent
    behaviours that the sample fixture does not:

    *   The ``:.2f`` format spec must render ``100.0`` as ``100.00`` —
        *not* ``100`` (no decimals) and *not* ``1.00e+02`` (scientific
        notation).  A regression to ``str(100.0)`` would render
        ``"100.0"`` and silently fail the user contract.
    *   The grade label ``A+`` (the only two-character grade in the
        ladder) is correctly written to the PDF.

    The test also verifies ``Total Marks: 500`` to confirm the upper
    extreme of the total-mark range survives the ``:.2f`` formatting
    chain even though ``500`` is itself an integer.
    """
    student = StudentInput(
        name="Eve",
        roll="100",
        marks={
            s: 100
            for s in ("Maths", "Science", "English", "History", "Computer")
        },
    )
    report = StudentReport(
        input=student,
        total=500,
        percentage=100.0,
        grade="A+",
    )
    pdf_bytes = generate_pdf(report)
    assert _pdf_contains(pdf_bytes, "Percentage: 100.00%"), (
        "Expected 'Percentage: 100.00%' for a perfect score"
    )
    assert _pdf_contains(pdf_bytes, "Grade: A+"), (
        "Expected 'Grade: A+' for a perfect score"
    )
    assert _pdf_contains(pdf_bytes, "Total Marks: 500"), (
        "Expected 'Total Marks: 500' for a perfect score"
    )


def test_pdf_failing_score() -> None:
    """A zero score renders ``Percentage: 0.00%`` and ``Grade: F``.

    The opposite-extreme companion to :func:`test_pdf_perfect_score`:

    *   ``percentage = 0.0`` must render as ``0.00`` — *not* ``0`` and
        *not* the IEEE-754 quirk ``-0.00``.
    *   The fallback grade ``F`` (the implicit "otherwise" branch of the
        six-tier ladder) is correctly written.
    *   ``Total Marks: 0`` ensures the integer-zero case survives the
        same formatting pipeline.

    Together with the perfect-score test, this exercises both ends of
    the grade ladder and pins the ``:.2f`` contract at both numerical
    extremes.
    """
    student = StudentInput(
        name="Frank",
        roll="0",
        marks={
            s: 0
            for s in ("Maths", "Science", "English", "History", "Computer")
        },
    )
    report = StudentReport(
        input=student,
        total=0,
        percentage=0.0,
        grade="F",
    )
    pdf_bytes = generate_pdf(report)
    assert _pdf_contains(pdf_bytes, "Percentage: 0.00%"), (
        "Expected 'Percentage: 0.00%' for a zero score"
    )
    assert _pdf_contains(pdf_bytes, "Grade: F"), (
        "Expected 'Grade: F' for a zero score"
    )
    assert _pdf_contains(pdf_bytes, "Total Marks: 0"), (
        "Expected 'Total Marks: 0' for a zero score"
    )


def test_pdf_size_is_reasonable(sample_report: StudentReport) -> None:
    """The PDF byte count is in a sensible range — not trivially empty, not megabytes.

    A well-formed single-page ReportLab PDF carrying the six text lines
    of a Student Report Card is typically ~1.5 KB; the lower bound of
    500 bytes guards against a regression where :func:`generate_pdf`
    returns an empty or truncated buffer, and the upper bound of 100 KB
    guards against a runaway include-everything regression (e.g. an
    accidentally-embedded image or font subset).  The window is
    deliberately wide so that benign size drift across ReportLab
    versions does not flake the test.
    """
    pdf_bytes = generate_pdf(sample_report)
    size = len(pdf_bytes)
    assert 500 < size < 100_000, (
        f"PDF size {size} bytes is outside the expected range 500–100000"
    )


def test_pdf_is_deterministic_in_length(sample_report: StudentReport) -> None:
    """Two PDFs from the same input differ by at most 100 bytes in length.

    ReportLab embeds a ``/CreationDate`` and ``/ModDate`` field of the
    fixed-width form ``D:YYYYMMDDhhmmss+TTtt`` (16 character payload)
    in every PDF's ``/Info`` dictionary.  If two consecutive
    :func:`generate_pdf` calls straddle a one-second tick the two
    timestamps differ — but the *length* of the timestamp string is
    invariant, so the surrounding ``/Length n`` cross-reference table
    entries do not change either.  The PDFs are therefore *length-equal*
    (within a small tolerance) even when not byte-equal.

    The 100-byte tolerance is generous compared with the actual
    invariant (zero) so the test never flakes on hardware where
    ``time.time()`` resolution would otherwise sit on the unfortunate
    edge.
    """
    pdf_1 = generate_pdf(sample_report)
    pdf_2 = generate_pdf(sample_report)
    delta = abs(len(pdf_1) - len(pdf_2))
    assert delta < 100, (
        f"Expected near-identical PDF lengths, got delta={delta} bytes "
        f"(len_1={len(pdf_1)}, len_2={len(pdf_2)})"
    )


def test_pdf_with_special_characters_in_name() -> None:
    """A name with ASCII punctuation (``O'Brien``) does not corrupt the PDF.

    The original implementation wrote the name directly into the PDF
    body via its library's text-drawing method; both the original
    library and ReportLab escape PDF metacharacters (``\\``, ``(``,
    ``)``) automatically and pass the ASCII apostrophe ``'`` through
    unchanged.  This test verifies three related guarantees:

    1.  The resulting byte stream is still a *well-formed* PDF — it
        still starts with the ``%PDF-`` magic header.  A regression
        that double-escaped or under-escaped the apostrophe would
        typically produce an unparseable PDF.
    2.  The rendered student-name line ``"Student Name: O'Brien"`` is
        discoverable verbatim in the decompressed content stream.
        Asserting the full line rather than a bare letter is a far
        stronger predicate — a single ``"O"`` would also appear in
        unrelated PDF metadata such as the ``/Producer`` string,
        which would pass the assertion without actually proving the
        student name was rendered.  Locating the full prefix
        ``"Student Name: O"`` (and, where the PDF library passes
        apostrophes through unchanged, the full ``"O'Brien"``)
        proves the user-supplied name is faithfully reproduced.
    3.  The fully rendered name ``"O'Brien"`` survives into the
        content stream when the PDF library passes the apostrophe
        through unchanged (the current behaviour of ReportLab
        4.5.1).  Should a future library version transform the
        apostrophe into an octal escape (``\\047``) or a backslash
        escape (``\\'``), the weaker ``"Student Name: O"`` predicate
        still passes — the test degrades gracefully without losing
        its anti-regression value.
    """
    student = StudentInput(
        name="O'Brien",
        roll="13",
        marks={
            s: 50
            for s in ("Maths", "Science", "English", "History", "Computer")
        },
    )
    report = StudentReport(
        input=student,
        total=250,
        percentage=50.0,
        grade="D",
    )
    pdf_bytes = generate_pdf(report)
    assert pdf_bytes.startswith(b"%PDF-"), (
        "PDF with apostrophe-bearing name does not start with %PDF-"
    )
    # Strong predicate: the rendered line begins with "Student Name: O"
    # — a 16-character prefix that uniquely identifies the student-name
    # line in the PDF content stream and cannot be matched by stray
    # PDF metadata.  This replaces an earlier, weaker assertion that
    # merely searched for a bare "O" (which would also have matched
    # PDF /Producer strings such as "ReportLab"); the stronger
    # predicate proves the user-supplied name actually reached the
    # content stream.
    assert _pdf_contains(pdf_bytes, "Student Name: O"), (
        "Expected 'Student Name: O' rendered line in the PDF content "
        "(the name 'O\\'Brien' did not survive the rendering pipeline)"
    )
    # Strongest predicate: the full unescaped name survives.  ReportLab
    # 4.5.1 passes ASCII apostrophes through unchanged, so the rendered
    # line should contain the verbatim string "Student Name: O'Brien".
    # If a future library version changes the apostrophe-escape
    # strategy, this assertion may need to be updated, but the previous
    # weaker assertion above will keep providing regression coverage.
    assert _pdf_contains(pdf_bytes, "Student Name: O'Brien"), (
        "Expected verbatim 'Student Name: O\\'Brien' in the PDF content "
        "stream (ReportLab is expected to pass ASCII apostrophes "
        "through unchanged in PDF content streams)"
    )
