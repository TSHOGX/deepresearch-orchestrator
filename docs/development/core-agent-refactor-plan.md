# Core Agent 抽象层重构方案

> 版本: v2.0
> 日期: 2026-01-15
> 状态: 待评审
> 更新: 根据反馈大幅简化，移除能力声明、工具配置、公共模型映射

## 1. 背景与动机

### 1.1 当前状态

项目经历了从 Claude CLI 到 OpenCode SDK 的迁移，产生了两套 executor 实现：

| 实现 | 文件 | 状态 |
|------|------|------|
| Claude CLI | `agent_executor.py` | 已删除 (未提交) |
| OpenCode SDK | `opencode_executor.py` | 新增 (未提交) |

### 1.2 问题

1. **强耦合**: Orchestrator 直接依赖具体的 executor 实现
2. **切换成本高**: 切换 agent provider 需要修改多处代码
3. **无法组合**: 无法在运行时选择不同的 agent 用于不同角色
4. **扩展困难**: 添加新 provider (如 Aider, Cursor Agent) 需要大量重复代码

### 1.3 目标

- 定义统一的 agent 执行接口
- 支持运行时切换 provider
- 保持向后兼容性
- 便于添加新的 agent provider

---

## 2. 现有代码分析

### 2.1 Claude CLI 实现特点

```python
class ClaudeExecutor:
    def __init__(self, model, timeout):
        ...

    async def execute(self, prompt, system_prompt, on_message) -> ExecutionResult:
        # subprocess 调用 claude CLI
        # 流式输出
        cmd = ["claude", "-p", "--verbose", "--output-format", "stream-json",
               "--dangerously-skip-permissions", ...]
        # 非流式输出
        cmd = ["claude", "-p", "--output-format", "json",
               "--dangerously-skip-permissions", ...]
        process = await asyncio.create_subprocess_exec(*cmd, ...)
```

**关键特性**:
- 通过 subprocess 调用 CLI
- 使用 `--dangerously-skip-permissions` 跳过权限检查（工具权限由 agent 自己处理）
- 无状态，每次调用独立
- 模型格式: `opus` / `sonnet` / `haiku`

**注意**: Claude CLI 不支持 token-level 的 JSON schema 强制，不需要 `--json-schema` 参数

### 2.2 OpenCode SDK 实现特点

```python
class OpenCodeExecutor:
    def __init__(self, model, timeout):
        ...

    async def execute(self, prompt, system_prompt, on_message) -> ExecutionResult:
        # HTTP API 调用
        session_id = await self._ensure_session()  # 内部管理 session
        async with http.post(f"{base_url}/session/{session_id}/message", ...) as resp:
            ...
```

**关键特性**:
- 通过 HTTP API 调用 OpenCode server
- Session 状态在 provider 内部管理，不暴露到公共接口
- 工具权限通过 `opencode.json` 配置（全部允许）
- 模型格式: `provider/model-id`

### 2.3 共同接口

两个实现已经自然形成了相同的接口模式：

```python
# 相同的数据结构
@dataclass
class ExecutionResult:
    success: bool
    content: str
    messages: list[StreamMessage]
    error: str | None
    execution_time: float

@dataclass
class StreamMessage:
    type: MessageType
    content: str
    raw: dict
    tool_name: str | None
    tool_input: dict | None

# 相同的方法签名
async def execute(prompt, system_prompt, on_message) -> ExecutionResult
async def execute_stream(prompt, system_prompt) -> AsyncIterator[StreamMessage]

# 相同的工厂函数
def create_planner_executor() -> Executor
def create_researcher_executor() -> Executor
def create_synthesizer_executor() -> Executor
```

### 2.4 Orchestrator 使用方式

```python
# orchestrator.py:156-157, 435, 613
executor = create_planner_executor()
result = await executor.execute(user_prompt, system_prompt)

executor = create_researcher_executor()
result = await executor.execute(user_prompt, system_prompt, on_message=callback)

executor = create_synthesizer_executor()
result = await executor.execute(user_prompt, system_prompt, on_message=callback)
```

**关键观察**: Orchestrator 只使用工厂函数和 `execute()` 方法，不关心具体实现。

---

## 3. 设计方案

### 3.1 架构概览

```
src/deep_research/
├── core/
│   └── agent/
│       ├── __init__.py          # 公共导出
│       ├── types.py             # 共享类型定义
│       ├── base.py              # ABC 基类定义
│       ├── factory.py           # 工厂 + 注册表
│       └── providers/
│           ├── __init__.py      # Provider 注册
│           ├── claude_cli/
│           │   ├── __init__.py
│           │   ├── executor.py  # Claude CLI 实现
│           │   └── config.yaml  # 模型映射等配置
│           └── opencode/
│               ├── __init__.py
│               ├── executor.py  # OpenCode 实现
│               └── config.yaml  # 模型映射等配置
├── config/
│   └── settings.py              # 新增 provider 配置
└── services/
    └── orchestrator.py          # 保持不变
```

