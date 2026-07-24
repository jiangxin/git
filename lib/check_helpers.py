"""Shared check helpers: summary completeness and URL index lookup.

Parameterized by ``skill_subdir`` (e.g. ``ai-trends``, ``git-news``)
so multiple skills can reuse the same check logic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from site_store import iter_articles, load_url_index, url_index_path  # noqa: E402
from summary_io import is_valid_summary, load_summary, summary_path  # noqa: E402


def resolve_skill_dir(
    end_date: str,
    skill_subdir: str,
    weekly_root: Path | str | None = None,
) -> Path:
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if weekly_root is None:
        repo_root = Path(__file__).resolve().parents[1]
        weekly_root = repo_root / "weekly"
    else:
        weekly_root = Path(weekly_root)
    skill_dir = Path(weekly_root) / end_date / skill_subdir
    if not skill_dir.is_dir():
        print(f"ERROR: {skill_subdir} directory not found: {skill_dir}", file=sys.stderr)
        print("Run setup_week.py first.", file=sys.stderr)
        sys.exit(2)
    return skill_dir


def check_summaries(skill_dir: Path) -> dict[str, int]:
    """Return counts dict: summarized, missing, sites."""
    sites_root = Path(skill_dir) / "sites"
    if not sites_root.is_dir():
        return {"summarized": 0, "missing": 0, "sites": 0}
    summarized = 0
    missing = 0
    site_slugs: set[str] = set()
    for slug_dir in sorted(sites_root.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        for record in iter_articles(skill_dir, slug):
            status = record.meta.get("status")
            if status not in ("fetched", "cached"):
                continue
            site_slugs.add(slug)
            s_path = summary_path(skill_dir, slug, record.hash)
            data = load_summary(s_path)
            if is_valid_summary(data):
                summarized += 1
            else:
                missing += 1
    return {
        "summarized": summarized,
        "missing": missing,
        "sites": len(site_slugs),
    }


def format_result(counts: dict[str, int]) -> str:
    return (
        f"OK: summarized={counts['summarized']} "
        f"missing={counts['missing']} "
        f"sites={counts['sites']}"
    )


def get_url_index(
    end_date: str,
    skill_subdir: str,
    root_override: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if root_override is not None:
        weekly_root = Path(root_override)
    else:
        repo_root = Path(__file__).resolve().parents[1]
        weekly_root = repo_root / "weekly"
    idx_path = url_index_path(weekly_root / end_date / skill_subdir)
    if not idx_path.is_file():
        print(f"ERROR: url_index.jsonl not found at {idx_path}", file=sys.stderr)
        print("Run setup_week.py and discover_and_fetch.py first.", file=sys.stderr)
        sys.exit(2)
    return load_url_index(idx_path)


def check_url(url_index: dict[str, dict[str, Any]], url: str) -> dict[str, Any] | None:
    return url_index.get(url)
