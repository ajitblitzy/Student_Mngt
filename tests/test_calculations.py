"""Tests for compute_total and compute_percentage — F-002 contract verification.

This module exercises the two pure calculation functions exposed by
:mod:`report_generator.calculations` and proves that they are
behaviour-equivalent to the original JavaScript implementation that lived
in ``Readme.md`` lines 174–192 of the source repository::

    let total = 0;
    for (let subject in subjects) {
        total += subjects[subject];
    }
    const percentage = (total / 500) * 100;

The Python port replaces the hand-rolled for-in accumulator with the
C-implemented :func:`sum` builtin and surfaces the denominator ``500`` as
:data:`report_generator.models.MAX_TOTAL`.  The user rule
**Ajit_Test_Refactor** ("Refactor the code without changing the
functionality") demands that the *observable* arithmetic remain identical
— this test module is the executable proof of that promise for the F-002
feature contract (Total Marks and Percentage Calculation).

Design notes
------------
*   Tests are grouped by phase to mirror the agent-prompt structure:

    - **Phase 2** — individual ``compute_total`` cases (perfect / zero /
      mixed) drawn from the F-002 acceptance examples.
    - **Phase 3** — individual ``compute_percentage`` cases mirroring the
      same three F-002 acceptance scenarios.
    - **Phase 4** — type-return guards.  Important because ``True is 1``
      in Python: without the ``not isinstance(result, bool)`` check, a
      regression that returned ``True``/``False`` from ``compute_total``
      would silently pass equality assertions.
    - **Phase 5** — parametrized tables that compress repetitive cases
      per the folder requirement "use pytest.parametrize where it
      tightens the code".
    - **Phase 6** — edge cases: empty dict, single subject, custom
      denominator, default denominator, key-order invariance, and float
      precision.

*   Every test signature carries PEP 484 type hints and every test
    function carries a PEP 257 docstring per AAP §0.7.5.
*   ``pytest.approx`` is used only where IEEE-754 representation would
    introduce trailing-bit noise — exact-equality assertions are
    preferred for all other cases per the testing best practice "be
    strict where you can, lenient where you must".
*   The only test dependency is :mod:`pytest` per AAP §0.5.1.
*   ``from __future__ import annotations`` (PEP 563) lets the
    parametrized test signature use the modern ``dict[str, int]`` syntax
    without runtime evaluation overhead on Python 3.10+.
"""

from __future__ import annotations

import pytest

from report_generator.calculations import compute_percentage, compute_total


# ---------------------------------------------------------------------------
# Phase 2: compute_total — individual acceptance cases
# ---------------------------------------------------------------------------


def test_compute_total_perfect_score() -> None:
    """All-100s yield a total of 500 (the maximum possible)."""
    marks = {"Maths": 100, "Science": 100, "English": 100, "History": 100, "Computer": 100}
    assert compute_total(marks) == 500


def test_compute_total_zero_score() -> None:
    """All-zeros yield a total of 0.

    Matches the original JS behaviour when every form field is empty:
    ``parseInt("" || 0)`` returns ``0`` for each subject, so the
    accumulator stays at ``0``.
    """
    marks = {"Maths": 0, "Science": 0, "English": 0, "History": 0, "Computer": 0}
    assert compute_total(marks) == 0


def test_compute_total_mixed() -> None:
    """Mixed marks: 45+55+65+75+85 = 325 — an F-002 acceptance scenario."""
    marks = {"Maths": 45, "Science": 55, "English": 65, "History": 75, "Computer": 85}
    assert compute_total(marks) == 325


# ---------------------------------------------------------------------------
# Phase 3: compute_percentage — individual acceptance cases
# ---------------------------------------------------------------------------


def test_compute_percentage_perfect() -> None:
    """A total of 500 yields percentage 100.0."""
    assert compute_percentage(500) == 100.0


def test_compute_percentage_zero() -> None:
    """A total of 0 yields percentage 0.0 — F-002 acceptance case."""
    assert compute_percentage(0) == 0.0


