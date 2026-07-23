"""钉钉文档 MCP 客户端（与仓库根 dingtalk_doc_patched 逻辑对齐）。

配置文件：**~/.dingtalk-doc-rw/servers.json**（`mcp_servers` 数组）。

兼容常见手写格式：
- ``{"url": "https://mcp-gw.../server/<id>", "key": "..."}``（url 不含 query）
- ``{"base_url": "https://...", "key": "..."}``
- ``{"url": "https://.../server/<id>?key=...", ...}``（完整 MCP 地址，与 setup 写入一致）

依赖：``requests``（与 dingtalk-doc-rw skill 一致）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

MCP_PROTOCOL_VERSION = "2024-11-05"
DEFAULT_CONFIG_PATH = Path.home() / ".dingtalk-doc-rw" / "servers.json"
_NODE_ID_RE = re.compile(r"/nodes/([a-zA-Z0-9]+)")


class DingMCPError(Exception):
    """钉钉 MCP API 错误。"""

    def __init__(self, message: str, details=None):
        self.details = details
        super().__init__(message)


def _parse_mcp_url(mcp_url: str) -> dict[str, str]:
    """从完整 MCP URL 解析 ``base_url``、``server_id``、``key``。"""
    parsed = urlparse(mcp_url)
    qs = parse_qs(parsed.query)
    key = qs.get("key", [None])[0]
    if not key:
        raise ValueError(
            f"MCP URL 中缺少 key 参数: {mcp_url}\n"
            "正确格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
        )
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2 or path_parts[0] != "server":
        raise ValueError(
            f"MCP URL 路径格式不正确: {parsed.path}\n"
            "正确格式: https://mcp-gw.dingtalk.com/server/<server_id>?key=<api_key>"
        )
    server_id = path_parts[1]
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return {"base_url": base_url, "server_id": server_id, "key": key}


def normalize_mcp_server_entry(raw: dict) -> dict[str, str]:
    """将 ``servers.json`` 中的单条记录规范为 ``_mcp_call`` 所需字段。"""
    if not isinstance(raw, dict):
        raise ValueError(f"服务器配置须为对象: {raw!r}")
    name = str(raw.get("name") or "default")

    if raw.get("base_url") and raw.get("key"):
        base = str(raw["base_url"]).split("?", 1)[0].rstrip("/")
        return {"name": name, "base_url": base, "key": str(raw["key"])}

    url = (raw.get("url") or raw.get("mcp_url") or "").strip()
    key_field = raw.get("key")

    if url:
        qs = parse_qs(urlparse(url).query)
        if qs.get("key", [None])[0]:
            parsed = _parse_mcp_url(url.split("#", 1)[0])
            return {"name": name, "base_url": parsed["base_url"].rstrip("/"), "key": parsed["key"]}

    if url and key_field:
        base = url.split("?", 1)[0].rstrip("/")
        return {"name": name, "base_url": base, "key": str(key_field)}

    raise ValueError(
        "无法解析 MCP 服务器项，需要 ``base_url``+``key`` 或 ``url``+``key`` 或带 ``?key=`` 的完整 MCP URL。\n"
        f"当前项: {raw!r}"
    )


def load_mcp_servers(config_path: Path | None = None) -> list[dict[str, str]]:
    """读取并规范化 ``~/.dingtalk-doc-rw/servers.json`` 中的服务器列表。"""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    servers = data.get("mcp_servers", [])
    if not isinstance(servers, list):
        return []
    out: list[dict[str, str]] = []
    for i, item in enumerate(servers):
        try:
            out.append(normalize_mcp_server_entry(item))
        except ValueError as e:
            raise DingMCPError(f"servers.json 第 {i + 1} 条无效: {e}") from e
    return out


def _get_headers() -> dict[str, str]:
    return {"Content-Type": "application/json", "Accept": "application/json"}


def _mcp_call(server: dict, method: str, params: dict, request_id: int = 1, timeout: int = 60) -> dict:
    if requests is None:
        raise DingMCPError("缺少依赖 requests，请执行: pip install requests")
    url = f"{server['base_url']}?key={server['key']}"
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    response = requests.post(url, headers=_get_headers(), json=payload, timeout=timeout)
    if not response.ok:
        raise DingMCPError(
            f"HTTP {response.status_code}: {response.text}",
            details={"status_code": response.status_code},
        )
    data = response.json()
    if "error" in data:
        err = data["error"]
        raise DingMCPError(
            f"MCP Error {err.get('code')}: {err.get('message')}",
            details=err,
        )
    return data.get("result", {})


def _mcp_tool_call(server: dict, tool_name: str, arguments: dict, timeout: int = 60) -> dict:
    result = _mcp_call(
        server,
        method="tools/call",
        params={"name": tool_name, "arguments": arguments},
        timeout=timeout,
    )
    contents = result.get("content", [])
    if not contents:
        return {}
    text = contents[0].get("text", "")
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {"raw_text": text}


def _initialize_server(server: dict) -> dict:
    return _mcp_call(
        server,
        method="initialize",
        params={
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "publish-weekly-report", "version": "1.0.0"},
        },
    )


def try_all_servers(
    servers: list[dict[str, str]],
    tool_name: str,
    arguments: dict,
    *,
    timeout: int = 60,
) -> dict:
    """在多组织配置下依次尝试，与 dingtalk_doc_patched._try_all_servers 行为一致。"""
    if not servers:
        raise DingMCPError("未加载任何 MCP 服务器（检查 ~/.dingtalk-doc-rw/servers.json）。")
    errors: list[str] = []
    for server in servers:
        try:
            _initialize_server(server)
            result = _mcp_tool_call(server, tool_name, arguments, timeout=timeout)
            if isinstance(result, dict) and result.get("errorCode") == "forbidden.accessDenied":
                errors.append(
                    f"[{server.get('name', '?')}] 跨组织限制: {result.get('errorMessage', '')}"
                )
                continue
            if isinstance(result, dict) and result.get("success") is False:
                errors.append(f"[{server.get('name', '?')}] {result.get('errorMessage', '未知错误')}")
                continue
            return result
        except DingMCPError as e:
            errors.append(f"[{server.get('name', '?')}] {e!s}")
            continue
        except Exception as e:
            if requests is not None and isinstance(e, requests.RequestException):
                errors.append(f"[{server.get('name', '?')}] 网络错误: {e!s}")
                continue
            raise
    raise DingMCPError("所有 MCP 服务器均无法完成请求:\n" + "\n".join(errors), details={"errors": errors})


def extract_node_id(url_or_id: str) -> str:
    """从钉钉文档 URL 中提取 nodeId；若已是纯 ID 则原样返回。"""
    m = _NODE_ID_RE.search(url_or_id)
    if m:
        return m.group(1)
    if "/" not in url_or_id:
        return url_or_id
    raise DingMCPError(f"无法从 URL 中提取 nodeId: {url_or_id}")


def mcp_list_all_nodes(servers: list[dict[str, str]], folder_id: str, *, timeout: int = 120) -> list[dict]:
    """分页列出文件夹下全部节点（``list_nodes``）。"""
    all_nodes: list[dict] = []
    arguments: dict = {"folderId": folder_id}
    while True:
        result = try_all_servers(servers, "list_nodes", arguments, timeout=timeout)
        nodes = result.get("nodes") or []
        if isinstance(nodes, list):
            all_nodes.extend(n for n in nodes if isinstance(n, dict))
        if not result.get("hasMore"):
            break
        token = result.get("nextPageToken")
        if not token:
            break
        arguments = {"folderId": folder_id, "pageToken": token}
    return all_nodes


def mcp_create_document(
    servers: list[dict[str, str]],
    *,
    name: str,
    folder_id: str,
    markdown: str = "",
    timeout: int = 180,
) -> dict:
    arguments: dict = {"name": name, "folderId": folder_id}
    if markdown:
        arguments["markdown"] = markdown
    return try_all_servers(servers, "create_document", arguments, timeout=timeout)


def mcp_update_document(
    servers: list[dict[str, str]],
    *,
    node_id_or_url: str,
    markdown: str,
    mode: str = "overwrite",
    timeout: int = 300,
) -> dict:
    node_id = extract_node_id(node_id_or_url)
    args: dict = {"nodeId": node_id, "markdown": markdown, "mode": mode}
    return try_all_servers(
        servers,
        "update_document",
        args,
        timeout=timeout,
    )


def mcp_rename_document(
    servers: list[dict[str, str]],
    *,
    node_id_or_url: str,
    new_name: str,
    timeout: int = 60,
) -> dict:
    node_id = extract_node_id(node_id_or_url)
    return try_all_servers(
        servers,
        "rename_document",
        {"nodeId": node_id, "newName": new_name},
        timeout=timeout,
    )


def extract_node_id_from_doc_result(result: dict) -> str:
    """从 ``create_document`` 等返回体中取出新文档 nodeId。"""
    for key in ("nodeId", "dentryUuid", "id", "docId"):
        v = result.get(key)
        if v and str(v).strip():
            return str(v).strip()
    return ""
