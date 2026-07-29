# AI 技术点时间线 (2024-2026)

本文档记录了 2024 年末至 2026 年以来 AI、AI Coding 领域的重要技术点及其出现时间。

---

## 1. MCP (Model Context Protocol)

**出现时间**: 2024 年 11 月 25 日

**描述**: Anthropic 开源的模型上下文协议，为 AI 应用连接外部系统（数据源、工具、工作流）提供统一标准。

**相关链接**:
- Anthropic 官方博客: https://www.anthropic.com/news/model-context-protocol
- 官方网站: https://modelcontextprotocol.io
- 文档: https://modelcontextprotocol.io/docs

**说明**: MCP 被称为"AI 应用的 USB-C 接口"，让 Claude、ChatGPT 等 AI 助手能够标准化地连接到各种数据源和工具。

---

## 2. Vibe Coding (氛围编程)

**出现时间**: 2025 年 2 月

**提出者**: Andrej Karpathy

**描述**: 一种新兴的 AI 辅助编程范式，强调通过自然语言描述和 AI 协作来创建软件，降低编程门槛。开发者通过"氛围"（vibe）来描述想要的效果，AI 帮助实现代码。

**关键项目**:
- **BloopAI/vibe-kanban**: 2025-06-14 (27,569 stars)
  - https://github.com/BloopAI/vibe-kanban

- **datawhalechina/easy-vibe**: 2025-12-28 (18,583 stars)
  - https://github.com/datawhalechina/easy-vibe
  - "vibe coding 2026 | Your First Modern Coding Course Beginners to Master Step by Step."

**说明**: Vibe Coding 由 Andrej Karpathy 于 2025 年 2 月首次提出，是一种更直观、更自然的编程方式，用户通过描述想要什么，AI 帮助实现代码。2025 年下半年至 2026 年出现了多个相关的教程和工具。

---

## 3. SDD (Spec-Driven Development)

**出现时间**: 2025 年 7 月 28 日 (首个 MCP Server 实现)

**描述**: 规范驱动开发，一种面向 AI 编码助手的开发方法论，通过详细的规范文档来指导 AI 代理进行代码生成。

**关键项目**:
- **formulahendry/mcp-server-spec-driven-development**: 2025-07-28
  - https://github.com/formulahendry/mcp-server-spec-driven-development
  - 首个 SDD MCP Server 实现

- **Fission-AI/OpenSpec**: 2025-08-05 (62,956 stars)
  - https://github.com/Fission-AI/OpenSpec
  - https://openspec.dev/
  - "Spec-driven development (SDD) for AI coding assistants"

- **github/spec-kit**: 2025-08-21 (124,341 stars)
  - https://github.com/github/spec-kit
  - https://github.github.com/spec-kit/
  - "Toolkit to help you get started with Spec-Driven Development"

**说明**: SDD 强调通过详细的规范文档（spec files）来指导 AI 编码代理，而非简单的提示词，从而提高代码生成的质量和一致性。

---

## 4. Skills (AI Agent Skills)

**出现时间**: 2025 年 10 月 9 日 (首次实现) / 2025 年 10 月 16 日 (官方公告)

**描述**: AI 代理的技能系统，允许代理通过可重用的技能（skills）扩展功能，实现特定任务的自动化。技能以 SKILL.md 文件形式定义，包含指令、脚本和资源，代理在需要时自动加载相关技能。

**起源**:
- **首次实现**: obra/superpowers 项目 (2025-10-09)
  - https://github.com/obra/superpowers (262,741 stars)
  - "An agentic skills framework & software development methodology that works."
  - 官方博客公告: https://blog.fsck.com/2025/10/09/superpowers/

- **官方公告**: Anthropic Claude 官方博客 (2025-10-16)
  - https://claude.com/blog/skills
  - 标题: "Introducing Agent Skills"
  - 发布日期: Oct 16, 2025

**关键生态项目**:
- **jeremylongshore/claude-code-plugins-plus-skills**: 2025-10-10 (2,564 stars)
  - https://github.com/jeremylongshore/claude-code-plugins-plus-skills
  - "425 plugins, 2,810 skills, 200 agents for Claude Code. Open-source marketplace at tonsofskills.com"

- **FrancyJGLisboa/agent-skill-creator**: 2025-10-18 (1,989 stars)
  - https://github.com/FrancyJGLisboa/agent-skill-creator
  - "Turn any workflow into reusable AI agent skills that install on 17 platforms — Claude Code, Copilot, Cursor, Windsurf, Codex, Gemini, Kiro, and more. One SKILL.md, every platform."

- **microsoft/skills**: 2026-01-16 (2,833 stars)
  - https://github.com/microsoft/skills
  - "Skills, MCP servers, Custom Agents, Agents.md for SDKs to ground Coding Agents"

- **VoltAgent/awesome-openclaw-skills**: 2026-01-25 (51,576 stars)
  - https://github.com/VoltAgent/awesome-openclaw-skills
  - https://clawskills.sh/
  - "The awesome collection of OpenClaw skills. 5,400+ skills filtered and categorized from the official OpenClaw Skills Registry."

