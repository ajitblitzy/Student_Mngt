"""Typed, immutable data containers for the Student Report Generator.

This module is the FOUNDATIONAL layer of the ``report_generator`` package.
It defines the immutable constants and frozen dataclasses that every other
module in the package consumes.  By design, it imports only from the Python
standard library and has no internal dependencies — keeping it at the bottom
of the package's dependency tree.

Public surface
--------------
:data:`SUBJECTS`
    The five fixed subject names (``Maths``, ``Science``, ``English``,
    ``History``, ``Computer``) whose marks make up a student's report.  The
    order is significant: it determines the on-screen table row order and
    the PDF row order, matching the original JavaScript object literal at
    ``Readme.md`` lines 166–171.
:data:`MAX_TOTAL`
    The denominator used by the percentage formula
    ``percentage = (total / MAX_TOTAL) * 100``.  Equals 500
    (= 5 subjects × 100 marks each), preserved verbatim from the original
    JavaScript at ``Readme.md`` line 192.
:class:`StudentInput`
    Immutable container for form-submitted data (name, roll number, marks).
:class:`StudentReport`
    Immutable container for the fully computed report (input + total +
    percentage + grade).

Design notes
------------
*   Both dataclasses use ``frozen=True`` and ``slots=True`` (PEP 557 + PEP
    557 amendment for slots).  Frozen instances raise
    :class:`dataclasses.FrozenInstanceError` on assignment, enforcing
    immutability at runtime.  ``__slots__`` removes the per-instance
    ``__dict__`` for a smaller memory footprint and faster attribute access.
*   ``from __future__ import annotations`` (PEP 563) enables postponed
    evaluation of type hints so that the parametrised generic
    ``Mapping[str, int]`` can be used as a dataclass field annotation
    without triggering runtime evaluation cost.
*   :data:`SUBJECTS` and :data:`MAX_TOTAL` are qualified with
    :data:`typing.Final` so static analysers (mypy, pyright) reject any
    reassignment attempt.
*   The :attr:`StudentInput.marks` field uses ``field(default_factory=dict)``
    rather than a literal ``{}`` because mutable defaults are forbidden in
    dataclasses — the factory creates a fresh empty dict for each new
    instance.

This module honours the user rule ``Ajit_Test_Refactor`` ("Refactor the code
without changing the functionality") by preserving the exact subject names,
order, and ``MAX_TOTAL`` value from the original JavaScript implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Mapping


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SUBJECTS: Final[tuple[str, ...]] = (
    "Maths",
    "Science",
    "English",
    "History",
    "Computer",
)
"""The five fixed subjects whose marks the student enters.

Order matters — it determines the on-screen table row order and the PDF row
order.  Preserved verbatim from the original JavaScript object literal at
``Readme.md`` lines 166–171::

    const subjects = {
        Maths:    parseInt(document.getElementById('maths').value    || 0),
        Science:  parseInt(document.getElementById('science').value  || 0),
        English:  parseInt(document.getElementById('english').value  || 0),
        History:  parseInt(document.getElementById('history').value  || 0),
        Computer: parseInt(document.getElementById('computer').value || 0)
    };

The :data:`Final` qualifier and use of an immutable :class:`tuple` together
guarantee — at both static-analysis time and runtime — that the canonical
subject list cannot be silently mutated by an unrelated caller.
"""


MAX_TOTAL: Final[int] = 500
"""The maximum possible total: 5 subjects × 100 marks each.

The percentage formula in :mod:`report_generator.calculations` uses this
value as the denominator::

    percentage = (total / MAX_TOTAL) * 100

Preserved verbatim from the original JavaScript at ``Readme.md`` line 192
(``const percentage = (total / 500) * 100;``).  Naming the constant — rather
than embedding the literal ``500`` in arithmetic expressions — honours the
"no magic numbers" requirement of AAP §0.7.5.
"""


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StudentInput:
    """The data entered by the user into the form.

    All three fields originate from HTML form inputs in ``templates/index.html``:

    * :attr:`name`  — populated from ``request.form['studentName']``
    * :attr:`roll`  — populated from ``request.form['rollNumber']``
    * :attr:`marks` — populated by parsing each subject's mark input into an
      ``int`` and assembling a ``{subject_name: mark}`` mapping.

    The class is frozen (PEP 557 ``frozen=True``) so an instance acts as a
    value type: attribute assignment after construction raises
    :class:`dataclasses.FrozenInstanceError`.  It is also slotted
    (``slots=True``) for reduced memory overhead.

    Notes
    -----
    *   :attr:`roll` is typed as :class:`str`, not :class:`int`.  The HTML
        form uses ``<input type="text" id="rollNumber">`` (``Readme.md``
        line 47), so the original JavaScript reads ``.value`` as a string —
        allowing alphanumeric roll numbers (e.g. ``"21A001"``) and preserving
        leading zeros.  Storing it as :class:`str` maintains exact parity
        with the JavaScript implementation.
    *   :attr:`marks` is typed with the covariant supertype
        :class:`typing.Mapping` rather than the concrete :class:`dict` so
        callers may pass any read-only mapping (for example a
        :class:`types.MappingProxyType` view).  The default factory still
        produces a plain :class:`dict`, which is a valid
        :class:`Mapping`.
    """

    name: str
    roll: str
    marks: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StudentReport:
    """The computed report for a single student.

    Aggregates the original :class:`StudentInput` with the three derived
    values:

    * :attr:`total`      — sum of all marks (produced by
      :func:`report_generator.calculations.compute_total`).
    * :attr:`percentage` — ``(total / MAX_TOTAL) * 100`` (produced by
      :func:`report_generator.calculations.compute_percentage`).
    * :attr:`grade`      — letter grade in the set
      ``{"A+", "A", "B", "C", "D", "F"}`` (produced by
      :func:`report_generator.grading.assign_grade`).

    Like :class:`StudentInput`, this dataclass is frozen and slotted: once
    a :class:`StudentReport` is built it can be safely passed through the
    request pipeline (template renderer, PDF generator) without any
    component being able to mutate it in transit.
    """

    input: StudentInput
    total: int
    percentage: float
    grade: str
