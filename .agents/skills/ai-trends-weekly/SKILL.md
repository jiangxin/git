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

## 参数与周期变量

- **参数 `date`**（可选）：格式 `YYYY-MM-DD`，含义见下节「确定收集周期」。未提供时使用当前日期（与下节一致）。
- **`start_date` / `end_date`**：执行 `setup_week.py` 后，将其**标准输出首行**按空白拆分为两段，依次赋值给变量 **`start_date`**、**`end_date`**。后续凡涉及「目标周期」「收集区间」「起止日期」，均指闭区间 **`[start_date, end_date]`**（含端点）。

## 数据源与代理配置

每个数据源的 `use_proxy` 字段取值说明：
- `true`：必须使用代理（如被墙或严格限制的站点）
- `false`：不需要使用代理
- `auto`：优先直连，失败后自动切换代理

```json
[
  {
    "name": "Anthropic News",
    "url": "https://www.anthropic.com/news",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "Anthropic Research",
    "url": "https://www.anthropic.com/research",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "Anthropic Blog",
    "url": "https://claude.com/blog",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "OpenAI Blog",
    "url": "https://openai.com/blog",
    "use_proxy": false,
    "fallback": "search"
  },
  {
    "name": "OpenAI News",
    "url": "https://openai.com/news",
    "use_proxy": false,
    "fallback": "search"
  },
  {
    "name": "Google DeepMind Blog",
    "url": "https://deepmind.google/blog",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "Google AI Blog",
    "url": "https://blog.google/technology/ai",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "Meta AI Blog",
    "url": "https://ai.meta.com/blog",
    "use_proxy": true,
    "fallback": "aggregate"
  },
  {
    "name": "Microsoft AI Blog",
    "url": "https://news.microsoft.com/source/topics/ai",
    "use_proxy": false,
    "fallback": "search"
  },
  {
    "name": "Cohere Blog",
    "url": "https://cohere.com/blog",
    "use_proxy": false,
    "fallback": "search"
  },
  {
    "name": "TechCrunch AI",
    "url": "https://techcrunch.com/category/artificial-intelligence",
    "use_proxy": auto,
    "fallback": "search"
  },
  {
    "name": "The Verge AI",
    "url": "https://www.theverge.com/ai-artificial-intelligence",
    "use_proxy": auto,
    "fallback": "search"
  },
  {
    "name": "VentureBeat AI",
    "url": "https://venturebeat.com/ai",
    "use_proxy": auto,
    "fallback": "search"
  },
  {
    "name": "每日AI快讯",
    "url": "https://ai-bot.cn/daily-ai-news/",
    "use_proxy": false,
    "fallback": "skip"
  },
  {
    "name": "大黑 AI 速报",
    "url": "https://news.daheiai.com/",
    "use_proxy": false,
    "fallback": "skip"
  }
]
```

## 工作流程

### 1. 确定收集周期与初始化目录

- 将 skill 参数 **`date`**（格式 `YYYY-MM-DD`）作为锚定日期；汇总周期为 **`setup_week.py` 输出的闭区间 `[start_date, end_date]`**（由仓库根 `config.json` 的 **`start_day` / `end_day`** 决定，缺省为周六至周五）。锚定日落在该区间内任意一天时，`end_date` 相同。
- 若未提供 **`date`**，锚定日期为当前日期。

使用 `setup_week.py` 脚本初始化目录，并把输出写入 **`start_date`**、**`end_date`**：

```bash
# 输出: start_date end_date（同一行、空格分隔）
# 同时创建 weekly/<end_date>/ai-trends/ 目录
# 将 skill 参数 date 设为 shell 变量（未传参则省略下行，改用下一行的缺省当前日期）
# export date=2026-05-10
read -r start_date end_date < <(python3 .agents/skills/ai-trends-weekly/scripts/setup_week.py "${date:-$(date +%F)}")
# 若环境不支持上述写法，可先执行脚本再将 stdout 首行前两列赋给 start_date、end_date
```

- **`start_date`**、**`end_date`** 即上一步命令标准输出的两个字段；后续爬取、筛选、搜索引擎补充与 Markdown 生成均以此闭区间为准（见第 5.2、6、7 节）。
- 后续脚本与路径均使用显式 **`weekly/$end_date/`**（由本节 `end_date` 变量确定）。
- 示例（缺省 `start_day=saturday`、`end_day=friday`）：输入 `2026-05-15`（周五），输出 `2026-05-09 2026-05-15`。
- 示例（同上配置）：输入 `2026-05-13`（周三，同周期），输出仍为 `2026-05-09 2026-05-15`。

