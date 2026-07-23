"""仓库根目录定位与 config.json 读取（跨 skill 共享）。

用法::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))
    from repo_config import load_repo_config

    cfg = load_repo_config(Path(__file__))
    value = cfg.get("some_key", "default")
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


class RepoRootMismatchError(RuntimeError):
    """脚本推算的仓库根与 ``git rev-parse --show-toplevel`` 不一致。"""


def resolve_repo_root(script_file: Path) -> Path:
    """从 *script_file* 向上查找含 ``.git`` 的目录，并与 git 交叉校验。

    Raises:
        RuntimeError: 找不到 ``.git`` 或与 ``git rev-parse`` 结果不一致。
    """
    resolved = Path(script_file).resolve()
    candidate: Path | None = None
    for anc in resolved.parents:
        if (anc / ".git").exists():
            candidate = anc
            break
    if candidate is None:
        raise RuntimeError(
            f"无法定位仓库根：从 {resolved} 向上未找到 .git 目录"
        )

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(candidate),
        )
        if result.returncode == 0:
            git_root = Path(result.stdout.strip()).resolve()
            if git_root != candidate.resolve():
                raise RepoRootMismatchError(
                    f"仓库根路径不一致：.git 推算为 {candidate}，"
                    f"git rev-parse 返回 {git_root}"
                )
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        pass

    return candidate


def load_repo_config(script_file: Path) -> dict:
    """读取仓库根目录下的 ``config.json``，文件缺失或格式错误返回空 dict。"""
    root = resolve_repo_root(script_file)
    config_path = root / "config.json"
    if not config_path.is_file():
        return {}
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}