**说明**: Skills 系统由 obra/superpowers 项目于 2025-10-09 首次实现，Anthropic 于 2025-10-16 在 Claude 官方博客正式发布介绍文章。随后被 Claude Code、OpenClaw、Cursor、Codex 等多个 AI 编码工具采纳。技能以 SKILL.md 文件格式定义，可以被代理自动发现和调用。用户可以通过安装技能来赋予代理新的能力，如邮件管理、日历控制、代码审查等。技能也可以被代理自己创建和修改。

---

## 5. OpenClaw

**出现时间**: 2025 年 11 月 24 日

**描述**: 开源的个人 AI 助手项目，可在本地运行，支持多种聊天平台（WhatsApp、Telegram 等），能够执行实际任务。

**相关链接**:
- GitHub: https://github.com/openclaw/openclaw (384,438 stars)
- 官方网站: https://openclaw.ai
- 文档: https://docs.openclaw.ai/

**说明**: OpenClaw 是 GitHub 上增长最快的项目之一，5 个月内获得 346k+ stars。它是一个可以在用户本地机器上运行的 24/7 AI 助手，能够访问文件、邮件、日历等，并通过技能（Skills）系统扩展功能。被描述为"真正能做事的 AI"。

---

## 6. Harness Engineering (驾驭工程)

**出现时间**: 2026 年 3 月 31 日

**描述**: 一种面向 AI 代理的系统工程方法，涉及优化系统提示、路由、检索和编排代码，以提高 AI 代理的性能和可靠性。

**关键项目**:
- **raphaelchristi/harness-evolver**: 2026-03-31
  - https://github.com/raphaelchristi/harness-evolver
  - "Automated harness evolution for AI agents. A Claude Code plugin that iteratively optimizes system prompts, routing, retrieval, and orchestration code using full-trace counterfactual diagnosis."

- **codylindley/ai-harness-engineering-compatibility-matrix**: 2026-04-14
  - https://github.com/codylindley/ai-harness-engineering-compatibility-matrix
  - "AI agent config compatibility matrix — which configuration files are read by which AI coding tools"

**相关资源**:
- **mrgizmo212/make-no-mistakes**: 2026-06-24
  - "Agent harness research ebook — model-agnostic architecture specification (June 2026)"

- **microsoft/Build26-BRK243-claw-and-agent-harness-in-microsoft-foundry**: 2026-04-10
  - "Resources for building and deploying agents using Claw and agent harness in Microsoft Foundry"

**说明**: Harness Engineering 关注如何"驾驭"AI 代理，通过系统化的工程方法优化代理的行为和性能。OpenClaw 等项目被认为是早期的 agent harness 实现。

---

## 7. Loop Engineering (循环工程)

**出现时间**: 2026 年 6 月 9 日

**描述**: 一种设计和编排 AI 编码代理的模式和方法论，关注如何构建有效的代理循环（agent loops）来完成复杂任务。

**关键项目**:
- **cobusgreyling/loop-engineering**: 2026-06-09 (9,552 stars)
  - https://github.com/cobusgreyling/loop-engineering
  - https://cobusgreyling.github.io/loop-engineering/
  - "Practical patterns, starters & CLI tools for loop engineering with AI coding agents. Design systems that prompt and orchestrate agents (inspired by Addy Osmani and Boris Cherny). Includes loop-audit, loop-init, loop-cost."

- **alchaincyf/loop-engineering-orange-book**: 2026-06-15 (1,054 stars)
  - https://github.com/alchaincyf/loop-engineering-orange-book
  - "别再问我什么是 Loop Engineering — 橙皮书系列。A plain-language guide to loop engineering (中文 + English PDF). Free."

**说明**: Loop Engineering 受到 Addy Osmani 和 Boris Cherny 等人的启发，提供了一套实用的模式和工具来设计、审计和优化 AI 代理的工作循环。相关工具包括 loop-audit、loop-init、loop-cost 等。

---

## 其他相关技术

### Context Engineering (上下文工程)
- 关注如何为 AI 代理提供有效的上下文信息
- 相关项目: dair-ai/Prompt-Engineering-Guide (77,100 stars)

### Agentic Coding (代理编程)
- 使用 AI 代理自主完成编码任务
- 相关项目:
  - obra/superpowers (262,737 stars)
  - affaan-m/ECC (234,860 stars)

---

## 技术全景

| 时间 | 技术点 | 核心主题 |
|------|--------|----------|
| 2024-11 | MCP | AI 应用连接外部系统的统一协议标准 |
| 2025-02 | Vibe Coding | 自然语言驱动的 AI 协作编程范式 |
| 2025-07 | SDD | 以规范文档指导 AI 代理代码生成 |
| 2025-10 | Skills | AI 代理的可复用技能扩展体系 |
| 2025-11 | OpenClaw | 本地运行的开源个人 AI 助手 |
| 2026-03 | Harness Engineering | 系统化驾驭和优化 AI 代理行为 |
| 2026-06 | Loop Engineering | 设计和编排 AI 代理工作循环 |

---

*文档生成时间: 2026-07-29*
