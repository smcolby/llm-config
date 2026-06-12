"""Exemplar module for the python-docs rule (NumPy docstring standard).

Imitate the docstring shapes here, never the domain: one-line imperative
summary, canonical section order, loose readable types in prose with the
signature carrying the precise contract, and doctest examples that run.
"""

from collections.abc import Sequence


def moving_average(values: Sequence[float], window: int) -> list[float]:
    """Compute the simple moving average over an ordered sequence.

    Parameters
    ----------
    values : sequence of float
        Ordered observations to average.
    window : int
        Number of trailing observations per average, between 1 and
        ``len(values)`` inclusive.

    Returns
    -------
    list of float
        One average per complete window, of length
        ``len(values) - window + 1``.

    Raises
    ------
    ValueError
        If ``window`` is not between 1 and ``len(values)``.

    Examples
    --------
    >>> moving_average([1.0, 2.0, 3.0, 4.0], window=2)
    [1.5, 2.5, 3.5]
    """
    _validate_window(len(values), window)
    return [sum(values[i : i + window]) / window for i in range(len(values) - window + 1)]


def _validate_window(length: int, window: int) -> None:
    # private helper: underscore prefix exempts it from the docstring
    # requirement; a comment suffices when behavior is non-obvious
    if not 1 <= window <= length:
        raise ValueError(f"window must be in 1..{length}, got {window}")