def test_compute_percentage_mixed() -> None:
    """A total of 325 yields percentage 65.0 (= 325/500*100)."""
    assert compute_percentage(325) == 65.0


# ---------------------------------------------------------------------------
# Phase 4: Type-return guards
# ---------------------------------------------------------------------------


def test_compute_total_returns_int() -> None:
    """``compute_total`` returns a Python :class:`int` (NOT float, NOT bool).

    The ``not isinstance(result, bool)`` assertion is essential because
    :class:`bool` is a subclass of :class:`int` in Python (``True is 1``).
    Without this guard, a regression that accidentally returned a
    :class:`bool` would silently pass the ``isinstance(result, int)``
    check — exactly the kind of regression this test exists to catch.
    """
    marks = {"Maths": 50, "Science": 50, "English": 50, "History": 50, "Computer": 50}
    result = compute_total(marks)
    assert isinstance(result, int)
    assert not isinstance(result, bool)  # bool is subclass of int — exclude
    assert result == 250


def test_compute_percentage_returns_float() -> None:
    """``compute_percentage`` returns a Python :class:`float`.

    Python 3's ``/`` operator always performs true division and returns
    a :class:`float` — even when both operands are :class:`int`.  This
    test pins the contract so a regression that re-introduced integer
    division (``//``) or rounding (:func:`round`) would be caught.
    """
    result = compute_percentage(325)
    assert isinstance(result, float)
    assert result == 65.0


# ---------------------------------------------------------------------------
# Phase 5: Parametrized tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("marks", "expected_total"),
    [
        # Maximum possible — all five subjects at 100
        ({"Maths": 100, "Science": 100, "English": 100, "History": 100, "Computer": 100}, 500),
        # Minimum possible — all five subjects at 0 (F-002 acceptance case)
        ({"Maths": 0, "Science": 0, "English": 0, "History": 0, "Computer": 0}, 0),
        # F-002 mixed-mark acceptance scenario
        ({"Maths": 45, "Science": 55, "English": 65, "History": 75, "Computer": 85}, 325),
        # A second mixed example — higher band
        ({"Maths": 90, "Science": 85, "English": 80, "History": 75, "Computer": 95}, 425),
        # Uniform 50s — middle band
        ({"Maths": 50, "Science": 50, "English": 50, "History": 50, "Computer": 50}, 250),
        # Increasing sequence
        ({"Maths": 10, "Science": 20, "English": 30, "History": 40, "Computer": 50}, 150),
        # Empty mapping edge case — sum of an empty iterable is 0
        ({}, 0),
    ],
)
def test_compute_total_parametrized(marks: dict[str, int], expected_total: int) -> None:
    """``compute_total`` returns the correct sum for a representative range of inputs.

    Compresses what would otherwise be seven nearly-identical test
    functions into a single parametrized table.  Each row is independent
    — there is no shared state between parametrize iterations.
    """
    assert compute_total(marks) == expected_total


@pytest.mark.parametrize(
    ("total", "expected_percentage"),
    [
        (500, 100.0),  # Perfect score
        (0, 0.0),      # Zero score (F-002 acceptance case)
        (325, 65.0),   # F-002 mixed acceptance scenario
        (425, 85.0),   # Upper-band mixed
        (250, 50.0),   # D/F threshold value
        (150, 30.0),   # Mid-F band
        (450, 90.0),   # A/A+ threshold value
        (375, 75.0),   # B/B+ mid
        (100, 20.0),   # Low-F band
    ],
)
def test_compute_percentage_parametrized(total: int, expected_percentage: float) -> None:
    """``compute_percentage`` returns ``total/500*100`` for a representative range of inputs.

    All chosen totals divide evenly by 5 so the resulting percentages are
    exactly representable as IEEE-754 floats — no ``pytest.approx`` is
    required for these specific values.  Precision-sensitive cases live
    in :func:`test_compute_percentage_precision` below.
    """
    assert compute_percentage(total) == expected_percentage


# ---------------------------------------------------------------------------
# Phase 6: Edge-case tests
# ---------------------------------------------------------------------------


