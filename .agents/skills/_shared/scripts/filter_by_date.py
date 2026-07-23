#!/usr/bin/env python3
"""
Filter a JSON array of objects by a date field against an inclusive [start_date, end_date].

Reads a JSON array from --input FILE or stdin. Writes the filtered array to stdout.
Logs excluded entries to stderr. Exit code 0 if nothing excluded, 1 if any excluded.

Usage:
  python3 filter_by_date.py --start YYYY-MM-DD --end YYYY-MM-DD --date-field FIELD \\
    [--input path.json]

  echo '[{"publish_date":"2026-05-04","url":"x"}]' | \\
    python3 filter_by_date.py --start 2026-05-03 --end 2026-05-10 --date-field publish_date
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def extract_date(value: Any) -> str | None:
    """Return YYYY-MM-DD from a field value, or None if missing/invalid."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # epoch ms (unlikely for these skills) — not supported here
        return None
    s = str(value).strip()
    if not s:
        return None
    m = _DATE_PREFIX.match(s)
    if not m:
        return None
    day = m.group(1)
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return None
    return day


def entry_label(entry: dict[str, Any]) -> str:
    """Short label for stderr logging."""
    if not isinstance(entry, dict):
        return repr(entry)[:120]
    for key in ("url", "articleId", "nodeId", "cn_title", "articleTitle", "name"):
        if key in entry and entry[key] is not None:
            return f"{key}={entry[key]!r}"
    return str(entry)[:120]


def filter_entries(
    entries: list[Any],
    start_date: str,
    end_date: str,
    date_field: str,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str, str]]]:
    """
    Split entries into in-range and excluded.

    Returns:
        (in_range, excluded_triples) where each triple is (entry, raw_value, reason).
    """
    in_range: list[dict[str, Any]] = []
    excluded: list[tuple[dict[str, Any], str, str]] = []

    for entry in entries:
        if not isinstance(entry, dict):
            excluded.append(({"_raw": entry}, "", "not_an_object"))
            continue
        raw = entry.get(date_field)
        day = extract_date(raw)
        if day is None:
            excluded.append((entry, str(raw), "missing_or_unparseable_date"))
            continue
        if day < start_date or day > end_date:
            excluded.append((entry, day, "out_of_range"))
            continue
        in_range.append(entry)

    return in_range, excluded


def load_json_array_from_stream(stream) -> list[Any]:
    raw = stream.read()
    if not raw.strip():
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("root JSON must be an array")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Filter JSON array entries by inclusive date range on a named field.",
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument(
        "--date-field",
        required=True,
        help="Object key holding date or datetime string (e.g. publish_date, createTimeShadow)",
    )
    parser.add_argument(
        "--input",
        metavar="PATH",
        default=None,
        help="Input JSON file (array); omit to read stdin",
    )
    args = parser.parse_args()

    for label, d in (("start", args.start), ("end", args.end)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: invalid {label} date (expected YYYY-MM-DD): {d!r}", file=sys.stderr)
            return 2

    if args.input:
        path = Path(args.input)
        if not path.is_file():
            print(f"ERROR: input file not found: {path}", file=sys.stderr)
            return 2
        raw_text = path.read_text(encoding="utf-8")
    else:
        raw_text = sys.stdin.read()

    try:
        entries = json.loads(raw_text) if raw_text.strip() else []
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed: {e}", file=sys.stderr)
        return 3

    if not isinstance(entries, list):
        print("ERROR: root JSON must be an array", file=sys.stderr)
        return 3

    in_range, excluded = filter_entries(entries, args.start, args.end, args.date_field)

    for entry, val, reason in excluded:
        print(
            f"EXCLUDED [{reason}] date_field={args.date_field!r} value={val!r} {entry_label(entry)}",
            file=sys.stderr,
        )

    sys.stdout.write(json.dumps(in_range, ensure_ascii=False, indent=2) + "\n")
    return 1 if excluded else 0


if __name__ == "__main__":
    raise SystemExit(main())
