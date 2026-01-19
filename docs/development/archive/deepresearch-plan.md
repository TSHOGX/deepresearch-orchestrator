# Deep Research System 完整设计计划

基于 Claude Code CLI 的多智能体深度研究系统

---

## 设计决策（用户确认）

| 决策项 | 选择 |
|-------|------|
| 报告语言 | 自动检测（根据用户输入） |
| 并行智能体数量 | 无上限，根据研究项灵活放缩 |
| 断点续传 | 支持（检查点恢复） |
| 模型选择 | 用户可配置 |

---

## 业界最佳实践总结

### 各平台工作流对比

| 平台 | 工作流模式 | 核心特点 | 时间 |
|------|-----------|---------|------|
| ChatGPT | 5阶段：查询澄清→任务分解→迭代搜索→内容分析→综合优化 | Plan-Act-Observe 循环，o3 模型 | 5-30分钟 |
| Gemini | 4阶段：计划→搜索→推理→报告 | 用户可编辑研究计划，Workspace 集成 | 5-10分钟 |
| Perplexity | 检索-推理-细化循环 | DeepSeek R1 + TTC 框架，极速 | 2-4分钟 |
| LangChain | 3阶段：范围界定→研究执行→报告生成 | 监督者-研究者模式，开源 | 可配置 |
| Anthropic | 编排者-工作者模式 | Opus+Sonnet 分层，动态检索 | 可配置 |

### 关键设计原则（来自 Anthropic）

1. **上下文隔离**：每个子智能体独立 200k token 上下文，防止令牌膨胀
2. **动态检索**：从宽到窄的搜索策略，迭代改进
3. **模型分层**：Opus 编排 + Sonnet 研究 + Haiku 简单任务
4. **工件系统**：大型发现存储到外部，通过轻量级引用连接
5. **检查点恢复**：支持长运行任务的断点续传

---

## 第一部分：整体系统设计

### 1.1 系统架构图

```
┌────────────────────────────────────────────────────────────────────┐
│                        用户界面层                                   │
├─────────────────────────────┬──────────────────────────────────────┤
│   CLI Client (Rich/Textual) │        Web Client (Next.js)          │
│   - 交互式对话               │    - React + Tailwind                │
│   - 滚动进度面板             │    - SSE 实时更新                    │
│   - Markdown 报告渲染        │    - Markdown 渲染/下载              │
└─────────────────────────────┴──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                     API 网关层 (FastAPI)                            │
├────────────────────────────────────────────────────────────────────┤
│  REST: /api/research/*      │  Streaming: SSE /api/stream/*        │
│  - POST /start              │  - 实时进度推送                       │
│  - POST /confirm-plan       │  - 多智能体状态聚合                   │
│  - GET /report              │                                      │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    研究协调服务层 (Orchestrator)                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐            │
│  │  Phase 1    │ →  │  Phase 2    │ →  │  Phase 3    │            │
│  │  Planner    │    │ Researchers │    │ Synthesizer │            │
│  │  (可配置)    │    │ (可配置×N)  │    │  (可配置)    │            │
│  └─────────────┘    └─────────────┘    └─────────────┘            │
│         │                  │                  │                    │
│         └──────────────────┴──────────────────┘                    │
│                            │                                       │
│              ┌─────────────▼─────────────┐                        │
│              │     Session Manager       │                        │
│              │  - 状态持久化 (SQLite)     │                        │
│              │  - 检查点和恢复            │                        │
│              └───────────────────────────┘                        │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                 Claude CLI 适配层 (Subprocess)                      │
├────────────────────────────────────────────────────────────────────┤
│  claude --print --output-format stream-json                        │
│         --system-prompt "{role_prompt}"                            │
│         --model {opus|sonnet|haiku}                                │
│         --tools "WebSearch,Read,Grep,Glob,WebFetch"               │
│         "{task_prompt}"                                            │
└────────────────────────────────────────────────────────────────────┘
```

### 1.2 三阶段工作流设计

**借鉴最佳实践**：
- Gemini 的用户可编辑计划
- Anthropic 的编排者-工作者模式
- LangChain 的上下文隔离
- Perplexity 的速度优化

