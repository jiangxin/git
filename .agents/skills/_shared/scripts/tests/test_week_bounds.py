"""Tests for week_bounds.py — shared date computation and week directories."""

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from week_bounds import (
    compute_week_dates,
    days_back_from_end_to_start,
    end_exclusive_datetime,
    end_exclusive_iso,
    ensure_week_dir,
    parse_weekday_name,
    repo_weekly_root_from_skill_script,
    resolve_anchor_datetime,
    start_date_for_end,
    week_dir,
    start_inclusive_iso,
    week_day_bounds_from_config,
)


def _make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    return repo


class TestResolveAnchorDatetime:
    def test_explicit_string(self):
        dt = resolve_anchor_datetime("2026-05-08")
        assert dt == datetime(2026, 5, 8, 0, 0, 0)

    def test_none_uses_local_today(self):
        fixed = date(2026, 5, 8)
        with patch("week_bounds.date") as mock_date:
            mock_date.today.return_value = fixed
            dt = resolve_anchor_datetime(None)
        assert dt == datetime(2026, 5, 8, 0, 0, 0)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            resolve_anchor_datetime("not-a-date")


class TestParseWeekdayName:
    def test_case_insensitive(self):
        assert parse_weekday_name("Saturday") == 5
        assert parse_weekday_name("FRIDAY") == 4

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="invalid weekday"):
            parse_weekday_name("notaday")


class TestDaysBackFromEndToStart:
    def test_saturday_to_friday(self):
        assert days_back_from_end_to_start(4, 5) == 6

    def test_sunday_to_sunday(self):
        assert days_back_from_end_to_start(6, 6) == 7


