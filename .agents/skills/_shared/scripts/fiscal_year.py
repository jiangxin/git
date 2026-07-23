"""Fiscal year helpers (FY starts April 1)."""

from __future__ import annotations

from datetime import date, datetime


def fiscal_year_start(end_date: str) -> str:
    """Return the fiscal year start date (April 1) for the FY containing *end_date*.

    If *end_date* is after April 1 of its calendar year, the FY begins that year on
    4/1. If *end_date* falls on or before April 1 (Jan 1 through Apr 1 inclusive),
    the FY begins the previous calendar year on 4/1.

    Args:
        end_date: Anchor date in ``YYYY-MM-DD`` format.

    Returns:
        Fiscal year first day as ``YYYY-MM-DD``.

    Raises:
        ValueError: if *end_date* is not a valid ``YYYY-MM-DD`` string.
    """
    d = _parse_date(end_date)
    april_first = date(d.year, 4, 1)
    if d > april_first:
        fy_start = april_first
    else:
        fy_start = date(d.year - 1, 4, 1)
    return fy_start.strftime("%Y-%m-%d")


def days_since_fiscal_year_start(end_date: str) -> int:
    """Return whole days from the FY start (inclusive anchor) to *end_date*.

    On the fiscal year first day itself, returns ``0``.

    Args:
        end_date: Anchor date in ``YYYY-MM-DD`` format.

    Returns:
        Non-negative day count: ``end_date - fiscal_year_start(end_date)``.

    Raises:
        ValueError: if *end_date* is not a valid ``YYYY-MM-DD`` string.
    """
    end = _parse_date(end_date)
    start = _parse_date(fiscal_year_start(end_date))
    return (end - start).days


def _parse_date(date_str: str) -> date:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"invalid date: {date_str!r}, expected YYYY-MM-DD") from e