```
Phase 1: Plan (规划阶段)
├─ 输入：用户模糊问题
├─ 处理：
│   ├─ Planner Agent (可配置模型) 分析问题
│   ├─ 生成 N 个研究方向（无上限）
│   ├─ 识别需要澄清的模糊点
│   └─ 返回结构化研究计划
├─ 输出：ResearchPlan JSON
└─ 用户交互：
    ├─ 显示计划供用户审阅
    ├─ 列出模糊点请求澄清
    ├─ 支持修改/确认
    └─ 循环直到用户确认

Phase 2: Research (研究阶段)
├─ 输入：确认的 ResearchPlan
├─ 处理：
│   ├─ 为每个研究方向 spawn Researcher Agent
│   ├─ 并行执行（数量 = 研究项数量，无上限）
│   ├─ 每个 Agent 独立上下文窗口
│   ├─ 迭代搜索：宽→窄策略
│   └─ 实时流式进度反馈
├─ 输出：AgentResult[]
├─ 检查点：定期保存进度，支持断点续传
└─ 特性：
    ├─ 工件外部化（大型发现存文件）
    ├─ 收敛检测（避免无限搜索）
    └─ 失败重试（单个失败不影响整体）

Phase 3: Synthesize (整合阶段)
├─ 输入：所有 AgentResult + 原始问题 + 研究计划
├─ 处理：
│   ├─ Synthesizer Agent (可配置模型)
│   ├─ 综合所有发现
│   ├─ 解决矛盾信息
│   ├─ 生成结构化报告
│   └─ 添加引用和来源
├─ 输出：Markdown 报告（语言自动检测）
└─ 特性：
    ├─ 流式输出（用户实时看到）
    ├─ 多语言支持（自动检测用户输入语言）
    └─ 导出 PDF/Markdown
```

### 1.3 数据流设计

```
用户输入 "研究 AI Agent 的最新发展趋势"
           │
           ▼
┌──────────────────────────────────────────┐
│ POST /api/research/start                 │
│ {query: "研究 AI Agent...", options: {}} │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ Planner Agent                            │
│ 系统提示：研究规划专家                    │
│                                          │
│ 输出：                                   │
│ {                                        │
│   "understanding": "用户想了解...",      │
│   "clarifications": [...],               │
│   "plan_items": [                        │
│     {id, topic, description, scope}...   │
│   ]                                      │
│ }                                        │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ SSE: plan_draft 事件                     │
│ 用户审阅并确认/修改                       │
└──────────────────────────────────────────┘
           │ (用户确认)
           ▼
┌──────────────────────────────────────────┐
│ 并行 spawn Researcher Agents             │
│                                          │
│ Agent 1 ─────┐                           │
│ Agent 2 ─────┼──→ 全部并行执行           │
│ Agent 3 ─────┤   （数量=研究项数）        │
│ ...    ─────┘                            │
│ Agent N                                  │
│                                          │
│ 每个 Agent:                              │
│ - 独立上下文窗口                          │
│ - 迭代搜索（宽→窄）                       │
│ - 工具调用：WebSearch, Read, WebFetch    │
│ - 返回结构化发现                          │
│                                          │
│ 检查点：每 60 秒保存进度                  │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ SSE: agent_progress 事件流               │
│ 实时显示每个 Agent 的状态                 │
└──────────────────────────────────────────┘
           │ (全部完成)
           ▼
┌──────────────────────────────────────────┐
│ Synthesizer Agent                        │
│ 系统提示：研究综合专家                    │
│                                          │
│ 输入：                                   │
│ - 原始问题                               │
│ - 研究计划                               │
│ - 所有 Agent 的发现                      │
│                                          │
│ 输出：Markdown 报告（语言自动检测）       │
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│ SSE: report_ready 事件                   │
│ 返回完整报告给用户                        │
└──────────────────────────────────────────┘
```

---

## 第二部分：前端 UI 设计

### 2.1 CLI 界面设计 (Rich/Textual)

**技术选型**：
- `rich`: 富文本终端输出
- `textual`: TUI 框架（可选，用于更复杂布局）
- `aiohttp`: 异步 HTTP 客户端

#### Phase 1: 规划阶段 UI

