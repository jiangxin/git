"""Tests for summary_io.py — front-matter parse, validate, write."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from summary_io import (  # noqa: E402
    SummaryData,
    is_valid_summary,
    iter_missing_summaries,
    load_summary,
    parse_summary,
    summary_path,
    validate_summary,
    write_summary,
)
from site_store import claim_url  # noqa: E402


VALID_DATA = {
    "en_summary": "English summary text.",
    "cn_title": "中文标题",
    "cn_summary": "中文概述内容。",
    "collected_at": "2026-07-23T11:30:00",
}

VALID_WITH_RANK = {**VALID_DATA, "rank_hint": 1}


class TestParseSummary:
    def test_valid_front_matter(self):
        text = (
            "---\n"
            "en_summary: \"English summary text.\"\n"
            "cn_title: \"中文标题\"\n"
            "cn_summary: \"中文概述内容。\"\n"
            "collected_at: \"2026-07-23T11:30:00\"\n"
            "---\n"
        )
        result = parse_summary(text)
        assert result is not None
        assert result["en_summary"] == "English summary text."
        assert result["cn_title"] == "中文标题"

    def test_with_optional_rank_hint(self):
        text = (
            "---\n"
            "en_summary: \"E\"\n"
            "cn_title: \"中\"\n"
            "cn_summary: \"概\"\n"
            "collected_at: \"2026-07-23T11:30:00\"\n"
            "rank_hint: 3\n"
            "---\n"
        )
        result = parse_summary(text)
        assert result is not None
        assert result["rank_hint"] == 3

    def test_with_body_after_delimiter(self):
        text = (
            "---\n"
            "en_summary: \"E\"\n"
            "cn_title: \"中\"\n"
            "cn_summary: \"概\"\n"
            "collected_at: \"2026-07-23T11:30:00\"\n"
            "---\n"
            "\n"
            "Some body text here.\n"
        )
        result = parse_summary(text)
        assert result is not None
        assert result["en_summary"] == "E"

    def test_missing_front_matter_returns_none(self):
        assert parse_summary("no front matter here") is None

    def test_empty_string_returns_none(self):
        assert parse_summary("") is None

    def test_malformed_yaml_returns_none(self):
        text = "---\n: : : broken\n---\n"
        assert parse_summary(text) is None

    def test_non_dict_yaml_returns_none(self):
        text = "---\n- just\n- a\n- list\n---\n"
        assert parse_summary(text) is None

    def test_missing_closing_delimiter_returns_none(self):
        text = "---\nen_summary: only one delimiter\n"
        assert parse_summary(text) is None


class TestValidateSummary:
    def test_valid_data_passes(self):
        ok, missing = validate_summary(VALID_DATA)
        assert ok is True
        assert missing == []

    def test_valid_with_rank_hint_passes(self):
        ok, missing = validate_summary(VALID_WITH_RANK)
        assert ok is True
        assert missing == []

    def test_missing_single_field(self):
        data = {**VALID_DATA}
        del data["cn_title"]
        ok, missing = validate_summary(data)
        assert ok is False
        assert "cn_title" in missing

    def test_missing_multiple_fields(self):
        data = {"en_summary": "ok"}
        ok, missing = validate_summary(data)
        assert ok is False
        assert set(missing) == {"cn_title", "cn_summary", "collected_at"}

    def test_empty_string_field_is_invalid(self):
        data = {**VALID_DATA, "cn_summary": "   "}
        ok, missing = validate_summary(data)
        assert ok is False
        assert "cn_summary" in missing

    def test_non_string_field_is_invalid(self):
        data = {**VALID_DATA, "en_summary": 123}
        ok, missing = validate_summary(data)
        assert ok is False
        assert "en_summary" in missing

    def test_invalid_rank_hint_type(self):
        data = {**VALID_DATA, "rank_hint": "not-a-number"}
        ok, missing = validate_summary(data)
        assert ok is False
        assert "rank_hint" in missing

    def test_none_rank_hint_is_ok(self):
        data = {**VALID_DATA, "rank_hint": None}
        ok, missing = validate_summary(data)
        assert ok is True

    def test_integer_rank_hint_is_ok(self):
        data = {**VALID_DATA, "rank_hint": 5}
        ok, missing = validate_summary(data)
        assert ok is True

    def test_none_data_is_invalid(self):
        ok, missing = validate_summary(None)
        assert ok is False

    def test_empty_dict_is_invalid(self):
        ok, missing = validate_summary({})
        assert ok is False
        assert set(missing) == set(
            ("en_summary", "cn_title", "cn_summary", "collected_at")
        )


class TestIsValidSummary:
    def test_true_for_valid(self):
        assert is_valid_summary(VALID_DATA) is True

    def test_false_for_missing(self):
        assert is_valid_summary({"en_summary": "only one"}) is False

    def test_false_for_none(self):
        assert is_valid_summary(None) is False


class TestWriteAndLoad:
    def test_roundtrip_dict(self, tmp_path):
        p = tmp_path / "abc.summary.md"
        write_summary(p, VALID_DATA)
        loaded = load_summary(p)
        assert loaded is not None
        assert loaded["en_summary"] == VALID_DATA["en_summary"]
        assert loaded["cn_title"] == VALID_DATA["cn_title"]
        assert loaded["cn_summary"] == VALID_DATA["cn_summary"]
        assert loaded["collected_at"] == VALID_DATA["collected_at"]
        ok, _ = validate_summary(loaded)
        assert ok

    def test_roundtrip_summary_data(self, tmp_path):
        p = tmp_path / "abc.summary.md"
        sd = SummaryData(
            en_summary="Hello",
            cn_title="标题",
            cn_summary="概述",
            collected_at="2026-07-23T12:00:00",
            rank_hint=2,
        )
        write_summary(p, sd)
        loaded = load_summary(p)
        assert loaded is not None
        assert loaded["rank_hint"] == 2

    def test_roundtrip_with_body(self, tmp_path):
        p = tmp_path / "abc.summary.md"
        write_summary(p, VALID_DATA, body="Some body text.\n")
        text = p.read_text(encoding="utf-8")
        assert "Some body text." in text
        loaded = load_summary(p)
        assert is_valid_summary(loaded)

    def test_creates_parent_directories(self, tmp_path):
        p = tmp_path / "deep" / "nested" / "abc.summary.md"
        write_summary(p, VALID_DATA)
        assert p.is_file()

    def test_load_missing_file_returns_none(self, tmp_path):
        p = tmp_path / "no-such-file.summary.md"
        assert load_summary(p) is None

    def test_load_malformed_file_returns_none(self, tmp_path):
        p = tmp_path / "bad.summary.md"
        p.write_text("not front matter\n")
        assert load_summary(p) is None


class TestSummaryPath:
    def test_layout(self, tmp_path):
        ai = tmp_path / "ai-trends"
        p = summary_path(ai, "my-site", "abc123")
        assert p == ai / "sites" / "my-site" / "articles" / "abc123.summary.md"


class TestIterMissingSummaries:
    def test_yields_articles_without_summary(self, tmp_path):
        ai = tmp_path / "ai-trends"
        result = claim_url(
            ai,
            url="https://e.com/no-summary",
            slug="s",
            meta={"original_title": "A", "source": "s", "status": "fetched"},
            body="c" * 500,
        )
        assert result.won
        missing = list(iter_missing_summaries(ai))
        assert len(missing) == 1
        slug, hash_, meta_file, summary_file = missing[0]
        assert slug == "s"
        assert hash_ == result.hash

    def test_skips_when_valid_summary_present(self, tmp_path):
        ai = tmp_path / "ai-trends"
        result = claim_url(
            ai,
            url="https://e.com/has-summary",
            slug="s",
            meta={"original_title": "A", "source": "s", "status": "fetched"},
            body="c" * 500,
        )
        assert result.won
        s_path = summary_path(ai, "s", result.hash)
        write_summary(s_path, VALID_DATA)
        missing = list(iter_missing_summaries(ai))
        assert len(missing) == 0

    def test_skips_non_terminal_status(self, tmp_path):
        ai = tmp_path / "ai-trends"
        claim_url(
            ai,
            url="https://e.com/error-article",
            slug="s",
            meta={"original_title": "A", "source": "s", "status": "error"},
            body="",
        )
        missing = list(iter_missing_summaries(ai))
        assert len(missing) == 0

    def test_empty_when_no_sites(self, tmp_path):
        ai = tmp_path / "ai-trends"
        assert list(iter_missing_summaries(ai)) == []
