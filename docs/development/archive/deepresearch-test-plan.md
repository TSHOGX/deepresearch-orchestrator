# Deep Research 测试验证方案

每阶段开发完成后的验证清单

---

## Week 1: 核心框架验证

### 1.1 项目初始化验证

```bash
# 验证命令
cd claudecli-deepresearch
python -c "import deep_research; print('✓ Package imported')"
```

**通过标准**: 无 ImportError

### 1.2 Claude CLI 执行器验证

```python
# tests/test_executor.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_executor_basic():
    """验证基础执行能力"""
    from deep_research.services.agent_executor import AgentExecutor

    executor = AgentExecutor()
    chunks = []

    async for chunk in executor.execute(
        prompt="Say 'test ok' and nothing else",
        system_prompt="You are a helpful assistant",
        model="haiku",  # 使用最便宜的模型测试
        tools=[]
    ):
        chunks.append(chunk)

    # 验证收到了响应
    assert len(chunks) > 0
    assert any("test" in c.content.lower() for c in chunks if c.content)

@pytest.mark.asyncio
async def test_executor_streaming():
    """验证流式输出"""
    executor = AgentExecutor()
    chunk_count = 0

    async for chunk in executor.execute(
        prompt="Count from 1 to 5",
        system_prompt="",
        model="haiku"
    ):
        chunk_count += 1

    assert chunk_count > 1  # 应该收到多个 chunk

@pytest.mark.asyncio
async def test_executor_with_tools():
    """验证工具调用"""
    executor = AgentExecutor()
    tool_called = False

    async for chunk in executor.execute(
        prompt="Search for 'test query' on the web",
        system_prompt="Use WebSearch tool",
        model="haiku",
        tools=["WebSearch"]
    ):
        if chunk.type == "tool_call":
            tool_called = True
            break

    assert tool_called
```

**手动验证**:
```bash
# 运行测试
pytest tests/test_executor.py -v

# 或快速手动测试
python -c "
import asyncio
from deep_research.services.agent_executor import AgentExecutor

async def test():
    executor = AgentExecutor()
    async for chunk in executor.execute('Say hello', '', 'haiku'):
        print(f'{chunk.type}: {chunk.content[:50] if chunk.content else \"\"}'[:80])

asyncio.run(test())
"
```

**通过标准**:
- ✓ 收到流式响应
- ✓ 正确解析 chunk 类型
- ✓ 工具调用被检测到

### 1.3 配置管理验证

```python
# tests/test_config.py
def test_settings_default():
    """验证默认配置"""
    from deep_research.config.settings import Settings

    settings = Settings()
    assert settings.planner_model in ["opus", "sonnet", "haiku"]
    assert settings.researcher_model in ["opus", "sonnet", "haiku"]
    assert settings.checkpoint_interval > 0

def test_settings_env_override():
    """验证环境变量覆盖"""
    import os
    os.environ["DR_PLANNER_MODEL"] = "haiku"

    from deep_research.config.settings import Settings
    settings = Settings()
    assert settings.planner_model == "haiku"
```

### 1.4 基础 API 验证

```bash
# 启动服务器
deep-research-server &

# 健康检查
curl http://localhost:8000/health
# 期望: {"status": "ok"}

# 关闭服务器
kill %1
```

---

## Week 2: 三阶段工作流验证

### 2.1 Planner Agent 验证

```python
# tests/test_planner.py
@pytest.mark.asyncio
async def test_planner_output_format():
    """验证 Planner 输出格式"""
    from deep_research.services.orchestrator import ResearchOrchestrator

    orchestrator = ResearchOrchestrator(...)

    result = await orchestrator.run_planning_phase_and_collect(
        query="研究 AI Agent 的发展趋势"
    )

    # 验证输出结构
    assert "understanding" in result
    assert "plan_items" in result
    assert len(result["plan_items"]) >= 1

    for item in result["plan_items"]:
        assert "id" in item
        assert "topic" in item
        assert "description" in item
```

**手动验证**:
```bash
# 命令行快速测试
python -c "
from deep_research.agents.prompts import PLANNER_SYSTEM_PROMPT
print('Planner prompt length:', len(PLANNER_SYSTEM_PROMPT))
print('Contains JSON format:', 'plan_items' in PLANNER_SYSTEM_PROMPT)
"
```

### 2.2 Researcher Agent 验证

