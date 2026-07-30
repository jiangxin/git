"""Shared report rendering: collect, filter, rank, and render Markdown/HTML.

Parameterized by ``skill_subdir`` (e.g. ``ai-trends``, ``git-news``),
``output_filename``, and ``title`` so multiple skills can reuse the
same rendering pipeline.
"""

from __future__ import annotations

import html as html_mod
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cluster_articles import load_clusters  # noqa: E402
from filter_by_date import extract_date  # noqa: E402
from site_store import iter_articles  # noqa: E402
from summary_io import is_valid_summary, load_summary, summary_path  # noqa: E402

MAX_ITEMS = 50
DEFAULT_QUALITY_MIN = 5


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


def collect_entries(skill_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    sites_root = Path(skill_dir) / "sites"
    if not sites_root.is_dir():
        return entries
    for slug_dir in sorted(sites_root.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        for record in iter_articles(skill_dir, slug):
            status = record.meta.get("status")
            if status not in ("fetched", "cached"):
                continue
            s_path = summary_path(skill_dir, slug, record.hash)
            sdata = load_summary(s_path)
            if not is_valid_summary(sdata):
                continue
            entry: dict[str, Any] = {
                "original_title": record.meta.get("original_title") or "",
                "url": record.meta.get("url") or "",
                "publish_date": record.meta.get("publish_date"),
                "source": record.meta.get("source") or "",
                "hash": record.hash,
                "en_summary": sdata.get("en_summary", ""),
                "cn_title": sdata.get("cn_title", ""),
                "cn_summary": sdata.get("cn_summary", ""),
                "collected_at": sdata.get("collected_at", ""),
            }
            rh = sdata.get("rank_hint")
            if rh is not None:
                entry["rank_hint"] = rh
            topic_id = sdata.get("topic_id")
            if topic_id:
                entry["_topic_id"] = topic_id
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


def build_cluster_index(
    clusters_data: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Map article hash → cluster record from ``clusters.json``."""
    index: dict[str, dict[str, Any]] = {}
    if not clusters_data:
        return index
    for cluster in clusters_data.get("clusters", []):
        for art in cluster.get("articles", []):
            h = art.get("hash")
            if h:
                index[h] = cluster
    return index


def partition_by_cluster(
    entries: list[dict[str, Any]],
    cluster_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split entries into cluster leaders and non-cluster members.

    Returns ``(leaders, orphans)``. For each cluster, the first entry
    (by existing sort order) becomes the leader; remaining members are
    attached as ``_cluster_peers`` on the leader.
    """
    seen: set[str] = set()
    leaders: list[dict[str, Any]] = []
    orphans: list[dict[str, Any]] = []
    entry_by_hash: dict[str, dict[str, Any]] = {
        e["hash"]: e for e in entries if e.get("hash")
    }

    for entry in entries:
        h = entry.get("hash") or ""
        cluster = cluster_index.get(h)
        if not cluster:
            orphans.append(entry)
            continue
        cid = cluster["id"]
        if cid in seen:
            continue
        seen.add(cid)
        peers = [
            entry_by_hash[a["hash"]]
            for a in cluster.get("articles", [])
            if a.get("hash") and a["hash"] != h and a["hash"] in entry_by_hash
        ]
        leader = dict(entry)
        leader["_cluster_id"] = cid
        leader["_cluster_peers"] = peers
        leaders.append(leader)

    return leaders, orphans


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


def _md_article_line(entry: dict[str, Any], *, bold_title: bool = True) -> str:
    title = entry.get("cn_title") or entry.get("original_title") or "(untitled)"
    url = entry.get("url") or ""
    summary = (entry.get("cn_summary") or "").rstrip("。. ")
    source = entry.get("source") or ""
    day = extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
    link = f"**[{title}]({url})**" if bold_title else f"[{title}]({url})"
    return f"* {link}：{summary}。📰 {source} 📅 {day}"


def format_item(entry: dict[str, Any]) -> str:
    peers = entry.get("_cluster_peers")
    if not peers:
        return _md_article_line(entry)
    n = len(peers)
    lines = [
        _md_article_line(entry),
        "",
        f'<details open><summary>相关报道 · {n} 篇（点击收起）</summary>',
        "",
    ]
    for peer in peers:
        lines.append(_md_article_line(peer))
        lines.append("")
    lines.append("</details>")
    return "\n".join(lines)


def render_markdown(
    end_date: str,
    entries: list[dict[str, Any]],
    title: str,
    subtitle: str,
    *,
    max_per_day: int | None = None,
    clusters_data: dict[str, Any] | None = None,
) -> str:
    cluster_index = build_cluster_index(clusters_data)
    if cluster_index:
        leaders, orphans = partition_by_cluster(entries, cluster_index)
        entries = leaders + orphans
    items = apply_max_per_day(entries[:MAX_ITEMS], max_per_day)
    lines: list[str] = [
        f"## {end_date} {title}",
        "",
        f"### {subtitle}",
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


def collect_source_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        src = entry.get("source") or "(unknown)"
        counts[src] = counts.get(src, 0) + 1
    return counts


def _html_article_body(entry: dict[str, Any]) -> tuple[str, str]:
    """Return ``(source_escaped, inner_html)`` for one article row."""
    title = html_mod.escape(entry.get("cn_title") or entry.get("original_title") or "(untitled)")
    url = html_mod.escape(entry.get("url") or "")
    summary = html_mod.escape((entry.get("cn_summary") or "").rstrip("。. "))
    source = html_mod.escape(entry.get("source") or "")
    day = html_mod.escape(
        extract_date(entry.get("publish_date")) or str(entry.get("publish_date") or "")
    )
    inner = (
        f'<strong><a href="{url}">{title}</a></strong>'
        f'：{summary}。'
        f'<span class="meta">📰 {source} 📅 {day}</span>'
    )
    return source, inner


def _html_article_item(entry: dict[str, Any]) -> str:
    source, inner = _html_article_body(entry)
    return f'<div class="article-item" data-source="{source}">{inner}</div>'


def _html_cluster_item(entry: dict[str, Any]) -> str:
    """Leader as normal article; peers in mint indented tree, default expanded."""
    peers = entry.get("_cluster_peers") or []
    if not peers:
        return _html_article_item(entry)
    leader_source, leader_inner = _html_article_body(entry)
    n = len(peers)
    parts = [
        '<div class="cluster-group">',
        f'<div class="article-item" data-source="{leader_source}">{leader_inner}</div>',
        '<div class="cluster">',
        (
            f'<button type="button" class="cluster-toggle" '
            f'aria-expanded="true" onclick="toggleCluster(this)">'
            f'<span class="chevron">▼</span>'
            f'相关报道 · {n} 篇（<span class="toggle-label">点击收起</span>）'
            f'</button>'
        ),
        '<ul class="cluster-list">',
    ]
    for peer in peers:
        source, inner = _html_article_body(peer)
        parts.append(
            f'<li class="article-item" data-source="{source}">{inner}</li>'
        )
    parts.append("</ul>")
    parts.append("</div>")
    parts.append("</div>")
    return "\n".join(parts)


def render_html(
    end_date: str,
    entries: list[dict[str, Any]],
    source_counts: dict[str, int],
    title: str,
    subtitle: str,
    *,
    max_per_day: int | None = None,
    clusters_data: dict[str, Any] | None = None,
) -> str:
    cluster_index = build_cluster_index(clusters_data)
    if cluster_index:
        leaders, orphans = partition_by_cluster(entries, cluster_index)
        entries = leaders + orphans
    items = apply_max_per_day(entries[:MAX_ITEMS], max_per_day)
    groups = group_by_date(items)

    sorted_sources = sorted(source_counts.keys())
    chips_html = '<button class="source-chip active" data-source="__all__">全部</button>\n'
    for src in sorted_sources:
        cnt = source_counts[src]
        esc = html_mod.escape(src)
        chips_html += (
            f'<button class="source-chip active" data-source="{esc}">'
            f'{esc} ({cnt})</button>\n'
        )
    chips_html += '<button class="source-chip" data-source="__none__">清空</button>'

    articles_parts: list[str] = []
    for day, group in groups:
        articles_parts.append(f'<div class="date-group" data-date="{html_mod.escape(day)}">')
        articles_parts.append(f'<h3>{html_mod.escape(day)}</h3>')
        for entry in group:
            if entry.get("_cluster_peers"):
                articles_parts.append(_html_cluster_item(entry))
            else:
                articles_parts.append(_html_article_item(entry))
        articles_parts.append("</div>")
    articles_html = "\n".join(articles_parts)

    page_title = f"{html_mod.escape(end_date)} {title}"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }}
h1 {{ margin-bottom: 8px; }}
.source-filter {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 24px; }}
.source-chip {{ border: 1px solid #ccc; border-radius: 16px; padding: 4px 14px; font-size: 13px; cursor: pointer; background: #f5f5f5; color: #666; transition: all .15s; }}
.source-chip.active {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
.source-chip:hover {{ opacity: .85; }}
.date-group {{ margin-bottom: 24px; }}
.date-group h3 {{ color: #555; border-bottom: 1px solid #eee; padding-bottom: 4px; }}
.date-group.hidden {{ display: none; }}
.article-item {{ margin: 10px 0; line-height: 1.6; }}
.article-item.hidden {{ display: none; }}
.article-item .meta {{ font-size: 12px; color: #888; }}
.article-item a {{ color: #2563eb; text-decoration: none; }}
.article-item a:hover {{ text-decoration: underline; }}
.back-link {{ display: inline-flex; align-items: center; gap: 6px; color: #667eea; text-decoration: none; font-size: 14px; margin-bottom: 16px; transition: all 0.15s; }}
.back-link:hover {{ color: #764ba2; gap: 10px; }}
.cluster-group {{ margin: 10px 0; }}
.cluster-group.hidden {{ display: none; }}
.cluster {{ margin: 4px 0 10px; background: #f0fdf6; border: 1px solid #bbf7d0; border-radius: 8px; padding: 8px 12px 10px 8px; }}
.cluster.hidden {{ display: none; }}
.cluster-toggle {{ display: inline-flex; align-items: center; gap: 6px; border: none; background: transparent; padding: 2px 4px; margin: 0 0 4px; font-size: 12px; color: #047857; cursor: pointer; text-align: left; }}
.cluster-toggle:hover {{ color: #065f46; text-decoration: underline; }}
.cluster-toggle .chevron {{ display: inline-block; font-size: 10px; transition: transform .15s; }}
.cluster.collapsed .chevron {{ transform: rotate(-90deg); }}
.cluster.collapsed .cluster-list {{ display: none; }}
.cluster-list {{ list-style: none; margin: 0 0 0 6px; padding: 0 0 0 16px; }}
.cluster-list > .article-item {{ position: relative; margin: 0; padding: 8px 0 8px 10px; }}
.cluster-list > .article-item + .article-item {{ border-top: 1px solid rgba(6, 95, 70, .06); }}
.cluster-list > .article-item::before {{ content: ""; position: absolute; left: -10px; top: 0; bottom: 0; width: 12px; border-left: 1px solid #86efac; }}
.cluster-list > .article-item::after {{ content: ""; position: absolute; left: -10px; top: 18px; width: 12px; border-top: 1px solid #86efac; }}
.cluster-list > .article-item:last-child::before {{ bottom: auto; height: 18px; }}
</style>
</head>
<body>
<a href="index.html" class="back-link">← 本期周报</a>
<h1>{page_title}</h1>
<h2>{html_mod.escape(subtitle)}</h2>
<div class="source-filter">
{chips_html}
</div>
<div class="articles">
{articles_html}
</div>
<script>
function toggleCluster(btn) {{
  var cluster = btn.closest('.cluster');
  cluster.classList.toggle('collapsed');
  var open = !cluster.classList.contains('collapsed');
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  var label = btn.querySelector('.toggle-label');
  if (label) label.textContent = open ? '点击收起' : '点击展开';
}}
(function() {{
  var allSources = {str(sorted_sources).replace("'", '"')};
  var selected = new Set(allSources);
  var chips = document.querySelectorAll('.source-chip');
  var items = document.querySelectorAll('.article-item');
  var clusters = document.querySelectorAll('.cluster');
  var clusterGroups = document.querySelectorAll('.cluster-group');
  var groups = document.querySelectorAll('.date-group');

  function updateUI() {{
    chips.forEach(function(chip) {{
      var s = chip.dataset.source;
      if (s === '__all__') {{
        chip.classList.toggle('active', selected.size === allSources.length);
      }} else if (s === '__none__') {{
        chip.classList.toggle('active', selected.size === 0);
      }} else {{
        chip.classList.toggle('active', selected.has(s));
      }}
    }});
    items.forEach(function(item) {{
      item.classList.toggle('hidden', !selected.has(item.dataset.source));
    }});
    clusters.forEach(function(c) {{
      var visible = c.querySelectorAll('.article-item:not(.hidden)');
      c.classList.toggle('hidden', visible.length === 0);
    }});
    clusterGroups.forEach(function(g) {{
      var visible = g.querySelectorAll('.article-item:not(.hidden)');
      g.classList.toggle('hidden', visible.length === 0);
    }});
    groups.forEach(function(g) {{
      var visible = g.querySelectorAll('.article-item:not(.hidden)');
      g.classList.toggle('hidden', visible.length === 0);
    }});
  }}

  chips.forEach(function(chip) {{
    chip.addEventListener('click', function() {{
      var s = chip.dataset.source;
      if (s === '__all__') {{
        allSources.forEach(function(x) {{ selected.add(x); }});
      }} else if (s === '__none__') {{
        selected.clear();
      }} else {{
        if (selected.has(s)) {{ selected.delete(s); }} else {{ selected.add(s); }}
      }}
      updateUI();
    }});
  }});

  updateUI();
}})();
</script>
</body>
</html>
"""


def run_report(
    start_date: str,
    end_date: str,
    skill_subdir: str,
    output_filename: str,
    title: str,
    subtitle: str,
    weekly_root: Path | str | None = None,
    *,
    max_per_day: int | None = None,
    quality_min: int = DEFAULT_QUALITY_MIN,
) -> Path:
    skill_dir = resolve_skill_dir(end_date, skill_subdir, weekly_root)
    all_entries = collect_entries(skill_dir)
    in_range, excluded = filter_entries(all_entries, start_date, end_date)
    for entry, val, reason in excluded:
        label = entry.get("url") or entry.get("cn_title") or repr(entry)[:80]
        print(
            f"EXCLUDED [{reason}] publish_date={val!r} {label}",
            file=sys.stderr,
        )
    emit_quality_warning(len(in_range), quality_min=quality_min)
    sorted_entries = sort_entries(in_range)
    clusters_data = load_clusters(skill_dir)
    if clusters_data:
        n_clusters = len(clusters_data.get("clusters", []))
        print(f"CLUSTERS: found {n_clusters} clusters in clusters.json", file=sys.stderr)
    md = render_markdown(
        end_date, sorted_entries, title, subtitle,
        max_per_day=max_per_day, clusters_data=clusters_data,
    )
    week_dir = skill_dir.parent
    out_path = week_dir / output_filename
    out_path.write_text(md, encoding="utf-8")

    source_counts = collect_source_counts(in_range)
    html_filename = output_filename.rsplit(".", 1)[0] + ".html"
    html_content = render_html(
        end_date, sorted_entries, source_counts, title, subtitle,
        max_per_day=max_per_day, clusters_data=clusters_data,
    )
    html_path = week_dir / html_filename
    html_path.write_text(html_content, encoding="utf-8")

    return out_path