**设计原则**:
- 工具权限由各 coding agent 自己处理，抽象层不管
- 模型映射在各 provider 目录下用 yaml 配置
- Session 等内部状态不暴露到公共接口

### 3.2 核心类型 (`types.py`)

```python
"""共享类型定义，与具体 provider 无关。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Union

class MessageType(Enum):
    """消息类型枚举。"""
    ASSISTANT = "assistant"
    RESULT = "result"
    SYSTEM = "system"
    ERROR = "error"
    TOOL_USE = "tool_use"

@dataclass
class StreamMessage:
    """流式消息。"""
    type: MessageType
    content: str
    raw: dict = field(default_factory=dict)
    tool_name: str | None = None
    tool_input: dict | None = None

@dataclass
class ExecutionResult:
    """执行结果。"""
    success: bool
    content: str
    messages: list[StreamMessage] = field(default_factory=list)
    error: str | None = None
    execution_time: float = 0.0

# 回调类型
MessageCallback = Callable[[StreamMessage], Union[None, Awaitable[None]]]
```

### 3.3 抽象基类 (`base.py`)

使用 ABC (Abstract Base Class) 定义接口，更直观易懂。

```python
"""Agent executor 抽象基类。"""

from abc import ABC, abstractmethod
from typing import AsyncIterator
from .types import ExecutionResult, StreamMessage, MessageCallback


class AgentExecutor(ABC):
    """Agent 执行器抽象基类。

    所有 agent provider 必须继承此类并实现抽象方法。
    """

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        system_prompt: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> ExecutionResult:
        """执行单次请求。"""
        pass

    @abstractmethod
    async def execute_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StreamMessage]:
        """流式执行。"""
        pass

    async def close(self) -> None:
        """释放资源（可选实现）。"""
        pass

    async def __aenter__(self) -> "AgentExecutor":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
```

**ABC vs Protocol 说明**:

| 特性 | ABC | Protocol |
|------|-----|----------|
| 继承要求 | 必须显式继承 | 不需要继承，只要方法签名匹配 |
| 类型检查 | 实例化时检查 | 静态类型检查 |
| 适用场景 | 明确的继承体系 | Duck typing |

对于我们的场景，ABC 更合适：provider 数量有限，显式继承更清晰。

### 3.4 配置管理

配置大幅简化，移除工具和 schema 相关配置。

**全局配置 (`settings.py`)**:

```python
class Settings(BaseSettings):
    # Agent Provider 选择
    agent_provider: str = Field(
        default="claude_cli",
        description="Active agent provider (claude_cli, opencode, etc.)"
    )

    # 逻辑模型名（各 provider 自己映射到具体模型）
    planner_model: str = Field(default="opus")
    researcher_model: str = Field(default="sonnet")
    synthesizer_model: str = Field(default="sonnet")
```

**Provider 配置 (`providers/claude_cli/config.yaml`)**:

```yaml
# Claude CLI provider 配置
name: claude_cli
version: "1.0"

# 模型映射：逻辑名 -> 实际模型名
models:
  opus: opus
  sonnet: sonnet
  haiku: haiku

# CLI 参数模板
cli:
  streaming: ["-p", "--verbose", "--output-format", "stream-json", "--dangerously-skip-permissions"]
  non_streaming: ["-p", "--output-format", "json", "--dangerously-skip-permissions"]
```

**Provider 配置 (`providers/opencode/config.yaml`)**:

```yaml
# OpenCode provider 配置
name: opencode
version: "1.0"

# 模型映射
models:
  opus: anthropic/claude-3-opus
  sonnet: anthropic/claude-3-sonnet
  haiku: anthropic/claude-3-haiku
  minimax: opencode/minimax-m2.1-free

# 服务器配置
server:
  host: 127.0.0.1
  port: 4096
```

### 3.5 工厂与注册表 (`factory.py`)

```python
"""Agent 工厂和注册表。"""

from typing import Type
from enum import Enum
from deep_research.config import get_settings
from .base import AgentExecutor


class AgentRole(Enum):
    """Agent 角色。"""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    SYNTHESIZER = "synthesizer"


class AgentRegistry:
    """Agent provider 注册表。"""

    _providers: dict[str, Type[AgentExecutor]] = {}
    _default: str | None = None

    @classmethod
    def register(cls, name: str, *, default: bool = False):
        """注册装饰器。"""
        def decorator(provider_cls: Type[AgentExecutor]):
            cls._providers[name] = provider_cls
            if default:
                cls._default = name
            return provider_cls
        return decorator

    @classmethod
    def get(cls, name: str | None = None) -> Type[AgentExecutor]:
        """获取 provider 类。"""
        name = name or cls._default
        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}")
        return cls._providers[name]


def create_executor(role: AgentRole, provider: str | None = None) -> AgentExecutor:
    """创建指定角色的 executor。"""
    settings = get_settings()
    provider = provider or settings.agent_provider

    # 获取角色对应的模型
    model_map = {
        AgentRole.PLANNER: settings.planner_model,
        AgentRole.RESEARCHER: settings.researcher_model,
        AgentRole.SYNTHESIZER: settings.synthesizer_model,
    }

    provider_cls = AgentRegistry.get(provider)
    return provider_cls(model=model_map[role])


# 向后兼容的工厂函数
def create_planner_executor() -> AgentExecutor:
    return create_executor(AgentRole.PLANNER)

def create_researcher_executor() -> AgentExecutor:
    return create_executor(AgentRole.RESEARCHER)

def create_synthesizer_executor() -> AgentExecutor:
    return create_executor(AgentRole.SYNTHESIZER)
```

