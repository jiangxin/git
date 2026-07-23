import json
import subprocess
import sys
from pathlib import Path

import pytest

from filter_by_date import extract_date, filter_entries

SCRIPT = Path(__file__).resolve().parent.parent / "filter_by_date.py"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-05-04", "2026-05-04"),
        ("2026-05-09T18:27:47+08:00", "2026-05-09"),
        ("2026-05-09 18:27:47", "2026-05-09"),
        ("  2026-01-07  ", "2026-01-07"),
        ("", None),
        ("not-a-date", None),
        (None, None),
        ("2026-13-40", None),  # invalid month/day
    ],
)
def test_extract_date(raw, expected):
    assert extract_date(raw) == expected


def test_filter_entries_boundaries():
    entries = [
        {"url": "a", "publish_date": "2026-05-03"},
        {"url": "b", "publish_date": "2026-05-10"},
        {"url": "c", "publish_date": "2026-05-02"},
        {"url": "d", "publish_date": "2026-05-11"},
    ]
    kept, excl = filter_entries(entries, "2026-05-03", "2026-05-10", "publish_date")
    assert {e["url"] for e in kept} == {"a", "b"}
    assert len(excl) == 2


def test_filter_entries_iso_field():
    entries = [
        {"articleId": 1, "createTimeShadow": "2026-05-09T18:27:47+08:00"},
        {"articleId": 2, "createTimeShadow": "2026-05-01T00:00:00"},
    ]
    kept, excl = filter_entries(entries, "2026-05-03", "2026-05-10", "createTimeShadow")
    assert len(kept) == 1 and kept[0]["articleId"] == 1
    assert len(excl) == 1


def test_filter_entries_missing_field():
    entries = [{"url": "x"}]
    kept, excl = filter_entries(entries, "2026-05-03", "2026-05-10", "publish_date")
    assert kept == []
    assert len(excl) == 1 and excl[0][2] == "missing_or_unparseable_date"


def test_filter_entries_not_object():
    entries = ["bad"]
    kept, excl = filter_entries(entries, "2026-05-03", "2026-05-10", "publish_date")
    assert kept == []
    assert excl[0][2] == "not_an_object"


def test_filter_entries_empty():
    kept, excl = filter_entries([], "2026-05-03", "2026-05-10", "publish_date")
    assert kept == [] and excl == []


def test_cli_exit_0_all_in_range(tmp_path):
    data = [{"url": "u", "publish_date": "2026-05-05"}]
    p = tmp_path / "in.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--start", "2026-05-03", "--end", "2026-05-10", "--date-field", "publish_date", "--input", str(p)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == data
    assert "EXCLUDED" not in proc.stderr


def test_cli_exit_1_some_excluded(tmp_path):
    data = [
        {"url": "in", "publish_date": "2026-05-05"},
        {"url": "out", "publish_date": "2026-04-01"},
    ]
    p = tmp_path / "in.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--start", "2026-05-03", "--end", "2026-05-10", "--date-field", "publish_date", "--input", str(p)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    out = json.loads(proc.stdout)
    assert len(out) == 1 and out[0]["url"] == "in"
    assert "EXCLUDED" in proc.stderr


def test_cli_stdin():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--start", "2026-05-03", "--end", "2026-05-10", "--date-field", "createTime"],
        input=json.dumps([{"name": "n", "createTime": "2026-05-05"}]),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)[0]["name"] == "n"


def test_cli_invalid_start_date():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--start", "not-a-date", "--end", "2026-05-10", "--date-field", "x"],
        input="[]",
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