### 2. 读取代理配置

在**仓库根目录**（与 `weekly/` 同级）维护 `config.json`，用 **`jq`** 读取字段 **`proxy`**（HTTP/HTTPS 代理 URL 字符串，可为 `null` 表示不走代理）。

**检视当前配置**（与下列命令一致）：

```bash
jq ".proxy" <config.json
```

**供后续 Bash / `curl` 使用**：将原始字符串写入 `PROXY`（去掉 JSON 引号；`proxy` 为 `null` 时得到空串）：

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROXY=$(jq -r '.proxy // empty' <config.json)
```

将 `PROXY` 保存为环境变量后，按数据源 `use_proxy` 规则选用。注意 `WebFetch` 工具本身不支持代理，对于标记为 `use_proxy: true` 的数据源，需通过 Bash 调用 `curl -x "$PROXY" <url>`（若 `PROXY` 为空则勿传 `-x`，或仅直连/再按 `auto` 分支重试）。

### 3. 错误日志

在 `weekly/$end_date/ai-trends/` 目录下维护 `error.log` 文件，用于记录所有失败的 URL 访问。

- **追加模式**：每次访问失败时，向 `error.log` 追加一行，不覆盖已有内容
- **记录内容**：时间戳、失败的 URL、使用的访问方式（WebFetch / curl 直连 / curl 代理）、简短错误信息
- **格式**：`[YYYY-MM-DD HH:MM:SS] FAILED <访问方式> <URL> - <错误原因>`
- 仅记录 URL 访问失败的情况，内容解析失败不计入

示例：
```
[2026-05-11 10:30:15] FAILED WebFetch https://techcrunch.com/category/artificial-intelligence - Connection refused
[2026-05-11 10:31:02] FAILED curl(proxy) https://www.anthropic.com/news - Timeout after 30s
```

### 4. 加载 archives.json 用于查重

通过 `weekly/$end_date/ai-trends/archives.json` 访问存档（如不存在则初始化为空数组 `[]`）。

```json
[
  {
    "original_title": "Original Article Title",
    "en_summary": "English summary of the article content.",
    "cn_title": "中文标题",
    "cn_summary": "中文概述，2-3 句话概括核心信息",
    "url": "https://example.com/article",
    "publish_date": "2026-05-08",
    "source": "数据源名称",
    "collected_at": "2026-05-11T10:30:00"
  }
]
```

**查重**：在爬取每个文章 URL 前，使用 `check_url.py` 检查是否已存在：

```bash
# 检查单个 URL
python3 .agents/skills/ai-trends-weekly/scripts/check_url.py --end-date "$end_date" <URL>

# 批量检查多个 URL
python3 .agents/skills/ai-trends-weekly/scripts/check_url.py --end-date "$end_date" --file urls.txt
```

- 输出 `FOUND` 表示已收录，跳过该 URL
- 输出 `NOT_FOUND` 表示未收录，可以继续爬取
- 如果 JSON 解析失败，脚本会输出详细错误信息（错误位置、上下文），末尾标记 `JSON_REPAIR_NEEDED`。此时由大模型根据错误信息修复 `archives.json`，修复后重新执行

### 5. 循环爬取每个数据源

遍历上述数据源列表，针对每个数据源执行以下步骤：

#### 5.1 决策是否使用代理

```
source = 当前数据源
if source.use_proxy == true:
    使用代理（Bash: curl -x "$PROXY" <url>）
elif source.use_proxy == false:
    优先尝试 WebFetch 直连
    如果直连失败，尝试代理
elif source.use_proxy == auto:
    优先尝试 WebFetch 直连
    如果失败，再使用代理
```

#### 5.1.1 curl 浏览器头

使用 curl 时统一添加浏览器头，降低被 Cloudflare 等拦截的概率：

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
curl -s -x "$PROXY" \
  -H "User-Agent: $UA" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  --max-time 30 "$url"
```

#### 5.1.2 Cloudflare 检测与降级策略

curl 返回 HTML 后，使用 `check_cloudflare.py` 检测是否为 Cloudflare challenge 页面：

```bash
echo "$html" | python3 .agents/skills/ai-trends-weekly/scripts/check_cloudflare.py
# 退出码: 0=正常页面, 1=Cloudflare challenge, 2=其他错误
```

**降级策略**（根据数据源的 `fallback` 字段）：

