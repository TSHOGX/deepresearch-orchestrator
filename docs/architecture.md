# Architecture

Deep Research is a multi-agent research system built on a three-phase workflow architecture.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interfaces                                 │
├─────────────────────────────────┬───────────────────────────────────────────┤
│   CLI (Rich/Textual)            │         Web Client (Next.js)              │
│   - Interactive mode            │    - React + Tailwind                     │
│   - Batch mode with JSON output │    - SSE real-time updates                │
│   - Session management          │    - Markdown rendering                   │
└─────────────────────────────────┴───────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API Gateway (FastAPI)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  REST: /api/research/*          │  Streaming: SSE /api/research/*/stream    │
│  - POST /start                  │  - Real-time progress events              │
│  - POST /confirm                │  - Multi-agent status aggregation         │
│  - GET /report                  │                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Research Orchestrator Service                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────────────┐    ┌─────────────┐              │
│  │  Phase 1    │ →  │     Phase 2         │ →  │  Phase 3    │              │
│  │  Planner    │    │   Researchers       │    │ Synthesizer │              │
│  │  (opus)     │    │   (sonnet × N)      │    │  (opus)     │              │
│  └─────────────┘    └─────────────────────┘    └─────────────┘              │
│         │                    │                        │                      │
│         └────────────────────┴────────────────────────┘                      │
│                              │                                               │
│              ┌───────────────▼───────────────┐                              │
│              │      Session Manager          │                              │
│              │  - State persistence (SQLite) │                              │
│              │  - Checkpoint & recovery      │                              │
│              └───────────────────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Agent Abstraction Layer                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  AgentExecutor (Abstract Base Class)                                        │
│  ├── execute(prompt, system_prompt, on_message) → ExecutionResult           │
│  └── execute_stream(prompt, system_prompt) → AsyncIterator[StreamMessage]   │
│                                                                              │
│  Providers:                                                                  │
│  ├── Claude CLI   - Subprocess invocation                                   │
│  └── OpenCode     - HTTP API to opencode serve                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Three-Phase Workflow

### Phase 1: Planning

The Planner Agent analyzes the user's query and generates a structured research plan.

```
User Query
    │
    ▼
┌─────────────────────────────────┐
│         Planner Agent           │
│         (opus model)            │
├─────────────────────────────────┤
│ 1. Understand core intent       │
│ 2. Identify key aspects         │
│ 3. Check for ambiguities        │
│ 4. Generate research items      │
└─────────────────────────────────┘
    │
    ├─── Clarifications needed? ──→ User Input ──┐
    │                                            │
    ▼                                            │
┌─────────────────────────────────┐              │
│       Research Plan             │◀─────────────┘
│  - understanding                │
│  - plan_items[]                 │
│    - topic                      │
│    - description                │
│    - key_questions              │
│  - estimated_time               │
└─────────────────────────────────┘
    │
    ▼
User Confirmation (skip/modify/confirm)
```

**Output**: `ResearchPlan` with multiple `PlanItem` entries.

### Phase 2: Research

Parallel Researcher Agents investigate each plan item independently.

```
                    Research Plan
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Researcher 1│  │ Researcher 2│  │ Researcher N│
│  (sonnet)   │  │  (sonnet)   │  │  (sonnet)   │
├─────────────┤  ├─────────────┤  ├─────────────┤
│ WebSearch   │  │ WebSearch   │  │ WebSearch   │
│ WebFetch    │  │ WebFetch    │  │ WebFetch    │
│ Analysis    │  │ Analysis    │  │ Analysis    │
└─────────────┘  └─────────────┘  └─────────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
              ┌─────────────────────┐
              │    AgentResult[]    │
              │  - topic            │
              │  - findings         │
              │  - sources          │
              │  - confidence       │
              └─────────────────────┘
```

**Key Features**:
- Parallel execution with configurable concurrency limit
- Independent context windows per agent
- Checkpoint saving every 60 seconds
- Individual agent failure doesn't block others

### Phase 3: Synthesis

The Synthesizer Agent combines all findings into a comprehensive report.

```
┌─────────────────────────────────┐
│      All Research Results       │
│  - Original query               │
│  - Research plan                │
│  - Agent results[]              │
└─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│       Synthesizer Agent         │
│         (opus model)            │
├─────────────────────────────────┤
│ 1. Integrate findings           │
│ 2. Resolve contradictions       │
│ 3. Identify patterns            │
│ 4. Draw conclusions             │
│ 5. Format citations             │
└─────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────┐
│      Markdown Report            │
│  - Executive Summary            │
│  - Key Findings                 │
│  - Analysis                     │
│  - Conclusions                  │
│  - Sources                      │
└─────────────────────────────────┘
```

## Core Components

### Orchestrator (`services/orchestrator.py`)

Central coordinator managing the three-phase workflow:

