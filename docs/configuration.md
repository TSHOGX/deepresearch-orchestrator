# Configuration Guide

Deep Research is configured through environment variables, which can be set directly or via a `.env` file.

## Quick Setup

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

## Environment Variables

### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API server bind address |
| `API_PORT` | `12050` | API server port |

### Agent Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_PROVIDER` | `claude_cli` | Active provider: `claude_cli`, `opencode` |

**Provider Options**:

- `claude_cli` - Direct Claude CLI subprocess calls
- `opencode` - OpenCode server HTTP API

### Model Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `PLANNER_MODEL` | `opus` | Model for planner agent |
| `RESEARCHER_MODEL` | `sonnet` | Model for researcher agents |
| `SYNTHESIZER_MODEL` | `sonnet` | Model for synthesizer agent |

**Model Options** (logical names mapped by provider):

| Logical Name | Use Case | Cost |
|--------------|----------|------|
| `opus` | Complex reasoning, planning, synthesis | High |
| `sonnet` | General research, balanced quality/cost | Medium |
| `haiku` | Simple tasks, high volume | Low |

### OpenCode Provider Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCODE_HOST` | `127.0.0.1` | OpenCode server host |
| `OPENCODE_PORT` | `4096` | OpenCode server port |

### Research Settings

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `MAX_PARALLEL_AGENTS` | `10` | 1-50 | Maximum concurrent researcher agents |
| `AGENT_TIMEOUT_SECONDS` | `0` | 0+ | Per-agent timeout (0 = no timeout) |
| `CHECKPOINT_INTERVAL_SECONDS` | `60` | 10-300 | Checkpoint save interval |

### Data Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `./data` | Base data directory |
| `DATABASE_PATH` | `./data/sessions.db` | SQLite database path |
| `CHECKPOINTS_DIR` | `./data/checkpoints` | Checkpoint storage directory |
| `REPORTS_DIR` | `./output/reports` | Report output directory |

### Logging

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Logging verbosity |

## Example Configurations

### Development (Default)

```bash
# .env
AGENT_PROVIDER=opencode
PLANNER_MODEL=opus
RESEARCHER_MODEL=sonnet
SYNTHESIZER_MODEL=sonnet
MAX_PARALLEL_AGENTS=5
LOG_LEVEL=DEBUG
```

### Production

```bash
# .env
AGENT_PROVIDER=opencode
PLANNER_MODEL=opus
RESEARCHER_MODEL=sonnet
SYNTHESIZER_MODEL=opus
MAX_PARALLEL_AGENTS=20
AGENT_TIMEOUT_SECONDS=600
CHECKPOINT_INTERVAL_SECONDS=30
LOG_LEVEL=WARNING
```

### Cost-Optimized

```bash
# .env
AGENT_PROVIDER=opencode
PLANNER_MODEL=sonnet
RESEARCHER_MODEL=haiku
SYNTHESIZER_MODEL=sonnet
MAX_PARALLEL_AGENTS=10
```

### Quality-Focused

```bash
# .env
AGENT_PROVIDER=opencode
PLANNER_MODEL=opus
RESEARCHER_MODEL=opus
SYNTHESIZER_MODEL=opus
MAX_PARALLEL_AGENTS=5
```

### Claude CLI Direct

```bash
# .env
AGENT_PROVIDER=claude_cli
PLANNER_MODEL=opus
RESEARCHER_MODEL=sonnet
SYNTHESIZER_MODEL=opus
```

## Provider Configuration

### OpenCode Provider

OpenCode requires a running server and API key configuration.

**Setup**:

```bash
# Install OpenCode
curl -fsSL https://opencode.ai/install | bash

# Start OpenCode TUI to configure API keys
opencode
# In TUI: /connect → Select provider → Enter API key

# Start server
opencode serve --port 4096
```

**Verify**:

```bash
curl http://127.0.0.1:4096/health
```

### Claude CLI Provider

Claude CLI requires the `claude` command to be available and authenticated.

**Setup**:

```bash
# Install Claude CLI (if not already installed)
npm install -g @anthropic-ai/claude-cli

# Authenticate
claude login
```

**Verify**:

```bash
claude --version
claude -p "Hello"
```

## Port Allocation

| Service | Default Port | Variable |
|---------|--------------|----------|
| FastAPI Backend | 12050 | `API_PORT` |
| Next.js Frontend | 12051 | N/A (in web/package.json) |
| OpenCode Server | 4096 | `OPENCODE_PORT` |

## Data Directory Structure

```
data/
├── sessions.db          # SQLite database
└── checkpoints/
    └── {session_id}.json

output/
└── reports/
    └── research_report_{session_id}.md
```

## Runtime Configuration

Configuration can also be modified at runtime via the API:

```bash
# Get current config
curl http://localhost:12050/api/config

# Update config
curl -X PUT http://localhost:12050/api/config \
  -H "Content-Type: application/json" \
  -d '{"max_parallel_agents": 5}'
```

**Note**: Runtime changes are temporary and reset when the server restarts.

## Troubleshooting

### OpenCode Connection Failed

```
Error: OpenCode server not responding
```

**Solutions**:
1. Ensure OpenCode server is running: `opencode serve --port 4096`
2. Check port configuration matches: `OPENCODE_PORT=4096`
3. Verify server health: `curl http://127.0.0.1:4096/health`

### Claude CLI Not Found

```
Error: claude command not found
```

**Solutions**:
1. Install Claude CLI: `npm install -g @anthropic-ai/claude-cli`
2. Ensure `claude` is in PATH
3. Authenticate: `claude login`

### Database Errors

```
Error: Unable to open database
```

**Solutions**:
1. Ensure `DATA_DIR` exists and is writable
2. Check disk space
3. Delete corrupted database: `rm data/sessions.db`

### High Memory Usage

**Solutions**:
1. Reduce `MAX_PARALLEL_AGENTS`
2. Enable agent timeout: `AGENT_TIMEOUT_SECONDS=300`
3. Use smaller models: `RESEARCHER_MODEL=haiku`
