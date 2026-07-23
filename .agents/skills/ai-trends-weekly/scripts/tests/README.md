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

### check_url.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestLoadArchives` | 有效 JSON、空文件、格式错误、非数组根节点 |
| `TestCheckUrl` | URL 精确匹配、不匹配、后缀不匹配 |
| `TestMain` | FOUND/NOT_FOUND 输出、批量模式、无参数错误、缺失 archives |

### fetch_backends.py

| 测试类 | 覆盖内容 |
|--------|---------|
| `TestParseFetchConfig` | `fetch` / `browser_on_cloudflare` 解析 |
| `TestFetchHtmlBackends` | http/browser 选择、Cloudflare 一次降级、缺失 playwright |
