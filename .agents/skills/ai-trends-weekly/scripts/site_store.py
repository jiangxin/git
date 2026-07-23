"""Per-site article store with atomic write and cross-site URL dedupe.

Directory layout under ``weekly/<end_date>/ai-trends/``::

    url_index.jsonl          # global: url → {site, hash, at}
    sites/<slug>/
        index.jsonl          # per-site: url/status/hash/at/...
        articles/
            <hash>.meta.json
            <hash>.body.txt
            <hash>.summary.md   # Agent sidecar (written by another module)

The module exposes:

* ``slugify`` — derive a URL-safe slug from a source name / explicit slug.
* Path helpers: ``site_dir``, ``articles_dir``, ``site_index_path``,
  ``url_index_path``, ``meta_path``, ``body_path``.
* ``claim_url`` — first-writer-wins atomic article write.
* Index readers / appenders: ``load_site_index``, ``load_url_index``,
  ``append_site_index``, ``append_url_index``.
* ``iter_articles`` — iterate article triples for a site.
* ``resolve_unique_slug`` — pick a slug, handling same-week collisions.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SLUG_VALID = re.compile(r"^[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?$")
SLUG_BAD_CHARS = re.compile(r"[^a-z0-9]+")
SLUG_DASH_RUNS = re.compile(r"-{2,}")


def url_hash(url: str) -> str:
    """SHA-1 hex digest of the URL bytes (UTF-8)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def slugify(name: str, explicit_slug: str | None = None) -> str:
    """Derive a ``[a-z0-9-]+`` slug from ``name``.

    Priority: ``explicit_slug`` when it matches the allowed pattern.
    Otherwise: lowercase, keep unicode letters/digits, convert other chars
    to ``-``, collapse runs, strip edges. Fall back to ``s`` +
    ``sha1(name)[:10]`` if the result is empty.
    """
    if explicit_slug and SLUG_VALID.match(explicit_slug):
        return explicit_slug
    text = name.lower()
    out: list[str] = []
    for ch in text:
        if ch.isalnum() or ch == "-":
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out)
    slug = SLUG_DASH_RUNS.sub("-", slug)
    slug = slug.strip("-")
    if not slug:
        return "s" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return slug


def site_dir(ai_trends_dir: Path, slug: str) -> Path:
    return Path(ai_trends_dir) / "sites" / slug


def articles_dir(ai_trends_dir: Path, slug: str) -> Path:
    return site_dir(ai_trends_dir, slug) / "articles"


def site_index_path(ai_trends_dir: Path, slug: str) -> Path:
    return site_dir(ai_trends_dir, slug) / "index.jsonl"


def url_index_path(ai_trends_dir: Path) -> Path:
    return Path(ai_trends_dir) / "url_index.jsonl"


def meta_path(ai_trends_dir: Path, slug: str, hash: str) -> Path:
    return articles_dir(ai_trends_dir, slug) / f"{hash}.meta.json"


def body_path(ai_trends_dir: Path, slug: str, hash: str) -> Path:
    return articles_dir(ai_trends_dir, slug) / f"{hash}.body.txt"


@dataclass
class ArticleRecord:
    url: str
    site: str
    hash: str
    meta: dict[str, Any]
    body: str
    body_file: Path
    meta_file: Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def load_site_index(path: Path) -> dict[str, dict[str, Any]]:
    """Load ``sites/<slug>/index.jsonl`` → ``{url: record}`` (later wins)."""
    out: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(path):
        u = row.get("url")
        if isinstance(u, str) and u:
            out[u] = row
    return out


def load_url_index(path: Path) -> dict[str, dict[str, Any]]:
    """Load ``url_index.jsonl`` → ``{url: record}`` (later wins)."""
    out: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(path):
        u = row.get("url")
        if isinstance(u, str) and u:
            out[u] = row
    return out


