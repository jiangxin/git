"""Tests for setup_week.py — ai-trends directory creation."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))
from setup_week import setup_week


class TestSetupWeek:
    def test_creates_ai_trends_directory(self, tmp_weekly_root):
        setup_week(tmp_weekly_root, "2026-05-10")
        assert (tmp_weekly_root / "2026-05-10" / "ai-trends").is_dir()

    def test_idempotent_across_end_dates(self, tmp_weekly_root):
        setup_week(tmp_weekly_root, "2026-05-03")
        setup_week(tmp_weekly_root, "2026-05-10")
        assert (tmp_weekly_root / "2026-05-03" / "ai-trends").is_dir()
        assert (tmp_weekly_root / "2026-05-10" / "ai-trends").is_dir()

    def test_creates_nested_ai_trends_dir(self, tmp_weekly_root):
        setup_week(tmp_weekly_root, "2026-12-28")
        assert (tmp_weekly_root / "2026-12-28").is_dir()
        assert (tmp_weekly_root / "2026-12-28" / "ai-trends").is_dir()