```python
# tests/test_researcher.py
@pytest.mark.asyncio
async def test_single_researcher():
    """验证单个 Researcher"""
    orchestrator = ResearchOrchestrator(...)

    plan_item = PlanItem(
        id="test1",
        topic="Test topic",
        description="Test description"
    )

    result = await orchestrator._run_researcher("session1", plan_item)

    assert result.topic == "Test topic"
    assert len(result.sources) > 0
    assert result.findings is not None

@pytest.mark.asyncio
async def test_parallel_researchers():
    """验证并行执行"""
    import time

    start = time.time()

    # 创建 3 个研究项
    plan_items = [
        PlanItem(id=f"p{i}", topic=f"Topic {i}", description="...")
        for i in range(3)
    ]

    results = await orchestrator.run_research_phase_and_collect(plan_items)

    elapsed = time.time() - start

    assert len(results) == 3
    # 并行应该比串行快（假设每个 30 秒，并行应 < 60 秒）
    assert elapsed < 90  # 宽松阈值
```

### 2.3 Synthesizer Agent 验证

```python
# tests/test_synthesizer.py
@pytest.mark.asyncio
async def test_synthesizer_output():
    """验证报告生成"""
    # 模拟研究结果
    mock_results = [
        AgentResult(topic="Topic 1", findings="Finding 1...", sources=[...]),
        AgentResult(topic="Topic 2", findings="Finding 2...", sources=[...]),
    ]

    report = await orchestrator.run_synthesis_and_collect(
        query="Test query",
        plan=mock_plan,
        results=mock_results
    )

    # 验证 Markdown 结构
    assert "# " in report  # 有标题
    assert "## " in report  # 有二级标题
    assert "References" in report or "参考" in report
```

### 2.4 检查点系统验证

```python
# tests/test_checkpoint.py
@pytest.mark.asyncio
async def test_checkpoint_save_load():
    """验证检查点保存和恢复"""
    session_manager = SessionManager(...)

    # 创建测试会话
    session = ResearchSession(
        session_id="test123",
        phase=ResearchPhase.RESEARCHING,
        ...
    )

    # 保存检查点
    await session_manager.save_checkpoint("test123")

    # 加载检查点
    checkpoint = await session_manager.load_checkpoint("test123")

    assert checkpoint is not None
    assert checkpoint.session_id == "test123"
    assert checkpoint.phase == ResearchPhase.RESEARCHING
```

**集成测试 - 完整工作流**:
```bash
# 端到端测试脚本
python -c "
import asyncio
from deep_research.services.orchestrator import ResearchOrchestrator

async def e2e_test():
    orch = ResearchOrchestrator(...)

    # Phase 1
    print('Phase 1: Planning...')
    plan = await orch.run_planning_phase_and_collect('Test query')
    print(f'  Got {len(plan[\"plan_items\"])} items')

    # Phase 2 (只测试 1 个)
    print('Phase 2: Researching...')
    results = await orch.run_research_phase_and_collect(plan['plan_items'][:1])
    print(f'  Got {len(results)} results')

    # Phase 3
    print('Phase 3: Synthesizing...')
    report = await orch.run_synthesis_and_collect(...)
    print(f'  Report length: {len(report)} chars')

    print('✓ E2E test passed')

asyncio.run(e2e_test())
"
```

---

## Week 3: CLI 界面验证

### 3.1 Rich 组件验证

```python
# tests/test_cli_components.py
def test_plan_table_render():
    """验证计划表格渲染"""
    from deep_research.cli.components import render_plan_table
    from rich.console import Console
    from io import StringIO

    console = Console(file=StringIO(), force_terminal=True)

    plan = {"plan_items": [
        {"id": "p1", "topic": "Test", "priority": 1}
    ]}

    render_plan_table(console, plan)
    output = console.file.getvalue()

    assert "p1" in output
    assert "Test" in output

def test_progress_panel_render():
    """验证进度面板渲染"""
    from deep_research.cli.components import render_progress_panel

    agents = [
        {"id": "p1", "status": "running", "progress": 50},
        {"id": "p2", "status": "completed", "progress": 100}
    ]

    panel = render_progress_panel(agents)
    assert panel is not None
```

### 3.2 交互流程验证

**手动验证脚本**:
```bash
# 模拟用户输入的自动化测试
echo -e "Test research query\nconfirm\nY\ntest_report.md" | deep-research

# 验证输出文件
[ -f test_report.md ] && echo "✓ Report generated" || echo "✗ Report missing"

# 检查报告内容
head -20 test_report.md
```

**交互式验证清单**:
```
□ 欢迎界面正确显示
□ 输入提示正常工作
□ 计划表格清晰可读
□ 澄清问题正确列出
□ confirm/modify/cancel 选项可用
□ 进度面板实时更新
□ 报告正确渲染
□ 文件保存成功
```

---

## Week 4: API 服务验证

### 4.1 REST API 验证

