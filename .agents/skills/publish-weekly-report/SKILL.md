---
name: publish-weekly-report
disable-model-invocation: true
description: >
  Explicit invocation only (e.g. `/publish-weekly-report`); never auto-triggered.
  Publishes weekly/END_DATE/weekly-report.md to DingTalk under the fixed
  parent folder defined in publish_prep.py (**父文件夹（固定）** below).
  Requires prior generate-report-weekly; uploads local images so they resolve in DingTalk.
arguments:
  - name: date
    format: YYYY-MM-DD
    required: false
    description: 与 generate-report-weekly 相同：锚定周；由 setup_week.py 得到 end_date。未提供时使用当前日期。
---

# Publish Weekly Report

本 skill 须由用户显式加载（如 `/publish-weekly-report`）后按本文执行。

## 参数与周期变量

- **参数 `date`**（可选）：`YYYY-MM-DD`。与 **`generate-report-weekly`** 一致，经 `setup_week.py` / `config.json` 的 **`start_day` / `end_day`** 计算 **`end_date`**（周期结束日，非固定周日）。
- **`start_date` / `end_date`**：在仓库根执行 `generate-report-weekly` 的 `setup_week.py` 后，将标准输出首行拆为两段（见该 skill）。

## 依赖

- **`python3`**
- **`generate-report-weekly`**：必须先能生成 `weekly/<end_date>/weekly-report.md`。
- **钉钉文档写入（二选一，脚本自动优先 MCP）**：
  - **推荐**：**`~/.dingtalk-doc-rw/servers.json`**（与仓库根 **`dingtalk_doc_patched.py`** / **dingtalk-doc-rw** 一致）。内容为 `{"mcp_servers": [...]}`，每条支持 **`url` + `key` 分字段**（钉钉控制台复制的网关地址常无 `?key=`）或 **`base_url` + `key`** / **完整 MCP URL（含 `?key=`）**。一键脚本通过钉钉 **MCP 网关** 调用 `list_nodes` / `create_document` / `update_document`，**不经过 `dws` PAT**。需 **`pip install requests`**。
  - **备选**：**`dingtalk-dws`**：`dws` 已安装并完成 Wukong 授权；在 **未配置** 上述 `servers.json`、或显式 **`--use-dws`** 时用于 `doc list` / `doc create` / `doc update` / **`doc upload`**（仅 dws 支持 **`--upload-images`**）。
- **`dingtalk-doc-rw`**（可选）：大模型侧可用 MCP 工具辅助；本机一键脚本以 **`servers.json`** 为准。

## 父文件夹（固定）

钉钉父文件夹（列子节点、新建周报所在目录）以 **`scripts/publish_prep.py`** 为准：

- **`DEFAULT_PARENT_NODE_ID`**：文件夹节点 ID（供 MCP / `dws` 使用）。
- **`DEFAULT_PARENT_ALIDOCS_URL`**：该节点在 alidocs 的 HTTPS 链接。

运行 **`publish_prep.py "$end_date"`** 时，stdout JSON 的 **`parent_folder_node_id`** / **`parent_alidocs_url`** 分别等于上述两常量。所有新建或列出的周报文档均视为该文件夹下的子节点；下文「父文件夹节点」均指该节点 ID。

## 工作流程

### 1. 解析 `end_date`

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
read -r start_date end_date < <(python3 .agents/skills/generate-report-weekly/scripts/setup_week.py "${date:-$(date +%F)}")
```

### 2. 校验 `weekly-report.md`（必须）

```bash
python3 .agents/skills/publish-weekly-report/scripts/publish_prep.py "$end_date" --check-only
```

- **退出码 `0`**：文件存在，可继续。
- **退出码 `3`**：不存在 — **必须先执行** **`/generate-report-weekly`**（同一 `date`）生成汇总后再发布；stderr 含缺失路径说明。
- **退出码 `2`**：无法推断仓库根（极少见）。

可选：输出发布用 JSON（路径、标题、图片清单）供后续步骤使用：

```bash
python3 .agents/skills/publish-weekly-report/scripts/publish_prep.py "$end_date"
```

JSON 字段说明：

| 字段 | 含义 |
|------|------|
| `doc_title` | 从 Markdown 首个 `# ...` 抽取的标题（含「预览版」若有） |
| `weekly_md` | 本地 `weekly-report.md` 绝对路径 |
| `images` | `{"href": "相对路径", "path": "本地绝对路径"}` 数组，仅含已存在的本地文件 |
| `parent_folder_node_id` / `parent_alidocs_url` | 上述父文件夹 |

