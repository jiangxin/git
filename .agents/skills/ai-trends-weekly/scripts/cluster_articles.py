#!/usr/bin/env python3
"""Cluster similar articles before report rendering.

Reads per-site article data, computes similarity, and writes
``clusters.json`` to the skill directory.

Usage:
    python3 cluster_articles.py --end-date YYYY-MM-DD [--weekly-root PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[3]
sys.path.insert(0, str(REPO_ROOT / "lib"))

from cluster_articles import cluster_entries, write_clusters  # noqa: E402
from render_report import collect_entries, resolve_skill_dir  # noqa: E402
from filter_by_date import extract_date  # noqa: E402

SKILL_SUBDIR = "ai-trends"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cluster similar articles before report rendering.",
        epilog="示例: python3 cluster_articles.py --end-date 2026-07-31",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--weekly-root", metavar="PATH", default=None)
    parser.add_argument(
        "--threshold", type=float, default=0.45,
        help="Similarity threshold for clustering (default: 0.45)",
    )
    args = parser.parse_args()

    skill_dir = resolve_skill_dir(args.end_date, SKILL_SUBDIR, args.weekly_root)
    all_entries = collect_entries(skill_dir)

    clusters, singletons = cluster_entries(all_entries, threshold=args.threshold)

    out_path = write_clusters(skill_dir, clusters, singletons)

    total = len(all_entries)
    clustered = sum(len(c["articles"]) for c in clusters)
    print(
        f"CLUSTERED: total={total} clusters={len(clusters)} "
        f"clustered_articles={clustered} singletons={len(singletons)}"
    )
    print(f"WROTE: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
