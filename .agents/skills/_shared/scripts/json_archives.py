"""Shared JSON array loading, atomic saving, and key-based merging utilities.

Used by ai-trends-weekly and ata-team-update-weekly merge_archives.py scripts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json_array(path: Path, label: str) -> list:
    """Load a JSON file and validate it as an array.

    Prints detailed diagnostic information on parse failure (for LLM repair).

    Args:
        path: JSON file path.
        label: human-readable name for error messages (e.g. "new.json").

    Returns:
        Parsed list.

    Raises:
        SystemExit: on empty file, parse error, or non-array root.
    """
    raw = path.read_text(encoding="utf-8")
    stripped = raw.strip()

    if not stripped:
        print(f"ERROR: {label} is empty: {path}", file=sys.stderr)
        sys.exit(3)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed in {label} ({path})", file=sys.stderr)
        print(f"  Error: {e.msg}", file=sys.stderr)
        print(f"  Line {e.lineno}, Column {e.colno}", file=sys.stderr)
        lines = raw.splitlines()
        if e.lineno is not None and 1 <= e.lineno <= len(lines):
            print(f"  Problematic line: {lines[e.lineno - 1].strip()}", file=sys.stderr)
            if e.colno is not None:
                print(f"  {' ' * (e.colno - 1)}^", file=sys.stderr)
        pos = e.pos or 0
        ctx_start = max(0, pos - 80)
        ctx_end = min(len(raw), pos + 80)
        print(f"  Context: ...{raw[ctx_start:ctx_end]}...", file=sys.stderr)
        print("JSON_REPAIR_NEEDED", file=sys.stderr)
        sys.exit(3)

    if not isinstance(data, list):
        print(f"ERROR: {label} root is not an array, got {type(data).__name__}: {path}", file=sys.stderr)
        sys.exit(3)

    return data


def save_json_atomic(data: list, target_path: Path) -> None:
    """Write JSON data to a .tmp file then atomically replace the target."""
    tmp_path = target_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(target_path)


def merge_by_key(archives: list, new_entries: list, key: str) -> tuple[list, int]:
    """Append new_entries to archives, deduplicating by *key* field.

    Returns:
        (merged_list, added_count)
    """
    existing_keys = {entry.get(key) for entry in archives}
    merged = list(archives)
    added = 0
    for entry in new_entries:
        k = entry.get(key)
        if k not in existing_keys:
            merged.append(entry)
            existing_keys.add(k)
            added += 1
    return merged, added
