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

每个数据源字段：

| 字段 | 说明 |
|------|------|
| `name` | 展示名，写入条目 `source` |
| `url` | 列表页 URL |
| `use_proxy` | `true` / `false` / `"auto"`：必须代理 / 直连 / 优先直连失败再代理 |
| `fallback` | `"search"` \| `"aggregate"` \| `"skip"`（首版仅作语义标记；脚本遇失败记 `error.log` 并跳过，不触发 WebSearch） |

示例（完整列表见 `references/sources.json`，勿在此内嵌全量）：

```json
[
  {
    "name": "Anthropic News",
    "url": "https://www.anthropic.com/news",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "OpenAI Blog",
    "url": "https://openai.com/blog",
    "use_proxy": false,
    "fallback": "search"
  }
]
```

## 代理配置

在**仓库根目录**（与 `weekly/` 同级）维护 `config.json`。`discover_and_fetch.py` 通过 `load_repo_config` 读取 **`proxy`**（HTTP/HTTPS 代理 URL；`null` 或空表示不走代理），并按各源 `use_proxy` 决定是否使用。

检视当前配置：

```bash
jq ".proxy" <config.json
```

Agent **无需**自行用 curl/`WebFetch` 按源爬取；代理仅由发现脚本消费。

## 工作流程总览

```text
setup_week.py
    → start_date end_date，创建 weekly/<end_date>/ai-trends/
discover_and_fetch.py --start-date --end-date
    → pending.json（可选 raw/）；失败写入 error.log
Agent: pending.json → new.json（仅补摘要字段）
merge_archives.py --end-date
    → archives.json（删除 new.json）
render_ai_trends.py --start-date --end-date
    → AI-trends.md（内部按 publish_date 过滤，复用 filter_by_date 逻辑）
```

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
```

可选参数：

- `--sources PATH`：覆盖默认 `references/sources.json`
- `--weekly-root PATH`：覆盖 `weekly/` 根目录
- `--no-raw`：不写 `raw/<sha1>.txt` 正文缓存

行为摘要：

- 读 `references/sources.json` 与根目录 `config.json` 的 `proxy`
- 拉列表页、抽链、相对 `archives.json` 去重、按 `[start_date, end_date]` 过滤、抓详情正文
- **覆盖写** `weekly/$end_date/ai-trends/pending.json`（每次运行整文件重写）
- HTTP / Cloudflare 失败追加 `error.log` 并跳过该源/URL；首版**不做** WebSearch 降级
- 可选写入 `raw/<sha1>.txt`

若 `pending=0`：可跳过第 3 节摘要，直接进入第 5 节渲染（仍可基于已有 `archives.json` 出周报）。

### 3. Agent 摘要：`pending.json` → `new.json`

**这是 Agent 在本 skill 中的唯一内容职责。**须对 `pending.json` **每一条**补齐摘要字段后写入 `new.json`，禁止只处理子集或仅精修部分条目。

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

`publish_date` 可为 `null`。正文不足时可参考同周 `raw/` 下对应缓存；**不要**为补全而重新全源爬取。

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
```

- 按 `url` 去重后追加到 `archives.json`（原子写入）
- 成功后删除 `new.json`
- JSON 解析失败时脚本输出诊断并含 `JSON_REPAIR_NEEDED`；修复后重跑本步

### 5. 渲染周报 Markdown

**由脚本生成** `weekly/$end_date/AI-trends.md`，Agent 不要手写该文件结构。

```bash
python3 .agents/skills/ai-trends-weekly/scripts/render_ai_trends.py \
  --start-date "$start_date" --end-date "$end_date"
# stdout: WROTE: .../weekly/<end_date>/AI-trends.md
```

脚本内部：

- 读 `archives.json`，按 `publish_date` 落在 **`[start_date, end_date]`** 过滤（与 `_shared/scripts/filter_by_date.py` 同源逻辑；被剔除项打印到 stderr）
- 选取：按 `rank_hint` 升序（缺省视为很大），同优先级再按 `publish_date` 降序，最多 **50** 条
- 展示：正文按 `publish_date` 分组（`#### YYYY-MM-DD`），日期从新到旧；同日内仍按 `rank_hint` 升序
- 条目格式：`* **[cn_title](url)**：cn_summary。📰 source 📅 publish_date`
- 「### 参考来源」与正文收录条目一致，链到 `original_title`
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
      archives.json          # 历史存档
      pending.json           # discover_and_fetch 产出（覆盖写）
      new.json               # Agent 摘要产出；merge 后删除
      error.log              # URL/抓取失败日志（追加）
      raw/<sha1>.txt         # 可选正文缓存
.agents/skills/ai-trends-weekly/
  references/sources.json    # 权威数据源列表
  scripts/
    setup_week.py
    discover_and_fetch.py
    merge_archives.py
    render_ai_trends.py
    check_url.py             # 可选：单 URL 查重
    check_cloudflare.py      # 由发现脚本复用
config.json                  # 仓库根：proxy、start_day、end_day 等
```

## 辅助脚本（按需）

```bash
# 检查 URL 是否已在 archives 中
python3 .agents/skills/ai-trends-weekly/scripts/check_url.py --end-date "$end_date" <URL>
```

- 输出 `FOUND` / `NOT_FOUND`；若 JSON 损坏则含 `JSON_REPAIR_NEEDED`，修复后重试。