---

## 4. 方案评审

### 4.1 优点

| 优点 | 说明 |
|------|------|
| **简洁** | 移除了不必要的能力声明和工具配置 |
| **低耦合** | Orchestrator 不依赖具体实现 |
| **易扩展** | 新增 provider 只需继承 ABC 并注册 |
| **各司其职** | 工具权限、模型映射由各 provider 自己管理 |
| **向后兼容** | 保留工厂函数签名 |

### 4.2 设计决策说明

| 决策 | 理由 |
|------|------|
| 不配置工具权限 | 各 coding agent 自己处理，Claude CLI 用 `--dangerously-skip-permissions` |
| 不支持 JSON Schema | Claude CLI 也不支持 token-level 限制，统一用 prompt 引导 |
| 模型映射在 provider 内 | 不同 provider 模型体系差异大，各自用 yaml 管理更灵活 |
| Session 状态内部化 | OpenCode 的 session 是实现细节，不暴露到公共接口 |
| 使用 ABC 而非 Protocol | Provider 数量有限，显式继承更清晰直观 |

---

## 5. 实现计划

### Phase 1: 基础结构 (低风险)

1. 创建目录结构 `core/agent/` 和 `core/agent/providers/`
2. 创建 `types.py` - 移入共享类型
3. 创建 `base.py` - 定义 ABC

### Phase 2: Provider 实现 (中风险)

1. 创建 `providers/claude_cli/`
   - `executor.py` - 从 git history 恢复并适配
   - `config.yaml` - 模型映射和 CLI 参数
2. 创建 `providers/opencode/`
   - `executor.py` - 从现有代码迁移
   - `config.yaml` - 模型映射和服务器配置

### Phase 3: 工厂整合 (中风险)

1. 创建 `factory.py` - 注册表和工厂函数
2. 更新 `settings.py` - 添加 `agent_provider` 配置
3. 在 `providers/__init__.py` 中注册所有 provider

### Phase 4: 集成测试 (高风险)

1. 更新 orchestrator 导入路径
2. 运行完整流程测试
3. 验证两个 provider 都能正常工作

---

## 6. 迁移指南

### 6.1 切换 Provider

```bash
# 环境变量
export AGENT_PROVIDER=opencode

# 或 .env 文件
AGENT_PROVIDER=opencode
```

### 6.2 添加新 Provider

```python
# providers/my_agent/__init__.py

from deep_research.core.agent import AgentExecutor, AgentRegistry, ExecutionResult

@AgentRegistry.register("my_agent")
class MyAgentExecutor(AgentExecutor):
    """自定义 agent 实现。"""

    def __init__(self, model: str):
        self.model = self._map_model(model)  # 内部处理模型映射

    def _map_model(self, logical_model: str) -> str:
        # 从 config.yaml 读取映射
        ...

    async def execute(self, prompt, system_prompt=None, on_message=None):
        # 实现执行逻辑，工具权限自己处理
        ...

    async def execute_stream(self, prompt, system_prompt=None):
        # 实现流式执行
        ...
```

---

## 7. 开放问题

1. **多 provider 组合**: 是否支持不同角色使用不同 provider？（如 planner 用 Claude CLI，researcher 用 OpenCode）

2. **错误处理统一**: 不同 provider 的错误类型差异大，是否需要统一的错误分类？

3. **超时配置**: 超时应该在全局配置还是各 provider 自己管理？

---

## 8. 附录

### A. 文件变更清单

| 操作 | 文件 |
|------|------|
| 新增 | `src/deep_research/core/__init__.py` |
| 新增 | `src/deep_research/core/agent/__init__.py` |
| 新增 | `src/deep_research/core/agent/types.py` |
| 新增 | `src/deep_research/core/agent/base.py` |
| 新增 | `src/deep_research/core/agent/factory.py` |
| 新增 | `src/deep_research/core/agent/providers/__init__.py` |
| 新增 | `src/deep_research/core/agent/providers/claude_cli/` |
| 新增 | `src/deep_research/core/agent/providers/opencode/` |
| 修改 | `config/settings.py` |
| 修改 | `services/orchestrator.py` |
| 删除 | `services/opencode_executor.py` (迁移到 providers/) |

### B. 依赖关系图

```
settings.py
    ↓
factory.py ──→ AgentRegistry
    ↓              ↓
base.py      providers/
    ↓         ├── claude_cli/
types.py      │   ├── executor.py
              │   └── config.yaml
              └── opencode/
                  ├── executor.py
                  └── config.yaml
```

