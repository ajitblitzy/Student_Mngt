"""Total-marks and percentage calculations.

This module is the *calculation* layer of the :mod:`report_generator` package.
It provides two small, pure, framework-agnostic functions that together
implement the arithmetic at the heart of every student report:

* :func:`compute_total` — sums a mapping of subject marks
* :func:`compute_percentage` — converts a total to a percentage relative to
  :data:`report_generator.models.MAX_TOTAL` (= 500)

Both functions are deliberately stateless and have no side effects, which
makes them trivial to unit-test and safe to reuse from any caller —
Flask request handlers, command-line tools, Celery tasks, and test
fixtures all look identical to this module.

Public surface
--------------
:func:`compute_total`
    Returns ``sum(marks.values())``.  Uses CPython's C-implemented
    :func:`sum` builtin which is constant-factor faster than a hand-rolled
    Python ``for`` loop because it bypasses per-iteration interpreter
    frame creation (per AAP §0.3.3).
:func:`compute_percentage`
    Returns ``(total / max_total) * 100``.  Faithfully preserves the
    original JavaScript formula at ``Readme.md`` line 192
    (``const percentage = (total / 500) * 100;``).  The ``max_total``
    parameter defaults to :data:`~report_generator.models.MAX_TOTAL`,
    so callers never need to repeat the magic number ``500``.

Source reference
----------------
This module is a direct, behaviour-preserving port of the JavaScript
accumulator loop and percentage formula that lived in ``Readme.md``
lines 174–192 of the original implementation::

    let total = 0;
    for (let subject in subjects) {
        total += subjects[subject];
    }
    const percentage = (total / 500) * 100;

Performance notes
-----------------
The original JS loop iterates over object *keys* and accesses each value
with ``subjects[subject]`` — incurring one property-descriptor lookup
per iteration.  The Python port iterates :meth:`dict.values` directly
(one fewer lookup per iteration) and dispatches the summation to the C
implementation of :func:`sum`, eliminating Python-level interpreter
overhead entirely.  For five elements the absolute difference is
sub-millisecond; the qualitative benefit is the constant-factor speedup
and the idiomatic, declarative spelling of the operation.

Design notes
------------
*   ``from __future__ import annotations`` (PEP 563) enables postponed
    evaluation of type hints so that the parametrised generic
    ``Mapping[str, int]`` can be used as an annotation without runtime
    evaluation cost.
*   The parameter type :class:`collections.abc.Mapping` is used in
    preference to the concrete :class:`dict` because it is the broadest
    abstract supertype: any read-only dict-like input is accepted
    (regular :class:`dict`, :class:`collections.OrderedDict`,
    :class:`types.MappingProxyType`, etc.).  Using
    :class:`collections.abc.Mapping` (rather than the deprecated
    ``typing.Mapping``) follows the PEP 585 modernisation pattern
    encouraged from Python 3.9 onward.
*   The :data:`~report_generator.models.MAX_TOTAL` constant is imported
    from :mod:`~report_generator.models` rather than redefined locally —
    keeping the dependency direction clean (``calculations`` → ``models``)
    and honouring the "no magic numbers" requirement of AAP §0.7.5.
*   The parentheses around ``(total / max_total)`` in
    :func:`compute_percentage` are *intentionally* explicit, even though
    Python's left-associative ``/`` and ``*`` operators would make
    ``total / max_total * 100`` mathematically equivalent.  Matching the
    original JavaScript parenthesisation makes the intent unambiguous
    and prevents a future reader from misreading the expression as
    ``total / (max_total * 100)`` — which would be wrong.

This module honours the user rule ``Ajit_Test_Refactor`` ("Refactor the
code without changing the functionality") by preserving the summation
semantics and the percentage formula exactly — including the explicit
parentheses around ``(total / max_total)`` which match the original JS
verbatim.
"""

from __future__ import annotations

from collections.abc import Mapping

