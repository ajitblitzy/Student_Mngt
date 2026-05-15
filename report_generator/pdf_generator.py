"""PDF generation using ReportLab, replacing the original browser-side JavaScript implementation.

This module is the *presentation* layer of the :mod:`report_generator`
package.  Its single public function, :func:`generate_pdf`, accepts a fully
computed :class:`~report_generator.models.StudentReport` and returns the
raw bytes of a PDF document whose visual layout is identical to the output
of the original ``downloadPDF()`` JavaScript function (``Readme.md`` lines
215–237).

Coordinate-system reconciliation (per AAP §0.6.1)
-------------------------------------------------
The original implementation used a browser-side PDF library with its
default top-left, millimetre-based coordinate system; ReportLab 4.5.1
uses different defaults.  Visual parity therefore requires an explicit
coordinate translation on every drawing call:

* **Source defaults** (original top-left millimetre coordinate system):
  origin at top-left corner, Y axis increases *downward*, units in
  millimetres (``mm``), default page A4 portrait (210 × 297 mm).
* **ReportLab default**: origin at bottom-left corner, Y axis increases
  *upward*, units in points (1 pt = 1/72 inch), A4 portrait expressed as
  (595.28 × 841.89 pt) — the same physical paper.
* **Translation rule**::

      reportlab_y_pt = (page_height_mm - source_y_mm) * mm

  where ``mm`` is :data:`reportlab.lib.units.mm` (≈ 2.834645669 pt/mm)
  and ``page_height_mm`` is :data:`PAGE_HEIGHT_MM` (= 297 for A4
  portrait).  The private helper :func:`_y` encapsulates this rule so the
  body of :func:`generate_pdf` reads exactly like the original JavaScript
  source, modulo the syntactic differences between JavaScript and Python.

Design notes
------------
*   The PDF is rendered into an in-memory :class:`io.BytesIO` buffer and
    returned as raw :class:`bytes` — no temporary files are ever written
    to disk (per AAP §0.3.3).  The caller (``app.py``'s ``/download``
    route) wraps these bytes in a fresh :class:`~io.BytesIO` for
    :func:`flask.send_file`.
*   Both the original PDF library and ReportLab ship Helvetica as a
    *standard* PDF Type 1 font (part of the PDF 1.4 specification, no
    font-file embedding required).  Character glyph rendering is
    therefore byte-for-byte equivalent between the two implementations.
*   The percentage value is formatted with the ``:.2f`` f-string spec to
    match the original JavaScript ``.toFixed(2)`` at ``Readme.md`` line
    211 — preserving exactly two decimal places.  This is a hard
    requirement of the user rule ``Ajit_Test_Refactor`` ("Refactor the
    code without changing the functionality").
*   ``from __future__ import annotations`` (PEP 563) enables postponed
    evaluation of type hints so the annotations are stored as strings
    rather than evaluated at import time — reducing import-time cost and
    eliminating forward-reference hazards.

This module honours the user rule ``Ajit_Test_Refactor`` by preserving
every observable property of the original PDF output: page size, font
family, font sizes (18 pt title, 12 pt body), title text, left margin
(20 mm), vertical spacing (10 mm between body lines), and filename
pattern (``<name>_Report.pdf`` — applied by the caller).
"""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .models import StudentReport

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

PAGE_HEIGHT_MM: int = 297  # A4 portrait height in mm
"""A4 portrait page height in millimetres.

Used by :func:`_y` to convert source top-left Y coordinates (measured
*downward* from the top of the page) into ReportLab bottom-left Y
coordinates (measured *upward* from the bottom of the page).  ReportLab's
own :data:`reportlab.lib.pagesizes.A4` constant is in *points*; we keep
the height available in *millimetres* here because the original source
coordinates are also in millimetres, which keeps the translation
arithmetic readable.
"""


TITLE_FONT_SIZE: int = 18
"""Title font size in points.

Matches the value passed to ``doc.setFontSize(18)`` in the original
JavaScript at ``Readme.md`` line 226.  Naming the constant — rather than
inlining the literal ``18`` — honours the "no magic numbers" requirement
of AAP §0.7.5.
"""


