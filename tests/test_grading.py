"""Tests for the grade assignment logic — F-003 contract verification.

This module exercises :func:`report_generator.grading.assign_grade` against
every threshold boundary of the six-tier grade ladder
(``A+``/``A``/``B``/``C``/``D``/``F``) defined in the F-003 feature contract
and originally implemented as the JavaScript ``if`` / ``else if`` chain at
``Readme.md`` lines 194–206::

    let grade = 'F';
    if (percentage >= 90)      { grade = 'A+'; }
    else if (percentage >= 80) { grade = 'A';  }
    else if (percentage >= 70) { grade = 'B';  }
    else if (percentage >= 60) { grade = 'C';  }
    else if (percentage >= 50) { grade = 'D';  }

The test design follows the Test-Driven Development discipline encoded in
the user rule **Ajit_Test_Refactor** ("Refactor the code without changing
the functionality") and the AAP §0.7 quality bar.  Specifically:

* **Boundary exhaustiveness.**  Every threshold (50, 60, 70, 80, 90) is
  exercised with three values — just below, exactly at, and just above —
  using :func:`pytest.mark.parametrize`.  Because the original ladder uses
  ``>=``, the threshold value itself must map to the *higher* grade; an
  off-by-one regression would be caught immediately by the "exactly-at"
  pair (e.g. ``50.0 → "D"``, not ``"F"``).
* **Mid-range smoke tests.**  Six dedicated tests exercise the middle of
  each grade band, providing easy-to-read regression assertions distinct
  from the dense parametrized table.
* **Type variation.**  ``assign_grade`` is annotated ``percentage: float``
  but Python's numeric tower treats ``int`` and ``float`` identically for
  the ``>=`` operator, so passing ``int`` must yield the same grade.  A
  dedicated test pins this behaviour so a future change to ``isinstance``
  guards would be detected.
* **Edge cases.**  Negative percentages and percentages above 100 are
  defensively tested — the original JavaScript imposes no upper or lower
  bound on the input, and we preserve that permissive contract.
* **Cache observability.**  :func:`assign_grade` is wrapped by
  :func:`functools.lru_cache` per AAP §0.3.3.  The cache's ``cache_info``
  and ``cache_clear`` introspection helpers are exercised to confirm the
  decorator is actually applied (a missing decorator would yield an
  :class:`AttributeError` on the first ``cache_clear`` call).

All test functions carry PEP 484 type hints and PEP 257 docstrings per
AAP §0.7.5; the only external test dependency is :mod:`pytest` per AAP
§0.5.1.
"""

from __future__ import annotations

import pytest

from report_generator.grading import assign_grade


# ---------------------------------------------------------------------------
# Phase 2: Boundary tests (every threshold, three values each)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("percentage", "expected_grade"),
    [
        # F to D boundary (50.0 threshold) — values strictly below 50 stay F
        (0.0, "F"),
        (49.99, "F"),
        (50.0, "D"),
        (50.01, "D"),
        # D to C boundary (60.0 threshold)
        (59.99, "D"),
        (60.0, "C"),
        (60.01, "C"),
        # C to B boundary (70.0 threshold)
        (69.99, "C"),
        (70.0, "B"),
        (70.01, "B"),
        # B to A boundary (80.0 threshold)
        (79.99, "B"),
        (80.0, "A"),
        (80.01, "A"),
        # A to A+ boundary (90.0 threshold)
        (89.99, "A"),
        (90.0, "A+"),
        (90.01, "A+"),
        # Upper bound — 100 is the natural maximum for a percentage
        (100.0, "A+"),
    ],
)
def test_assign_grade_boundaries(percentage: float, expected_grade: str) -> None:
    """Verify every grade-threshold boundary preserves the original JS semantics.

    The original JS ladder at ``Readme.md`` lines 194–206 uses ``>=`` for
    every threshold, so the threshold value itself belongs to the *higher*
    grade.  This parametrized test exercises three points around each of
    the five thresholds (50, 60, 70, 80, 90) plus the natural endpoints
    (0 and 100), giving 17 distinct test runs that together pin the entire
    grading contract.
    """
    assert assign_grade(percentage) == expected_grade


# ---------------------------------------------------------------------------
# Phase 3: Individual mid-range tests
# ---------------------------------------------------------------------------


def test_assign_grade_F_mid_range() -> None:
    """Mid-F range returns 'F'."""
    assert assign_grade(25.0) == "F"


def test_assign_grade_D_mid_range() -> None:
    """Mid-D range returns 'D'."""
    assert assign_grade(55.0) == "D"


def test_assign_grade_C_mid_range() -> None:
    """Mid-C range returns 'C'."""
    assert assign_grade(65.0) == "C"