### 3. 判断是否已有同周周报（钉钉）

**若 `publish_to_dingtalk.py` 走 MCP（默认在 `~/.dingtalk-doc-rw/servers.json` 存在且可解析时）**：脚本内部等价于 **`list_nodes`**（父文件夹节点，见上文 **父文件夹（固定）**）+ **`update_document`** / **`create_document`**。

**若走 `dws`**（无 MCP 配置或 **`--use-dws`**）：

```bash
DWS="$HOME/.real/.bin/dws/bin/dws"
PARENT_FOLDER_NODE_ID="$(python3 .agents/skills/publish-weekly-report/scripts/publish_prep.py "$end_date" | python3 -c 'import json,sys; print(json.load(sys.stdin)["parent_folder_node_id"])')"
$DWS doc list --folder "$PARENT_FOLDER_NODE_ID" --format json
```

- 在返回的节点中查找 **标题或文件名** 含有 **`【${end_date}】`** 的条目（与正式版 / 预览版标题一致即可匹配到同一周）。
- **若已存在**：视为更新场景 → 取得该文档 **`nodeId`**（或完整 alidocs URL），后续 **`update_document`（MCP）** 或 **`doc update`（dws）**。
- **若不存在**：创建场景 → **`create_document`**（MCP）或 **`doc create --name "<doc_title>" --folder ...`**（`dws`），再写入正文。

> **禁止**猜测 `nodeId`：必须从 `list` / `create` 的 JSON 响应中提取。

### 4. 配图进正文（必须）

`weekly-report.md` 中图表多为 **相对路径**（如 `token-metrics/...png`），钉钉无法读取本机路径。

**推荐（与 `publish_to_dingtalk.py` 默认一致）**：在用于 **覆盖写入** 的正文中，将每张配图读入并写成 Markdown 图片语法 **`![](data:image/png;base64,...)`**（或其它 `image/*` MIME），使图片**随正文一并写入文档**，**不在**父文件夹下产生与周报并列的独立图片文件节点。`publish_prep.py` 的 `images` 数组仍用于定位本地文件。

**备选（仅当正文长度或产品限制不接受内联 base64 时）**：须使用 **`dws`**（**`--use-dws`**）：**`dws doc upload`** 上传到**非周报父目录并列位置**（例如父文件夹下的子文件夹 `周报配图-<end_date>`），从 **`--format json`** 取 **`downloadUrl` / `url`** 等**可直接作为图片加载的 HTTPS 直链**（以命令输出为准），再替换 Markdown 中的相对路径。勿仅用 `docUrl` 填进 `![](...)`（常为文档预览页，无法当图片渲染）。

若 `images` 为空，仍应发布正文，但无配图替换步。

**`<details>` 折叠块（`publish_to_dingtalk.py`）**：在读取本地 `weekly-report.md` 后、配图替换与写入钉钉之前，脚本会将每个 `<details>…</details>` 整段替换为一条 Markdown 链接：`[<summary> 纯文本](https://code.alibaba-inc.com/AI-coding-workshop/ai-coding-weekly-report/blob/master/weekly/<end_date>/weekly-report.md)`，其中 `<end_date>` 为本次发布的 `end_date`（与 `trailer.md` 中「源码」占位符 `<end-date>` 同义）。折叠区内原正文不再上传钉钉，读者通过链接在仓库查看完整 `weekly-report.md`。

### 5. 写入钉钉文档

