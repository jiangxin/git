# Tech Trends Report

本工程通过两个 Agent Skill 自动生成技术趋势分析周报，输出到 `weekly/<YYYY-MM-DD>/` 目录。

## Skill 说明

| Skill | 触发方式 | 产出 |
|-------|---------|------|
| **ai-trends-weekly** | `/ai-trends-weekly [date]` | `weekly/<end_date>/AI-trends.md` — AI 行业动态 |
| **git-news-weekly** | `/git-news-weekly [date]` | `weekly/<end_date>/Git-news.md` — Git 技术动态 |

两个 skill 均收集一周内（`start_date` ~ `end_date`）的文章，由 Agent 为每篇文章撰写摘要，最终渲染为 Markdown 周报。数据源配置在各 skill 的 `references/sources.json` 中。

### 基本用法

```bash
# 生成本周 AI 行业动态周报
/ai-trends-weekly

# 生成指定日期的周报（以该日期所在周为周期）
/ai-trends-weekly 2026-07-28

# Git 技术动态同理
/git-news-weekly
/git-news-weekly 2026-07-28
```

### 工作流程（两个 skill 相同）

1. `setup_week.py` — 确定收集周期，创建输出目录
2. `discover_and_fetch.py` — 从数据源发现链接并抓取正文（RSS → HTML → fallback → 详情抓取）
3. Agent 为每篇文章写 `.summary.md` sidecar（中英双语摘要）
4. `check_summaries.py` — 校验摘要完备性
5. `cluster_articles.py` — 相似文章聚类
6. `render_ai_trends.py` / `render_git_news.py` — 渲染最终 Markdown 报告

## 需要登录态的网站

部分网站（如 `https://newsletter.pragmaticengineer.com/`）有付费墙或需要登录才能获取完整内容。这些数据源配置了 `fetch: "browser"` 和 `storage_state`，在抓取时会通过 Playwright 加载已保存的登录态 cookie。

### 登录态存储

登录态 cookie 数据保存在 `data/cache/` 目录下（已 gitignore），文件名对应数据源标识符：

```
data/cache/
  pragmaticengineer.json    # The Pragmatic Engineer
  anthropic.json            # Anthropic
```

`config.json` 中的 `playwright_storage_state_dir` 配置了该目录路径。

### 更新登录态

使用 Makefile 的 rule 打开浏览器进行手动登录，登录完成后自动保存 cookie 到 `data/cache/`：

```bash
# 1. 初始化（仅首次）
cp makefile.auth.example makefile.auth

# 2. 更新 The Pragmatic Engineer 的登录态
make auth-pragmaticengineer
```

执行后会：
1. 打开 headed 浏览器（playwright-cli）导航到 Substack 登录页
2. 用户在浏览器中手动完成登录（邮箱验证码或密码）
3. 登录成功后，`playwright-cli state-save` 将 cookie/localStorage 保存到 `data/cache/pragmaticengineer.json`
4. 后续 skill 运行时自动加载该登录态抓取完整内容

### 添加新的登录态数据源

在 `makefile.auth` 中参照现有格式添加新 target：

```makefile
# ── New Site ─────────────────────────────────────────────
NEWSITE_LOGIN_URL ?= https://example.com/login
NEWSITE_SESSION ?= newsite
NEWSITE_STATE_PATH ?= $(AUTH_DIR)/newsite.json

.PHONY: auth-newsite

auth-newsite:
	@mkdir -p $(AUTH_DIR)
	@echo "A browser window will open — please complete the login manually."
	playwright-cli -s=$(NEWSITE_SESSION) open "$(NEWSITE_LOGIN_URL)" --headed --persistent
	playwright-cli -s=$(NEWSITE_SESSION) state-save $(NEWSITE_STATE_PATH)
	@echo "State saved to $(NEWSITE_STATE_PATH)"
```

同时在对应 skill 的 `sources.json` 中为该数据源添加 `storage_state: "newsite"` 字段。