```
╭─────────────────────────────────────────────────────────────╮
│                    Deep Research System                      │
│                                                              │
│  A multi-agent research assistant powered by Claude          │
╰─────────────────────────────────────────────────────────────╯

? What would you like to research?
> 研究 2025 年 AI Agent 的最新发展趋势和技术架构

⠋ Analyzing your query...

╭─ Understanding ─────────────────────────────────────────────╮
│ 用户希望了解 2025 年 AI Agent 领域的最新进展，包括技术      │
│ 架构演进、主流框架、应用场景和未来趋势。                    │
╰─────────────────────────────────────────────────────────────╯

⚠ Clarifications Needed:
  • 是否关注特定类型的 Agent（如研究型、编码型、通用型）？
  • 是否需要包含开源框架的对比分析？

╭─ Research Plan ─────────────────────────────────────────────╮
│ ID  │ Topic                    │ Priority │ Status         │
├─────┼──────────────────────────┼──────────┼────────────────┤
│ p1  │ Multi-agent 架构模式     │ ★★★      │ pending        │
│ p2  │ 主流框架对比             │ ★★★      │ pending        │
│ p3  │ 企业应用案例             │ ★★       │ pending        │
│ p4  │ 性能与成本优化           │ ★★       │ pending        │
│ p5  │ 未来发展趋势             │ ★★       │ pending        │
╰─────────────────────────────────────────────────────────────╯

Estimated time: ~8 minutes

? Action [confirm/modify/cancel]:
```

#### Phase 2: 研究阶段 UI（滚动进度窗口）

```
╭─ Phase 2: Executing Research ───────────────────────────────╮
│                                                              │
│ ┌─ Agent p1: Multi-agent 架构模式 ────────────────────────┐ │
│ │ Status: [████████░░] 80%                                │ │
│ │ Action: WebSearch "orchestrator-worker pattern 2025"    │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ Agent p2: 主流框架对比 ────────────────────────────────┐ │
│ │ Status: [██████░░░░] 60%                                │ │
│ │ Action: Reading anthropic.com/engineering...            │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ Agent p3: 企业应用案例 ────────────────────────────────┐ │
│ │ Status: [████░░░░░░] 40%                                │ │
│ │ Action: Thinking about enterprise adoption...           │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ Agent p4: 性能与成本优化 ──────────────────────────────┐ │
│ │ Status: [██░░░░░░░░] 20%                                │ │
│ │ Action: WebSearch "LLM cost optimization strategies"    │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌─ Agent p5: 未来发展趋势 ────────────────────────────────┐ │
│ │ Status: ✓ Completed                                     │ │
│ │ Found: 12 sources, 8 key findings                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
╰─ Progress: 3/5 agents completed ── Checkpoint: 2 min ago ───╯
```

**滚动进度窗口实现**：
```python
# 使用 Rich Live 实现实时更新
with Live(layout, refresh_per_second=4, console=console) as live:
    async for event in stream_events():
        update_agent_panel(event)
        live.update(layout)
```

#### Phase 3: 整合阶段 UI

```
╭─ Phase 3: Synthesizing Report ──────────────────────────────╮
│                                                              │
│  ⣾ Analyzing findings...                                    │
│  ⣽ Cross-referencing sources...                             │
│  ⣻ Identifying patterns...                                  │
│  ⢿ Writing conclusions...                                   │
│                                                              │
╰─────────────────────────────────────────────────────────────╯

╭─ Research Report ───────────────────────────────────────────╮
│                                                              │
│ # 2025 年 AI Agent 发展趋势分析报告                         │
│                                                              │
│ ## 执行摘要                                                  │
│ 本报告综合分析了 2025 年 AI Agent 领域的最新发展...         │
│                                                              │
│ ## 1. 多智能体架构模式                                      │
│ ### 1.1 编排者-工作者模式                                   │
│ Anthropic 的研究表明，编排者-工作者模式相比单智能体...      │
│                                                              │
│ ## 2. 主流框架对比                                          │
│ | 框架 | 特点 | 适用场景 |                                   │
│ |------|------|---------|                                    │
│ | LangGraph | 状态图... | 复杂工作流 |                      │
│ ...                                                          │
│                                                              │
│ ## References                                                │
│ [1] Anthropic Engineering Blog...                            │
│ [2] LangChain Documentation...                               │
│                                                              │
╰─────────────────────────────────────────────────────────────╯

? Save report to file? [Y/n]: Y
? Filename [research_report.md]: ai_agent_trends_2025.md
✓ Report saved to ai_agent_trends_2025.md
```

### 2.2 Web 界面设计 (Next.js)

#### 页面结构