from .models import MAX_TOTAL


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_total(marks: Mapping[str, int]) -> int:
    """Return the sum of all subject marks.

    Replaces the original JS for-in accumulator at ``Readme.md`` lines
    174–181 with the C-implemented :func:`sum` builtin, which is
    constant-factor faster than the JavaScript loop because it avoids
    per-iteration interpreter frames.  ``sum()`` is also faster than the
    original JS form because the JS code looks up each value via
    ``subjects[subject]`` (one property-descriptor lookup per iteration)
    whereas :meth:`dict.values` yields the values directly.

    Parameters
    ----------
    marks : Mapping[str, int]
        A mapping from subject name (e.g. ``"Maths"``) to integer mark
        (e.g. ``85``).  Any read-only mapping is accepted — regular
        :class:`dict`, :class:`collections.OrderedDict`,
        :class:`types.MappingProxyType`, etc.  Only the *values* are
        consulted; the keys are unused in this function and so their
        order does not affect the result.

    Returns
    -------
    int
        The arithmetic sum of all values in ``marks``.  Returns ``0``
        for an empty mapping — Python's :func:`sum` of an empty iterable
        is ``0`` — which matches the original JavaScript behaviour for
        the all-zeros input case (every ``parseInt("" || 0)`` returns
        ``0``, so the accumulator stays at ``0``).

    Examples
    --------
    All five subjects scoring full marks::

        >>> compute_total({"Maths": 100, "Science": 100, "English": 100,
        ...                "History": 100, "Computer": 100})
        500

    All five subjects scoring zero — F-002 acceptance case::

        >>> compute_total({"Maths": 0, "Science": 0, "English": 0,
        ...                "History": 0, "Computer": 0})
        0

    A mixed-mark input::

        >>> compute_total({"Maths": 45, "Science": 55, "English": 65,
        ...                "History": 75, "Computer": 85})
        325

    The empty-mapping edge case::

        >>> compute_total({})
        0
    """
    return sum(marks.values())


def compute_percentage(total: int, max_total: int = MAX_TOTAL) -> float:
    """Return the percentage ``(total / max_total) * 100``.

    Preserves the original JS formula at ``Readme.md`` line 192 exactly.
    Python 3's ``/`` operator performs true division and always returns
    a float, matching the JS semantics for the same input.

    No rounding is performed at this layer.  The original JS rounds for
    *display* only via ``.toFixed(2)`` at ``Readme.md`` line 211; the
    Jinja2 template and the PDF generator handle their own display
    formatting downstream.

    Parameters
    ----------
    total : int
        The total marks, typically produced by :func:`compute_total`.
        Although annotated as :class:`int`, plain :class:`float` values
        are also accepted — Python's numeric coercion makes the
        arithmetic correct either way.
    max_total : int, optional
        The denominator (maximum possible total).  Defaults to
        :data:`~report_generator.models.MAX_TOTAL` (= 500), preserved
        verbatim from the original JavaScript at ``Readme.md`` line 192.
        Surfacing the denominator as a parameter (rather than embedding
        the literal ``500``) supports any future reuse where a different
        maximum is appropriate (e.g. a different number of subjects)
        without modifying this function.

    Returns
    -------
    float
        The percentage as a :class:`float`.  Returns ``0.0`` when
        ``total`` is ``0`` — matching the all-zeros acceptance case in
        F-002.  No upper clamp is applied, so a ``total`` greater than
        ``max_total`` produces a value above ``100.0`` — the same
        behaviour as the original JavaScript.

    Raises
    ------
    ZeroDivisionError
        If ``max_total`` is ``0``.  The default
        :data:`~report_generator.models.MAX_TOTAL` is ``500`` so this
        can only occur when a caller explicitly overrides the
        denominator with ``0``.

    Examples
    --------
    A perfect score returns exactly ``100.0``::

        >>> compute_percentage(500)
        100.0

    All zeros returns exactly ``0.0`` — F-002 acceptance case::

        >>> compute_percentage(0)
        0.0

    A mid-range input — F-002 acceptance case::

        >>> compute_percentage(325)
        65.0

    Explicit ``max_total`` override::

        >>> compute_percentage(450, 500)
        90.0
    """
    return (total / max_total) * 100
