"""Grade assignment based on percentage thresholds.

This module maps a numeric percentage (typically 0.0–100.0, though values
outside that range are handled deterministically) to a single-letter grade
drawn from the six-tier ladder ``{"A+", "A", "B", "C", "D", "F"}``.  It is
a direct, behaviour-preserving port of the JavaScript ``if`` / ``else if``
ladder that lived in ``Readme.md`` lines 194–206 of the original
implementation::

    let grade = 'F';
    if (percentage >= 90)      { grade = 'A+'; }
    else if (percentage >= 80) { grade = 'A';  }
    else if (percentage >= 70) { grade = 'B';  }
    else if (percentage >= 60) { grade = 'C';  }
    else if (percentage >= 50) { grade = 'D';  }

Public surface
--------------
:data:`GRADE_THRESHOLDS`
    Five ``(min_percentage, grade_letter)`` tuples in descending order of
    threshold.  This is the data driving the lookup; the *order matters*
    because :func:`assign_grade` returns the first matching grade.
:data:`DEFAULT_GRADE`
    The grade returned when *no* threshold is satisfied (i.e. when the
    percentage is strictly less than 50).  Equal to ``"F"``.
:func:`assign_grade`
    Pure function that performs the lookup.  Decorated with
    :func:`functools.lru_cache` so repeated calls with the same percentage
    avoid the linear scan.  The cache wrapper exposes the standard
    introspection helpers :meth:`assign_grade.cache_info` and
    :meth:`assign_grade.cache_clear`.

Design notes
------------
*   **Boundary semantics are preserved exactly.**  The original ladder uses
    ``>=`` (greater-than-or-equal), so each threshold value itself belongs
    to the *higher* grade — ``90.0`` is an ``"A+"``, ``89.99`` is an
    ``"A"``, and so on.  This module replicates that with the same operator.
*   **First match wins.**  Because the tuples are ordered from highest
    threshold to lowest, a simple top-to-bottom linear scan reproduces the
    short-circuit semantics of the JavaScript ``if`` / ``else if`` chain.
*   **No magic numbers, no magic strings.**  The threshold integers
    (``90``, ``80``, ``70``, ``60``, ``50``) and the grade letters
    (``"A+"``, ``"A"``, ``"B"``, ``"C"``, ``"D"``) appear *only* inside
    :data:`GRADE_THRESHOLDS`; the fallback letter ``"F"`` appears *only*
    inside :data:`DEFAULT_GRADE`.  This honours AAP §0.7.5.
*   **Cheap-insurance caching.**  Per AAP §0.3.3, the
    :func:`functools.lru_cache` decorator with ``maxsize=128`` memoises
    results.  In the typical single-request web flow only one call is
    made per request, so the cache is effectively a no-op — but it is
    harmless and yields a constant-time hit for any batch caller (for
    example a hypothetical future endpoint that grades many students at
    once).
*   **Type qualifier discipline.**  The two module-level constants are
    annotated with :data:`typing.Final` so static analysers (mypy,
    pyright) flag any accidental reassignment.  ``from __future__ import
    annotations`` enables PEP 563 postponed evaluation, allowing the
    ``tuple[tuple[float, str], ...]`` subscription syntax to be used as
    an annotation without runtime evaluation cost.

This module honours the user rule ``Ajit_Test_Refactor`` ("Refactor the
code without changing the functionality") by preserving the six grade
labels, the five threshold values, the ``>=`` boundary operator, and the
default-to-``"F"`` fallback exactly as they appeared in the original
JavaScript implementation.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Final


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


GRADE_THRESHOLDS: Final[tuple[tuple[float, str], ...]] = (
    (90, "A+"),
    (80, "A"),
    (70, "B"),
    (60, "C"),
    (50, "D"),
)
"""Six-tier grade ladder as ``(min_percentage, grade_letter)`` tuples.