```
/                           # 首页 - 输入研究问题
/research/[session_id]      # 研究会话页面
/reports                    # 历史报告列表
/reports/[report_id]        # 报告详情页
/settings                   # 配置页面（模型选择等）
```

#### 核心组件

**1. QueryInput 组件**
```tsx
<div className="max-w-2xl mx-auto">
  <h1>Deep Research</h1>
  <textarea
    placeholder="What would you like to research?"
    className="w-full p-4 border rounded-lg"
  />
  <button>Start Research</button>
</div>
```

**2. PlanReview 组件**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Research Plan</CardTitle>
  </CardHeader>
  <CardContent>
    <Alert>{plan.understanding}</Alert>
    {plan.clarifications.map(c => (
      <ClarificationItem key={c.id} question={c} />
    ))}
    <Table>
      {plan.plan_items.map(item => (
        <EditablePlanItem key={item.id} item={item} />
      ))}
    </Table>
  </CardContent>
  <CardFooter>
    <Button onClick={confirm}>Confirm</Button>
    <Button variant="outline" onClick={modify}>Modify</Button>
  </CardFooter>
</Card>
```

**3. AgentProgress 组件（滚动窗口）**
```tsx
<div className="h-96 overflow-y-auto border rounded-lg p-4">
  {agents.map(agent => (
    <AgentCard key={agent.id}>
      <div className="flex justify-between">
        <span>{agent.topic}</span>
        <Badge variant={agent.status}>{agent.status}</Badge>
      </div>
      <Progress value={agent.progress} />
      <div className="text-sm text-gray-500 truncate">
        {agent.currentAction}
      </div>
    </AgentCard>
  ))}
</div>

{/* 实时日志滚动 */}
<div className="h-48 overflow-y-auto bg-gray-900 text-green-400 p-2 font-mono text-sm">
  {logs.map((log, i) => (
    <div key={i}>{log}</div>
  ))}
</div>
```

**4. ReportViewer 组件**
```tsx
<div className="prose max-w-none">
  <ReactMarkdown>{report}</ReactMarkdown>
</div>

<div className="flex gap-2 mt-4">
  <Button onClick={copyToClipboard}>
    <Copy /> Copy
  </Button>
  <Button onClick={downloadMarkdown}>
    <Download /> Download .md
  </Button>
  <Button onClick={downloadPDF}>
    <FileText /> Download PDF
  </Button>
</div>
```

#### SSE 实时更新 Hook

```tsx
// hooks/useSSE.ts
function useSSE(sessionId: string) {
  const [phase, setPhase] = useState<ResearchPhase>('planning');
  const [agents, setAgents] = useState<AgentProgress[]>([]);
  const [report, setReport] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(
      `/api/research/${sessionId}/stream`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.event_type) {
        case 'phase_change':
          setPhase(data.data.phase);
          break;
        case 'agent_progress':
          updateAgent(data.data);
          break;
        case 'report_ready':
          setReport(data.data.report);
          break;
      }
    };

    return () => eventSource.close();
  }, [sessionId]);

  return { phase, agents, report };
}
```

---

## 第三部分：后端 API 与智能体服务架构

### 3.1 API 端点设计

```python
# REST API
POST   /api/research/start          # 启动研究会话
GET    /api/research/{id}           # 获取会话状态
POST   /api/research/{id}/confirm   # 确认/修改计划
POST   /api/research/{id}/cancel    # 取消研究
POST   /api/research/{id}/resume    # 恢复中断的会话
GET    /api/research/{id}/report    # 获取最终报告

# SSE Streaming
GET    /api/research/{id}/stream    # 实时进度流

# 配置
GET    /api/config                  # 获取当前配置
PUT    /api/config                  # 更新配置

# 事件类型
- plan_draft          # 初版计划生成
- plan_updated        # 计划更新
- phase_change        # 阶段切换
- agent_started       # 子智能体启动
- agent_progress      # 进度更新
- agent_completed     # 子智能体完成
- checkpoint_saved    # 检查点已保存
- synthesis_progress  # 整合进度
- report_ready        # 报告完成
- error               # 错误
```

### 3.2 数据模型

```python
# models/research.py

class ResearchPhase(str, Enum):
    PLANNING = "planning"
    PLAN_REVIEW = "plan_review"
    RESEARCHING = "researching"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"

