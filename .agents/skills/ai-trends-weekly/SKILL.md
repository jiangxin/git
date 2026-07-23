---
name: ai-trends-weekly
disable-model-invocation: true
description: >
  Explicit invocation only (e.g. `/ai-trends-weekly`); never auto-triggered by conversation context or keywords.
  Collects AI industry news for the configured week interval [start_date, end_date] (see config.json start_day/end_day) and compiles them into the "AI 行业动态" section of the weekly report.
  Produces `weekly/<YYYY-MM-DD>/AI-trends.md` summarizing that week's AI news.
  Accepts an optional `date` argument (YYYY-MM-DD); defaults to today if omitted. See "参数与周期变量" in the body for details.
arguments:
  - name: date
    format: YYYY-MM-DD
    required: false
    description: 锚定周报的参考日期；传给 `setup_week.py` 以计算收集闭区间 [start_date, end_date]（与脚本参数一致时可省略，脚本默认本地今天）。
---

# AI Trends Weekly

本 skill 已设置 `disable-model-invocation: true`，须由用户显式加载（如 `/ai-trends-weekly`）后按本文执行。

**编排原则**：发现链接、抓取正文、合并存档与渲染 Markdown 均由脚本完成；Agent **仅**将 `pending.json` 摘要为 `new.json`。不得自行遍历数据源做 WebFetch/curl 爬取，不得手写整份 `AI-trends.md` 结构。

## 参数与周期变量

- **参数 `date`**（可选）：格式 `YYYY-MM-DD`，含义见下节「确定收集周期」。未提供时使用当前日期。
- **`start_date` / `end_date`**：执行 `setup_week.py` 后，将其**标准输出首行**按空白拆分为两段，依次赋值给变量 **`start_date`**、**`end_date`**。后续凡涉及「目标周期」「收集区间」「起止日期」，均指闭区间 **`[start_date, end_date]`**（含端点）。

## 数据源

权威列表位于 skill 内 **`references/sources.json`**（由 `discover_and_fetch.py` 默认读取）。**禁止**在运行本 skill 时修改该文件或另写一份源列表。

### 必填字段

| 字段 | 说明 |
|------|------|
| `name` | 展示名，写入条目 `source` |
| `url` | 列表页 URL（RSS 失败或未配置时使用） |
| `use_proxy` | `true` / `false` / `"auto"`：必须代理 / 直连 / 优先直连失败再代理 |
| `fallback` | `"search"` \| `"aggregate"` \| `"skip"`（列表失败时由脚本执行，见下） |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `rss_url` | string | 优先用于发现条目的 RSS/Atom |
| `fallback_rss_url` | string | `fallback=aggregate` 时优先尝试的备选 RSS |
| `url_include` | string[] | 详情 URL 正则；**命中任一**才保留；缺省用内置启发式 |
| `url_exclude` | string[] | 命中任一则丢弃 |
| `max_links` | number | 每源最多保留候选条数 |
| `allow_undated` | bool | 默认 `false`：无 `publish_date` 不抓详情 |
| `undated_quota` | number | 仅当 `allow_undated=true` 时，无日期最多抓 N 条 |
| `fetch` | `"http"` \| `"browser"` | 默认 `http`；`browser` 走 Playwright |
| `browser_on_cloudflare` | bool | 默认 `true`：HTTP 判 Cloudflare 时可降级 browser 重试一次 |
| `date_attr` | string | HTML 列表页取日期的属性名（若有） |

示例（完整列表见 `references/sources.json`，勿在此内嵌全量）：

```json
[
  {
    "name": "OpenAI News",
    "url": "https://openai.com/news",
    "use_proxy": false,
    "fallback": "search",
    "rss_url": "https://openai.com/news/rss.xml",
    "url_include": ["/index/", "/research/"]
  },
  {
    "name": "Anthropic News",
    "url": "https://www.anthropic.com/news",
    "use_proxy": true,
    "fallback": "aggregate",
    "fetch": "browser",
    "url_include": ["/news/"]
  }
]
```

## 代理与仓库配置

在**仓库根目录**（与 `weekly/` 同级）维护 `config.json`。`discover_and_fetch.py` 通过 `load_repo_config` 读取：

