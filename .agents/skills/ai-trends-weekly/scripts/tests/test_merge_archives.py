"""Tests for merge_archives.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from merge_archives import load_json_array, merge, save_json_atomic, run


@pytest.fixture
def week_env(tmp_path):
    """创建 weekly/<end_date>/ai-trends/ 与 archives.json、new.json。

    返回工厂 _make(archives_data, new_data, end_date=...) -> (weekly_root, ai_trends_dir)
    archives_data / new_data 为 list 时序列化，为 str 时直接写入（用于测试损坏 JSON）。
    archives_data 为 None 时不创建 archives.json（脚本应自动初始化）。
    """
    def _make(archives_data=None, new_data=None, end_date="2026-05-10"):
        weekly_root = tmp_path / "weekly"
        weekly_root.mkdir(exist_ok=True)
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True, exist_ok=True)

        if archives_data is not None:
            ap = ai_trends / "archives.json"
            if isinstance(archives_data, (list, dict)):
                ap.write_text(json.dumps(archives_data, ensure_ascii=False, indent=2))
            else:
                ap.write_text(archives_data)

        if new_data is not None:
            np = ai_trends / "new.json"
            if isinstance(new_data, (list, dict)):
                np.write_text(json.dumps(new_data, ensure_ascii=False, indent=2))
            else:
                np.write_text(new_data)

        return weekly_root, ai_trends

    return _make


def _entry(url, title="Title"):
    return {
        "original_title": title,
        "en_summary": "Summary.",
        "cn_title": "标题",
        "cn_summary": "概述",
        "url": url,
        "publish_date": "2026-05-08",
        "source": "Test",
        "collected_at": "2026-05-10T10:00:00",
    }


class TestLoadJsonArray:
    """测试 JSON 加载与错误报告。"""

    def test_valid_array(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('[{"a":1}]')
        result = load_json_array(p, "data.json")
        assert result == [{"a": 1}]

    def test_empty_file_exits(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text("")
        with pytest.raises(SystemExit) as exc:
            load_json_array(p, "data.json")
        assert exc.value.code == 3

    def test_malformed_json_exits(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('[{"a": 1,}]')
        with pytest.raises(SystemExit) as exc:
            load_json_array(p, "data.json")
        assert exc.value.code == 3

    def test_not_array_exits(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"key": "value"}')
        with pytest.raises(SystemExit) as exc:
            load_json_array(p, "data.json")
        assert exc.value.code == 3

    def test_malformed_json_stderr_has_repair_marker(self, tmp_path, capsys):
        p = tmp_path / "data.json"
        p.write_text('[{"a": 1,}]')
        with pytest.raises(SystemExit):
            load_json_array(p, "data.json")
        assert "JSON_REPAIR_NEEDED" in capsys.readouterr().err


class TestMerge:
    """测试合并与去重逻辑。"""

    def test_append_new(self):
        archives = [_entry("https://a.com")]
        new = [_entry("https://b.com")]
        merged, added = merge(archives, new)
        assert added == 1
        assert len(merged) == 2

    def test_dedup(self):
        archives = [_entry("https://a.com")]
        new = [_entry("https://a.com"), _entry("https://b.com")]
        merged, added = merge(archives, new)
        assert added == 1
        assert len(merged) == 2

    def test_empty_new(self):
        archives = [_entry("https://a.com")]
        merged, added = merge(archives, [])
        assert added == 0
        assert len(merged) == 1

    def test_empty_archives(self):
        merged, added = merge([], [_entry("https://a.com")])
        assert added == 1
        assert len(merged) == 1

    def test_dedup_within_new(self):
        """new.json 自身重复的 url 只保留首条。"""
        new = [_entry("https://a.com", "First"), _entry("https://a.com", "Second")]
        merged, added = merge([], new)
        assert added == 1
        assert merged[0]["original_title"] == "First"


class TestSaveJsonAtomic:
    """测试原子写入。"""

    def test_writes_and_replaces(self, tmp_path):
        target = tmp_path / "out.json"
        target.write_text("old")
        save_json_atomic([{"x": 1}], target)
        assert not (tmp_path / "out.json.tmp").exists()
        data = json.loads(target.read_text())
        assert data == [{"x": 1}]


class TestRun:
    """测试完整 run() 流程。"""

    def test_basic_merge(self, week_env):
        weekly_root, ai_trends = week_env(
            archives_data=[_entry("https://old.com")],
            new_data=[_entry("https://new.com")],
        )
        added, total = run("2026-05-10", weekly_root=weekly_root)
        assert added == 1
        assert total == 2
        archives = json.loads((ai_trends / "archives.json").read_text())
        assert len(archives) == 2
        assert not (ai_trends / "new.json").exists()

    def test_no_archives_auto_init(self, week_env):
        """archives.json 不存在时自动初始化为空数组。"""
        weekly_root, ai_trends = week_env(
            archives_data=None,
            new_data=[_entry("https://first.com")],
        )
        added, total = run("2026-05-10", weekly_root=weekly_root)
        assert added == 1
        assert total == 1

    def test_new_json_missing_exits(self, week_env):
        weekly_root, _ = week_env(archives_data=[], new_data=None)
        with pytest.raises(SystemExit) as exc:
            run("2026-05-10", weekly_root=weekly_root)
        assert exc.value.code == 2

    def test_malformed_new_json_exits(self, week_env):
        weekly_root, _ = week_env(archives_data=[], new_data="{bad")
        with pytest.raises(SystemExit) as exc:
            run("2026-05-10", weekly_root=weekly_root)
        assert exc.value.code == 3

    def test_malformed_archives_exits(self, week_env):
        weekly_root, _ = week_env(archives_data="{bad", new_data=[])
        with pytest.raises(SystemExit) as exc:
            run("2026-05-10", weekly_root=weekly_root)
        assert exc.value.code == 3

    def test_tmp_not_left_behind(self, week_env):
        """成功后 .tmp 文件不应残留。"""
        weekly_root, ai_trends = week_env(
            archives_data=[],
            new_data=[_entry("https://a.com")],
        )
        run("2026-05-10", weekly_root=weekly_root)
        assert not (ai_trends / "archives.json.tmp").exists()

    def test_dedup_across_merge(self, week_env):
        weekly_root, ai_trends = week_env(
            archives_data=[_entry("https://dup.com")],
            new_data=[_entry("https://dup.com"), _entry("https://unique.com")],
        )
        added, total = run("2026-05-10", weekly_root=weekly_root)
        assert added == 1
        assert total == 2


class TestUpsert:
    def test_merge_upsert_updates_summary_fields(self):
        archives = [
            _entry("https://a.com"),
        ]
        archives[0]["cn_summary"] = "旧概述"
        archives[0]["rank_hint"] = 9
        new = [
            {
                **_entry("https://a.com"),
                "cn_summary": "新概述",
                "en_summary": "New summary.",
                "rank_hint": 1,
                "collected_at": "2026-05-11T12:00:00",
            }
        ]
        # default: no update
        merged, added = merge(archives, new)
        assert added == 0
        assert merged[0]["cn_summary"] == "旧概述"

        merged2, added2 = merge(archives, new, upsert=True)
        assert added2 == 0
        assert merged2[0]["cn_summary"] == "新概述"
        assert merged2[0]["en_summary"] == "New summary."
        assert merged2[0]["rank_hint"] == 1
        assert merged2[0]["collected_at"] == "2026-05-11T12:00:00"
        assert merged2[0]["url"] == "https://a.com"

    def test_run_upsert(self, week_env):
        old = _entry("https://a.com")
        old["cn_summary"] = "旧"
        new = {**_entry("https://a.com"), "cn_summary": "新", "rank_hint": 2}
        weekly_root, ai_trends = week_env(archives_data=[old], new_data=[new])
        added, total = run("2026-05-10", weekly_root=weekly_root, upsert=True)
        assert added == 0
        assert total == 1
        archives = json.loads((ai_trends / "archives.json").read_text())
        assert archives[0]["cn_summary"] == "新"
        assert archives[0]["rank_hint"] == 2
        assert not (ai_trends / "new.json").exists()
