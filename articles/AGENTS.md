# articles/ 目录规范

## 文件命名

- 文件名以文章发布日期为前缀，格式 `YYYY-MM-DD`
- 日期取自文章的原始发布时间
- 示例：`2026-07-28-inside-anthropic.md`

## 目录结构

```
articles/
  AGENTS.md
  2026-07-28-inside-anthropic.md          # 英文原文
  2026-07-28-inside-anthropic-zh.md       # 中文翻译
  2026-07-28-inside-anthropic/            # 同名目录存放图片等附件
    image-1.png
    image-2.jpeg
```

## 翻译文件

- 原文为英文的，翻译为同名、以 `-zh` 结尾的 markdown 文档
- 示例：原文 `2026-07-28-inside-anthropic.md` → 译文 `2026-07-28-inside-anthropic-zh.md`

## 附件目录

- 文章中的图片等附件放在同名的目录中（不含 `.md` 后缀）
- 示例：`2026-07-28-inside-anthropic.md` 的附件放在 `2026-07-28-inside-anthropic/`
- Markdown 中图片引用格式：`![alt](2026-07-28-inside-anthropic/image.png)`