class PlanItem(BaseModel):
    id: str
    topic: str
    description: str
    scope: str | None = None
    priority: int = 1
    key_questions: list[str] = []
    suggested_sources: list[str] = []
    status: str = "pending"

class ResearchPlan(BaseModel):
    understanding: str
    clarifications: list[dict]
    plan_items: list[PlanItem]
    estimated_time_minutes: int

class AgentProgress(BaseModel):
    agent_id: str
    plan_item_id: str
    status: str  # running, thinking, tool_call, completed
    current_action: str | None
    tool_name: str | None
    progress_percent: int
    timestamp: datetime

class AgentResult(BaseModel):
    agent_id: str
    plan_item_id: str
    topic: str
    findings: str
    sources: list[dict]
    confidence: float
    raw_notes: str | None

class Checkpoint(BaseModel):
    """断点续传检查点"""
    session_id: str
    phase: ResearchPhase
    plan: ResearchPlan | None
    completed_agents: list[str]
    agent_results: list[AgentResult]
    pending_agents: list[str]
    timestamp: datetime

class ResearchSession(BaseModel):
    session_id: str
    user_query: str
    phase: ResearchPhase
    plan: ResearchPlan | None
    agent_results: list[AgentResult]
    final_report: str | None
    checkpoint: Checkpoint | None
    created_at: datetime
    updated_at: datetime
```

### 3.3 配置设计

```python
# config/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 模型配置 - 用户可配置
    planner_model: str = "opus"       # opus / sonnet / haiku
    researcher_model: str = "sonnet"  # opus / sonnet / haiku
    synthesizer_model: str = "opus"   # opus / sonnet / haiku

    # 执行配置
    agent_timeout: int = 300          # 单个 agent 超时(秒)
    checkpoint_interval: int = 60     # 检查点保存间隔(秒)

    # 语言配置
    language_mode: str = "auto"       # auto / zh / en

    # 会话配置
    session_ttl: int = 86400          # 24小时
    enable_checkpoints: bool = True   # 启用断点续传

    # 数据库
    database_url: str = "sqlite:///./data/sessions.db"

    class Config:
        env_file = ".env"
        env_prefix = "DR_"
```

### 3.4 Agent 提示词模板

#### Planner Agent

```python
PLANNER_SYSTEM_PROMPT = """You are a Research Planning Specialist.

## Your Task
Analyze the user's research query and create a comprehensive research plan.

## Process
1. Understand the core research intent
2. Identify any ambiguities that need clarification
3. Break down into specific, independent research topics
4. Estimate scope and suggest appropriate depth

## Output Format (JSON)
{
    "understanding": "Your interpretation of the research goal",
    "clarifications": [
        {"id": "c1", "question": "Question needing user input"}
    ],
    "plan_items": [
        {
            "id": "p1",
            "topic": "Specific research topic",
            "description": "What to investigate and why",
            "scope": "Constraints (time/domain/geography)",
            "key_questions": ["Question 1", "Question 2"],
            "suggested_sources": ["web", "arxiv", "github"],
            "priority": 1
        }
    ],
    "estimated_time_minutes": 10
}

## Guidelines
- Create as many plan items as needed for comprehensive coverage
- Each item should be independently researchable
- Prioritize based on relevance to user's core question
- Be specific about scope to avoid scope creep
- Respond in the same language as the user's query
"""
```

#### Researcher Agent

```python
RESEARCHER_SYSTEM_PROMPT_TEMPLATE = """You are a Deep Research Specialist.

## Your Focus
Topic: {topic}
Description: {description}
Scope: {scope}

## Key Questions to Answer
{key_questions}

## Research Protocol
1. **Search Broadly**: Start with wide queries, then narrow down
2. **Verify Information**: Cross-reference across multiple sources
3. **Analyze Deeply**: Extract insights, not just facts
4. **Note Limitations**: Acknowledge gaps and uncertainties
5. **Cite Sources**: Track all sources with URLs

## Search Strategy (From Wide to Narrow)
- Round 1: Broad exploration of the landscape
- Round 2: Focus on promising directions
- Round 3: Deep dive into specific findings
- Stop when: sufficient coverage OR diminishing returns

## Output Format (JSON)
{
    "topic": "{topic}",
    "summary": "Executive summary (2-3 sentences)",
    "key_findings": [
        {
            "finding": "Specific insight",
            "evidence": "Supporting data",
            "confidence": 0.9,
            "sources": [{"url": "...", "title": "..."}]
        }
    ],
    "data_points": [
        {"metric": "...", "value": "...", "source": "..."}
    ],
    "gaps_and_limitations": ["..."],
    "related_topics": ["Topics worth exploring further"]
}

## Quality Standards
- Minimum 5 distinct sources
- Include recent sources (last 2 years) when available
- Present conflicting viewpoints fairly
- Respond in the same language as the original query
"""
```

#### Synthesizer Agent

```python
SYNTHESIZER_SYSTEM_PROMPT = """You are a Research Synthesis Expert.

## Your Task
Integrate multiple research findings into a cohesive, professional report.

## Input
You will receive:
1. Original research question
2. Approved research plan
3. Findings from multiple specialist agents

## Report Structure (Markdown)

# {Title}

## Executive Summary
[2-3 paragraph overview]

## 1. Introduction
[Context, scope, methodology]

## 2. Key Findings
### 2.1 [Topic Area 1]
[Synthesized findings with [citations]]

### 2.2 [Topic Area 2]
...

## 3. Analysis
### 3.1 Trends and Patterns
### 3.2 Conflicting Perspectives
### 3.3 Implications

## 4. Conclusions
[Main takeaways]

## 5. Recommendations
[Actionable suggestions]

## 6. Limitations
[Gaps identified]

## References
[Numbered citations]

---
*Generated by Deep Research System*

## Quality Guidelines
- Write in clear, professional prose
- Maintain objectivity
- Include confidence levels for conclusions
- Target: 2000-5000 words depending on complexity
- Use the same language as the original query
"""
```

### 3.5 核心服务实现

#### Claude CLI 执行器

```python
# services/agent_executor.py
import asyncio
import json
from typing import AsyncIterator
from dataclasses import dataclass

