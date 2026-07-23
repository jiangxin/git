# ai-trends-weekly Scripts Tests

## 运行测试

```bash
cd .agents/skills/ai-trends-weekly/scripts
pytest -v
```

## Playwright（browser 抓取）

源配置 `fetch: "browser"` 或 HTTP 遇 Cloudflare 且 `browser_on_cloudflare`
（默认 `true`）时，脚本走 Python Playwright Chromium。

安装（可选，仅 browser 通道需要）：

```bash
pip install playwright
playwright install chromium
```

未安装时，browser 请求会记入 `error.log`，不会中断整次 `discover_and_fetch` 运行。
单元测试用 mock，不依赖本机 Chromium。

## 测试覆盖

### setup_week.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestComputeWeekDates` | 日期计算（参数化覆盖周一至周日、跨月场景） |
| `TestSetupWeek` | 目录创建 |

### site_store.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestSlugify` | ASCII / 中文名 / 空结果 fallback / 显式 slug 优先 |
| `TestClaimUrl` | O_EXCL 原子写入、并行竞态（同站仅一胜）、跨站首写胜 |
| `TestUrlIndex` | first-writer-wins、并发追加安全 |
| `TestSiteIndex` | later-wins 语义 |
| `TestIterArticles` | 遍历文章记录 |
| `TestResolveUniqueSlug` | 冲突后缀 `-2`、确定性（跨运行同 slug） |

### summary_io.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestParseSummary` | 合法 front matter 解析、缺失/malformed 返回 None |
| `TestValidateSummary` | 四必填字段校验、rank_hint 可选、类型检查 |
| `TestWriteAndLoad` | 写入/读取 roundtrip |
| `TestIterMissingSummaries` | 扫描缺 summary 的文章 |

### discover_and_fetch.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestExtractLinks` | HTML 链接提取 |
| `TestDateAllows` | 日期过滤策略 |
| `TestArticleGateAndTitle` | 标题/正文门禁 |
| `TestDiscoverAndFetchRun` | 端到端：产出 sites/ + url_index.jsonl、resume 跳过终态、跨源同 URL 仅一站、retry-errors、并行烟雾 |

### check_summaries.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestCheck` | 全有 summary exit 0、缺一篇非零 |

### render_ai_trends.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `test_format_item_shape` | 条目格式 |
| `test_sort_*` | rank_hint 排序 |
| `test_collect_entries_from_sidecars` | 从 sidecar 聚合 |
| `test_run_filters_and_renders` | 端到端渲染 |
| `test_quality_warning*` | QUALITY_WARNING 触发与跳过 |

### check_url.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestGetUrlIndex` | 加载 url_index.jsonl |
| `TestCheckUrl` | FOUND / NOT_FOUND |
| `TestMain` | 命令行入口、批量模式 |

### fetch_backends.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestParseFetchConfig` | `fetch` / `browser_on_cloudflare` 解析 |
| `TestFetchHtmlBackends` | http/browser 选择、Cloudflare 一次降级 |
| `TestBackoffRetry` | 429/5xx 可重试判定、指数退避 |