The list is ordered from the highest threshold down to the lowest.  Because
:func:`assign_grade` returns the first tuple whose ``min_percentage`` is
``<=`` the input, this ordering is what implements the
"first-match-wins" semantics of the original JavaScript ``if`` / ``else if``
ladder at ``Readme.md`` lines 194–206.

Preserved verbatim from the original JavaScript:

============ ==========
threshold    grade
============ ==========
``>= 90``    ``"A+"``
``>= 80``    ``"A"``
``>= 70``    ``"B"``
``>= 60``    ``"C"``
``>= 50``    ``"D"``
``< 50``     ``"F"``  (see :data:`DEFAULT_GRADE`)
============ ==========

The :data:`typing.Final` qualifier combined with the use of an immutable
:class:`tuple` of :class:`tuple` ensures that this constant cannot be
silently mutated at runtime — any ``GRADE_THRESHOLDS[0] = ...`` attempt
raises :class:`TypeError`, and static analysers reject reassignment to the
name itself.

Integer literals are used for the threshold values (``90`` not ``90.0``)
because Python's ``>=`` operator handles mixed ``int``/``float`` comparisons
identically — ``90 >= 90.0`` and ``90.0 >= 90`` both evaluate to ``True``
— so the resulting type annotation ``tuple[tuple[float, str], ...]``
remains accurate (Python's numeric tower treats :class:`int` as a subtype
of :class:`float` for comparison purposes).
"""


DEFAULT_GRADE: Final[str] = "F"
"""The grade returned when no threshold in :data:`GRADE_THRESHOLDS` matches.

A percentage strictly below ``50`` falls through the entire threshold list
and receives this default.  Naming the value — rather than embedding the
literal ``"F"`` inside :func:`assign_grade` — eliminates the magic string
per AAP §0.7.5 and matches the original JavaScript initialisation at
``Readme.md`` line 194 (``let grade = 'F';``) which uses ``'F'`` as the
pre-loop default.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@lru_cache(maxsize=128)
def assign_grade(percentage: float) -> str:
    """Return the letter grade corresponding to ``percentage``.

    Scans :data:`GRADE_THRESHOLDS` in declaration order and returns the
    ``grade_letter`` of the first tuple whose ``min_percentage`` is less
    than or equal to ``percentage``.  When no threshold matches (i.e.
    ``percentage < 50``), returns :data:`DEFAULT_GRADE` (``"F"``).

    The comparison uses ``>=`` to match the original JavaScript ladder
    exactly — each threshold value itself belongs to the *higher* grade.

    Parameters
    ----------
    percentage : float
        The student's percentage as produced by
        :func:`report_generator.calculations.compute_percentage`.  Although
        annotated as :class:`float`, plain :class:`int` values are also
        accepted (Python's numeric coercion makes the comparison correct
        either way).

    Returns
    -------
    str
        One of ``"A+"``, ``"A"``, ``"B"``, ``"C"``, ``"D"``, or ``"F"``.

    Examples
    --------
    Threshold values themselves belong to the higher grade::

        >>> assign_grade(90.0)
        'A+'
        >>> assign_grade(89.99)
        'A'
        >>> assign_grade(80.0)
        'A'
        >>> assign_grade(49.99)
        'F'

    Values above the top threshold all map to ``"A+"``::

        >>> assign_grade(100.0)
        'A+'
        >>> assign_grade(150.0)
        'A+'

    Notes
    -----
    The :func:`functools.lru_cache` decorator memoises results with a
    cache of up to 128 entries.  Per AAP §0.3.3 this is *cheap insurance*
    for batch callers; in the typical single-request web flow only one
    call is made per request, so the cache rarely contains more than a
    handful of entries.  The decorator also exposes :meth:`cache_info`
    (returning hit/miss/size statistics) and :meth:`cache_clear` (resetting
    the cache) on the wrapped function — useful for tests that want to
    assert cache behaviour or isolate themselves from cross-test cache
    pollution.
    """
    for threshold, grade in GRADE_THRESHOLDS:
        if percentage >= threshold:
            return grade
    return DEFAULT_GRADE