| `fallback` 取值 | 行为 |
|----------------|------|
| `"search"` | 该站点被 Cloudflare 阻挡时，使用 `WebSearch` 搜索 `site:<域名> <start_date> .. <end_date>` 获取转载信息，优先筛选 AIToolsRecap、Axios 等聚合站点 |
| `"aggregate"` | 优先从 AIToolsRecap (`aitoolsrecap.com/Blog/`)、Buttondown (`buttondown.com/5minuteai/archive/`) 等聚合站点中获取该来源的新闻 |
| `"skip"` | 完全无法获取时跳过该数据源 |

**检测失败后的完整降级流程**：

```
html = curl 返回内容
result = check_cloudflare.py(html)
if result == 0:
    正常解析页面，提取文章列表
elif result == 1:  # Cloudflare challenge
    log_error("Cloudflare challenge blocked <url>")
    fallback = source.fallback
    if fallback == "search":
        WebSearch: "site:<domain> AI news <start_date> <end_date>"
        从搜索结果中筛选有价值的文章，用 WebFetch/curl 获取正文
    elif fallback == "aggregate":
        检查 aitoolsrecap.com/Blog/ 和 buttondown.com/5minuteai/archive/
        筛选来源为 <source.name> 的新闻
    elif fallback == "skip":
        log_error("Skipping <source.name> - no fallback available")
```

**注意**：WebFetch 工具对部分域名（如 `anthropic.com`、`openai.com`）会返回"Unable to verify if domain is safe"错误，这不属于 Cloudflare challenge。遇到此错误时直接降级为 curl 代理访问，若 curl 也返回 Cloudflare challenge 则再触发上述降级流程。

#### 5.2 爬取与筛选

- 使用 `WebFetch` 或 `curl` 获取页面内容
- 筛选 **`publish_date` 落在闭区间 `[start_date, end_date]` 内**（含端点）的文章/新闻；`start_date`、`end_date` 为第 1 节由 `setup_week.py` 标准输出确定的变量
- 提取文章标题、摘要、链接、发布日期
- 对于博客首页只列出标题的文章，可进一步 WebFetch 详情页链接获取摘要
- **所有 URL 访问失败时，必须将失败信息追加到 `weekly/$end_date/ai-trends/error.log`**（见第 3 节）

#### 5.3 查重并写入临时 JSON

对每篇新文章（`url` 不在 `archives.json` 中），将其信息追加到一个临时 JSON 文件 `weekly/$end_date/ai-trends/new.json`：

```json
[
  {
    "original_title": "Original Article Title",
    "en_summary": "English summary of the article content.",
    "cn_title": "中文标题",
    "cn_summary": "中文概述",
    "url": "https://example.com/article",
    "publish_date": "2026-05-08",
    "source": "数据源名称",
    "collected_at": "2026-05-11T10:30:00"
  }
]
```

### 6. 用搜索引擎补充

遍历完所有数据源后，使用 `WebSearch` 对未覆盖的领域进行补充搜索，关键词示例（将 **`start_date`**、**`end_date`** 替换为第 1 节确定的实际值）：
- `"AI news <start_date> .. <end_date>"`
- `"LLM 发布 <YYYY-MM>"`（月份可与 `start_date` / `end_date` 对齐）
- `"AI industry news this week"`

从搜索结果中挑选有价值的动态，用 `WebFetch` 或 `curl` 获取正文，同样经过查重后追加到 `new.json`。

### 7. 合并存档并生成 Markdown

使用 `merge_archives.py` 脚本将 `new.json` 合并到 `archives.json`（去重、原子写入、自动删除 `new.json`）：

```bash
python3 .agents/skills/ai-trends-weekly/scripts/merge_archives.py --end-date "$end_date"
```

- 脚本根据 `--end-date` 定位 `weekly/$end_date/ai-trends/` 目录
- 对 `new.json` 和 `archives.json` 进行反序列化验证，任一解析失败即报错退出并输出诊断信息（含 `JSON_REPAIR_NEEDED` 标记），由大模型根据错误信息修复后重新执行
- 按 `url` 去重后追加新条目，先写入 `archives.json.tmp` 再原子替换 `archives.json`
- 合并成功后自动删除 `new.json`

**日期校验（必须）**：合并后、写 Markdown 前，用共用脚本按 `publish_date` 过滤 `archives.json`，仅保留闭区间 **`[start_date, end_date]`** 内条目（含端点）。脚本将剔除项写入 stderr；退出码 `1` 表示有条目被剔除但仍已输出有效 JSON，可继续生成 Markdown。

