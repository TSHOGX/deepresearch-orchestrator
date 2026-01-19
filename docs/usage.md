# Usage Guide

Complete guide for using Deep Research CLI and Web interfaces.

## CLI Usage

### Basic Commands

```bash
# Interactive mode - prompts for query
deep-research

# Direct query
deep-research "Research the latest developments in AI agents"

# Auto-confirm plan (skip confirmation prompt)
deep-research -y "Your research question"

# Verbose logging
deep-research -v "Your research question"
```

### Batch Mode

Non-interactive mode for automation and scripting:

```bash
# Batch mode - auto-confirm, auto-save report
deep-research -b "Your research question"

# Custom output file
deep-research -b -o report.md "Your research question"

# JSON output for programmatic use
deep-research -b --json "Your research question"
```

**JSON Output Structure**:

```json
{
  "session_id": "64e11013-...",
  "query": "Your research question",
  "status": "completed",
  "plan": {
    "plan_items": [
      {"id": "p1", "topic": "...", "description": "...", "status": "completed"}
    ]
  },
  "findings": [
    {"agent_id": "researcher-p1", "topic": "...", "content": "..."}
  ],
  "report": "# Research Report\n...",
  "report_file": "./output/reports/research_report_64e11013.md",
  "execution_time_seconds": 180.5,
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Session Management

```bash
# List recent sessions
deep-research -l

# List without pager (for piping)
deep-research -l --no-pager

# Resume a session (full ID)
deep-research -r 64e11013-1234-5678-9abc-def012345678

# Resume with short ID prefix (8 chars)
deep-research -r 64e11013
```

### CLI Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--auto-confirm` | `-y` | Automatically confirm the research plan |
| `--batch` | `-b` | Batch mode: no prompts, auto-save report |
| `--output FILE` | `-o` | Output file path (default: auto-generated) |
| `--json` | | JSON output to stdout (progress to stderr) |
| `--resume ID` | `-r` | Resume a previous session |
| `--list` | `-l` | List recent sessions |
| `--no-pager` | | Disable pager for list output |
| `--verbose` | `-v` | Enable debug logging |

## Interactive Workflow

### Phase 1: Query Input

```
╭─────────────────────────────────────────────────────────────╮
│                    Deep Research System                      │
│                                                              │
│  A multi-agent research assistant powered by AI              │
╰─────────────────────────────────────────────────────────────╯

Enter your research question: Research 2025 AI agent trends
```

### Phase 2: Plan Review

The system may ask clarification questions:

```
⚠ Clarifications Needed:
  • Are you interested in specific agent types (research, coding, general)?
  • Should we include open-source framework comparisons?

Your answer: Focus on multi-agent architectures and enterprise use cases
```

After clarifications, a research plan is generated:

```
╭─ Research Plan ─────────────────────────────────────────────╮
│ ID  │ Topic                    │ Priority │ Status         │
├─────┼──────────────────────────┼──────────┼────────────────┤
│ p1  │ Multi-agent architectures│ ★★★      │ pending        │
│ p2  │ Enterprise adoption      │ ★★★      │ pending        │
│ p3  │ Performance optimization │ ★★       │ pending        │
│ p4  │ Future trends            │ ★★       │ pending        │
╰─────────────────────────────────────────────────────────────╯

Action [confirm/skip/feedback/cancel]:
```

**Options**:
- `confirm` (or `c`) - Proceed with the plan
- `skip` (or `s`) - Skip specific items (e.g., `s 2,3`)
- `feedback` (or `f`) - Provide feedback to refine the plan
- `cancel` - Abort the research

### Phase 3: Research Progress

