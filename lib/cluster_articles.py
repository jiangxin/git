"""Article clustering for weekly reports.

Groups similar articles by title token overlap (Jaccard), URL domain
similarity, and optional ``topic_id`` hints from Agent summaries.

Usage as library::

    from cluster_articles import cluster_entries, write_clusters

    clusters, singletons = cluster_entries(entries, threshold=0.45)
    write_clusters(skill_dir, clusters, singletons)

Usage as CLI::

    python3 lib/cluster_articles.py --end-date 2026-07-31
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_STOP_WORDS: set[str] = set(
    "a an the is are was were be been being have has had do does did will "
    "would shall should may might can could this that these those it its i me "
    "my we our you your he she they them his her their what which who whom "
    "how when where why of in on at to for with from by as is are and or "
    "not no but if then so than too very just about into through during "
    "before after above below between under again further once here there "
    "all each every both few more most other some such only own same also "
    "s t don let say said go went gone get got make made take took taken "
    "come came new now old".split()
)

_SPLIT_RE = re.compile(r"[^a-zA-Z0-9\u4e00-\u9fff]+")

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    text = text.lower()
    tokens: list[str] = []
    for raw in _SPLIT_RE.split(text):
        raw = raw.strip()
        if not raw:
            continue
        if _CJK_RE.search(raw):
            for ch in raw:
                if ch not in _STOP_WORDS:
                    tokens.append(ch)
        elif raw not in _STOP_WORDS:
            tokens.append(raw)
    return tokens


def _jaccard(tokens_a: list[str], tokens_b: list[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    set_a = set(tokens_a)
    set_b = set(tokens_b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        host = re.sub(r"^www\.", "", host)
        return host
    except Exception:
        return ""


def _url_path_tokens(url: str) -> list[str]:
    try:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        return [t for t in _SPLIT_RE.split(path) if t and len(t) > 2]
    except Exception:
        return []


def _url_similarity(url_a: str, url_b: str) -> float:
    if not url_a or not url_b:
        return 0.0
    domain_a = _extract_domain(url_a)
    domain_b = _extract_domain(url_b)
    if not domain_a or not domain_b:
        return 0.0
    if domain_a != domain_b:
        return 0.0
    path_a = _url_path_tokens(url_a)
    path_b = _url_path_tokens(url_b)
    if not path_a or not path_b:
        return 0.3
    return _jaccard(path_a, path_b) * 0.5 + 0.5


def _title_similarity(title_a: str, title_b: str) -> float:
    if not title_a or not title_b:
        return 0.0
    tokens_a = _tokenize(title_a)
    tokens_b = _tokenize(title_b)
    return _jaccard(tokens_a, tokens_b)


def _combined_similarity(entry_a: dict[str, Any], entry_b: dict[str, Any]) -> float:
    title_a = (
        entry_a.get("cn_title") or entry_a.get("original_title") or ""
    )
    title_b = (
        entry_b.get("cn_title") or entry_b.get("original_title") or ""
    )
    url_a = entry_a.get("url") or ""
    url_b = entry_b.get("url") or ""
    title_sim = _title_similarity(title_a, title_b)
    url_sim = _url_similarity(url_a, url_b)
    return 0.55 * title_sim + 0.45 * url_sim


def _union_find_cluster(
    entries: list[dict[str, Any]],
    threshold: float = 0.45,
) -> list[list[int]]:
    n = len(entries)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if entries[i].get("_topic_id") and entries[i]["_topic_id"] == entries[j].get("_topic_id"):
                union(i, j)
                continue
            sim = _combined_similarity(entries[i], entries[j])
            if sim >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def cluster_entries(
    entries: list[dict[str, Any]],
    threshold: float = 0.45,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Cluster entries into groups of similar articles.

    Returns ``(clusters, singletons)`` where each cluster is a dict::

        {
            "id": "cluster_<index>",
            "articles": [entry, ...],
            "representative_hash": "<hash>",
            "topic_id": "<topic_id or None>",
        }

    Singletons are entries that have no similar articles.
    """
    if not entries:
        return [], []

    group_indices = _union_find_cluster(entries, threshold)

    clusters: list[dict[str, Any]] = []
    singletons: list[dict[str, Any]] = []
    cluster_idx = 0

    for indices in group_indices:
        group = [entries[i] for i in indices]
        topic_id = None
        for e in group:
            tid = e.get("_topic_id")
            if tid:
                topic_id = tid
                break

        if len(group) == 1:
            singletons.append(group[0])
            continue

        group_sorted = sorted(
            group,
            key=lambda e: (e.get("rank_hint") or float("inf")),
        )
        representative = group_sorted[0]
        clusters.append({
            "id": f"cluster_{cluster_idx:03d}",
            "articles": group_sorted,
            "representative_hash": representative.get("hash") or "",
            "topic_id": topic_id,
        })
        cluster_idx += 1

    clusters.sort(
        key=lambda c: min(
            (e.get("rank_hint") or float("inf")) for e in c["articles"]
        ),
    )

    return clusters, singletons


def write_clusters(
    skill_dir: Path,
    clusters: list[dict[str, Any]],
    singletons: list[dict[str, Any]],
) -> Path:
    """Write clustering results to ``<skill_dir>/clusters.json``."""
    skill_dir = Path(skill_dir)
    output = {
        "clusters": [
            {
                "id": c["id"],
                "representative_hash": c["representative_hash"],
                "topic_id": c.get("topic_id"),
                "article_count": len(c["articles"]),
                "articles": [
                    {
                        "hash": e.get("hash") or "",
                        "url": e.get("url") or "",
                        "original_title": e.get("original_title") or "",
                        "cn_title": e.get("cn_title") or "",
                        "cn_summary": e.get("cn_summary") or "",
                        "source": e.get("source") or "",
                        "publish_date": e.get("publish_date") or "",
                        "rank_hint": e.get("rank_hint"),
                    }
                    for e in c["articles"]
                ],
            }
            for c in clusters
        ],
        "singleton_count": len(singletons),
    }
    out_path = skill_dir / "clusters.json"
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out_path


def load_clusters(skill_dir: Path) -> dict[str, Any] | None:
    """Load ``<skill_dir>/clusters.json`` if it exists."""
    path = Path(skill_dir) / "clusters.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None