| 键 | 说明 |
|------|------|
| `proxy` | HTTP/HTTPS 代理 URL；`null` 或空表示不走代理 |
| `fetch_concurrency` | 详情抓取全局并发上限（可选，有合理默认） |
| `fetch_concurrency_per_source` | 每源并发上限（可选） |
| `raw_ttl_days` | `raw/index.jsonl` 缓存 TTL 天数（默认 7） |
| `search_api` | 受限搜索：`{"provider":"serper","api_key_env":"SERPER_API_KEY"}`（可选） |

检视代理：

```bash
jq ".proxy" <config.json
```

Agent **无需**自行用 curl/`WebFetch` 按源爬取；代理与搜索密钥仅由脚本消费。

### Playwright（browser 通道）

源配置 `fetch: "browser"`，或 HTTP 遇 Cloudflare 且 `browser_on_cloudflare` 允许时，脚本经 **Python Playwright** 取页面。环境需：

```bash
pip install playwright
playwright install chromium
```

未安装时该源/URL 记入 `error.log`，不拖垮整次运行。不必调用 `playwright-cli` skill。

## 工作流程总览

```text
setup_week.py
    → start_date end_date，创建 weekly/<end_date>/ai-trends/
discover_and_fetch.py --start-date --end-date
    → 每源：RSS → HTML 列表 → fallback →（http|browser）详情
    → URL 过滤 + 日期策略 + 有效稿门禁
    → pending.json / fetch_state.jsonl / raw/（增量；默认 --resume）
Agent: pending.json → new.json（对每一条补摘要）
merge_archives.py --end-date
    → archives.json（可选 --upsert；删除 new.json）
render_ai_trends.py --start-date --end-date
    → AI-trends.md（Top-50 + 按日分组；可选 --max-per-day）
```

**存量不动**：不清洗、不回写已有周目录中的历史 `archives.json` 噪音；门禁与过滤仅作用于新入库数据。

### 1. 确定收集周期与初始化目录

- 将 skill 参数 **`date`**（格式 `YYYY-MM-DD`）作为锚定日期；汇总周期为 **`setup_week.py` 输出的闭区间 `[start_date, end_date]`**（由仓库根 `config.json` 的 **`start_day` / `end_day`** 决定，缺省为周六至周五）。
- 若未提供 **`date`**，锚定日期为当前日期。

```bash
# 输出: start_date end_date（同一行、空格分隔）
# 同时创建 weekly/<end_date>/ai-trends/ 目录
# export date=2026-05-10   # 可选
read -r start_date end_date < <(python3 .agents/skills/ai-trends-weekly/scripts/setup_week.py "${date:-$(date +%F)}")
```

- 后续路径均使用显式 **`weekly/$end_date/`**。
- 示例（缺省 `start_day=saturday`、`end_day=friday`）：输入 `2026-05-15` → `2026-05-09 2026-05-15`。

### 2. 发现链接并抓取正文

由脚本完成；**不要**用 Agent 遍历 `sources.json` 做 WebFetch。

```bash
python3 .agents/skills/ai-trends-weekly/scripts/discover_and_fetch.py \
  --start-date "$start_date" --end-date "$end_date"
# stdout 示例: sources=N pending=M skipped=K errors=E
# 默认 --resume；全量重跑用 --fresh
```

可选参数：

| 参数 | 说明 |
|------|------|
| `--sources PATH` | 覆盖默认 `references/sources.json` |
| `--weekly-root PATH` | 覆盖 `weekly/` 根目录 |
| `--no-raw` | 不写 `raw/<sha1>.txt` 正文缓存 |
| `--resume` | 默认：加载 `fetch_state.jsonl`，合并已有 `pending.json`，跳过已终态 URL |
| `--fresh` | 清空 `fetch_state.jsonl` 与 `pending.json` 后全量重跑 |
| `--retry-errors` | 对 state 中 `error` 的 URL 再试 |

#### 每源发现顺序

1. 若有 `rss_url` → 拉 RSS/Atom，解析 link/title/date。
2. 否则（或 RSS 失败 / 0 条）→ 拉 `url` 列表页（`fetch: http|browser`）。
3. 若仍失败或 0 条，按 `fallback`：
   - `skip` → 记 `error.log`，下一源；
   - `aggregate` → 尝试 `fallback_rss_url` 或同域有限 `/feed`/`/rss` 探测；
   - `search` → **受限搜索**（预定义 `site:` + 源名 + 日期窗）；无 API 密钥则记 error 并跳过该支路，**不得**由 Agent 手工 WebSearch 替代。

