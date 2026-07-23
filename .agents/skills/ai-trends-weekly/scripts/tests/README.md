# ai-trends-weekly Scripts Tests

## 运行测试

```bash
cd .agents/skills/ai-trends-weekly/scripts
pytest -v
```

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