```bash
# 启动服务器
deep-research-server &
sleep 2

# 测试 /start
SESSION=$(curl -s -X POST http://localhost:8000/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query"}' | jq -r '.session_id')

echo "Session: $SESSION"

# 测试 /status
curl -s http://localhost:8000/api/research/$SESSION | jq '.phase'
# 期望: "planning"

# 测试 /confirm
curl -s -X POST http://localhost:8000/api/research/$SESSION/confirm \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm"}'

# 等待完成后测试 /report
sleep 60
curl -s http://localhost:8000/api/research/$SESSION/report | head -100

kill %1
```

### 4.2 SSE 流验证

```bash
# 启动会话并监听 SSE
SESSION=$(curl -s -X POST http://localhost:8000/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"query": "Test"}' | jq -r '.session_id')

# 监听事件流（超时 10 秒）
timeout 10 curl -N http://localhost:8000/api/research/$SESSION/stream

# 期望看到:
# event: plan_draft
# data: {"session_id": "...", ...}
```

### 4.3 Python 客户端验证

```python
# tests/test_api_client.py
import httpx
import asyncio

@pytest.mark.asyncio
async def test_full_api_flow():
    """完整 API 流程测试"""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Start
        resp = await client.post("/api/research/start", json={"query": "Test"})
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        # Wait for plan
        await asyncio.sleep(5)

        # Confirm
        resp = await client.post(
            f"/api/research/{session_id}/confirm",
            json={"action": "confirm"}
        )
        assert resp.status_code == 200

        # Poll for completion
        for _ in range(60):
            resp = await client.get(f"/api/research/{session_id}")
            if resp.json()["phase"] == "completed":
                break
            await asyncio.sleep(2)

        # Get report
        resp = await client.get(f"/api/research/{session_id}/report")
        assert resp.status_code == 200
        assert len(resp.json()["report"]) > 100
```

---

## Week 5+: Web 界面验证

### 5.1 组件渲染验证

```bash
cd web
npm run build  # 构建应通过
npm run test   # 单元测试
```

### 5.2 E2E 验证 (Playwright)

```typescript
// tests/e2e/research.spec.ts
import { test, expect } from '@playwright/test';

test('complete research flow', async ({ page }) => {
  // 首页
  await page.goto('/');
  await expect(page.getByText('Deep Research')).toBeVisible();

  // 输入查询
  await page.fill('textarea', 'Test research query');
  await page.click('button:has-text("Start")');

  // 等待计划
  await expect(page.getByText('Research Plan')).toBeVisible({ timeout: 30000 });

  // 确认
  await page.click('button:has-text("Confirm")');

  // 等待进度
  await expect(page.getByText('Executing Research')).toBeVisible();

  // 等待报告
  await expect(page.getByText('Research Report')).toBeVisible({ timeout: 120000 });

  // 验证下载按钮
  await expect(page.getByText('Download')).toBeVisible();
});
```

---

## 快速验证命令汇总

```bash
# Week 1
pytest tests/test_executor.py tests/test_config.py -v
curl http://localhost:8000/health

# Week 2
pytest tests/test_planner.py tests/test_researcher.py tests/test_synthesizer.py -v
pytest tests/test_checkpoint.py -v
python scripts/e2e_workflow_test.py

# Week 3
pytest tests/test_cli_components.py -v
echo "test query" | timeout 120 deep-research --test-mode

# Week 4
pytest tests/test_api_client.py -v
./scripts/api_smoke_test.sh

# Week 5+
cd web && npm test && npm run build
npx playwright test
```

---

## 验收标准检查表

| 阶段 | 验收标准 | 验证方式 |
|------|---------|---------|
| W1 | CLI 执行器返回流式响应 | `pytest tests/test_executor.py` |
| W1 | 配置可通过环境变量覆盖 | `pytest tests/test_config.py` |
| W1 | API 健康检查返回 200 | `curl /health` |
| W2 | Planner 输出有效 JSON | `pytest tests/test_planner.py` |
| W2 | 并行研究正常工作 | `pytest tests/test_researcher.py` |
| W2 | 报告包含 Markdown 结构 | `pytest tests/test_synthesizer.py` |
| W2 | 检查点可保存/恢复 | `pytest tests/test_checkpoint.py` |
| W3 | CLI 完整流程可运行 | 手动测试 |
| W3 | 进度实时更新 | 视觉验证 |
| W4 | SSE 事件正确推送 | `curl -N /stream` |
| W4 | API 完整流程可用 | `./scripts/api_smoke_test.sh` |
| W5 | Web 构建成功 | `npm run build` |
| W5 | E2E 测试通过 | `npx playwright test` |