@dataclass
class AgentChunk:
    type: str  # "thinking", "tool_call", "tool_result", "text", "result"
    content: str
    tool_name: str | None = None

class AgentExecutor:
    """封装 Claude CLI subprocess 调用"""

    def __init__(self, cli_path: str = "claude"):
        self.cli_path = cli_path

    async def execute(
        self,
        prompt: str,
        system_prompt: str,
        model: str = "sonnet",
        tools: list[str] | None = None,
        timeout: int = 300
    ) -> AsyncIterator[AgentChunk]:
        """执行 Claude CLI 并流式返回结果"""

        cmd = [
            self.cli_path,
            "--print",
            "--output-format", "stream-json",
            "--model", model,
            "--system-prompt", system_prompt,
        ]

        if tools:
            cmd.extend(["--tools", ",".join(tools)])

        cmd.append(prompt)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            async for line in self._read_stream(process.stdout, timeout):
                chunk = self._parse_stream_json(line)
                if chunk:
                    yield chunk
        finally:
            if process.returncode is None:
                process.terminate()

    async def _read_stream(self, stream, timeout: int) -> AsyncIterator[str]:
        """读取流式输出"""
        buffer = ""
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError()

            try:
                chunk = await asyncio.wait_for(
                    stream.read(4096),
                    timeout=min(remaining, 30)
                )
                if not chunk:
                    break
                buffer += chunk.decode('utf-8', errors='replace')

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        yield line
            except asyncio.TimeoutError:
                continue

    def _parse_stream_json(self, line: str) -> AgentChunk | None:
        """解析 stream-json 格式"""
        try:
            data = json.loads(line)
            msg_type = data.get("type")

            if msg_type == "assistant":
                content = data.get("message", {}).get("content", [])
                for block in content:
                    if block.get("type") == "text":
                        return AgentChunk(type="text", content=block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        return AgentChunk(
                            type="tool_call",
                            content=f"Calling {block.get('name')}",
                            tool_name=block.get("name")
                        )
                    elif block.get("type") == "thinking":
                        return AgentChunk(type="thinking", content=block.get("thinking", ""))

            elif msg_type == "result":
                return AgentChunk(type="result", content=data.get("result", ""))

        except json.JSONDecodeError:
            pass

        return None
```

#### 研究编排器

```python
# services/orchestrator.py
import asyncio
from typing import AsyncIterator

class ResearchOrchestrator:
    """管理三阶段工作流"""

    def __init__(
        self,
        executor: AgentExecutor,
        session_manager: SessionManager,
        settings: Settings
    ):
        self.executor = executor
        self.session_manager = session_manager
        self.settings = settings

    async def run_planning_phase(
        self, session: ResearchSession
    ) -> AsyncIterator[SSEEvent]:
        """Phase 1: 生成研究计划"""
        async for chunk in self.executor.execute(
            prompt=session.user_query,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            model=self.settings.planner_model,
            tools=["WebSearch"]
        ):
            yield self._create_event("agent_progress", chunk)

    async def run_research_phase(
        self, session: ResearchSession
    ) -> AsyncIterator[SSEEvent]:
        """Phase 2: 并行执行研究（数量=研究项数，无上限）"""
        plan_items = session.plan.plan_items

        # 为每个研究项创建任务
        tasks = []
        progress_queues = {}

        for item in plan_items:
            queue = asyncio.Queue()
            progress_queues[item.id] = queue
            task = asyncio.create_task(
                self._run_researcher(session.session_id, item, queue)
            )
            tasks.append(task)

            yield SSEEvent(
                event_type="agent_started",
                data={"agent_id": item.id, "topic": item.topic}
            )

        # 启动检查点保存任务
        checkpoint_task = asyncio.create_task(
            self._checkpoint_loop(session.session_id)
        )

        # 流式收集所有 agent 的进度
        async for event in self._merge_progress_streams(
            session.session_id, progress_queues
        ):
            yield event

        # 等待全部完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        checkpoint_task.cancel()

        # 收集结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                yield SSEEvent(
                    event_type="agent_failed",
                    data={"agent_id": plan_items[i].id, "error": str(result)}
                )
            else:
                yield SSEEvent(
                    event_type="agent_completed",
                    data={"agent_id": plan_items[i].id}
                )

    async def _checkpoint_loop(self, session_id: str):
        """定期保存检查点"""
        while True:
            await asyncio.sleep(self.settings.checkpoint_interval)
            await self.session_manager.save_checkpoint(session_id)

    async def run_synthesis_phase(
        self, session: ResearchSession
    ) -> AsyncIterator[SSEEvent]:
        """Phase 3: 综合生成报告"""
        synthesis_prompt = self._build_synthesis_prompt(
            session.user_query,
            session.plan,
            session.agent_results
        )

        async for chunk in self.executor.execute(
            prompt=synthesis_prompt,
            system_prompt=SYNTHESIZER_SYSTEM_PROMPT,
            model=self.settings.synthesizer_model,
            tools=[]
        ):
            yield self._create_event("synthesis_progress", chunk)

    async def resume_session(
        self, session_id: str
    ) -> AsyncIterator[SSEEvent]:
        """从检查点恢复会话"""
        checkpoint = await self.session_manager.load_checkpoint(session_id)
        if not checkpoint:
            raise ValueError("No checkpoint found")

        # 跳过已完成的 agent，只运行 pending 的
        pending_items = [
            item for item in checkpoint.plan.plan_items
            if item.id in checkpoint.pending_agents
        ]

        # 继续研究阶段
        # ...
