# Deep Research System - TODO

基于 Claude Code CLI 的多智能体深度研究系统开发进度追踪

---

## 📋 项目概览

- **设计文档**: `../deepresearch-plan.md`
- **测试方案**: `../deepresearch-test-plan.md`
- **技术栈**: Python + FastAPI + Rich + Next.js
- **核心依赖**: Claude Code CLI (`claude --print --output-format stream-json`)

---

## Week 1: 核心框架

### 1.1 项目初始化
- [ ] 创建项目目录结构
- [ ] 编写 `pyproject.toml`
- [ ] 创建 `.env.example`
- [ ] 验证: `python -c "import deep_research"`

### 1.2 Claude CLI 执行器
- [ ] 实现 `services/agent_executor.py`
  - [ ] subprocess 异步封装
  - [ ] stream-json 解析
  - [ ] 超时和错误处理
- [ ] 验证: `pytest tests/test_executor.py -v`

### 1.3 配置管理
- [ ] 实现 `config/settings.py`
  - [ ] 模型选择配置 (planner/researcher/synthesizer)
  - [ ] 环境变量支持 (DR_ 前缀)
  - [ ] 检查点配置
- [ ] 验证: `pytest tests/test_config.py -v`

### 1.4 基础 API
- [ ] 实现 `api/app.py` FastAPI 应用
- [ ] 实现 `api/routes/health.py`
- [ ] 验证: `curl http://localhost:8000/health`

---

## Week 2: 三阶段工作流

### 2.1 数据模型
- [ ] 实现 `models/research.py`
  - [ ] ResearchPhase 枚举
  - [ ] PlanItem, ResearchPlan
  - [ ] AgentProgress, AgentResult
  - [ ] ResearchSession, Checkpoint

### 2.2 Agent 提示词
- [ ] 实现 `agents/prompts.py`
  - [ ] PLANNER_SYSTEM_PROMPT
  - [ ] RESEARCHER_SYSTEM_PROMPT_TEMPLATE
  - [ ] SYNTHESIZER_SYSTEM_PROMPT

### 2.3 会话管理
- [ ] 实现 `services/session_manager.py`
  - [ ] SQLite 会话存储
  - [ ] 检查点保存/加载
  - [ ] 会话恢复逻辑
- [ ] 验证: `pytest tests/test_checkpoint.py -v`

### 2.4 工作流编排
- [ ] 实现 `services/orchestrator.py`
  - [ ] Phase 1: run_planning_phase()
  - [ ] Phase 2: run_research_phase() (并行，无上限)
  - [ ] Phase 3: run_synthesis_phase()
  - [ ] 检查点定时保存
- [ ] 验证: `pytest tests/test_planner.py tests/test_researcher.py tests/test_synthesizer.py -v`

### 2.5 事件系统
- [ ] 实现 `models/events.py` SSE 事件类型
- [ ] 实现 `services/event_bus.py`

### 2.6 集成测试
- [ ] 编写 `scripts/e2e_workflow_test.py`
- [ ] 验证: 完整三阶段流程

---

## Week 3: CLI 界面

### 3.1 Rich 组件
- [ ] 实现 `cli/components.py`
  - [ ] 欢迎面板
  - [ ] 计划表格
  - [ ] 进度面板 (滚动窗口)
  - [ ] 报告渲染
- [ ] 验证: `pytest tests/test_cli_components.py -v`

### 3.2 CLI 主程序
- [ ] 实现 `cli/main.py`
  - [ ] Phase 1 交互 (输入 → 计划 → 确认/修改)
  - [ ] Phase 2 进度显示 (Live 实时更新)
  - [ ] Phase 3 报告展示
  - [ ] 断点恢复提示
  - [ ] 文件保存
- [ ] 实现 `__main__.py` 入口

### 3.3 CLI 验证
- [ ] 手动测试完整流程
- [ ] 验证: `echo "test" | deep-research --test-mode`

---

## Week 4: API 服务

### 4.1 REST 端点
- [ ] 实现 `api/routes/research.py`
  - [ ] POST /api/research/start
  - [ ] GET /api/research/{id}
  - [ ] POST /api/research/{id}/confirm
  - [ ] POST /api/research/{id}/resume
  - [ ] GET /api/research/{id}/report

### 4.2 SSE 流
- [ ] 实现 GET /api/research/{id}/stream
  - [ ] plan_draft, phase_change 事件
  - [ ] agent_started, agent_progress, agent_completed 事件
  - [ ] synthesis_progress, report_ready 事件

### 4.3 配置端点
- [ ] 实现 `api/routes/config.py`
  - [ ] GET /api/config
  - [ ] PUT /api/config

### 4.4 API 验证
- [ ] 编写 `scripts/api_smoke_test.sh`
- [ ] 验证: `pytest tests/test_api_client.py -v`

---

## Week 5+: Web 界面 (可选)

### 5.1 Next.js 初始化
- [ ] 创建 `web/` 项目
- [ ] 配置 Tailwind + shadcn/ui

### 5.2 核心组件
- [ ] QueryInput.tsx
- [ ] PlanReview.tsx
- [ ] AgentProgress.tsx
- [ ] ReportViewer.tsx
- [ ] Settings.tsx

### 5.3 Hooks
- [ ] useSSE.ts
- [ ] useResearchSession.ts

### 5.4 页面
- [ ] app/page.tsx (首页)
- [ ] app/research/[id]/page.tsx
- [ ] app/settings/page.tsx

### 5.5 Web 验证
- [ ] `npm run build`
- [ ] `npx playwright test`

---

## 📁 文件清单

```
src/deep_research/
├── __init__.py
├── __main__.py
├── config/
│   └── settings.py          # Week 1
├── models/
│   ├── research.py          # Week 2
│   └── events.py            # Week 2
├── services/
│   ├── agent_executor.py    # Week 1 ⭐
│   ├── session_manager.py   # Week 2
│   ├── orchestrator.py      # Week 2 ⭐
│   └── event_bus.py         # Week 2
├── agents/
│   └── prompts.py           # Week 2 ⭐
├── cli/
│   ├── main.py              # Week 3
│   └── components.py        # Week 3
└── api/
    ├── app.py               # Week 1
    └── routes/
        ├── health.py        # Week 1
        ├── research.py      # Week 4
        └── config.py        # Week 4
```

⭐ = 核心文件，优先实现

---

## 🧪 验证检查点

| 里程碑 | 验证命令 | 预期结果 |
|-------|---------|---------|
| W1 完成 | `pytest tests/test_executor.py -v` | 流式响应正常 |
| W2 完成 | `python scripts/e2e_workflow_test.py` | 三阶段流程通过 |
| W3 完成 | `deep-research` 手动测试 | CLI 交互正常 |
| W4 完成 | `./scripts/api_smoke_test.sh` | API 全部 200 |
| W5 完成 | `npm run build` | 构建成功 |

---

## 📝 备注

- 并行智能体数量 = 研究项数量（无上限）
- 报告语言自动检测用户输入
- 模型选择用户可配置
- 支持检查点断点续传
