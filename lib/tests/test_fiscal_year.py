"""Tests for fiscal_year.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiscal_year import days_since_fiscal_year_start, fiscal_year_start


@pytest.mark.parametrize(
    ("end_date", "expected_start"),
    [
        ("2026-05-17", "2026-04-01"),
        ("2026-04-02", "2026-04-01"),
        ("2026-04-01", "2025-04-01"),
        ("2026-03-31", "2025-04-01"),
        ("2026-01-01", "2025-04-01"),
        ("2025-12-31", "2025-04-01"),
        ("2025-04-01", "2024-04-01"),
    ],
)
def test_fiscal_year_start(end_date, expected_start):
    assert fiscal_year_start(end_date) == expected_start


@pytest.mark.parametrize(
    ("end_date", "expected_days"),
    [
        ("2026-04-01", 365),
        ("2026-04-02", 1),
        ("2026-05-17", 46),
        ("2026-01-01", 275),
        ("2025-04-01", 365),
    ],
)
def test_days_since_fiscal_year_start(end_date, expected_days):
    assert days_since_fiscal_year_start(end_date) == expected_days


def test_fiscal_year_start_invalid_date_raises():
    with pytest.raises(ValueError, match="invalid date"):
        fiscal_year_start("not-a-date")