- **MCP**：`update_document`（已有节点）或 `create_document`（新建，一次携带 Markdown）。
- **dws**：`doc update --node <已有DOC_ID> --mode overwrite`（或 `append`；周报通常 **overwrite**）。新建时先 `doc create` 再 `doc update`。

若 `doc update` 仅接受 Markdown，可将已替换图片 URL 后的 HTML 转为 Markdown（需额外工具时由执行环境安装），或 **上传最终 HTML 文件** 作为附件节点并在文档内链到该文件 — 以实际 `dws` 能力与产品限制为准。

### 6. PAT 与错误（仅 dws 路径）

- 使用 **`dws`** 且出现 **`PAT_*_NO_PERMISSION`** 时，**必须**按 **dingtalk-dws** skill 使用 **`dws_pat_bypass.sh`** 重试同等子命令，禁止未尝试 bypass 即放弃。
- **MCP 路径**不经过 `dws` PAT；若 MCP 报错，检查 **`servers.json`** 中的 **`url`/`key`** 是否与钉钉 MCP 授权页一致（可分字段写 `url` + `key`，与 **`dingtalk_doc_patched.py`** 的规范化逻辑一致）。

### 7. 可选：一键发布脚本

在仓库根解析好 **`end_date`** 后，脚本默认将配图 **内联为 data URI** 后 **覆盖写入钉钉文档**。

- **默认**：若存在 **`~/.dingtalk-doc-rw/servers.json`** 且含可解析的 **`mcp_servers`**，则走 **钉钉文档 MCP**（与 **`dingtalk_doc_patched.py`** 同源逻辑）；否则走 **`dws` + `dws_pat_bypass.sh`**。
- **`--upload-images`**：仅 **`dws`** 支持（子文件夹 + `doc upload` + HTTPS）；使用 MCP 时请勿加此参数，或显式 **`--use-dws`**。

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
read -r start_date end_date < <(python3 .agents/skills/generate-report-weekly/scripts/setup_week.py "${date:-$(date +%F)}")
python3 .agents/skills/publish-weekly-report/scripts/publish_to_dingtalk.py "$end_date"
```

- **`--dry-run`**：只向 stdout 打印计划 JSON，不调用网络 / `dws`。
- **`--upload-images`**：见上（**dws** 专用）。
- **`--node <NODE_ID>`**：跳过 list/create，仅对该文档 **overwrite**。
- **`--use-dws`**：强制 **`dws`**（忽略 MCP 配置文件）。
- **`--use-mcp`**：强制 MCP（须有效 **`servers.json`**；文件不存在退出码 `2`）。
- **`--mcp-config <路径>`**：指定 MCP 配置文件（默认 **`~/.dingtalk-doc-rw/servers.json`**）。
- **`--dws <路径>`**：覆盖默认的 `~/.real/.bin/dws/bin/dws`。
- **退出码**：`0` 成功；`2` 仓库根 / 传输配置不可用（如 **`--use-mcp`** 但无配置、或 dws/bypass 缺失）；`3` 缺 `weekly-report.md`；`4` 业务错误；`5` 仍为 PAT 拦截（**仅 dws**）。

大模型无本机脚本环境时，仍按上文步骤 3–6 手工或 MCP 执行即可。

## 文件结构

```
.agents/skills/publish-weekly-report/
  SKILL.md
  scripts/
    publish_prep.py         # 校验 Markdown、抽取标题与图片清单（JSON）
    dingtalk_doc_mcp.py     # 读取 ~/.dingtalk-doc-rw/servers.json，走钉钉 MCP 网关
    publish_to_dingtalk.py  # 一键发布（默认 MCP 优先；内联配图 + MD 覆盖）
    tests/
      conftest.py
      test_publish_prep.py
      test_publish_to_dingtalk.py
      test_dingtalk_doc_mcp.py
```

## 与 generate-report-weekly 的关系

| 步骤 | generate-report-weekly | publish-weekly-report |
|------|-------------------------|------------------------|
| 产出 `weekly-report.md`   | 是 | 否（仅消费） |
| 钉钉发布 | 否 | 是 |
