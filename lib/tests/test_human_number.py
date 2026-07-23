"""Tests for human_number — parse, format, daily_average."""

import pytest

from human_number import daily_average, format_human_number, parse_human_number


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("22.84 B", 22_840_000_000),
        ("20.18 K", 20_180),
        ("85.23 M", 85_230_000),
        ("3.89B", 3_890_000_000),
        ("100", 100),
        ("invalid", None),
    ],
)
def test_parse_human_number(raw, expected):
    result = parse_human_number(raw)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize(
    "value, expected",
    [
        (3_260_000_000, "3.26 B"),
        (555_710_000, "555.71 M"),
        (2_880, "2.88 K"),
        (320, "320.00"),
        (None, "—"),
    ],
)
def test_format_human_number(value, expected):
    assert format_human_number(value) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("3.89 B", "555.71 M"),
        ("2.24 K", "320.00"),
        ("20.67 M", "2.95 M"),
        ("invalid", "—"),
    ],
)
def test_daily_average(raw, expected):
    assert daily_average(raw) == expected