BODY_FONT_SIZE: int = 12
"""Body font size in points.

Matches the value passed to ``doc.setFontSize(12)`` in the original
JavaScript at ``Readme.md`` line 229.  Naming the constant honours the
"no magic numbers" requirement of AAP §0.7.5.
"""


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _y(source_y_mm: float) -> float:
    """Translate a source top-left mm Y-coordinate to a ReportLab bottom-left pt Y-coordinate.

    This is the core coordinate-system reconciliation routine documented at
    AAP §0.6.1.  It performs two operations in a single expression:

    1.  *Axis inversion* — subtracts the supplied Y from
        :data:`PAGE_HEIGHT_MM` to flip the origin from the top of the page
        (source coordinate system) to the bottom (ReportLab).
    2.  *Unit conversion* — multiplies by :data:`reportlab.lib.units.mm`
        (= 2.834645669 pt/mm) to convert millimetres to PDF points.

    Parameters
    ----------
    source_y_mm:
        Y coordinate in millimetres measured from the top of the page, as
        the original JavaScript expressed it (i.e. an original top-left
        millimetre coordinate).  May be any non-negative :class:`float` or
        :class:`int` ≤ :data:`PAGE_HEIGHT_MM`; values outside this range
        produce a coordinate off the visible page, which is the same
        behaviour the original code would exhibit.

    Returns
    -------
    float
        Y coordinate in points measured from the *bottom* of the page,
        suitable for direct use as the ``y`` argument of any ReportLab
        :class:`~reportlab.pdfgen.canvas.Canvas` drawing call.

    Examples
    --------
    >>> round(_y(20), 2)        # source y=20 mm from top  -> top of body area
    785.18
    >>> round(_y(80), 2)        # source y=80 mm from top  -> bottom-most line
    615.12
    """
    return (PAGE_HEIGHT_MM - source_y_mm) * mm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_pdf(report: StudentReport) -> bytes:
    """Render a :class:`StudentReport` as a PDF byte string.

    The PDF layout reproduces the original JavaScript implementation at
    ``Readme.md`` lines 215–237 *exactly*:

    *   Page format: A4 portrait (210 × 297 mm; 595 × 842 pt).
    *   Font family: Helvetica (a built-in PDF Type 1 font requiring no
        embedding).
    *   Title ``"Student Report Card"`` drawn at source coordinates
        (20 mm, 20 mm from top) in 18 pt.
    *   Five body lines drawn at source coordinates
        (20 mm, 40/50/60/70/80 mm from top) in 12 pt:

        1.  ``Student Name: <name>``
        2.  ``Roll Number: <roll>``
        3.  ``Total Marks: <total>``
        4.  ``Percentage: <percentage>%`` (two decimal places)
        5.  ``Grade: <grade>``

    The PDF is rendered into an in-memory :class:`io.BytesIO` buffer and
    returned as raw bytes — no disk I/O is performed.  The caller is
    responsible for setting the HTTP ``Content-Disposition`` header and
    filename (``<name>_Report.pdf`` per ``Readme.md`` line 236).

    Parameters
    ----------
    report:
        A fully computed :class:`StudentReport` carrying the
        :class:`~report_generator.models.StudentInput` (name, roll
        number) together with the three derived values
        (:attr:`~report_generator.models.StudentReport.total`,
        :attr:`~report_generator.models.StudentReport.percentage`,
        :attr:`~report_generator.models.StudentReport.grade`).

    Returns
    -------
    bytes
        The PDF document as a sequence of bytes.  Always begins with the
        PDF magic header ``b"%PDF-"`` and ends with the PDF trailer
        sentinel ``b"%%EOF"`` (modulo a trailing newline).
    """
    # In-memory buffer — no temporary files, no disk I/O (per AAP §0.3.3).
    buffer = BytesIO()

    # ReportLab canvas pointed at the in-memory buffer, A4 portrait.
    c = canvas.Canvas(buffer, pagesize=A4)

    # ---- Title ----------------------------------------------------------
    # Matches original JavaScript:  doc.setFontSize(18); doc.text('Student Report Card', 20, 20);
    c.setFont("Helvetica", TITLE_FONT_SIZE)
    c.drawString(20 * mm, _y(20), "Student Report Card")

    # ---- Body lines -----------------------------------------------------
    # Matches original JavaScript:  doc.setFontSize(12); doc.text(..., 20, <40|50|60|70|80>);
    c.setFont("Helvetica", BODY_FONT_SIZE)
    c.drawString(20 * mm, _y(40), f"Student Name: {report.input.name}")
    c.drawString(20 * mm, _y(50), f"Roll Number: {report.input.roll}")
    c.drawString(20 * mm, _y(60), f"Total Marks: {report.total}")
    c.drawString(20 * mm, _y(70), f"Percentage: {report.percentage:.2f}%")
    c.drawString(20 * mm, _y(80), f"Grade: {report.grade}")

    # Finalise the PDF: this writes the cross-reference table and EOF marker
    # into the buffer.  After this call no further drawing is possible.
    c.save()

    # `buffer.getvalue()` returns the full contents irrespective of cursor
    # position; the explicit `seek(0)` is defensive — it documents that the
    # buffer is being treated as a fresh stream ready for reading and would
    # also make a subsequent `buffer.read()` work if any caller swapped to
    # streaming semantics in the future.
    buffer.seek(0)
    return buffer.getvalue()