def test_compute_total_empty_dict() -> None:
    """``compute_total`` on an empty mapping returns 0 (sum of an empty iterable).

    This matches the JavaScript behaviour when every form field is empty:
    ``parseInt("" || 0) → 0`` for each subject, so the accumulator
    finishes at ``0 + 0 + 0 + 0 + 0 = 0``.  The Python equivalent — an
    empty :class:`dict` — bypasses the iteration entirely and returns
    the additive identity ``0`` directly, preserving the behavioural
    contract.
    """
    assert compute_total({}) == 0


def test_compute_total_single_subject() -> None:
    """``compute_total`` with one subject returns that subject's mark.

    Demonstrates that the function does not impose the canonical five-
    subject constraint at the calculation layer; subject-set validation
    is the responsibility of the caller (typically the Flask request
    handler).  Keeping ``compute_total`` agnostic to the subject set
    makes it trivially reusable from CLI scripts, test fixtures, and
    hypothetical future report types.
    """
    assert compute_total({"Maths": 87}) == 87


def test_compute_percentage_with_custom_max_total() -> None:
    """``compute_percentage`` accepts a custom ``max_total`` denominator.

    Verifies the optional ``max_total`` keyword argument works as
    documented in :func:`report_generator.calculations.compute_percentage`.
    Two cases are checked: ``50/100*100 = 50.0`` (non-default
    denominator) and ``250/500*100 = 50.0`` (explicit default).  Both
    must yield exactly ``50.0`` — the equality of these two cases at the
    *same* percentage proves the denominator is honoured.
    """
    assert compute_percentage(50, max_total=100) == 50.0
    assert compute_percentage(250, max_total=500) == 50.0


def test_compute_percentage_with_default_max_total() -> None:
    """``compute_percentage`` uses 500 as the default ``max_total``.

    Preserves the original JS formula ``(total / 500) * 100`` exactly:
    when ``max_total`` is omitted, the function must behave identically
    to the JavaScript line at ``Readme.md`` line 192.
    """
    # 250/500*100 = 50.0
    assert compute_percentage(250) == 50.0
    # 100/500*100 = 20.0
    assert compute_percentage(100) == 20.0


def test_compute_total_subject_order_irrelevant() -> None:
    """``compute_total`` is order-independent — addition is commutative.

    Although Python 3.7+ guarantees dict iteration in insertion order,
    :func:`sum` does not depend on the order in which it sees its
    operands.  This test pins that property so a hypothetical future
    refactor that introduced order-dependent logic (for example a
    short-circuit or an early-exit) would be caught immediately.
    """
    marks_order1 = {"Maths": 10, "Science": 20, "English": 30}
    marks_order2 = {"English": 30, "Maths": 10, "Science": 20}
    assert compute_total(marks_order1) == compute_total(marks_order2) == 60


def test_compute_percentage_precision() -> None:
    """``compute_percentage`` produces predictable float results.

    Three precision regimes are exercised:

    * **Exactly representable** — ``250/500*100`` is ``50.0`` to the bit,
      so strict equality is safe.
    * **Round-trip exact** — ``1/500`` is *not* exactly representable
      (``0.002`` has no terminating binary expansion), but the product
      ``(1/500)*100 == 0.2`` evaluates to the same IEEE-754 bit pattern
      as the literal ``0.2`` due to a fortuitous rounding alignment, so
      strict equality is still safe in CPython 3.13.
    * **Trailing-bit noise** — ``333/500*100`` evaluates to
      ``66.60000000000001``, *not* ``66.6``, because both ``333/500``
      and the subsequent multiplication accumulate rounding error.
      :func:`pytest.approx` is required here to tolerate that final bit
      of noise.
    """
    # 250/500*100 = 50.0 (exactly representable)
    assert compute_percentage(250) == 50.0
    # 1/500*100 = 0.2 (exact in CPython's IEEE-754 implementation)
    assert compute_percentage(1) == 0.2
    # 333/500*100 = 66.6 ± epsilon — must use approx
    assert compute_percentage(333) == pytest.approx(66.6)
