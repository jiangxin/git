---
name: git-news-weekly
disable-model-invocation: true
description: >
  Explicit invocation only (e.g. `/git-news-weekly`); never auto-triggered by conversation context or keywords.
  Collects Git technology news and blog posts for the configured week interval [start_date, end_date] (see config.json start_day/end_day) and compiles them into the "Git 技术动态" section of the weekly report.
  Produces `weekly/<YYYY-MM-DD>/Git-news.md` summarizing that week's Git tech news.
  Accepts an optional `date` argument (YYYY-MM-DD); defaults to today if omitted. See "参数与周期变量" in the body for details.
arguments:
  - name: date
    format: YYYY-MM-DD
    required: false
    description: 锚定周报的参考日期；传给 `setup_week.py` 以计算收集闭区间 [start_date, end_date]（与脚本参数一致时可省略，脚本默认本地今天）。
---

# Git News Weekly

本 skill 已设置 `disable-model-invocation: true`，须由用户显式加载（如 `/git-news-weekly`）后按本文执行。

**编排原则**：发现链接、抓取正文、渲染 Markdown 均由脚本完成；Agent **仅**为已抓取文章补写 `.summary.md` sidecar。不得自行遍历数据源做 WebFetch/curl 爬取，不得手写整份 `Git-news.md` 结构。

**执行纪律（必须遵守）**：

1. 工作目录为**仓库根目录**（含 `weekly/`、`lib/`、`.agents/`）。
2. 按下方 **§1 → §7 顺序完整执行**，不得跳过聚类（§5）或索引（§7）。
3. 任一步命令非零退出则**停止后续步骤**，修复后从该步重跑；§4 若 `missing>0`，回到 §3 补写摘要后再跑 §4。
4. 全部完成后核对产出：`weekly/<end_date>/Git-news.md`、`Git-news.html`、`weekly/<end_date>/git-news/clusters.json`、`weekly/index.html`。

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
| `slug` | string | 站目录名 `[a-z0-9-]+`；缺省由 `name` 自动生成 |
| `rss_url` | string | 优先用于发现条目的 RSS/Atom |
| `fallback_rss_url` | string | `fallback=aggregate` 时优先尝试的备选 RSS |
| `url_include` | string[] | 详情 URL 正则；**命中任一**才保留；缺省用内置启发式 |
| `url_exclude` | string[] | 命中任一则丢弃 |
| `max_links` | number | 每源最多保留候选条数 |
| `allow_undated` | bool | 默认 `false`：无 `publish_date` 不抓详情 |
| `undated_quota` | number | 仅当 `allow_undated=true` 时，无日期最多抓 N 条 |
| `fetch` | `"http"` \| `"browser"` | 默认 `http`；`browser` 走 Playwright |
| `browser_on_cloudflare` | bool | 默认 `true`：HTTP 判 Cloudflare 时可降级 browser 重试一次 |
| `stealth` | bool | 默认 `false`：启用 Playwright stealth 模式，隐藏自动化特征以绕过 Cloudflare 等反爬虫检测 |
| `storage_state` | string | Playwright storage_state 文件标识符；若指定，使用 `config.json` 的 `playwright_storage_state_dir` 下的 `<标识符>.json` 文件持久化浏览器会话（cookies、localStorage 等） |
| `date_attr` | string | HTML 列表页取日期的属性名（若有） |
| `max_pages` | number | 该源最大翻页数；覆盖 `config.json` 的 `default_max_pages`；默认 1（不翻页） |

## 代理与仓库配置

在**仓库根目录**（与 `weekly/` 同级）维护 `config.json`：

| 键 | 说明 |
|------|------|
| `proxy` | HTTP/HTTPS 代理 URL；`null` 或空表示不走代理 |
| `fetch_concurrency` | 详情抓取全局并发上限（默认 4） |
| `fetch_concurrency_per_source` | 每源并发上限（默认 2） |
| `source_concurrency` | 同时跑多少个源（默认 4） |
| `body_ttl_days` | 正文缓存 TTL 天数（默认 7） |
| `list_cache_ttl_seconds` | 列表/RSS 发现页短缓存秒数（默认 1800）；`0` 关闭 |
| `known_url_streak_stop` | 时间倒序列表上连续命中已抓 URL 条数后停止候选扫描（默认 5）；`0` 关闭 |
| `default_max_pages` | 全局翻页上限（默认 1，即不翻页）；可被源级 `max_pages` 覆盖 |
| `search_api` | 受限搜索：`{"provider":"serper","api_key_env":"SERPER_API_KEY"}`（可选） |
| `playwright_storage_state_dir` | Playwright storage_state 文件存储目录（默认 `~/.playwright-cli/states/`） |