```bash
python3 .agents/skills/_shared/scripts/filter_by_date.py \
  --start "$start_date" --end "$end_date" \
  --date-field publish_date \
  --input weekly/$end_date/ai-trends/archives.json > /tmp/ai-trends-filtered.json
```

- 生成 Markdown 时**仅依据** `/tmp/ai-trends-filtered.json`（或等价临时文件）中的条目，**不得**再直接使用未过滤的 `archives.json` 全文作为周期内列表
- 按重要程度排序后，**纳入周报正文展示的动态最多 50 条**（不足 50 则全部展示）；优先关注：
  - 大模型发布/更新（新版本、新能力）
  - AI 公司重要动向（融资、产品发布、战略调整）
  - 重要技术突破或开源项目
  - AI 政策和监管动态
  - AI 行业争议和负面事件

写入 `weekly/$end_date/AI-trends.md`：

```markdown
## <YYYY-MM-DD> AI 行业动态周报

### 本周 AI 行业动态

* **[中文标题 1](https://example.com/article-1)**：中文概述（2-3 句话概括核心信息）。📰 Anthropic Blog 📅 2026-05-05

* **[中文标题 2](https://example.com/article-2)**：中文概述。📰 OpenAI Blog 📅 2026-05-06

* **[中文标题 3](https://example.com/article-3)**：中文概述。📰 TechCrunch AI 📅 2026-05-07

### 参考来源

（与上文「本周 AI 行业动态」收录条目一致：同排序、同最多 50 条。）

1. [原始英文标题 1](https://example.com/article-1)
2. [原始英文标题 2](https://example.com/article-2)
3. [原始英文标题 3](https://example.com/article-3)
```

**展示规则**（排序后最多取 50 条写正文与参考来源）：
- **前 10 条**：在「### 本周 AI 行业动态」下**直接**按上述列表格式展示（含中文概述）。
- **第 11～50 条**（若存在）：全部放入 **`<details>`** 折叠块；**`<summary>`** 固定为 **`更多…（共 N 篇）`**，其中 **`N`** 为折叠区内条数（即正文第 11 条起的篇数）。折叠区内每条格式与外露部分相同：`* **[标题](url)**：概述。📰 来源 📅 日期`。
- **总条数 ≤10**：不使用 `<details>`。
- **总条数 >50**：仅取排序后的**前 50 条**参与正文与「参考来源」；其余不写入当周 `AI-trends.md`。
- **排版顺序建议**：`### 本周 AI 行业动态` 下先列外显 10 条 → 若有第 11 条及以后则紧跟 **`<details>`** 块 → 最后 **`### 参考来源`**（与正文收录条目一致）。

```markdown
<details>
<summary>更多…（共 N 篇）</summary>

* **[中文标题 11](https://example.com/article-11)**：中文概述。📰 来源 📅 2026-05-07

* **[中文标题 12](https://example.com/article-12)**：中文概述。📰 来源 📅 2026-05-08

</details>
```

### 8. 文件结构说明

```
weekly/
  <YYYY-MM-DD>/           # end_date 目录（由 setup_week.py 创建）
    AI-trends.md          # 汇总周报 Markdown 文件
    ai-trends/
      archives.json       # 历史文章存档，用于查重和增量更新
      error.log           # URL 访问失败日志，追加模式
config.json               # 仓库根目录：proxy 等（见第 2 节，jq ".proxy"）
scripts/
  setup_week.py           # 初始化周目录
  check_url.py            # 检查 URL 是否已收录
  merge_archives.py       # 合并 new.json → archives.json（去重、原子写入、清理）
  check_cloudflare.py     # 检测 HTML 是否为 Cloudflare challenge 页面
```

要求：
- 每条动态在 JSON 中保存原始标题、英文概述、中文标题、中文概述四个字段
- Markdown 中只呈现中文标题和中文概述
- 概述简明扼要，突出核心信息和影响
- 按重要程度从高到低排列
- 如有原文链接需附上链接
- 增量更新时 Markdown 文件从头生成（基于合并后的 archives.json），已有的旧条目保持不变，仅新增新条目
- `error.log` 每次运行追加写入，不清空，用于长期追踪失败的 URL 访问
- 使用 `check_url.py` 查重时，如果 JSON 解析失败（输出 `JSON_REPAIR_NEEDED`），根据脚本输出的详细错误信息修复 `archives.json`，修复后重新执行 `check_url.py`
- Markdown 中每个条目末尾的句号应紧接概述内容，与"来源"之间不应出现双句号（。。）