列表/详情 HTTP 遇 Cloudflare 且 `browser_on_cloudflare` 为真时，同一 URL 自动 browser 重试一次。

#### 日期策略（列表阶段即生效）

1. 能解析且落在 `[start_date, end_date]` → 允许。
2. 能解析但越界 → 拒绝（不发详情）。
3. 无法解析：`allow_undated=false`（默认）→ 拒绝；为 `true` 则计入该源 `undated_quota`，超额拒绝。

**无日期默认不抓**；不得因「详情可能补全日期」而放行列表候选。

#### URL 过滤与有效稿门禁

- `url_include` / `url_exclude`；无 include 时用内置启发式（已知媒体路径模式，或同站路径深度≥2 且排除 `/tag/` `/category/` 等）。
- 写入 `pending` 前还须：正文长度 ≥ 约 400 字符、标题非空且非纯 URL。
- 不满足则 `fetch_state` 记 `skipped_filter` / `skipped_date`，**不进** `pending`（也不会进 archives）。

#### 缓存与断点

| 产物 | 行为 |
|------|------|
| `fetch_state.jsonl` | 每行 `{url,status,source,at,sha1?}`；`fetched`/`skipped_*`/`cached` 在 resume 时跳过 |
| `raw/<sha1>.txt` | 抽取后正文纯文本 |
| `raw/index.jsonl` | `{url,sha1,source,fetched_at,publish_date,title}`；TTL 内命中则组装 pending，不 HTTP |
| `pending.json` | 增量原子保存；resume 按 url 合并，避免覆盖丢失 |

失败追加 `error.log`：`[ts] FAILED <method> <url> - <reason>`。

若 `pending=0`：可跳过第 3 节摘要，直接进入第 5 节渲染（仍可基于已有 `archives.json` 出周报）。

### 3. Agent 摘要：`pending.json` → `new.json`

**这是 Agent 在本 skill 中的唯一内容职责。**须对 `pending.json` **每一条**补齐摘要字段后写入 `new.json`，禁止只处理子集或仅精修部分条目。（pending 已收紧，条数通常为数十～百级。）

#### 输入（`pending.json`，脚本已写）

数组元素示例：

```json
{
  "url": "https://example.com/a",
  "original_title": "Original Article Title",
  "publish_date": "2026-07-20",
  "source": "Anthropic News",
  "content": "正文纯文本（可能截断）",
  "fetched_at": "2026-07-23T11:00:00"
}
```

`publish_date` 在通过门禁的条目上通常已解析；正文不足时可参考同周 `raw/` 下对应缓存；**不要**为补全而重新全源爬取。

#### 输出（`new.json`，Agent 写出）

路径：`weekly/$end_date/ai-trends/new.json`。对每条 pending 保留脚本字段，并**补齐**下列字段后写入数组：

| 字段 | 必填 | 说明 |
|------|------|------|
| `en_summary` | 是 | 英文概述 |
| `cn_title` | 是 | 中文标题 |
| `cn_summary` | 是 | 中文概述（2–3 句，突出核心与影响） |
| `collected_at` | 是 | ISO 本地时间，如 `2026-07-23T11:30:00` |
| `rank_hint` | 否 | number，**越小越重要**；缺省在渲染时视为最低优先级 |

完整条目示例：

```json
[
  {
    "url": "https://example.com/a",
    "original_title": "Original Article Title",
    "publish_date": "2026-07-20",
    "source": "Anthropic News",
    "content": "正文纯文本（可保留或省略，merge 不依赖）",
    "fetched_at": "2026-07-23T11:00:00",
    "en_summary": "English summary of the article content.",
    "cn_title": "中文标题",
    "cn_summary": "中文概述，2-3 句话概括核心信息",
    "collected_at": "2026-07-23T11:30:00",
    "rank_hint": 1
  }
]
```

`rank_hint` 建议优先给：大模型发布/更新、公司重大动向、重要技术突破或开源、政策监管、行业争议等。

#### 禁止项