def append_site_index(
    path: Path,
    *,
    url: str,
    status: str,
    hash: str,
    at: str | None = None,
) -> None:
    """Append one JSONL row to the per-site ``index.jsonl``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "url": url,
        "status": status,
        "hash": hash,
        "at": at or _now_iso(),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_url_index(
    path: Path,
    *,
    url: str,
    site: str,
    hash: str,
    at: str | None = None,
) -> bool:
    """Append one JSONL row to the global ``url_index.jsonl``.

    Uses ``fcntl.flock`` on a sibling lockfile so concurrent writers
    (cross-source parallel fetch) do not interleave bytes. First-writer-wins:
    if ``url`` is already present in the index, the append is skipped and
    the function returns ``False``. Returns ``True`` when a new row was
    written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".jsonl.lock")
    record = {
        "url": url,
        "site": site,
        "hash": hash,
        "at": at or _now_iso(),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        if path.is_file():
            existing = load_url_index(path)
            if url in existing:
                return False
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return True
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _atomic_create_meta(
    target: Path, payload: dict[str, Any]
) -> bool:
    """Write ``payload`` to ``target`` using O_EXCL. Returns True on success.

    Returns False when the file already exists (another site won the race).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        fd = os.open(
            str(target),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
    except FileExistsError:
        return False
    try:
        os.write(fd, data.encode("utf-8"))
    finally:
        os.close(fd)
    return True


@dataclass
class ClaimResult:
    won: bool
    hash: str
    meta_file: Path
    body_file: Path
    winner_site: str | None = None


def claim_url(
    ai_trends_dir: Path,
    *,
    url: str,
    slug: str,
    meta: dict[str, Any],
    body: str,
) -> ClaimResult:
    """Atomically claim ``url`` for ``slug`` and persist article files.

    Steps:

    1. ``O_EXCL`` create ``<hash>.meta.json`` — this is the claim.
    2. Write ``<hash>.body.txt``.
    3. Append row to site ``index.jsonl``.
    4. Append row to global ``url_index.jsonl`` (locked).

    Returns a ``ClaimResult``; ``won=False`` means another site had already
    created the meta file (caller should treat the URL as skipped).
    """
    digest = url_hash(url)
    m_path = meta_path(ai_trends_dir, slug, digest)
    b_path = body_path(ai_trends_dir, slug, digest)

    meta_payload: dict[str, Any] = dict(meta)
    meta_payload.setdefault("url", url)
    meta_payload.setdefault("hash", digest)
    meta_payload.setdefault("site", slug)
    meta_payload.setdefault("fetched_at", _now_iso())

    if not _atomic_create_meta(m_path, meta_payload):
        winner_site = _read_winner_site(m_path)
        _backfill_url_index_if_missing(
            ai_trends_dir,
            url=url,
            hash=digest,
            winner_site=winner_site,
        )
        return ClaimResult(
            won=False,
            hash=digest,
            meta_file=m_path,
            body_file=b_path,
            winner_site=winner_site,
        )

    b_path.parent.mkdir(parents=True, exist_ok=True)
    b_path.write_text(body or "", encoding="utf-8")

    append_site_index(
        site_index_path(ai_trends_dir, slug),
        url=url,
        status=meta_payload.get("status", "fetched"),
        hash=digest,
        at=meta_payload.get("fetched_at"),
    )
    append_url_index(
        url_index_path(ai_trends_dir),
        url=url,
        site=slug,
        hash=digest,
        at=meta_payload.get("fetched_at"),
    )
    return ClaimResult(
        won=True,
        hash=digest,
        meta_file=m_path,
        body_file=b_path,
        winner_site=slug,
    )


def _read_winner_site(meta_file: Path) -> str | None:
    try:
        with meta_file.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    site = data.get("site")
    return site if isinstance(site, str) else None


def _backfill_url_index_if_missing(
    ai_trends_dir: Path,
    *,
    url: str,
    hash: str,
    winner_site: str | None,
) -> None:
    if not winner_site:
        return
    idx_path = url_index_path(ai_trends_dir)
    if idx_path.is_file():
        existing = load_url_index(idx_path)
        if url in existing:
            return
    append_url_index(
        idx_path,
        url=url,
        site=winner_site,
        hash=hash,
    )


def iter_articles(
    ai_trends_dir: Path, slug: str
) -> Iterator[ArticleRecord]:
    """Yield ``ArticleRecord`` for each ``<hash>.meta.json`` under the site.

    Articles without a matching ``<hash>.body.txt`` still yield with an
    empty body so callers can report the inconsistency.
    """
    a_dir = articles_dir(ai_trends_dir, slug)
    if not a_dir.is_dir():
        return
    for meta_file in sorted(a_dir.glob("*.meta.json")):
        stem = meta_file.stem[: -len(".meta")]
        try:
            with meta_file.open(encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        b_file = a_dir / f"{stem}.body.txt"
        body = b_file.read_text(encoding="utf-8") if b_file.is_file() else ""
        yield ArticleRecord(
            url=meta.get("url") or "",
            site=slug,
            hash=stem,
            meta=meta,
            body=body,
            body_file=b_file,
            meta_file=meta_file,
        )


@dataclass
class SlugResolution:
    slug: str
    collision: bool
    warning: str | None = None


def resolve_unique_slug(
    ai_trends_dir: Path,
    source: dict[str, Any],
    taken: set[str] | None = None,
) -> SlugResolution:
    """Return a unique slug for ``source`` within the current run.

    Priority: explicit ``slug`` field; else derive from ``name``.
    If the chosen slug collides with ``taken`` (slugs already assigned
    to other sources in this run), append ``-2`` and emit a warning.
    The filesystem is NOT checked — slug resolution is deterministic
    from the source definition, so the same source always gets the
    same slug across runs.
    """
    name = source.get("name") or "unknown"
    explicit = source.get("slug") if isinstance(source.get("slug"), str) else None
    base = slugify(name, explicit_slug=explicit if isinstance(explicit, str) else None)

    existing: set[str] = set()
    if taken is not None:
        existing.update(taken)

    if base not in existing:
        return SlugResolution(slug=base, collision=False)

    candidate = f"{base}-2"
    suffix = 2
    while candidate in existing:
        suffix += 1
        candidate = f"{base}-{suffix}"
    warning = (
        f"slug collision: {base!r} already taken; using {candidate!r} "
        f"for source {name!r}"
    )
    print(f"WARNING: {warning}", file=sys.stderr)
    return SlugResolution(slug=candidate, collision=True, warning=warning)