### Playwright（browser 通道）

源配置 `fetch: "browser"`，或 HTTP 遇 Cloudflare 且 `browser_on_cloudflare` 允许时，脚本经 **Python Playwright** 取页面。环境需：

```bash
pip install playwright
playwright install chromium
```

## 目录布局

```text
weekly/<end_date>/git-news/
  url_index.jsonl                 # 全局：url → {site, hash, at}；先写胜
  error.log                       # URL/抓取失败日志
  clusters.json                   # 相似文章聚类结果
  sites/<slug>/
    index.jsonl                   # 该站：url/status/hash/at
    articles/
      <hash>.body.txt             # 抽取后正文
      <hash>.meta.json            # 抓取元数据
      <hash>.summary.md           # Agent sidecar（YAML front matter）
  Git-news.md                     # render 输出（在 weekly/<end_date>/）
  Git-news.html                   # render 输出（在 weekly/<end_date>/）
```

**停止写入**（新跑不再产生）：`pending.json`、`new.json`、`fetch_state.jsonl`、`raw/`、`archives.json`。历史周目录文件可残留，脚本不读。

### 文件契约

#### `<hash>.meta.json`

```json
{
  "url": "https://example.com/a",
  "original_title": "...",
  "publish_date": "2026-07-20",
  "source": "GitHub Blog",
  "site": "github-blog",
  "hash": "<sha1>",
  "fetched_at": "2026-07-23T11:00:00Z",
  "status": "fetched"
}
```

#### `<hash>.summary.md`

YAML front matter（Agent 写入），正文区可空：

```markdown
---
en_summary: "English summary..."
cn_title: "中文标题"
cn_summary: "中文概述..."
collected_at: "2026-07-23T11:30:00"
rank_hint: 1
topic_id: "git-lfs-perf"
topic_label: "Git LFS 性能相关"
---
```

`cn_title`、`cn_summary` **必须使用中文**（周报展示语言）；`en_summary` 使用英文。原文为非中文时，须翻译后再写入中文字段，不得把英文原文直接填入 `cn_title` / `cn_summary`。

`topic_id`（可选）：当 Agent 判断本文与已处理的其他文章属同一话题时，赋予相同的话题标识符。渲染时 `cluster_articles.py` 会据此将同话题文章聚合为一个 group，并在报告中折叠展示相似文章。`topic_label`（可选）：话题的中文描述标签。

#### `sites/<slug>/index.jsonl`

每行一条，later-wins 按 url：

```json
{"url":"...","status":"fetched|skipped_filter|skipped_date|error|cached","hash":"...","at":"..."}
```

#### `url_index.jsonl`（全局）

```json
{"url":"...","site":"<slug>","hash":"<sha1>","at":"..."}
```

## 工作流程总览

**必跑顺序**（不可省略、不可乱序）：

```text
§1 setup_week.py
    → start_date end_date，创建 weekly/<end_date>/git-news/
§2 discover_and_fetch.py --start-date --end-date --sources <path>
    → 站间并行：RSS → HTML → fallback → 详情抓取
    → URL 过滤 + 日期策略 + 有效稿门禁
    → sites/<slug>/articles/ + url_index.jsonl（增量；默认 --resume）
    → --skill-subdir 自动从 --sources 路径推导
§3 Agent: 扫描缺 .summary.md 的文章，逐篇写 sidecar
§4 check_summaries.py --end-date
    → 断言：所有 fetched/cached 条目均有合法 summary（失败则回 §3）
§5 cluster_articles.py --end-date
    → 相似文章聚类（摘要 Jaccard + 轻量标题 + topic_id 合并）
    → clusters.json（聚类结果）
§6 render_git_news.py --start-date --end-date
    → Git-news.md + Git-news.html（Top-50 + 按日分组 + 相似文章折叠）
§7 render_index.py
    → weekly/index.html（所有周期 HTML 报告导航索引）
```

### 1. 确定收集周期与初始化目录

在仓库根目录执行：

```bash
read -r start_date end_date < <(python3 .agents/skills/git-news-weekly/scripts/setup_week.py "${date:-$(date +%F)}")
# 确认已打印两段日期，且存在目录 weekly/$end_date/git-news/
```

### 2. 发现链接并抓取正文

```bash
python3 lib/discover_and_fetch.py \
  --start-date "$start_date" --end-date "$end_date" \
  --sources .agents/skills/git-news-weekly/references/sources.json
# stdout: sources=N fetched=M skipped=K errors=E
# --skill-subdir 自动从 --sources 路径推导，无需显式传递
# 非零退出则停止；默认同周增量 --resume，无需 --fresh
```