- **不得**修改 `references/sources.json` 或另建源列表
- **不得**用手写 Markdown / 自拟章节结构生成整份 `AI-trends.md`（必须由 `render_ai_trends.py` 产出）
- **不得**自行循环 WebFetch/curl 遍历全部数据源（发现与抓取已由脚本完成）
- **不得**跳过 `merge_archives.py` 直接改 `archives.json`（除非脚本报 `JSON_REPAIR_NEEDED` 需按诊断修复后再跑）

### 4. 合并存档

```bash
python3 .agents/skills/ai-trends-weekly/scripts/merge_archives.py --end-date "$end_date"
# stdout: MERGED: N new entries added, T total in archives.json
# 修摘要重跑时可加 --upsert（同 url 更新摘要字段，不清洗历史噪音）
```

- 默认按 `url` 去重后追加到 `archives.json`（原子写入）
- `--upsert`：同 url 时更新 `en_summary` / `cn_*` / `rank_hint` / `collected_at` 等
- 成功后删除 `new.json`
- JSON 解析失败时脚本输出诊断并含 `JSON_REPAIR_NEEDED`；修复后重跑本步

### 5. 渲染周报 Markdown

**由脚本生成** `weekly/$end_date/AI-trends.md`，Agent 不要手写该文件结构。

```bash
python3 .agents/skills/ai-trends-weekly/scripts/render_ai_trends.py \
  --start-date "$start_date" --end-date "$end_date"
# stdout: WROTE: .../weekly/<end_date>/AI-trends.md
# 可选: --max-per-day K   --quality-min M（默认 5）
```

脚本内部：

- 读 `archives.json`，按 `publish_date` 落在 **`[start_date, end_date]`** 过滤（与 `_shared/scripts/filter_by_date.py` 同源逻辑；被剔除项打印到 stderr）
- 选取：按 `rank_hint` 升序（缺省视为很大），同优先级再按 `publish_date` 降序，最多 **50** 条
- 可选 `--max-per-day K`：Top-50 之后按日再封顶（默认不限制）
- 展示：正文按 `publish_date` 分组（`#### YYYY-MM-DD`），日期从新到旧；同日内仍按 `rank_hint` 升序
- 条目格式：`* **[cn_title](url)**：cn_summary。📰 source 📅 publish_date`
- 「### 参考来源」与正文收录条目一致，链到 `original_title`
- 区间内有效条数 `< --quality-min`（默认 5）时 stderr 打印 `QUALITY_WARNING`
- Agent 须对 **pending.json 中每一条** 补齐摘要字段，不得只摘要子集

如需单独调试日期过滤，可调用：

```bash
python3 .agents/skills/_shared/scripts/filter_by_date.py \
  --start "$start_date" --end "$end_date" \
  --date-field publish_date \
  --input weekly/$end_date/ai-trends/archives.json
```

正式出刊仍以 **`render_ai_trends.py`** 为准。

## 文件结构

```
weekly/
  <YYYY-MM-DD>/              # end_date（setup_week.py 创建）
    AI-trends.md             # render_ai_trends.py 生成
    ai-trends/
      archives.json          # 历史存档（存量不清洗）
      pending.json           # discover_and_fetch 产出（增量 / resume 合并）
      fetch_state.jsonl      # 断点状态（追加）
      new.json               # Agent 摘要产出；merge 后删除
      error.log              # URL/抓取失败日志（追加）
      raw/<sha1>.txt         # 抽取后正文缓存
      raw/index.jsonl        # raw URL 索引（TTL 缓存）
.agents/skills/ai-trends-weekly/
  references/sources.json    # 权威数据源列表
  scripts/
    setup_week.py
    discover_and_fetch.py
    fetch_backends.py        # http / Playwright
    url_filter.py
    restricted_search.py
    merge_archives.py
    render_ai_trends.py
    check_url.py             # 可选：单 URL 查重
    check_cloudflare.py      # 由发现脚本复用
config.json                  # 仓库根：proxy、concurrency、raw_ttl、search_api 等
```

## 辅助脚本（按需）

```bash
# 检查 URL 是否已在 archives 中
python3 .agents/skills/ai-trends-weekly/scripts/check_url.py --end-date "$end_date" <URL>
```

- 输出 `FOUND` / `NOT_FOUND`；若 JSON 损坏则含 `JSON_REPAIR_NEEDED`，修复后重试。
