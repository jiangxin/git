"""Tests for publish_prep helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from publish_prep import (
    DEFAULT_PARENT_NODE_ID,
    build_publish_context,
    check_weekly_md,
    collect_local_image_refs,
    extract_first_h1_from_markdown,
    get_parent_node_id,
    resolve_repo_root,
    WeeklyMdMissing,
)


def test_resolve_repo_root():
    root = resolve_repo_root(Path(__file__))
    assert (root / "weekly").is_dir()
    assert (root / ".agents" / "skills").is_dir() or (root / ".claude" / "skills").is_dir()


def test_check_weekly_md_missing(tmp_path):
    repo = tmp_path / "repo"
    (repo / "weekly" / "2026-05-10").mkdir(parents=True)
    (repo / ".agents" / "skills").mkdir(parents=True)
    assert check_weekly_md(repo, "2026-05-10") is None


def test_check_weekly_md_present(tmp_path):
    repo = tmp_path / "repo"
    week = repo / "weekly" / "2026-05-10"
    week.mkdir(parents=True)
    (repo / ".agents" / "skills").mkdir(parents=True)
    md = week / "weekly-report.md"
    md.write_text("# 【2026-05-10】AI Native 周报\n", encoding="utf-8")
    assert check_weekly_md(repo, "2026-05-10") == md


def test_build_publish_context_with_explicit_md(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".agents" / "skills").mkdir(parents=True)
    week = repo / "weekly" / "2026-05-10"
    week.mkdir(parents=True)
    img = week / "token-metrics"
    img.mkdir(parents=True)
    (img / "tools.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    md = week / "weekly-report.md"
    md.write_text(
        "# 【2026-05-10】AI Native 周报（预览版）\n\n"
        "![t](token-metrics/tools.png)\n",
        encoding="utf-8",
    )
    ctx = build_publish_context(repo, "2026-05-10", md_path=md)
    assert ctx["doc_title"] == "【2026-05-10】AI Native 周报（预览版）"
    assert len(ctx["images"]) == 1
    assert ctx["images"][0]["href"] == "token-metrics/tools.png"
    assert Path(ctx["images"][0]["path"]).name == "tools.png"


def test_build_publish_context_raises_when_missing(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".agents" / "skills").mkdir(parents=True)
    (repo / "weekly" / "2026-05-10").mkdir(parents=True)
    with pytest.raises(WeeklyMdMissing):
        build_publish_context(repo, "2026-05-10")


def test_extract_first_h1_from_markdown():
    text = "# 【2026-05-10】AI 周报\n\nSome content"
    assert extract_first_h1_from_markdown(text) == "【2026-05-10】AI 周报"


def test_extract_first_h1_returns_none_when_absent():
    assert extract_first_h1_from_markdown("No heading here\n") is None


def test_collect_local_image_skips_absolute():
    base = Path("/tmp")
    text = "![](https://example.com/x.png) ![](rel.png)"
    assert collect_local_image_refs(text, base) == []


class TestGetParentNodeId:
    def test_reads_from_config(self):
        with patch("publish_prep.load_repo_config", return_value={"publish_parent_node_id": "custom_id"}):
            assert get_parent_node_id() == "custom_id"

    def test_falls_back_to_default(self):
        with patch("publish_prep.load_repo_config", return_value={}):
            assert get_parent_node_id() == DEFAULT_PARENT_NODE_ID

    def test_empty_string_falls_back(self):
        with patch("publish_prep.load_repo_config", return_value={"publish_parent_node_id": ""}):
            assert get_parent_node_id() == DEFAULT_PARENT_NODE_ID

    def test_whitespace_only_falls_back(self):
        with patch("publish_prep.load_repo_config", return_value={"publish_parent_node_id": "  "}):
            assert get_parent_node_id() == DEFAULT_PARENT_NODE_ID