可选参数：`--sources PATH`、`--weekly-root PATH`、`--skill-subdir SKILL_SUBDIR`（自动推导，通常无需指定）、`--resume`（默认）、`--fresh`、`--retry-errors`

### 3. Agent 摘要：写 `.summary.md` sidecar

**这是 Agent 在本 skill 中的唯一内容职责。**

扫描路径：`weekly/<end_date>/git-news/sites/*/articles/*.meta.json`。  
对每个 `status∈{fetched, cached}` 且缺少合法 `.summary.md` 的文章：

1. 读取同目录 `<hash>.body.txt` 正文
2. 写入 `<hash>.summary.md`，包含：`en_summary`（英文）、`cn_title` / `cn_summary`（**必须中文**）、`collected_at`（必填），`rank_hint`（可选），同话题时可写 `topic_id` / `topic_label`
3. **必须**处理每一个待摘要条目，不得只处理子集；非中文原文须先译成中文再写入 `cn_*` 字段
4. 全部写完后再进入 §4（不要边写边渲染）

#### 禁止项

- **不得**将英文或其他非中文内容写入 `cn_title` / `cn_summary`
- **不得**修改 `references/sources.json` 或另建源列表
- **不得**用手写 Markdown 生成整份 `Git-news.md`（必须由 `render_git_news.py` 产出）
- **不得**自行循环 WebFetch/curl 遍历全部数据源
- **不得**写入 `pending.json` / `new.json`
- **不得**在摘要未全部完成时跳到 §5/§6

### 4. 校验摘要完备性

```bash
python3 .agents/skills/git-news-weekly/scripts/check_summaries.py --end-date "$end_date"
# stdout: OK: summarized=N missing=0 sites=S
# missing>0 或非零退出 → 回到 §3 补齐后重跑本步；不得继续 §5
```

可选参数：`--weekly-root WEEKLY_ROOT`

### 5. 相似文章聚类

```bash
python3 .agents/skills/git-news-weekly/scripts/cluster_articles.py --end-date "$end_date"
# stdout: CLUSTERED: total=N clusters=M clustered_articles=K singletons=J
#         WROTE: .../weekly/<end_date>/git-news/clusters.json
```

脚本对已抓取文章进行相似性聚类，生成 `clusters.json`。聚类方法：

- **摘要 Jaccard 相似度**：对 `cn_summary` 分词后计算 token 集合的 Jaccard 系数（权重 70%）
- **标题轻量加权**：对中英文标题同样计算 Jaccard（权重 30%），用于同题短标题补强
- **topic_id 合并**：Agent 在 `.summary.md` 中标注了相同 `topic_id` 的文章直接合并
- **不使用 URL 相似度**：同站模板化 path 会导致误聚，故不参与加权

相似度超过阈值（默认 0.30）的文章被归为同一簇。`render_git_news.py` 会自动读取 `clusters.json`，在报告渲染时将相似文章折叠展示。

可选参数：`--weekly-root PATH`、`--threshold FLOAT`（默认 0.30）

### 6. 渲染周报（Markdown + HTML）

```bash
python3 .agents/skills/git-news-weekly/scripts/render_git_news.py \
  --start-date "$start_date" --end-date "$end_date"
# stdout: WROTE: .../weekly/<end_date>/Git-news.md
# 同时写出 Git-news.html；非零退出则停止
```

可选参数：`--weekly-root PATH`、`--max-per-day K`、`--quality-min M`（入围文章数 < M 时 stderr 输出 QUALITY_WARNING，默认 5）。

脚本从 `sites/*/articles/*.meta.json` + `.summary.md` 聚合，按日期过滤、rank_hint 排序、Top-50、按日分组渲染。如果存在 `clusters.json`，首篇按正文展示，相似文章缩进折叠在相关报道块内。

### 7. 生成索引页面

```bash
python3 lib/render_index.py
# stdout: WROTE: .../weekly/index.html
```

扫描 `weekly/` 下所有周期目录，为每个周期中存在的 HTML 报告生成导航索引。

### 完成检查

全部步骤成功后确认：

- [ ] `weekly/<end_date>/Git-news.md` 与 `Git-news.html` 已更新
- [ ] `weekly/<end_date>/git-news/clusters.json` 存在（本周跑过 §5）
- [ ] `weekly/index.html` 已更新
- [ ] §4 曾输出 `missing=0`

## 辅助脚本

```bash
# 检查 URL 是否已收录
python3 .agents/skills/git-news-weekly/scripts/check_url.py --end-date "$end_date" <URL>
# 批量检查（一行一个 URL）
python3 .agents/skills/git-news-weekly/scripts/check_url.py --end-date "$end_date" --file urls.txt
```

可选参数：`--weekly-root PATH`、`--file FILE`
