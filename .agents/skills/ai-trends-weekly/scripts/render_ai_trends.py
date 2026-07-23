#!/usr/bin/env python3
"""Render weekly/<end_date>/AI-trends.md from date-filtered archives.json.

Usage:
  python3 render_ai_trends.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
                              [--weekly-root PATH]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))

from filter_by_date import extract_date, filter_entries  # noqa: E402
from json_archives import load_json_array  # noqa: E402

MAX_ITEMS = 50


def resolve_ai_trends_dir(end_date: str, weekly_root=None) -> Path:
    """Locate ``weekly/<end_date>/ai-trends/`` (same pattern as merge_archives)."""
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if weekly_root is None:
        repo_root = SCRIPT_DIR.parents[3]
        weekly_root = repo_root / "weekly"
    else:
        weekly_root = Path(weekly_root)

    ai_trends = Path(weekly_root) / end_date / "ai-trends"
    if not ai_trends.is_dir():
        print(f"ERROR: ai-trends directory not found: {ai_trends}", file=sys.stderr)
        print("Run setup_week.py first.", file=sys.stderr)
        sys.exit(2)
    return ai_trends


def rank_hint_value(entry: dict[str, Any]) -> float:
    """Return rank_hint as float; missing/None → +inf (lowest priority)."""
    hint = entry.get("rank_hint")
    if hint is None:
        return float("inf")
    try:
        return float(hint)
    except (TypeError, ValueError):
        return float("inf")


def sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by rank_hint ascending, then publish_date descending (for Top-N pick)."""
    by_date = sorted(
        entries,
        key=lambda e: extract_date(e.get("publish_date")) or "",
        reverse=True,
    )
    return sorted(by_date, key=rank_hint_value)


def group_by_date(entries: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group entries by publish_date (newest first); within a day keep rank_hint order."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        day = extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
        buckets[day].append(entry)
    # Within each day: rank_hint asc, then keep relative order
    for day, group in buckets.items():
        buckets[day] = sorted(group, key=rank_hint_value)
    ordered_days = sorted(buckets.keys(), reverse=True)
    return [(day, buckets[day]) for day in ordered_days]


def format_item(entry: dict[str, Any]) -> str:
    """One Markdown bullet for the weekly body."""
    title = entry.get("cn_title") or entry.get("original_title") or "(untitled)"
    url = entry.get("url") or ""
    summary = (entry.get("cn_summary") or "").rstrip("。. ")
    source = entry.get("source") or ""
    day = extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
    return f"* **[{title}]({url})**：{summary}。📰 {source} 📅 {day}"


def format_reference(index: int, entry: dict[str, Any]) -> str:
    """One numbered reference line."""
    title = entry.get("original_title") or entry.get("cn_title") or "(untitled)"
    url = entry.get("url") or ""
    return f"{index}. [{title}]({url})"


def render_markdown(end_date: str, entries: list[dict[str, Any]]) -> str:
    """Build AI-trends.md: Top-N by rank, displayed grouped by date (newest first)."""
    items = entries[:MAX_ITEMS]
    lines: list[str] = [
        f"## {end_date} AI 行业动态周报",
        "",
        "### 本周 AI 行业动态",
        "",
    ]

    groups = group_by_date(items)
    for gi, (day, group) in enumerate(groups):
        lines.append(f"#### {day}")
        lines.append("")
        for i, entry in enumerate(group):
            lines.append(format_item(entry))
            if i < len(group) - 1:
                lines.append("")
        if gi < len(groups) - 1:
            lines.append("")
            lines.append("")

    if items:
        lines.append("")

    lines.append("### 参考来源")
    lines.append("")
    for i, entry in enumerate(items, start=1):
        lines.append(format_reference(i, entry))

    lines.append("")
    return "\n".join(lines)


def run(start_date: str, end_date: str, weekly_root=None) -> Path:
    """Filter, sort, render, and write AI-trends.md. Returns output path."""
    ai_trends = resolve_ai_trends_dir(end_date, weekly_root)
    archives_path = ai_trends / "archives.json"
    if not archives_path.is_file():
        print(f"ERROR: archives.json not found at {archives_path}", file=sys.stderr)
        sys.exit(2)

    archives = load_json_array(archives_path, "archives.json")
    in_range, excluded = filter_entries(archives, start_date, end_date, "publish_date")
    for entry, val, reason in excluded:
        label = entry.get("url") or entry.get("cn_title") or repr(entry)[:80]
        print(
            f"EXCLUDED [{reason}] publish_date={val!r} {label}",
            file=sys.stderr,
        )

    sorted_entries = sort_entries(in_range)
    md = render_markdown(end_date, sorted_entries)

    week_dir = ai_trends.parent
    out_path = week_dir / "AI-trends.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render AI-trends.md from date-filtered archives.json.",
        epilog="示例: python3 render_ai_trends.py --start-date 2026-05-03 --end-date 2026-05-10",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument(
        "--weekly-root",
        metavar="PATH",
        default=None,
        help="Override weekly/ directory path",
    )
    args = parser.parse_args()

    for label, d in (("start-date", args.start_date), ("end-date", args.end_date)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: invalid {label} (expected YYYY-MM-DD): {d!r}", file=sys.stderr)
            return 2

    out = run(args.start_date, args.end_date, weekly_root=args.weekly_root)
    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
