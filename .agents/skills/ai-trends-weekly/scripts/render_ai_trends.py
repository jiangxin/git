#!/usr/bin/env python3
"""Render weekly/<end_date>/AI-trends.md from per-site article sidecars.

Usage:
  python3 render_ai_trends.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
                              [--weekly-root PATH] [--max-per-day K]
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))

from filter_by_date import extract_date  # noqa: E402
from site_store import iter_articles  # noqa: E402
from summary_io import is_valid_summary, load_summary, summary_path  # noqa: E402

MAX_ITEMS = 50
DEFAULT_QUALITY_MIN = 5


def resolve_ai_trends_dir(end_date: str, weekly_root=None) -> Path:
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


def collect_entries(ai_trends_dir: Path) -> list[dict[str, Any]]:
    """Aggregate meta + summary sidecars into flat entry dicts."""
    entries: list[dict[str, Any]] = []
    sites_root = Path(ai_trends_dir) / "sites"
    if not sites_root.is_dir():
        return entries
    for slug_dir in sorted(sites_root.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        for record in iter_articles(ai_trends_dir, slug):
            status = record.meta.get("status")
            if status not in ("fetched", "cached"):
                continue
            s_path = summary_path(ai_trends_dir, slug, record.hash)
            sdata = load_summary(s_path)
            if not is_valid_summary(sdata):
                continue
            entry: dict[str, Any] = {
                "original_title": record.meta.get("original_title") or "",
                "url": record.meta.get("url") or "",
                "publish_date": record.meta.get("publish_date"),
                "source": record.meta.get("source") or "",
                "en_summary": sdata.get("en_summary", ""),
                "cn_title": sdata.get("cn_title", ""),
                "cn_summary": sdata.get("cn_summary", ""),
                "collected_at": sdata.get("collected_at", ""),
            }
            rh = sdata.get("rank_hint")
            if rh is not None:
                entry["rank_hint"] = rh
            entries.append(entry)
    return entries


def rank_hint_value(entry: dict[str, Any]) -> float:
    hint = entry.get("rank_hint")
    if hint is None:
        return float("inf")
    try:
        return float(hint)
    except (TypeError, ValueError):
        return float("inf")


def sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date = sorted(
        entries,
        key=lambda e: extract_date(e.get("publish_date")) or "",
        reverse=True,
    )
    return sorted(by_date, key=rank_hint_value)


def group_by_date(entries: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        day = extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
        buckets[day].append(entry)
    for day, group in buckets.items():
        buckets[day] = sorted(group, key=rank_hint_value)
    ordered_days = sorted(buckets.keys(), reverse=True)
    return [(day, buckets[day]) for day in ordered_days]


def apply_max_per_day(
    entries: list[dict[str, Any]],
    max_per_day: int | None,
) -> list[dict[str, Any]]:
    if max_per_day is None or max_per_day <= 0:
        return entries
    counts: dict[str, int] = defaultdict(int)
    out: list[dict[str, Any]] = []
    for entry in entries:
        day = extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
        if counts[day] >= max_per_day:
            continue
        counts[day] += 1
        out.append(entry)
    return out


def format_item(entry: dict[str, Any]) -> str:
    title = entry.get("cn_title") or entry.get("original_title") or "(untitled)"
    url = entry.get("url") or ""
    summary = (entry.get("cn_summary") or "").rstrip("。. ")
    source = entry.get("source") or ""
    day = extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
    return f"* **[{title}]({url})**：{summary}。📰 {source} 📅 {day}"


def format_reference(index: int, entry: dict[str, Any]) -> str:
    title = entry.get("original_title") or entry.get("cn_title") or "(untitled)"
    url = entry.get("url") or ""
    return f"{index}. [{title}]({url})"


def render_markdown(
    end_date: str,
    entries: list[dict[str, Any]],
    *,
    max_per_day: int | None = None,
) -> str:
    items = apply_max_per_day(entries[:MAX_ITEMS], max_per_day)
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


def emit_quality_warning(
    in_range_count: int,
    *,
    quality_min: int = DEFAULT_QUALITY_MIN,
    stream=None,
) -> bool:
    if quality_min <= 0 or in_range_count >= quality_min:
        return False
    out = stream if stream is not None else sys.stderr
    print(
        f"QUALITY_WARNING: in_range={in_range_count} < min={quality_min}",
        file=out,
    )
    return True


def filter_entries(
    entries: list[dict[str, Any]],
    start_date: str,
    end_date: str,
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], str, str]]]:
    in_range: list[dict[str, Any]] = []
    excluded: list[tuple[dict[str, Any], str, str]] = []
    for entry in entries:
        pub = entry.get("publish_date")
        day = extract_date(pub) if pub else None
        if day is not None and start_date <= day <= end_date:
            in_range.append(entry)
        elif day is not None:
            excluded.append((entry, day, "out_of_range"))
        else:
            excluded.append((entry, str(pub), "undated"))
    return in_range, excluded


def run(
    start_date: str,
    end_date: str,
    weekly_root=None,
    *,
    max_per_day: int | None = None,
    quality_min: int = DEFAULT_QUALITY_MIN,
) -> Path:
    ai_trends = resolve_ai_trends_dir(end_date, weekly_root)
    all_entries = collect_entries(ai_trends)
    in_range, excluded = filter_entries(all_entries, start_date, end_date)
    for entry, val, reason in excluded:
        label = entry.get("url") or entry.get("cn_title") or repr(entry)[:80]
        print(
            f"EXCLUDED [{reason}] publish_date={val!r} {label}",
            file=sys.stderr,
        )
    emit_quality_warning(len(in_range), quality_min=quality_min)
    sorted_entries = sort_entries(in_range)
    md = render_markdown(end_date, sorted_entries, max_per_day=max_per_day)
    week_dir = ai_trends.parent
    out_path = week_dir / "AI-trends.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render AI-trends.md from per-site article sidecars.",
        epilog="示例: python3 render_ai_trends.py --start-date 2026-05-03 --end-date 2026-05-10",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--weekly-root", metavar="PATH", default=None)
    parser.add_argument("--max-per-day", type=int, default=None, metavar="K")
    parser.add_argument(
        "--quality-min", type=int, default=DEFAULT_QUALITY_MIN, metavar="M",
        help=f"Stderr QUALITY_WARNING when in-range count < M (default: {DEFAULT_QUALITY_MIN})",
    )
    args = parser.parse_args()
    for label, d in (("start-date", args.start_date), ("end-date", args.end_date)):
        try:
            datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            print(f"ERROR: invalid {label} (expected YYYY-MM-DD): {d!r}", file=sys.stderr)
            return 2
    out = run(
        args.start_date, args.end_date,
        weekly_root=args.weekly_root,
        max_per_day=args.max_per_day,
        quality_min=args.quality_min,
    )
    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
