"""Read, write, and validate ``<hash>.summary.md`` sidecar files.

Summary sidecar format::

    ---
    en_summary: "English summary text."
    cn_title: "中文标题"
    cn_summary: "中文概述..."
    collected_at: "2026-07-23T11:30:00"
    rank_hint: 1
    ---

    (optional body area — may be empty)

Required front-matter fields: ``en_summary``, ``cn_title``, ``cn_summary``,
``collected_at``. ``rank_hint`` is optional.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml

from site_store import articles_dir, iter_articles

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
REQUIRED_FIELDS = ("en_summary", "cn_title", "cn_summary", "collected_at")
OPTIONAL_FIELDS = ("rank_hint",)


@dataclass
class SummaryData:
    en_summary: str
    cn_title: str
    cn_summary: str
    collected_at: str
    rank_hint: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "en_summary": self.en_summary,
            "cn_title": self.cn_title,
            "cn_summary": self.cn_summary,
            "collected_at": self.collected_at,
        }
        if self.rank_hint is not None:
            out["rank_hint"] = self.rank_hint
        return out


def summary_path(ai_trends_dir: Path, slug: str, hash: str) -> Path:
    return articles_dir(ai_trends_dir, slug) / f"{hash}.summary.md"


def parse_summary(text: str) -> dict[str, Any] | None:
    """Parse YAML front matter from ``text``.

    Returns the parsed dict on success, or ``None`` when the front matter
    is missing or malformed. Field validation is NOT performed here —
    use ``validate_summary`` for that.
    """
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return None
    raw_yaml = match.group(1)
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def validate_summary(data: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Return ``(is_valid, missing_fields)`` for a parsed summary dict.

    ``is_valid`` is True only when every required field is present with a
    non-empty string value (``rank_hint`` may be int/None and is optional).
    """
    if not isinstance(data, dict):
        return False, list(REQUIRED_FIELDS)
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    rh = data.get("rank_hint")
    if rh is not None and not isinstance(rh, (int, float)):
        missing.append("rank_hint")
    return (len(missing) == 0), missing


def is_valid_summary(data: dict[str, Any] | None) -> bool:
    ok, _ = validate_summary(data)
    return ok


def load_summary(path: Path) -> dict[str, Any] | None:
    """Read ``path`` and return parsed front matter, or ``None``."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_summary(text)


def _dump_front_matter(data: dict[str, Any]) -> str:
    yaml_text = yaml.safe_dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    ).rstrip("\n")
    return f"---\n{yaml_text}\n---\n"


def write_summary(
    path: Path,
    data: dict[str, Any] | SummaryData,
    body: str = "",
) -> None:
    """Write a summary sidecar file with YAML front matter + optional body.

    ``data`` may be a ``SummaryData`` instance or a plain dict. The
    function does NOT validate — caller should ensure required fields
    are present.
    """
    if isinstance(data, SummaryData):
        payload = data.to_dict()
    else:
        payload = dict(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _dump_front_matter(payload)
    if body:
        content += "\n" + body.lstrip("\n")
    path.write_text(content, encoding="utf-8")


def iter_missing_summaries(
    ai_trends_dir: Path,
) -> Iterator[tuple[str, str, Path, Path]]:
    """Yield ``(slug, hash, meta_file, summary_file)`` for articles without
    a valid summary sidecar.

    Articles whose meta.json status is not ``fetched`` or ``cached`` are
    skipped. Articles with a parseable, valid summary are skipped.
    """
    sites_root = Path(ai_trends_dir) / "sites"
    if not sites_root.is_dir():
        return
    for slug_dir in sorted(sites_root.iterdir()):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        for record in iter_articles(ai_trends_dir, slug):
            status = record.meta.get("status")
            if status not in ("fetched", "cached"):
                continue
            s_path = summary_path(ai_trends_dir, slug, record.hash)
            data = load_summary(s_path)
            if is_valid_summary(data):
                continue
            yield slug, record.hash, record.meta_file, s_path