def test_assign_grade_B_mid_range() -> None:
    """Mid-B range returns 'B'."""
    assert assign_grade(75.0) == "B"


def test_assign_grade_A_mid_range() -> None:
    """Mid-A range returns 'A'."""
    assert assign_grade(85.0) == "A"


def test_assign_grade_A_plus_mid_range() -> None:
    """Mid-A+ range returns 'A+'."""
    assert assign_grade(95.0) == "A+"


# ---------------------------------------------------------------------------
# Phase 4: Type variation tests
# ---------------------------------------------------------------------------


def test_assign_grade_accepts_int() -> None:
    """``assign_grade`` accepts ``int`` input and returns the correct grade.

    Python's ``>=`` operator handles ``int >= int`` and ``int >= float``
    identically, so passing an ``int`` produces the same result as passing
    the equivalent ``float``.  This test pins that behaviour so a future
    regression that adds an ``isinstance(percentage, float)`` guard would
    be caught immediately.
    """
    assert assign_grade(90) == "A+"
    assert assign_grade(85) == "A"
    assert assign_grade(75) == "B"
    assert assign_grade(65) == "C"
    assert assign_grade(55) == "D"
    assert assign_grade(45) == "F"


def test_assign_grade_returns_str() -> None:
    """``assign_grade`` returns a Python :class:`str` (not :class:`bytes`, not
    :class:`enum.Enum`).

    The F-003 contract names the grades as plain string literals ("A+",
    "A", "B", "C", "D", "F").  This test guards against a well-intentioned
    refactor that promotes the return value to an :class:`enum.Enum` or
    :class:`bytes` — either change would silently break template rendering
    and PDF generation, which both consume the value as a ``str``.
    """
    result = assign_grade(85.0)
    assert isinstance(result, str)
    assert result == "A"


# ---------------------------------------------------------------------------
# Phase 5: Edge-case tests
# ---------------------------------------------------------------------------


def test_assign_grade_exactly_50() -> None:
    """A percentage of exactly 50.0 returns 'D' (boundary belongs to higher grade)."""
    assert assign_grade(50.0) == "D"


def test_assign_grade_just_below_50() -> None:
    """A percentage just below 50.0 returns 'F' (default for non-matching)."""
    assert assign_grade(49.999999) == "F"


def test_assign_grade_negative_returns_F() -> None:
    """Negative percentage (defensive — shouldn't occur in practice) returns 'F'.

    The original JavaScript ladder does not validate the lower bound, so a
    negative value simply falls through every ``>=`` test and the function
    returns the default ``'F'``.  This test preserves that permissive
    contract.
    """
    assert assign_grade(-10.0) == "F"


def test_assign_grade_above_100() -> None:
    """Percentage above 100 (defensive — shouldn't occur in practice) returns 'A+'.

    The original JavaScript ladder has no upper-bound guard; any value
    ``>= 90`` matches the first arm of the ``if`` chain and returns
    ``'A+'``.  This test preserves that permissive contract — a future
    change that adds an upper-bound clamp would alter observable behaviour
    and is forbidden by the user rule *Ajit_Test_Refactor*.
    """
    assert assign_grade(150.0) == "A+"


# ---------------------------------------------------------------------------
# Phase 6: lru_cache behaviour verification
# ---------------------------------------------------------------------------


def test_assign_grade_uses_lru_cache() -> None:
    """``assign_grade`` is decorated with :func:`functools.lru_cache` and
    caches results.

    Per AAP §0.3.3 the function carries ``@lru_cache(maxsize=128)`` as
    cheap-insurance memoisation.  The decorator exposes the standard
    introspection helpers :meth:`cache_info` (returning a ``CacheInfo``
    named-tuple with ``hits``, ``misses``, ``maxsize``, ``currsize``) and
    :meth:`cache_clear` on the wrapped function — calling either of these
    on a non-decorated function would raise :class:`AttributeError`, so
    this test serves as a runtime guard that the decorator is actually
    applied.

    The assertions use ``>=`` rather than ``==`` because the cache may
    already contain entries from earlier tests within the same pytest
    session; the call to :meth:`cache_clear` resets that state so the
    deltas are well-defined.
    """
    # Reset cache state so this test is idempotent across reruns and
    # independent of any cache pollution from other tests in the session.
    assign_grade.cache_clear()

    # First call with a fresh percentage value: must be a cache miss.
    assign_grade(85.0)
    info_after_first = assign_grade.cache_info()
    assert info_after_first.misses >= 1
    assert info_after_first.currsize >= 1

    # Second call with the SAME input: must hit the cache.
    assign_grade(85.0)
    info_after_second = assign_grade.cache_info()
    assert info_after_second.hits >= 1
