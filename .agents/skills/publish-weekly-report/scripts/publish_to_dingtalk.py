#!/usr/bin/env python3
"""
将 weekly/<end_date>/ 周报发布到钉钉文档：配图内联进 Markdown（默认）、
list/create 目标文档、写入正文。

**传输方式**（二选一，自动选择）：
- 若存在 ``~/.dingtalk-doc-rw/servers.json`` 且可解析出 MCP 服务器，则优先走 **钉钉文档 MCP**
  （与 ``dingtalk_doc_patched.py`` 一致：网关 URL + key，无 dws PAT）。
- 否则走 **dws** + ``dws_pat_bypass.sh``（需 Wukong / PAT 授权）。

默认将本地配图编码为 data URI 写入 ``![](...)``；
若正文过大超过 MCP ``update_document`` 限制，则自动切换为 **文档附件上传** 模式：
通过 MCP ``get_doc_attachment_upload_info`` 将每张图上传为文档附件，
获得永久 ``resourceUrl`` 后嵌入 ``![](resourceUrl)``，不创建独立文件节点。

依赖：MCP 路径需 ``pip install requests``；dws 路径需本机可执行 ``dws``。
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
from pathlib import Path

import requests as _requests_lib

import dingtalk_doc_mcp
from publish_prep import (
    assert_weekly_md_exists,
    build_publish_context,
    get_parent_node_id,
    resolve_repo_root,
)


def parse_first_json_object(stdout: str) -> dict:
    """从 dws 混有日志的标准输出中解析第一个顶层 JSON 对象。"""
    s = stdout or ""
    i = s.find("{")
    if i < 0:
        raise ValueError("stdout 中未找到 JSON 对象")
    decoder = json.JSONDecoder()
    obj, _end = decoder.raw_decode(s[i:])
    if not isinstance(obj, dict):
        raise ValueError("解析结果不是 JSON 对象")
    return obj


def iter_folder_nodes(list_payload: dict) -> list[dict]:
    """从 ``doc list --format json`` 的多种返回形态中取出节点 dict 列表。"""
    candidates: list[object] = []
    for key in ("nodes", "result", "data", "items"):
        v = list_payload.get(key)
        if isinstance(v, list):
            candidates = v
            break
        if isinstance(v, dict):
            inner = v.get("nodes") or v.get("list")
            if isinstance(inner, list):
                candidates = inner
                break
    return [x for x in candidates if isinstance(x, dict)]


def find_weekly_doc_node_id(list_payload: dict, end_date: str) -> str | None:
    """在父文件夹下列表中查找标题含 ``【end_date}】`` 的文档节点 ID。"""
    needle = f"【{end_date}】"
    for node in iter_folder_nodes(list_payload):
        title = (
            node.get("name")
            or node.get("title")
            or node.get("fileName")
            or node.get("displayName")
            or ""
        )
        if needle in str(title):
            nid = node.get("nodeId") or node.get("dentryUuid") or node.get("id")
            if nid:
                return str(nid)
    return None


def extract_upload_public_url(upload_json: dict) -> str | None:
    """从 ``doc upload --format json`` 返回体中取可嵌入 ``![](...)`` 的 HTTPS 链接。

    优先 ``downloadUrl`` / ``url``（多为直链图片），避免使用 ``docUrl``（常为文档预览页，
    在 Markdown 图片语法中无法当作图片渲染）。
    """
    for key in ("downloadUrl", "url", "fileUrl", "docUrl"):
        v = upload_json.get(key)
        if isinstance(v, str) and v.startswith("https://"):
            return v
    return None


def find_named_folder_node_id(list_payload: dict, name: str) -> str | None:
    """在 ``doc list`` 结果中按名称查找文件夹节点 ID。"""
    for node in iter_folder_nodes(list_payload):
        if str(node.get("name") or "") != name:
            continue
        if str(node.get("nodeType") or "").lower() != "folder":
            continue
        nid = node.get("nodeId") or node.get("dentryUuid") or node.get("id")
        if nid:
            return str(nid)
    return None


def ensure_assets_subfolder_node(dws: Path, parent: str, end_date: str) -> str:
    """在 ``parent`` 下创建或复用 ``周报配图-<end_date>`` 子文件夹（仅 ``--upload-images`` 使用）。

    名称刻意不使用 ``【end_date】``，避免与 ``find_weekly_doc_node_id`` 的标题匹配冲突。
    """
    folder_name = f"周报配图-{end_date}"
    listed = run_dws(
        dws,
        ["doc", "list", "--folder", parent, "--format", "json"],
    )
    existing = find_named_folder_node_id(listed, folder_name)
    if existing:
        return existing
    created = run_dws(
        dws,
        [
            "doc",
            "folder",
            "create",
            "--name",
            folder_name,
            "--folder",
            parent,
            "--format",
            "json",
        ],
    )
    nid = str(created.get("nodeId") or created.get("dentryUuid") or created.get("id") or "")
    if not nid:
        print(json.dumps(created, ensure_ascii=False, indent=2), file=sys.stderr)
        print("ERROR: doc folder create 未返回 nodeId", file=sys.stderr)
        raise SystemExit(4)
    return nid


def build_href_to_data_uri_map(images: list[dict[str, str]]) -> dict[str, str]:
    """将本地配图读入为 ``data:image/...;base64,...``，供 Markdown 内联、不产生钉钉空间文件节点。"""
    out: dict[str, str] = {}
    for img in images:
        href = (img.get("href") or "").strip()
        path_str = img.get("path") or ""
        if not href or not path_str:
            continue
        path = Path(path_str)
        if not path.is_file():
            raise ValueError(f"图片路径无效或不存在: {path_str!r}")
        mime, _ = mimetypes.guess_type(str(path))
        if not mime or not mime.startswith("image/"):
            mime = "image/png"
        raw = path.read_bytes()
        b64 = base64.standard_b64encode(raw).decode("ascii")
        out[href] = f"data:{mime};base64,{b64}"
    return out


def build_href_to_url_map(
    images: list[dict[str, str]],
    upload_results: list[dict],
) -> dict[str, str]:
    """
    将 ``publish_prep`` 的 ``images`` 与按序上传返回的 JSON 列表对齐，得到 href -> URL。

    ``upload_results`` 须与 ``images`` 等长且顺序一致。
    """
    if len(images) != len(upload_results):
        raise ValueError("images 与 upload_results 长度不一致")
    out: dict[str, str] = {}
    for img, uj in zip(images, upload_results, strict=True):
        href = (img.get("href") or "").strip()
        if not href:
            continue
        url = extract_upload_public_url(uj)
        if not url:
            raise ValueError(f"上传结果缺少 HTTPS URL 字段: {uj!r}")
        out[href] = url
    return out


def replace_markdown_image_hrefs(markdown: str, href_to_url: dict[str, str]) -> str:
    """将 Markdown 正文中出现的相对 ``href`` 整段替换为对应 URL（子串替换）。"""
    text = markdown
    # 较长 href 先替换，避免 token-metrics/foo 与 token-metrics/foobar 歧义（当前无此例）
    for href in sorted(href_to_url, key=len, reverse=True):
        text = text.replace(href, href_to_url[href])
    return text


# 与 generate-report-weekly/assets/trailer.md 中「源码」链接一致；``<end-date>`` 由周目录替换。
_WEEKLY_REPORT_REPO_URL_TEMPLATE = (
    "https://code.alibaba-inc.com/AI-coding-workshop/ai-coding-weekly-report/"
    "blob/master/weekly/<end-date>/weekly-report.md"
)

_DETAILS_BLOCK = re.compile(
    r"<details\b[^>]*>(?P<body>.*?)</details>",
    re.IGNORECASE | re.DOTALL,
)
_SUMMARY_TAG = re.compile(
    r"<summary\b[^>]*>(?P<text>.*?)</summary>",
    re.IGNORECASE | re.DOTALL,
)


def weekly_report_repo_url(end_date: str) -> str:
    """仓库内该周 ``weekly-report.md`` 的 code.alibaba-inc.com 浏览 URL。"""
    return _WEEKLY_REPORT_REPO_URL_TEMPLATE.replace("<end-date>", end_date).replace(
        "<end_date>", end_date
    )


def _strip_html_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment or "")


def _escape_markdown_link_label(label: str) -> str:
    """避免 ``label`` 中的 ``[`` / ``]`` / ``\\`` 破坏 ``[...](...)`` 解析。"""
    return (
        (label or "")
        .replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def flatten_details_to_weekly_repo_links(markdown: str, end_date: str) -> str:
    """上传钉钉前：去掉 ``<details>`` 内折叠正文，将 ``<summary>`` 转为指向仓库该周 ``weekly-report.md`` 的 Markdown 链接（与 trailer 中源码 URL 规则一致）。"""
    url = weekly_report_repo_url(end_date)

    def repl(m: re.Match[str]) -> str:
        body = m.group("body") or ""
        sm = _SUMMARY_TAG.search(body)
        if sm:
            raw_label = _strip_html_tags(sm.group("text"))
            label = " ".join(raw_label.split()).strip() or "查看完整内容"
        else:
            label = "查看完整内容"
        return f"[{_escape_markdown_link_label(label)}]({url})"

    return _DETAILS_BLOCK.sub(repl, markdown)


_ATX_FIRST_LINE = re.compile(r"^#{1,6}\s+(.+?)\s*(?:#+\s*)?$")


def _normalize_report_title(text: str) -> str:
    """用于比对「钉钉文档标题」与 Markdown 首行标题是否同义（折叠空白）。

    另将 ``】`` 后的空白去掉，避免 HTML 与 Markdown 在「日期括号」与英文间多空格不一致。
    """
    s = " ".join((text or "").split())
    s = re.sub(r"】\s+", "】", s)
    return s


def strip_leading_duplicate_doc_title(markdown: str, doc_title: str | None) -> str:
    """若正文开头的一级标题与 ``doc_title`` 相同，则去掉该行及后随的一行空行。

    钉钉在 create/update 时已用 ``name``/文档标题展示报告名，正文中再保留 ``# 标题`` 会重复。
    """
    if not doc_title or not str(doc_title).strip():
        return markdown
    want = _normalize_report_title(str(doc_title))
    if not want:
        return markdown

    text = markdown.removeprefix("﻿")
    lines = text.splitlines(True)
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return markdown

    first_stripped = lines[i].strip()
    m = _ATX_FIRST_LINE.match(first_stripped)
    if m:
        got = _normalize_report_title(m.group(1))
        if got != want:
            return markdown
    else:
        if _normalize_report_title(first_stripped) != want:
            return markdown

    new_lines = lines[:i] + lines[i + 1 :]
    j = i
    if j < len(new_lines) and not new_lines[j].strip():
        new_lines = new_lines[:j] + new_lines[j + 1 :]
    return "".join(new_lines)


def default_dws_path() -> Path:
    return Path.home() / ".real" / ".bin" / "dws" / "bin" / "dws"


def default_bypass_path(repo_root: Path) -> Path:
    candidates = [
        repo_root / ".agents" / "skills" / "dingtalk-dws" / "scripts" / "dws_pat_bypass.sh",
        repo_root / ".claude" / "skills" / "dingtalk-dws" / "scripts" / "dws_pat_bypass.sh",
    ]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return candidates[0].resolve()


def default_mcp_config_path() -> Path:
    return dingtalk_doc_mcp.DEFAULT_CONFIG_PATH


# MCP update_document 字符上限（超出此限制时 ``update_document`` 会静默返回
# ``success: false, errorMessage: ""`` 或返回明确的长度错误。
# 实测上限为 10,000 字符，超过时报 ``Maximum allowed length is 10000``。
MCP_UPDATE_CHAR_LIMIT = 10_000


def estimate_body_size(*, markdown: str, images: list[dict[str, str]]) -> int:
    """估算将图片内联为 data URI 后 Markdown 正文的总字符数。

    用于在发布前判断是否需要切换为附件上传模式。
    """
    size = len(markdown)
    for img in images:
        path_str = img.get("path") or ""
        if not path_str:
            continue
        p = Path(path_str)
        if not p.is_file():
            continue
        raw_bytes = p.stat().st_size
        b64_chars = (raw_bytes + 2) // 3 * 4
        mime, _ = mimetypes.guess_type(str(p))
        if not mime or not mime.startswith("image/"):
            mime = "image/png"
        size += len(f"data:{mime};base64,") + b64_chars
    return size


def upload_image_as_doc_attachment(
    servers: list[dict[str, str]],
    *,
    node_id: str,
    file_path: Path,
    timeout: int = 120,
) -> dict[str, str]:
    """将单张本地图片上传为钉钉文档附件。

    返回 ``{"resource_id": "...", "resource_url": "...", "mime": "..."}``。

    - ``resource_id``：UUID，用于 ``insert_document_block`` 的 ``attachment.resourceId``。
    - ``resource_url``：完整 HTTPS 链接（拼接自 ``/core/api/resources/img/...``）。
    """
    mime, _ = mimetypes.guess_type(str(file_path))
    if not mime or not mime.startswith("image/"):
        mime = "image/png"
    file_size = file_path.stat().st_size
    file_name = file_path.name

    upload_info = dingtalk_doc_mcp.try_all_servers(
        servers,
        "get_doc_attachment_upload_info",
        {
            "nodeId": node_id,
            "fileName": file_name,
            "fileSize": file_size,
            "mimeType": mime,
        },
        timeout=timeout,
    )
    if not upload_info.get("success"):
        raise RuntimeError(
            f"get_doc_attachment_upload_info 失败: {upload_info.get('errorMsg', '未知错误')}"
        )

    upload_url = upload_info.get("uploadUrl", "")
    if not upload_url:
        raise RuntimeError(
            f"get_doc_attachment_upload_info 未返回 uploadUrl: {json.dumps(upload_info, ensure_ascii=False)}"
        )

    resource_id = upload_info.get("resourceId", "")
    if not resource_id:
        raise RuntimeError(
            f"get_doc_attachment_upload_info 未返回 resourceId: {json.dumps(upload_info, ensure_ascii=False)}"
        )

    resource_url = upload_info.get("resourceUrl", "")

    resp = _requests_lib.put(
        upload_url,
        data=file_path.read_bytes(),
        headers={"Content-Type": mime},
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OSS PUT 上传失败: HTTP {resp.status_code}, body={resp.text[:200]}")

    if resource_url and not resource_url.startswith(("http://", "https://")):
        resource_url = f"https://alidocs.dingtalk.com{resource_url}"

    return {"resource_id": resource_id, "resource_url": resource_url or "", "mime": mime}


def split_markdown_chunks(markdown: str, limit: int = MCP_UPDATE_CHAR_LIMIT) -> list[str]:
    """将 Markdown 按行边界拆分为多个 chunk，每个不超过 ``limit`` 字符。

    用于 ``update_document`` 的 10k 字符上限：首个 chunk 以 ``overwrite`` 写入，
    后续 chunk 以 ``append`` 追加。
    """
    if len(markdown) <= limit:
        return [markdown]

    lines = markdown.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_with_nl = len(line) + 1
        if current_len + line_with_nl > limit and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_with_nl
        else:
            current.append(line)
            current_len += line_with_nl

    if current:
        chunks.append("\n".join(current))

    return chunks


_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def split_at_local_images(
    markdown: str,
    local_hrefs: set[str],
) -> list[str | tuple[str, str]]:
    """将 Markdown 在本地配图位置拆分为交替的 ``[text, (alt, href), text, ...]`` 列表。

    仅在 ``href`` 属于 ``local_hrefs`` 的图片处拆分；外部图片保留在文本段中。
    返回列表首尾元素始终是 ``str``（可能为空串）。
    """
    result: list[str | tuple[str, str]] = []
    last_end = 0
    for m in _MD_IMAGE_RE.finditer(markdown):
        alt, href = m.group(1), m.group(2)
        if href not in local_hrefs:
            continue
        result.append(markdown[last_end:m.start()])
        result.append((alt, href))
        last_end = m.end()
    result.append(markdown[last_end:])
    return result


def _mcp_insert_image_block(
    servers: list[dict[str, str]],
    *,
    node_id: str,
    resource_id: str,
    file_name: str,
    mime_type: str = "image/png",
    timeout: int = 60,
) -> dict:
    """通过 ``insert_document_block`` 将已上传的图片附件插入文档末尾（``viewType: preview``）。

    ``resource_id`` 来自 ``get_doc_attachment_upload_info`` 返回的 UUID。
    """
    element = {
        "blockType": "attachment",
        "attachment": {
            "resourceId": resource_id,
            "name": file_name,
            "type": mime_type,
            "viewType": "preview",
        },
    }
    return dingtalk_doc_mcp.try_all_servers(
        servers,
        "insert_document_block",
        {"nodeId": node_id, "element": element},
        timeout=timeout,
    )


def resolve_transport(
    *,
    use_dws: bool,
    use_mcp: bool,
    mcp_servers: list[dict[str, str]],
) -> str:
    """返回 ``"mcp"`` 或 ``"dws"``。"""
    if use_dws:
        return "dws"
    if use_mcp:
        return "mcp"
    return "mcp" if mcp_servers else "dws"


def run_dws(
    dws: Path,
    args: list[str],
    *,
    timeout: int = 180,
) -> dict:
    r = subprocess.run(
        [str(dws)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (r.stdout or "") + (r.stderr or "")
    try:
        parsed = parse_first_json_object(out)
    except ValueError:
        print(out, file=sys.stderr)
        raise SystemExit(4) from None
    if parsed.get("success") is False:
        print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
        code = str(parsed.get("code") or "")
        if "PAT_" in code:
            raise SystemExit(5)
        raise SystemExit(4)
    if r.returncode != 0:
        print(out, file=sys.stderr)
        raise SystemExit(4)
    return parsed


def run_bypass_update(
    bypass: Path,
    dws: Path,
    *,
    node: str,
    markdown: str,
    timeout: int = 300,
) -> dict:
    env = os.environ.copy()
    env["DWS"] = str(dws)
    r = subprocess.run(
        [
            "bash",
            str(bypass),
            "doc",
            "update",
            "--node",
            node,
            "--markdown",
            markdown,
            "--mode",
            "overwrite",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    raw = (r.stdout or "").strip()
    if r.returncode != 0:
        print(r.stderr or "", file=sys.stderr)
        print(raw, file=sys.stderr)
        raise SystemExit(4)
    try:
        parsed = parse_first_json_object(raw)
    except ValueError:
        print(raw, file=sys.stderr)
        raise SystemExit(4) from None
    if parsed.get("success") is False:
        code = str(parsed.get("code") or "")
        print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
        if "PAT_" in code:
            raise SystemExit(5)
        raise SystemExit(4)
    return parsed


def _find_or_create_node(
    *,
    transport: str,
    mcp_servers: list[dict[str, str]],
    dws: Path,
    bypass: Path,
    parent: str,
    doc_title: str,
    end_date: str,
    node_hint: str,
    dry_run: bool,
) -> str:
    """查找或创建钉钉文档节点，返回 nodeId。"""
    node = (node_hint or "").strip()

    if transport == "mcp":
        if not node:
            listed_nodes = dingtalk_doc_mcp.mcp_list_all_nodes(mcp_servers, parent)
            payload = {"nodes": listed_nodes, "hasMore": False}
            node = find_weekly_doc_node_id(payload, end_date) or ""
        if not node:
            if dry_run:
                print("[dry-run] 将创建新文档", file=sys.stderr)
                return ""
            created = dingtalk_doc_mcp.mcp_create_document(
                mcp_servers,
                name=doc_title,
                folder_id=parent,
                markdown="",
            )
            node = dingtalk_doc_mcp.extract_node_id_from_doc_result(created)
            if not node:
                print(json.dumps(created, ensure_ascii=False, indent=2), file=sys.stderr)
                print("ERROR: MCP create_document 未返回 nodeId", file=sys.stderr)
                raise SystemExit(4)
    else:
        if not node:
            listed = run_dws(
                dws,
                ["doc", "list", "--folder", parent, "--format", "json"],
            )
            node = find_weekly_doc_node_id(listed, end_date) or ""
        if not node:
            if dry_run:
                print("[dry-run] 将创建新文档", file=sys.stderr)
                return ""
            created = run_dws(
                dws,
                [
                    "doc",
                    "create",
                    "--name",
                    doc_title,
                    "--folder",
                    parent,
                    "--format",
                    "json",
                ],
            )
            node = str(created.get("nodeId") or created.get("dentryUuid") or "")
            if not node:
                print(json.dumps(created, ensure_ascii=False, indent=2), file=sys.stderr)
                print("ERROR: doc create 未返回 nodeId", file=sys.stderr)
                raise SystemExit(4)
    return node


def main() -> None:
    parser = argparse.ArgumentParser(
        description="上传周报配图并创建/更新钉钉文档（Markdown 覆盖写入）。",
    )
    parser.add_argument(
        "end_date",
        metavar="END_DATE",
        help="周结束日 YYYY-MM-DD，对应 weekly/<END_DATE>/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印计划（JSON），不调用 dws",
    )
    parser.add_argument(
        "--node",
        metavar="NODE_ID",
        default="",
        help="已有文档节点 ID：跳过 list/create，直接对该节点 overwrite（便于 PAT 重试）",
    )
    parser.add_argument(
        "--dws",
        dest="dws_path",
        default="",
        help="dws 可执行文件路径（默认 ~/.real/.bin/dws/bin/dws）",
    )
    parser.add_argument(
        "--use-dws",
        action="store_true",
        help="强制使用 dws（忽略 ~/.dingtalk-doc-rw/servers.json 的 MCP）",
    )
    parser.add_argument(
        "--use-mcp",
        action="store_true",
        help="强制使用钉钉文档 MCP（须存在有效的 ~/.dingtalk-doc-rw/servers.json）",
    )
    parser.add_argument(
        "--mcp-config",
        dest="mcp_config_path",
        default="",
        help="MCP 配置文件路径（默认 ~/.dingtalk-doc-rw/servers.json）",
    )
    parser.add_argument(
        "--upload-images",
        action="store_true",
        help=(
            "强制将配图上传为文档附件（通过 MCP ``get_doc_attachment_upload_info``），"
            "以永久 ``resourceUrl`` 嵌入 ``![](...)``。"
            "默认在正文超 MCP 限制时自动触发。"
        ),
    )
    args = parser.parse_args()

    try:
        repo = resolve_repo_root(Path(__file__))
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2) from e

    assert_weekly_md_exists(repo, args.end_date)
    ctx = build_publish_context(repo, args.end_date)
    md_path_str = ctx.get("weekly_md")
    if not md_path_str:
        print(
            "ERROR: 未找到 weekly-report.md，无法以 Markdown 写入钉钉。\n"
            f"路径: {repo / 'weekly' / args.end_date / 'weekly-report.md'}",
            file=sys.stderr,
        )
        raise SystemExit(3)
    md_path = Path(md_path_str)
    doc_title = ctx.get("doc_title") or f"【{args.end_date}】云原生 AI Native 组织度量周报"
    images: list[dict[str, str]] = ctx.get("images") or []

    mcp_cfg = Path(args.mcp_config_path) if args.mcp_config_path else default_mcp_config_path()
    mcp_servers: list[dict[str, str]] = []
    if mcp_cfg.is_file():
        try:
            mcp_servers = dingtalk_doc_mcp.load_mcp_servers(mcp_cfg)
        except (dingtalk_doc_mcp.DingMCPError, json.JSONDecodeError, OSError, ValueError) as e:
            print(
                f"WARN: 无法读取 MCP 配置 {mcp_cfg}，将回退 dws: {e}",
                file=sys.stderr,
            )
            mcp_servers = []
    elif args.use_mcp:
        print(
            f"ERROR: --use-mcp 但未找到配置文件: {mcp_cfg}",
            file=sys.stderr,
        )
        raise SystemExit(2)

    transport = resolve_transport(
        use_dws=bool(args.use_dws),
        use_mcp=bool(args.use_mcp),
        mcp_servers=mcp_servers,
    )
    if transport == "mcp" and not mcp_servers:
        print(
            f"ERROR: 当前为 MCP 模式但未加载到任何服务器（检查 {mcp_cfg}，或改用 --use-dws）。",
            file=sys.stderr,
        )
        raise SystemExit(2)

    dws = Path(args.dws_path) if args.dws_path else default_dws_path()
    bypass = default_bypass_path(repo)

    parent = get_parent_node_id()
    markdown_src = md_path.read_text(encoding="utf-8")
    markdown_src = strip_leading_duplicate_doc_title(markdown_src, doc_title)
    markdown_src = flatten_details_to_weekly_repo_links(markdown_src, args.end_date)

    # 配图上传模式：当正文超 MCP 限制或显式 --upload-images 时启用。
    # 通过 MCP ``get_doc_attachment_upload_info`` 将图片上传为文档附件，
    # 获得永久 ``resourceUrl`` 后嵌入 ``![](resourceUrl)``，不创建独立文件节点。
    upload_images = bool(args.upload_images)
    if transport == "mcp" and images and not upload_images:
        estimated = estimate_body_size(markdown=markdown_src, images=images)
        if estimated > MCP_UPDATE_CHAR_LIMIT:
            upload_images = True
            print(
                f"WARN: 估算正文 {estimated:,} 字符超过 MCP 限制（{MCP_UPDATE_CHAR_LIMIT:,}），"
                f"自动切换为文档附件上传模式。",
                file=sys.stderr,
            )

    if transport == "dws":
        if not args.dry_run and (not dws.is_file() or not os.access(dws, os.X_OK)):
            print(f"ERROR: 未找到或可执行的 dws: {dws}", file=sys.stderr)
            raise SystemExit(2)
        if not args.dry_run and not bypass.is_file():
            print(f"ERROR: 未找到 dws_pat_bypass.sh: {bypass}", file=sys.stderr)
            raise SystemExit(2)

    if args.dry_run:
        plan = {
            "end_date": args.end_date,
            "parent_folder_node_id": parent,
            "doc_title": doc_title,
            "weekly_md": str(md_path),
            "image_count": len(images),
            "images": images,
            "existing_node": (args.node or None),
            "upload_images": upload_images,
            "transport": transport,
            "mcp_config": str(mcp_cfg) if mcp_cfg.is_file() else None,
            "dry_run": True,
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return

    # 确定目标文档节点（配图上传需要 nodeId）
    node = _find_or_create_node(
        transport=transport,
        mcp_servers=mcp_servers,
        dws=dws,
        bypass=bypass,
        parent=parent,
        doc_title=doc_title,
        end_date=args.end_date,
        node_hint=args.node,
        dry_run=args.dry_run,
    )

    # 写入钉钉文档
    result: dict = {}
    image_upload_method = "text_only"

    if transport == "mcp" and upload_images and images and mcp_servers:
        # ── MCP + 文档附件上传 ──
        # overwrite 会清空文档（含图片），所以必须：
        #   1. 先 overwrite 纯文本（无图片引用）
        #   2. 逐张上传图片（overwrite 之后才不会被清空）
        #   3. 用 insert_document_block 将图片插入文档
        #   4. 用 append 追加后续文本
        # 这样图片和文本交替写入，保持原始位置。
        image_upload_method = "doc_attachment"
        local_hrefs = {(img.get("href") or "").strip() for img in images} - {""}
        href_to_img = {}
        for img in images:
            h = (img.get("href") or "").strip()
            if h:
                href_to_img[h] = img

        segments = split_at_local_images(markdown_src, local_hrefs)
        try:
            # Step 1: overwrite 第一段文本（图片之前的所有内容）
            first_text = segments[0] if isinstance(segments[0], str) else ""
            chunks = split_markdown_chunks(first_text, MCP_UPDATE_CHAR_LIMIT)
            result = dingtalk_doc_mcp.mcp_update_document(
                mcp_servers, node_id_or_url=node,
                markdown=chunks[0], mode="overwrite",
            )
            for chunk in chunks[1:]:
                dingtalk_doc_mcp.mcp_update_document(
                    mcp_servers, node_id_or_url=node,
                    markdown=chunk, mode="append",
                )

            # Step 2: 逐个处理 (image, text) 对
            img_count = 0
            for seg in segments[1:]:
                if isinstance(seg, tuple):
                    alt, href = seg
                    img_info = href_to_img.get(href)
                    if not img_info:
                        continue
                    img_path = Path(img_info.get("path") or "")
                    if not img_path.is_file():
                        print(f"ERROR: 图片路径无效: {img_info!r}", file=sys.stderr)
                        raise SystemExit(3)
                    upload_result = upload_image_as_doc_attachment(
                        mcp_servers, node_id=node, file_path=img_path,
                    )
                    _mcp_insert_image_block(
                        mcp_servers, node_id=node,
                        resource_id=upload_result["resource_id"],
                        file_name=img_path.name,
                        mime_type=upload_result["mime"],
                    )
                    img_count += 1
                    print(
                        f"  [{img_count}/{len(local_hrefs)}] {href} -> 已插入",
                        file=sys.stderr,
                    )
                else:
                    # 文本段：append
                    text_seg = seg
                    if not text_seg.strip():
                        continue
                    for chunk in split_markdown_chunks(text_seg, MCP_UPDATE_CHAR_LIMIT):
                        dingtalk_doc_mcp.mcp_update_document(
                            mcp_servers, node_id_or_url=node,
                            markdown=chunk, mode="append",
                        )

            dingtalk_doc_mcp.mcp_rename_document(
                mcp_servers, node_id_or_url=node, new_name=doc_title,
            )
        except dingtalk_doc_mcp.DingMCPError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            raise SystemExit(4) from e

    elif transport == "mcp":
        # ── MCP 内联模式（base64 data URI 或无图片）──
        image_upload_method = "base64_inline" if images else "text_only"
        if images:
            try:
                href_map = build_href_to_data_uri_map(images)
            except ValueError as e:
                print(f"ERROR: {e}", file=sys.stderr)
                raise SystemExit(3) from e
            body = replace_markdown_image_hrefs(markdown_src, href_map)
        else:
            body = markdown_src

        try:
            chunks = split_markdown_chunks(body, MCP_UPDATE_CHAR_LIMIT)
            if len(chunks) > 1:
                print(
                    f"INFO: 正文 {len(body):,} 字符，拆分为 {len(chunks)} 段写入。",
                    file=sys.stderr,
                )
            result = dingtalk_doc_mcp.mcp_update_document(
                mcp_servers, node_id_or_url=node,
                markdown=chunks[0], mode="overwrite",
            )
            for i, chunk in enumerate(chunks[1:], 2):
                dingtalk_doc_mcp.mcp_update_document(
                    mcp_servers, node_id_or_url=node,
                    markdown=chunk, mode="append",
                )
                print(f"  已追加第 {i}/{len(chunks)} 段（{len(chunk):,} 字符）", file=sys.stderr)
            dingtalk_doc_mcp.mcp_rename_document(
                mcp_servers, node_id_or_url=node, new_name=doc_title,
            )
        except dingtalk_doc_mcp.DingMCPError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            raise SystemExit(4) from e

    else:
        # ── dws 路径 ──
        if images and upload_images:
            image_upload_method = "dws_upload"
            assets_folder = ensure_assets_subfolder_node(dws, parent, args.end_date)
            upload_jsons: list[dict] = []
            for img in images:
                path = img.get("path") or ""
                if not path or not Path(path).is_file():
                    print(f"ERROR: 图片路径无效: {img!r}", file=sys.stderr)
                    raise SystemExit(3)
                uj = run_dws(
                    dws,
                    ["doc", "upload", "--file", path, "--folder", assets_folder, "--format", "json"],
                    timeout=240,
                )
                if not uj.get("success", True):
                    print(json.dumps(uj, ensure_ascii=False, indent=2), file=sys.stderr)
                    raise SystemExit(4)
                upload_jsons.append(uj)
            href_map: dict[str, str] = {}
            for img_uj in zip(images, upload_jsons, strict=True):
                href = (img_uj[0].get("href") or "").strip()
                if href:
                    url = extract_upload_public_url(img_uj[1]) or ""
                    if url:
                        href_map[href] = url
            if len(href_map) < len(images):
                print("WARN: dws doc upload 未返回所有图片的可用 URL，回退 base64 内联。", file=sys.stderr)
                href_map = build_href_to_data_uri_map(images)
        elif images:
            image_upload_method = "base64_inline"
            try:
                href_map = build_href_to_data_uri_map(images)
            except ValueError as e:
                print(f"ERROR: {e}", file=sys.stderr)
                raise SystemExit(3) from e
        else:
            href_map = {}

        body = replace_markdown_image_hrefs(markdown_src, href_map)
        result = run_bypass_update(bypass, dws, node=node, markdown=body)
        if mcp_servers:
            try:
                dingtalk_doc_mcp.mcp_rename_document(
                    mcp_servers, node_id_or_url=node, new_name=doc_title,
                )
            except dingtalk_doc_mcp.DingMCPError as e:
                print(f"WARN: rename via MCP failed: {e}", file=sys.stderr)

    out = {
        "nodeId": node,
        "doc_url": f"https://alidocs.dingtalk.com/i/nodes/{node}",
        "transport": transport,
        "image_upload_method": image_upload_method,
        "update": result,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