```
╭─ Phase 2: Executing Research ───────────────────────────────╮
│                                                              │
│ ┌─ researcher-p1: Multi-agent architectures ─────────────┐  │
│ │ Status: [████████░░] 80%                               │  │
│ │ Action: WebSearch "orchestrator-worker pattern 2025"   │  │
│ └────────────────────────────────────────────────────────┘  │
│                                                              │
│ ┌─ researcher-p2: Enterprise adoption ───────────────────┐  │
│ │ Status: [██████░░░░] 60%                               │  │
│ │ Action: Reading enterprise case studies...             │  │
│ └────────────────────────────────────────────────────────┘  │
│                                                              │
╰─ Progress: 2/4 agents running ── Checkpoint: 1 min ago ─────╯
```

### Phase 4: Report

```
╭─ Research Report ───────────────────────────────────────────╮
│                                                              │
│ # 2025 AI Agent Development Trends                          │
│                                                              │
│ ## Executive Summary                                         │
│ This report analyzes the latest developments in AI agent    │
│ technology, focusing on multi-agent architectures...        │
│                                                              │
│ ## Key Findings                                              │
│ ...                                                          │
╰─────────────────────────────────────────────────────────────╯

Save report to file? [Y/n]: y
✓ Report saved to output/reports/research_report_64e11013.md
```

## Web Interface

### Starting the Services

```bash
# Terminal 1: Start OpenCode server
opencode serve --port 4096

# Terminal 2: Start API backend
deep-research-api

# Terminal 3: Start web frontend
cd web && npm run dev
```

Open http://localhost:12051 in your browser.

### Web Workflow

1. **Enter Query**: Type your research question and click "Start Research"

2. **Review Plan**:
   - View generated research plan
   - Edit or skip items if needed
   - Click "Confirm" to proceed

3. **Monitor Progress**:
   - Real-time progress updates via SSE
   - View each agent's status and current action
   - Checkpoint indicators

4. **View Report**:
   - Markdown-rendered report
   - Copy to clipboard
   - Download as .md file

## API Usage

### Starting a Research Session

```bash
# Start research
curl -X POST http://localhost:12050/api/research/start \
  -H "Content-Type: application/json" \
  -d '{"query": "Research AI agent trends"}'

# Response
{
  "session_id": "64e11013-...",
  "phase": "planning",
  "created_at": "2025-01-15T10:30:00Z"
}
```

### Confirming the Plan

```bash
curl -X POST http://localhost:12050/api/research/{session_id}/confirm \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm"}'
```

### Streaming Progress (SSE)

```bash
curl -N http://localhost:12050/api/research/{session_id}/stream
```

Events:
```
event: phase_change
data: {"session_id": "...", "old_phase": "planning", "new_phase": "researching"}

event: agent_progress
data: {"session_id": "...", "agent_id": "researcher-p1", "progress": 50}

event: report_ready
data: {"session_id": "...", "report_preview": "# Research Report..."}
```

### Getting the Report

```bash
curl http://localhost:12050/api/research/{session_id}/report
```

See [API Reference](api.md) for complete endpoint documentation.

## Tips and Best Practices

### Writing Good Research Queries

**Good queries** are specific and scoped:
- "Compare React and Vue.js for enterprise dashboard development in 2025"
- "Analyze the security implications of using LLMs in production applications"
- "Research best practices for multi-agent orchestration patterns"

**Avoid** overly broad queries:
- "Tell me about AI" (too broad)
- "Everything about programming" (no focus)

### Using Clarifications Effectively

When the system asks clarification questions:
- Provide specific constraints (time period, industry, technology)
- Mention what aspects are most important
- Exclude topics you don't need

### Optimizing Research Time

1. **Skip low-priority items**: Use `skip` to exclude less relevant topics
2. **Provide feedback**: Refine the plan before execution
3. **Use batch mode**: For automated/scheduled research
4. **Resume sessions**: Continue interrupted research instead of starting over

### Handling Long Research Sessions

- Sessions are checkpointed every 60 seconds
- Use `deep-research -l` to find previous sessions
- Resume with `deep-research -r SESSION_ID`
- Completed agents are preserved; only pending ones re-run
