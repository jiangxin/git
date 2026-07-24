"""Parse and format human-friendly numbers with K/M/B suffixes."""

import re

_UNIT_MULTIPLIERS = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
_UNIT_RE = re.compile(
    r"^([+-]?\d+(?:\.\d+)?)\s*([KMB])?\s*$", re.IGNORECASE,
)
_UNIT_THRESHOLDS = [(1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")]


def parse_human_number(raw):
    """Parse '22.84 B' → float. Returns None on failure."""
    s = str(raw).strip().replace(",", "").replace(" ", "")
    m = _UNIT_RE.match(s)
    if not m:
        return None
    v = float(m.group(1))
    unit = (m.group(2) or "").upper()
    return v * _UNIT_MULTIPLIERS.get(unit, 1)


def format_human_number(value):
    """Format a number to human-friendly string with K/M/B suffix."""
    if value is None:
        return "—"
    abs_v = abs(value)
    for threshold, suffix in _UNIT_THRESHOLDS:
        if abs_v >= threshold:
            scaled = value / threshold
            return f"{scaled:.2f} {suffix}"
    return f"{value:.2f}"


def daily_average(raw, days=7):
    """Parse a human-number string, divide by days, return formatted string."""
    v = parse_human_number(raw)
    return format_human_number(v / days) if v is not None else "—"