```python
class ResearchOrchestrator:
    async def start_research(query, language) -> ResearchSession
    async def run_planning_phase(session) -> ResearchPlan | list[str]
    async def confirm_plan(session, modifications, skip_items)
    async def run_research_phase(session) -> list[AgentResult]
    async def run_synthesis_phase(session) -> str
    async def resume_session(session_id) -> ResearchSession
```

### Agent Abstraction (`core/agent/`)

Provider-agnostic interface for AI agent execution:

```python
class AgentExecutor(ABC):
    @abstractmethod
    async def execute(prompt, system_prompt, on_message) -> ExecutionResult

    @abstractmethod
    async def execute_stream(prompt, system_prompt) -> AsyncIterator[StreamMessage]

# Factory functions
create_planner_executor() -> AgentExecutor
create_researcher_executor() -> AgentExecutor
create_synthesizer_executor() -> AgentExecutor
```

**Supported Providers**:

| Provider | Implementation | Connection |
|----------|---------------|------------|
| Claude CLI | `providers/claude_cli/` | Subprocess |
| OpenCode | `providers/opencode/` | HTTP API |

### Session Manager (`services/session_manager.py`)

Handles persistence and checkpoint recovery:

```python
class SessionManager:
    async def create_session(session) -> None
    async def get_session(session_id) -> ResearchSession
    async def update_session(session) -> None
    async def save_checkpoint(session) -> None
    async def restore_from_checkpoint(session_id) -> ResearchSession
    async def list_sessions(limit) -> list[ResearchSession]
```

**Storage**:
- SQLite database for session metadata
- JSON checkpoints in `data/checkpoints/`

### Event Bus (`services/event_bus.py`)

Publish-subscribe system for real-time updates:

```python
class EventBus:
    def subscribe(event_type, callback, session_id) -> Unsubscribe
    def subscribe_all(callback, session_id) -> Unsubscribe
    async def publish(event) -> None
```

**Event Types**:
- `PHASE_CHANGE` - Workflow phase transitions
- `PLAN_DRAFT` - Research plan generated
- `AGENT_STARTED` / `AGENT_PROGRESS` / `AGENT_COMPLETED`
- `SYNTHESIS_PROGRESS`
- `REPORT_READY`
- `CHECKPOINT_SAVED`
- `ERROR`

## Data Models

### Research Session

```python
class ResearchSession:
    session_id: str
    user_query: str
    detected_language: str
    phase: ResearchPhase
    plan: ResearchPlan | None
    agent_results: list[AgentResult]
    final_report: str | None
    clarification_history: list[tuple[str, str]]
    created_at: datetime
    updated_at: datetime
```

### Research Plan

```python
class ResearchPlan:
    understanding: str
    clarifications: list[str]
    plan_items: list[PlanItem]
    estimated_time_minutes: int

class PlanItem:
    id: str
    topic: str
    description: str
    scope: str
    priority: int
    key_questions: list[str]
    suggested_sources: list[str]
    status: PlanItemStatus
```

### Agent Result

```python
class AgentResult:
    agent_id: str
    plan_item_id: str
    topic: str
    findings: str
    sources: list[Source]
    confidence: float
    raw_notes: str
    execution_time: float
```

## Directory Structure

```
src/deep_research/
├── __init__.py
├── __main__.py                    # CLI entry
│
├── core/
│   └── agent/
│       ├── __init__.py            # Public exports
│       ├── base.py                # AgentExecutor ABC
│       ├── types.py               # Shared types
│       ├── factory.py             # Agent factory
│       └── providers/
│           ├── claude_cli/        # Claude CLI provider
│           └── opencode/          # OpenCode provider
│
├── services/
│   ├── orchestrator.py            # Workflow orchestration
│   ├── session_manager.py         # Persistence
│   └── event_bus.py               # Pub/sub events
│
├── models/
│   ├── research.py                # Domain models
│   └── events.py                  # Event definitions
│
├── agents/
│   ├── prompts.py                 # Prompt templates
│   └── schemas.py                 # JSON schemas
│
├── cli/
│   ├── main.py                    # CLI application
│   └── components.py              # Rich UI components
│
├── api/
│   ├── app.py                     # FastAPI application
│   └── routes/
│       ├── research.py            # Research endpoints
│       ├── config.py              # Config endpoints
│       └── health.py              # Health checks
│
└── config/
    └── settings.py                # Pydantic settings
```

## Design Principles

1. **Context Isolation**: Each researcher agent operates with independent context, preventing token bloat.

2. **Model Layering**: Opus for complex reasoning (planning, synthesis), Sonnet for parallel research tasks.

3. **Provider Abstraction**: Agent execution is decoupled from specific providers, enabling easy switching and extension.

4. **Checkpoint Recovery**: Long-running research can be resumed from the last checkpoint.

5. **Event-Driven Updates**: Real-time progress via pub/sub enables responsive UI updates.

6. **Language Matching**: System prompts include instructions to respond in the user's detected language.
