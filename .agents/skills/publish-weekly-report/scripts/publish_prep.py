#!/usr/bin/env python3
"""
周报发布前置：校验 weekly-report.md、抽取标题与本地图片清单。

纯函数 + CLI，供 publish-weekly-report skill 与 pytest 使用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))
from repo_config import load_repo_config

# 钉钉知识库 / 文件夹节点（用户提供的父节点）
DEFAULT_PARENT_NODE_ID = "kDnRL6jAJMLgNkw7tXBq29j4VyMoPYe1"


def get_parent_node_id() -> str:
    """优先从仓库根 ``config.json`` 读取 ``publish_parent_node_id``，缺失则回退硬编码默认值。"""
    cfg = load_repo_config(Path(__file__))
    return (cfg.get("publish_parent_node_id") or "").strip() or DEFAULT_PARENT_NODE_ID


def get_parent_alidocs_url() -> str:
    return f"https://alidocs.dingtalk.com/i/nodes/{get_parent_node_id()}"

_MD_H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_MD_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def _repo_has_skills_layout(anc: Path) -> bool:
    """本仓库 skills 主目录为 ``.agents/skills``；亦识别 ``.claude/skills``（旧布局或符号链接）。"""
    if not (anc / "weekly").is_dir():
        return False
    return (anc / ".agents" / "skills").is_dir() or (anc / ".claude" / "skills").is_dir()


def resolve_repo_root(script_file: Path | None = None) -> Path:
    """从 skill 脚本位置向上查找同时含 ``weekly/`` 与 skills 目录的仓库根。"""
    start = (script_file or Path(__file__)).resolve()
    for anc in start.parents:
        if _repo_has_skills_layout(anc):
            return anc
    raise RuntimeError(
        "无法推断仓库根目录：从当前文件向上未找到 weekly/ 与 (.agents/skills 或 .claude/skills)"
    )


def week_dir(repo_root: Path, end_date: str) -> Path:
    return repo_root / "weekly" / end_date


def weekly_md_path(repo_root: Path, end_date: str) -> Path:
    return week_dir(repo_root, end_date) / "weekly-report.md"


def check_weekly_md(repo_root: Path, end_date: str) -> Path | None:
    """若 ``weekly/<end_date>/weekly-report.md`` 存在则返回路径，否则 ``None``。"""
    p = weekly_md_path(repo_root, end_date)
    return p if p.is_file() else None


def assert_weekly_md_exists(repo_root: Path, end_date: str) -> Path:
    """若缺失则打印 stderr 并以退出码 3 结束进程。"""
    p = check_weekly_md(repo_root, end_date)
    if p is None:
        print(
            "ERROR: 未找到 weekly-report.md，请先执行 generate-report-weekly skill "
            f"生成汇总周报后再发布。\n缺失路径: {weekly_md_path(repo_root, end_date)}",
            file=sys.stderr,
        )
        sys.exit(3)
    return p


def extract_first_h1_from_markdown(text: str) -> str | None:
    """从 Markdown 文本中提取第一个一级标题（``# ...``）的内容。"""
    m = _MD_H1_RE.search(text)
    if not m:
        return None
    return m.group(1).strip() or None


def collect_local_image_refs(text: str, base_dir: Path) -> list[dict[str, str]]:
    """解析 Markdown 中 ``![...](...)`` 的相对路径，返回 ``href`` 与绝对 ``path``（仅文件存在时）。"""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in _MD_IMG_RE.finditer(text):
        raw = (m.group(1) or "").strip()
        if not raw or raw.startswith(("http://", "https://", "data:")):
            continue
        path_part = raw.split("?", 1)[0].strip()
        if not path_part or path_part in seen:
            continue
        seen.add(path_part)
        abs_path = (base_dir / path_part).resolve()
        try:
            abs_path.relative_to(base_dir.resolve())
        except ValueError:
            continue
        if abs_path.is_file():
            out.append({"href": path_part, "path": str(abs_path)})
    return out


class WeeklyMdMissing(FileNotFoundError):
    """``weekly/<end_date>/weekly-report.md`` 不存在。"""


def build_publish_context(repo_root: Path, end_date: str, *, md_path: Path | None = None) -> dict:
    """读取周报 Markdown，抽取标题与本地图片列表。若未传 ``md_path`` 则按周目录解析。"""
    p = md_path or check_weekly_md(repo_root, end_date)
    if p is None:
        raise WeeklyMdMissing(
            str(weekly_md_path(repo_root, end_date)),
        )
    text = p.read_text(encoding="utf-8")
    h1 = extract_first_h1_from_markdown(text)
    wdir = p.parent
    images = collect_local_image_refs(text, wdir)
    return {
        "end_date": end_date,
        "parent_folder_node_id": get_parent_node_id(),
        "parent_alidocs_url": get_parent_alidocs_url(),
        "weekly_md": str(p.resolve()),
        "doc_title": h1,
        "images": images,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="校验 weekly-report.md 存在并输出发布用 JSON（stdout）。",
    )
    parser.add_argument("end_date", metavar="END_DATE", help="周结束日 YYYY-MM-DD（与 weekly/<end_date>/ 一致）")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="仅校验 Markdown 是否存在，不向 stdout 写 JSON",
    )
    args = parser.parse_args()

    try:
        repo = resolve_repo_root(Path(__file__))
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    if args.check_only:
        assert_weekly_md_exists(repo, args.end_date)
        return

    assert_weekly_md_exists(repo, args.end_date)
    ctx = build_publish_context(repo, args.end_date)
    print(json.dumps(ctx, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
