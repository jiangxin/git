"""Shared weekly-report date computation and week directory helpers.

Exports pure functions used by each skill's setup_week.py thin wrapper.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from repo_config import load_repo_config

DAY_NAMES: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

DEFAULT_START_DAY = "saturday"
DEFAULT_END_DAY = "friday"
DEFAULT_TZ_OFFSET = "+08:00"

# Shared copy for skill setup_week.py docstrings / argparse (default Sat–Fri example).
SETUP_WEEK_INTERVAL_HELP = (
    "收集闭区间 [start_date, end_date] 由仓库根 config.json 的 start_day、end_day 计算"
    f"（缺省 {DEFAULT_START_DAY} / {DEFAULT_END_DAY}）；周目录名为 end_date。"
)
SETUP_WEEK_EPILOG = (
    f"示例（缺省 {DEFAULT_START_DAY}–{DEFAULT_END_DAY}）: "
    "setup_week.py 2026-05-15 → '2026-05-09 2026-05-15'"
)


def parse_weekday_name(name: str) -> int:
    """Map a day name (e.g. ``saturday``) to ``date.weekday()`` (Monday=0 … Sunday=6)."""
    key = name.strip().lower()
    if key not in DAY_NAMES:
        raise ValueError(
            f"invalid weekday {name!r}; expected one of: {', '.join(DAY_NAMES)}"
        )
    return DAY_NAMES[key]


DEFAULT_LOOKBACK_DAYS = 2


def week_day_bounds_from_config(script_file: Path | None = None) -> tuple[int, int]:
    """Read ``start_day`` / ``end_day`` from repo ``config.json`` (defaults: Sat–Fri)."""
    cfg = load_repo_config(script_file or Path(__file__))
    start_day = cfg.get("start_day", DEFAULT_START_DAY)
    end_day = cfg.get("end_day", DEFAULT_END_DAY)
    return parse_weekday_name(str(start_day)), parse_weekday_name(str(end_day))


def lookback_days_from_config(script_file: Path | None = None) -> int:
    """Read ``lookback_days`` from repo ``config.json`` (default: DEFAULT_LOOKBACK_DAYS)."""
    cfg = load_repo_config(script_file or Path(__file__))
    return int(cfg.get("lookback_days", DEFAULT_LOOKBACK_DAYS))


def days_back_from_end_to_start(end_weekday: int, start_weekday: int) -> int:
    """Inclusive span from *start_weekday* through *end_weekday* as days to subtract from end."""
    delta = end_weekday - start_weekday
    if delta <= 0:
        return 7 + delta
    return delta


def resolve_anchor_datetime(date_str: str | None) -> datetime:
    """Parse a CLI date argument into a datetime anchored at 00:00:00.

    Args:
        date_str: YYYY-MM-DD string, or None to use local today.

    Returns:
        datetime object at midnight.

    Raises:
        ValueError: if date_str is not a valid YYYY-MM-DD string.
    """
    if date_str is None:
        return datetime.combine(date.today(), datetime.min.time())
    return datetime.strptime(date_str, "%Y-%m-%d")


def compute_week_dates(
    input_date: datetime,
    script_file: Path | None = None,
) -> tuple[str, str]:
    """Compute the collection interval [start_date, end_date] from config week bounds.

    ``end_date`` is the upcoming configured end weekday (or today if anchor is already
    on that weekday). ``start_date`` is the configured start weekday of the same period.

    Week bounds come from ``config.json`` keys ``start_day`` / ``end_day`` (defaults:
    ``saturday`` / ``friday``).

    Returns:
        (start_date_str, end_date_str) in YYYY-MM-DD format.
    """
    start_wd, end_wd = week_day_bounds_from_config(script_file)
    anchor = input_date.date()
    days_until_end = (end_wd - anchor.weekday()) % 7
    end_dt = anchor + timedelta(days=days_until_end)
    span = days_back_from_end_to_start(end_wd, start_wd)
    start_dt = end_dt - timedelta(days=span)

    lookback = lookback_days_from_config(script_file)
    if lookback > 0:
        prev_end = start_dt - timedelta(days=1)
        if (anchor - prev_end).days <= lookback and (end_dt - anchor).days > lookback:
            end_dt = prev_end
            start_dt = end_dt - timedelta(days=span)

    return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")


def end_exclusive_datetime(end_date: str) -> datetime:
    """Return local midnight at ``end_date + 1 day`` (half-open range upper bound)."""
    end_day = datetime.strptime(end_date, "%Y-%m-%d").date()
    return datetime.combine(end_day + timedelta(days=1), datetime.min.time())


def end_exclusive_iso(end_date: str, *, offset: str = DEFAULT_TZ_OFFSET) -> str:
    """ISO-8601 upper bound for ``[start, end)`` queries (e.g. dws ``calendar event list --end``)."""
    return end_exclusive_datetime(end_date).strftime(f"%Y-%m-%dT%H:%M:%S{offset}")


def start_inclusive_iso(start_date: str, *, offset: str = DEFAULT_TZ_OFFSET) -> str:
    """ISO-8601 lower bound at ``start_date`` local midnight."""
    datetime.strptime(start_date, "%Y-%m-%d")
    return f"{start_date}T00:00:00{offset}"


def start_date_for_end(end_date_str: str, script_file: Path | None = None) -> str:
    """Given a period ``end_date`` (YYYY-MM-DD), return matching ``start_date``."""
    start_wd, end_wd = week_day_bounds_from_config(script_file)
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=days_back_from_end_to_start(end_wd, start_wd))
    return start_dt.strftime("%Y-%m-%d")


def week_dir(weekly_root: Path, end_date: str) -> Path:
    """Path to ``weekly/<end_date>/`` (directory may not exist yet)."""
    return Path(weekly_root) / end_date


def ensure_week_dir(weekly_root: Path, end_date: str) -> Path:
    """Create ``weekly/<end_date>/`` if missing.

    Returns:
        Path to the week directory (``weekly_root / end_date``).
    """
    path = week_dir(weekly_root, end_date)
    path.mkdir(parents=True, exist_ok=True)
    return path


def repo_weekly_root_from_skill_script(script_file: str | Path) -> Path:
    """Derive the repo's weekly/ directory from a skill script's __file__.

    Assumes the script lives at .agents/skills/<name>/scripts/<script>.py,
    so parent (scripts/) then parents[3] gives the repo root.
    """
    script_dir = Path(script_file).resolve().parent
    return script_dir.parents[3] / "weekly"