```

### 3.6 项目目录结构

```
claudecli-deepresearch/
├── README.md
├── pyproject.toml
├── .env.example
│
├── src/
│   └── deep_research/
│       ├── __init__.py
│       ├── __main__.py              # CLI 入口
│       │
│       ├── api/                      # FastAPI 后端
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── routes/
│       │   │   ├── research.py       # 研究 API
│       │   │   ├── config.py         # 配置 API
│       │   │   └── health.py
│       │   └── middleware/
│       │       └── cors.py
│       │
│       ├── models/                   # 数据模型
│       │   ├── research.py
│       │   ├── events.py
│       │   └── checkpoint.py
│       │
│       ├── services/                 # 核心服务
│       │   ├── session_manager.py    # 会话 + 检查点管理
│       │   ├── orchestrator.py       # 工作流编排
│       │   ├── agent_executor.py     # CLI 执行器
│       │   └── event_bus.py          # 事件总线
│       │
│       ├── agents/                   # Agent 配置
│       │   └── prompts.py            # 提示词模板
│       │
│       ├── cli/                      # CLI 界面
│       │   ├── main.py
│       │   └── components.py         # Rich 组件
│       │
│       └── config/
│           └── settings.py           # 配置管理
│
├── web/                              # Next.js 前端
│   ├── package.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── research/[id]/page.tsx
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── QueryInput.tsx
│   │   ├── PlanReview.tsx
│   │   ├── AgentProgress.tsx
│   │   └── ReportViewer.tsx
│   └── hooks/
│       └── useSSE.ts
│
├── data/                             # 数据目录
│   ├── sessions.db                   # SQLite 数据库
│   └── checkpoints/                  # 检查点文件
│
├── tests/
│   ├── test_api/
│   ├── test_services/
│   └── test_cli/
│
└── scripts/
    ├── dev.sh
    └── start.sh
