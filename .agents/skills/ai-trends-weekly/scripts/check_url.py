#!/usr/bin/env python3
"""
校验给定 URL 是否已在 archives.json 中出现过。

如果 JSON 解析失败，输出详细错误信息供大模型修复。

用法:
    python3 check_url.py --end-date YYYY-MM-DD <URL>
    python3 check_url.py --end-date YYYY-MM-DD --file urls.txt

返回: 如果 URL 存在输出 FOUND 及文章信息，否则输出 NOT_FOUND。
      JSON 解析失败时输出 ERROR 及详细诊断信息，以非零退出。
"""

import argparse
import json
import sys
from pathlib import Path


def get_archives_path(end_date: str, root_override=None):
    """``weekly/<end_date>/ai-trends/archives.json`` 路径。"""
    if not end_date:
        print("ERROR: end_date is required (YYYY-MM-DD)", file=sys.stderr)
        sys.exit(2)
    if root_override is not None:
        weekly_root = Path(root_override)
    else:
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parents[3]
        weekly_root = repo_root / "weekly"

    archives_path = weekly_root / end_date / "ai-trends" / "archives.json"

    if not archives_path.is_file():
        print(f"ERROR: archives.json not found at {archives_path}", file=sys.stderr)
        print("Run setup_week.py first.", file=sys.stderr)
        sys.exit(2)

    return archives_path


def load_archives(archives_path):
    """加载 archives.json，解析失败时报告详细错误。"""
    raw = archives_path.read_text(encoding="utf-8")

    stripped = raw.strip()
    if not stripped:
        print(f"ERROR: archives.json is empty: {archives_path}", file=sys.stderr)
        sys.exit(3)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed in {archives_path}", file=sys.stderr)
        print(f"  Error: {e.msg}", file=sys.stderr)
        print(f"  Line {e.lineno}, Column {e.colno}", file=sys.stderr)
        lines = raw.splitlines()
        if e.lineno is not None and 1 <= e.lineno <= len(lines):
            error_line = lines[e.lineno - 1]
            print(f"  Problematic line: {error_line.strip()}", file=sys.stderr)
            if e.colno is not None:
                pointer = " " * (e.colno - 1) + "^"
                print(f"  {pointer}", file=sys.stderr)
        pos = e.pos or 0
        context_start = max(0, pos - 80)
        context_end = min(len(raw), pos + 80)
        print(f"  Context: ...{raw[context_start:context_end]}...", file=sys.stderr)
        print("JSON_REPAIR_NEEDED", file=sys.stderr)
        sys.exit(3)

    if not isinstance(data, list):
        print(
            f"ERROR: archives.json root is not an array, got {type(data).__name__}: {archives_path}",
            file=sys.stderr,
        )
        sys.exit(3)

    return data


def check_url(archives, url):
    """检查 URL 是否在 archives 中出现过。"""
    for entry in archives:
        if entry.get("url") == url:
            return entry
    return None


def main():
    parser = argparse.ArgumentParser(
        description="校验给定 URL 是否已在 archives.json 中出现过。",
        epilog="示例:\n"
               "  python3 check_url.py --end-date 2026-05-10 https://example.com/article\n"
               "  python3 check_url.py --end-date 2026-05-10 --file urls.txt\n"
               "如果 JSON 解析失败，输出详细错误信息并标记 JSON_REPAIR_NEEDED。",
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("url", nargs="?", help="要检查的 URL")
    group.add_argument("--file", metavar="FILE", help="包含多个 URL 的文件（每行一个，# 开头为注释）")
    args = parser.parse_args()

    archives_path = get_archives_path(args.end_date, root_override=args.weekly_root)
    archives = load_archives(archives_path)

    if args.file:
        url_file = Path(args.file)
        if not url_file.exists():
            print(f"ERROR: file not found: {url_file}", file=sys.stderr)
            sys.exit(1)
        urls = [
            line.strip()
            for line in url_file.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
    else:
        urls = [args.url]

    for url in urls:
        entry = check_url(archives, url)
        if entry:
            print(f"FOUND: {url}")
            print(f"  Title: {entry.get('cn_title', 'N/A')}")
            print(f"  Date: {entry.get('publish_date', 'N/A')}")
            print(f"  Source: {entry.get('source', 'N/A')}")
        else:
            print(f"NOT_FOUND: {url}")

    sys.exit(0)


if __name__ == "__main__":
    main()