class TestComputeWeekDates:
    """Default config: start_day=saturday, end_day=friday."""

    @pytest.mark.parametrize(
        "date_str,expected_start,expected_end",
        [
            ("2026-05-10", "2026-05-02", "2026-05-08"),  # Sunday: grace fallback
            ("2026-05-04", "2026-05-02", "2026-05-08"),  # Monday
            ("2026-05-05", "2026-05-02", "2026-05-08"),  # Tuesday
            ("2026-05-06", "2026-05-02", "2026-05-08"),  # Wednesday
            ("2026-05-07", "2026-05-02", "2026-05-08"),  # Thursday
            ("2026-05-08", "2026-05-02", "2026-05-08"),  # Friday
            ("2026-05-09", "2026-05-02", "2026-05-08"),  # Saturday: grace fallback
            ("2026-05-03", "2026-04-25", "2026-05-01"),  # Sunday: grace fallback
            ("2026-05-11", "2026-05-09", "2026-05-15"),  # Monday
            ("2026-01-01", "2025-12-27", "2026-01-02"),  # Cross-year (Thu, no fallback)
            ("2026-01-31", "2026-01-24", "2026-01-30"),  # Saturday: grace fallback
        ],
    )
    def test_date_calculation(self, date_str, expected_start, expected_end):
        input_date = datetime.strptime(date_str, "%Y-%m-%d")
        start, end = compute_week_dates(input_date)
        assert start == expected_start
        assert end == expected_end

    def test_friday_anchor(self):
        input_date = datetime(2026, 5, 8)
        start, end = compute_week_dates(input_date)
        assert start == "2026-05-02"
        assert end == "2026-05-08"

    def test_sunday_to_sunday_from_config(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        (repo / "config.json").write_text(
            json.dumps({"start_day": "sunday", "end_day": "sunday"}),
            encoding="utf-8",
        )
        script = repo / ".agents" / "skills" / "x" / "scripts" / "t.py"
        script.parent.mkdir(parents=True)
        script.write_text("")
        input_date = datetime(2026, 5, 17)
        start, end = compute_week_dates(input_date, script)
        assert start == "2026-05-10"
        assert end == "2026-05-17"


class TestComputeWeekDatesLookback:
    """Lookback: fall back to previous period when within lookback_days of prev end."""

    def _make_repo_with_lookback(self, tmp_path, lookback_days):
        repo = _make_git_repo(tmp_path)
        (repo / "config.json").write_text(
            json.dumps({"lookback_days": lookback_days}),
            encoding="utf-8",
        )
        script = repo / ".agents" / "skills" / "x" / "scripts" / "t.py"
        script.parent.mkdir(parents=True)
        script.write_text("")
        return script

    @pytest.mark.parametrize(
        "date_str,expected_start,expected_end,desc",
        [
            ("2026-05-23", "2026-05-16", "2026-05-22", "Sat: 1 day after prev end, fallback"),
            ("2026-05-24", "2026-05-16", "2026-05-22", "Sun: 2 days after prev end, fallback"),
            ("2026-05-25", "2026-05-23", "2026-05-29", "Mon: 3 days, no fallback"),
            ("2026-05-22", "2026-05-16", "2026-05-22", "Fri: end_day itself, no fallback needed"),
            ("2026-05-28", "2026-05-23", "2026-05-29", "Thu: well into current period"),
        ],
    )
    def test_lookback_2_days(self, tmp_path, date_str, expected_start, expected_end, desc):
        script = self._make_repo_with_lookback(tmp_path, 2)
        input_date = datetime.strptime(date_str, "%Y-%m-%d")
        start, end = compute_week_dates(input_date, script)
        assert start == expected_start, desc
        assert end == expected_end, desc

    def test_lookback_0_no_fallback(self, tmp_path):
        script = self._make_repo_with_lookback(tmp_path, 0)
        input_date = datetime(2026, 5, 23)
        start, end = compute_week_dates(input_date, script)
        assert start == "2026-05-23"
        assert end == "2026-05-29"


class TestEndExclusiveBounds:
    @pytest.mark.parametrize(
        "end_date,expected",
        [
            ("2026-05-09", "2026-05-10T00:00:00+08:00"),
            ("2026-01-31", "2026-02-01T00:00:00+08:00"),
            ("2025-12-31", "2026-01-01T00:00:00+08:00"),
            ("2024-02-29", "2024-03-01T00:00:00+08:00"),
        ],
    )
    def test_end_exclusive_iso(self, end_date, expected):
        assert end_exclusive_iso(end_date) == expected

    def test_start_inclusive_iso(self):
        assert start_inclusive_iso("2026-05-03") == "2026-05-03T00:00:00+08:00"

    def test_end_exclusive_datetime_is_next_midnight(self):
        dt = end_exclusive_datetime("2026-05-09")
        assert dt == datetime(2026, 5, 10, 0, 0, 0)


class TestStartDateForEnd:
    def test_default_sat_fri(self):
        assert start_date_for_end("2026-05-09") == "2026-05-03"
        assert start_date_for_end("2026-05-16") == "2026-05-10"

    def test_sunday_end_from_config(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        (repo / "config.json").write_text(
            json.dumps({"start_day": "sunday", "end_day": "sunday"}),
            encoding="utf-8",
        )
        script = repo / "scripts" / "t.py"
        script.parent.mkdir(parents=True)
        script.write_text("")
        assert start_date_for_end("2026-05-10", script) == "2026-05-03"


class TestWeekDayBoundsFromConfig:
    def test_defaults_without_config(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        script = repo / "scripts" / "t.py"
        script.parent.mkdir(parents=True)
        script.write_text("")
        assert week_day_bounds_from_config(script) == (5, 4)


class TestWeekDir:
    def test_week_dir_path(self, tmp_path):
        assert week_dir(tmp_path, "2026-05-10") == tmp_path / "2026-05-10"


class TestEnsureWeekDir:
    def test_creates_directory(self, tmp_path):
        path = ensure_week_dir(tmp_path, "2026-05-10")
        assert path == tmp_path / "2026-05-10"
        assert path.is_dir()

    def test_idempotent(self, tmp_path):
        ensure_week_dir(tmp_path, "2026-05-10")
        ensure_week_dir(tmp_path, "2026-05-10")
        assert (tmp_path / "2026-05-10").is_dir()


class TestRepoWeeklyRoot:
    def test_derives_correct_path(self, tmp_path):
        repo = tmp_path / "repo"
        script = repo / ".agents" / "skills" / "test-skill" / "scripts" / "test.py"
        script.parent.mkdir(parents=True)
        script.write_text("")
        result = repo_weekly_root_from_skill_script(script)
        assert result == repo / "weekly"