```

---

## 第四部分：实施计划

### Week 1: 核心框架

1. **项目初始化**
   - 创建 Python 项目结构
   - 配置 pyproject.toml
   - 设置开发环境

2. **Claude CLI 执行器**
   - 实现 subprocess 封装
   - 流式 JSON 解析
   - 错误处理和超时

3. **配置管理**
   - Settings 类实现
   - 环境变量支持
   - 模型选择配置

4. **基础 API**
   - FastAPI 应用
   - 健康检查端点
   - 基本路由

### Week 2: 三阶段工作流

1. **Planner Agent**
   - 提示词模板
   - 输出解析
   - 用户确认逻辑

2. **Researcher Agent**
   - 并行执行框架（无上限）
   - 进度收集
   - 结果聚合

3. **Synthesizer Agent**
   - 报告生成
   - 引用处理
   - 语言自动检测

4. **检查点系统**
   - 检查点数据模型
   - 保存和恢复逻辑
   - SQLite 存储

### Week 3: CLI 界面

1. **Rich 组件**
   - 欢迎界面
   - 计划展示表格
   - 进度面板（滚动窗口）

2. **交互逻辑**
   - 用户输入处理
   - 确认/修改流程
   - 断点恢复提示
   - 报告保存

### Week 4: API 服务

1. **完整 REST API**
   - 所有端点实现
   - 请求验证
   - 错误处理

2. **SSE 流**
   - 事件推送
   - 连接管理
   - 重连支持

3. **配置 API**
   - 获取/更新配置
   - 模型选择

### Week 5+: Web 界面（可选）

1. **Next.js 项目**
   - 基础布局
   - 路由设置
   - API 代理

2. **核心组件**
   - QueryInput
   - PlanReview
   - AgentProgress
   - ReportViewer
   - Settings

3. **SSE 集成**
   - useSSE hook
   - 实时更新

---

## 关键文件清单

| 文件路径 | 优先级 | 说明 |
|---------|-------|------|
| `src/deep_research/services/agent_executor.py` | P0 | Claude CLI 核心封装 |
| `src/deep_research/services/orchestrator.py` | P0 | 三阶段工作流编排 |
| `src/deep_research/services/session_manager.py` | P0 | 会话 + 检查点管理 |
| `src/deep_research/agents/prompts.py` | P0 | 三种 Agent 提示词 |
| `src/deep_research/config/settings.py` | P1 | 配置管理（模型选择） |
| `src/deep_research/cli/main.py` | P1 | CLI 入口和交互 |
| `src/deep_research/api/routes/research.py` | P1 | REST + SSE API |
| `src/deep_research/models/research.py` | P1 | 数据模型定义 |
| `web/app/research/[id]/page.tsx` | P2 | Web 研究会话页 |
| `web/hooks/useSSE.ts` | P2 | SSE 实时更新 |

---

## 依赖

```toml
[project]
name = "deep-research"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "sse-starlette>=2.0.0",
    "aiohttp>=3.9.0",
    "rich>=13.7.0",
    "aiosqlite>=0.19.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
]

[project.scripts]
deep-research = "deep_research.cli.main:main"
deep-research-server = "deep_research.api.app:run_server"
```

---

## 风险和缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Claude CLI 输出格式变化 | 高 | 抽象解析层，版本锁定 |
| 并行 Agent 超时 | 中 | 单个超时不影响整体，自动重试 |
| 上下文窗口溢出 | 中 | 工件外部化，结果压缩 |
| 幻觉问题 | 中 | 引用验证，用户最终确认 |
| 长时间运行中断 | 中 | 检查点恢复机制 |
| API 成本过高 | 中 | 模型分层，用户可配置 |
