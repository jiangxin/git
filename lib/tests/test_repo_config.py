"""Tests for repo_config: resolve_repo_root & load_repo_config."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from repo_config import RepoRootMismatchError, load_repo_config, resolve_repo_root


def _make_git_repo(tmp_path: Path) -> Path:
    """在 tmp_path 下创建一个真正的 git 仓库，返回仓库根。"""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, check=True)
    return repo


class TestResolveRepoRoot:
    def test_finds_git_root(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        deep = repo / "a" / "b" / "c"
        deep.mkdir(parents=True)
        script = deep / "test.py"
        script.write_text("")

        root = resolve_repo_root(script)
        assert root.resolve() == repo.resolve()

    def test_no_git_dir_raises(self, tmp_path):
        script = tmp_path / "no_repo" / "test.py"
        script.parent.mkdir(parents=True)
        script.write_text("")

        with pytest.raises(RuntimeError, match="未找到 .git"):
            resolve_repo_root(script)

    def test_mismatch_raises(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        script = repo / "test.py"
        script.write_text("")

        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="/some/other/path\n", stderr=""
        )
        with patch("repo_config.subprocess.run", return_value=fake_result):
            with pytest.raises(RepoRootMismatchError, match="不一致"):
                resolve_repo_root(script)

    def test_git_not_installed_passes(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        script = repo / "test.py"
        script.write_text("")

        with patch("repo_config.subprocess.run", side_effect=FileNotFoundError):
            root = resolve_repo_root(script)
            assert root.resolve() == repo.resolve()


class TestLoadRepoConfig:
    def test_reads_valid_config(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        cfg = repo / "config.json"
        cfg.write_text('{"key": "value"}', encoding="utf-8")
        script = repo / "a" / "b" / "test.py"
        script.parent.mkdir(parents=True)
        script.write_text("")

        result = load_repo_config(script)
        assert result == {"key": "value"}

    def test_missing_config_returns_empty(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        script = repo / "test.py"
        script.write_text("")

        assert load_repo_config(script) == {}

    def test_invalid_json_returns_empty(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        (repo / "config.json").write_text("not json", encoding="utf-8")
        script = repo / "test.py"
        script.write_text("")

        assert load_repo_config(script) == {}

    def test_non_dict_returns_empty(self, tmp_path):
        repo = _make_git_repo(tmp_path)
        (repo / "config.json").write_text("[1, 2]", encoding="utf-8")
        script = repo / "test.py"
        script.write_text("")

        assert load_repo_config(script) == {}
