# CLAUDE.md

## 端口分配

| 服务 | 端口 |
|-----|------|
| FastAPI 后端 | 12050 |
| Next.js 前端 | 12051 |
| 备用 | 12052+ |

## Claude CLI 模型选择

| 任务 | 模型 |
|-----|------|
| Planner Agent | `opus` |
| Synthesizer Agent | `opus` |
| Researcher Agent | `sonnet` |

```python
# 规划/整合 - opus
model="opus"

# 研究 - sonnet
model="sonnet"
```

## CLI 调用格式

```bash
claude --print --output-format stream-json --model {opus|sonnet} --system-prompt "..." "{prompt}"
```

## 关键规范

- **并行数量**：研究 Agent 数量 = 研究项数量，无上限
- **语言检测**：提示词包含 `Respond in the same language as the user's query`
- **检查点**：每 60 秒保存，存储于 `data/checkpoints/`

## 文档索引

- 设计方案：`deepresearch-plan.md`
- 测试方案：`deepresearch-test-plan.md`
- 任务参考：`TODO.md`
