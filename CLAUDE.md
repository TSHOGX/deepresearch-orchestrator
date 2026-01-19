# CLAUDE.md

## 项目概述

Deep Research 是一个多 Agent 深度研究系统，支持 Claude CLI 和 OpenCode 两种 Agent Provider。

## 端口分配

| 服务 | 端口 |
|-----|------|
| FastAPI 后端 | 12050 |
| Next.js 前端 | 12051 |
| OpenCode Server | 4096 |

## Agent 配置

| 角色 | 默认模型 | 用途 |
|-----|--------|------|
| Planner | `opus` | 分析问题，生成研究计划 |
| Researcher | `sonnet` | 并行执行具体研究任务 |
| Synthesizer | `opus` | 整合研究结果，生成报告 |

## 关键规范

- **Agent Provider**：支持 `claude_cli` 和 `opencode`
- **并行数量**：研究 Agent 数量 = 研究项数量，默认上限 10
- **语言检测**：提示词包含 `Respond in the same language as the user's query`
- **检查点**：每 60 秒保存，存储于 `data/checkpoints/`

## 文档索引

### 用户文档

| 文档 | 路径 | 说明 |
|-----|------|------|
| 架构设计 | `docs/architecture.md` | 系统架构和组件说明 |
| 使用指南 | `docs/usage.md` | CLI 和 Web 使用方法 |
| API 参考 | `docs/api.md` | REST API 和 SSE 端点 |
| 配置参考 | `docs/configuration.md` | 环境变量和设置 |

### 开发文档

| 文档 | 路径 | 说明 |
|-----|------|------|
| 开发索引 | `docs/development/README.md` | 开发文档导航 |
| Agent 重构方案 | `docs/development/core-agent-refactor-plan.md` | 多 Provider 抽象层 |
| 初版设计 | `docs/development/archive/` | 归档的设计文档 |

## 目录结构

```
src/deep_research/
├── core/agent/          # Agent 抽象层
│   └── providers/       # Claude CLI, OpenCode 实现
├── services/            # 编排器、会话管理
├── models/              # 数据模型
├── agents/              # Prompt 模板
├── cli/                 # 命令行界面
├── api/                 # REST API
└── config/              # 配置管理
```

## 常用命令

```bash
# 启动 OpenCode Server
opencode serve --port 4096

# CLI 交互模式
deep-research

# CLI 批量模式
deep-research -b "研究问题"

# API 服务
deep-research-api

# 运行测试
pytest
```
