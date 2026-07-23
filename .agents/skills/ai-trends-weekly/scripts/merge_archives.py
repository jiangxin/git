#!/usr/bin/env python3
"""
将 new.json 中的新文章合并到 archives.json。

流程：
1. 反序列化 new.json 和 archives.json（任一解析失败即报错退出，以便大模型修复）
2. 按 url 去重后追加（可选 --upsert 同 url 更新摘要字段）
3. 写入 archives.json.tmp，成功后原子替换 archives.json
4. 删除 new.json

用法: python3 merge_archives.py --end-date YYYY-MM-DD [--weekly-root PATH] [--upsert]
不指定 --weekly-root 时，通过脚本相对位置推断 repo root 下的 weekly/ 目录。
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))
from json_archives import (  # noqa: F401 — re-exported for tests
    load_json_array,
    merge_by_key,
    merge_by_key_upsert,
    save_json_atomic,
)


def resolve_ai_trends_dir(end_date: str, weekly_root=None):
    """定位 ``weekly/<end_date>/ai-trends/`` 目录。"""
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if weekly_root is None:
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parents[3]
        weekly_root = repo_root / "weekly"
    else:
        weekly_root = Path(weekly_root)

    ai_trends = weekly_root / end_date / "ai-trends"
    if not ai_trends.is_dir():
        print(f"ERROR: ai-trends directory not found: {ai_trends}", file=sys.stderr)
        print("Run setup_week.py first.", file=sys.stderr)
        sys.exit(2)
    return ai_trends


def merge(archives, new_entries, *, upsert: bool = False):
    """将 new_entries 按 url 合并到 archives。

    默认仅追加新 url（兼容）。``upsert=True`` 时同 url 刷新摘要字段。
    返回 ``(merged, added)``；upsert 时 ``added`` 仍为新增条数。
    """
    if upsert:
        merged, added, _updated = merge_by_key_upsert(archives, new_entries, "url")
        return merged, added
    return merge_by_key(archives, new_entries, "url")


def run(end_date: str, weekly_root=None, *, upsert: bool = False):
    """核心流程，供 main() 和测试调用。

    Returns:
        (added_count, total_count) 新增条目数和合并后总条目数
    """
    ai_trends_dir = resolve_ai_trends_dir(end_date, weekly_root)
    archives_path = ai_trends_dir / "archives.json"
    new_path = ai_trends_dir / "new.json"

    if not new_path.exists():
        print(f"ERROR: new.json not found at {new_path}", file=sys.stderr)
        sys.exit(2)

    if not archives_path.exists():
        archives_path.write_text("[]\n", encoding="utf-8")

    archives = load_json_array(archives_path, "archives.json")
    new_entries = load_json_array(new_path, "new.json")

    merged, added = merge(archives, new_entries, upsert=upsert)
    save_json_atomic(merged, archives_path)
    new_path.unlink()

    return added, len(merged)


def main():
    parser = argparse.ArgumentParser(
        description="将 new.json 合并到 archives.json（去重、原子写入、清理 new.json）。",
        epilog="示例: python3 merge_archives.py --end-date 2026-05-10",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--end-date",
        metavar="END_DATE",
        required=True,
        help="周目录名 YYYY-MM-DD（与 setup_week 输出的 end_date 一致）",
    )
    parser.add_argument(
        "--weekly-root",
        metavar="PATH",
        default=None,
        help="覆盖 weekly 目录路径（默认自动推断）",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="同 url 时更新摘要字段（en_summary/cn_*/rank_hint/collected_at 等）",
    )
    args = parser.parse_args()

    added, total = run(args.end_date, weekly_root=args.weekly_root, upsert=args.upsert)
    print(f"MERGED: {added} new entries added, {total} total in archives.json")


if __name__ == "__main__":
    main()
