# Deep Research

A multi-agent deep research system that conducts comprehensive research through parallel AI agents.

## Overview

Deep Research breaks down complex research questions into parallel investigation tasks, executes them concurrently, and synthesizes findings into comprehensive reports.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Three-Phase Workflow                         │
├─────────────────┬─────────────────────┬─────────────────────────┤
│   Phase 1       │      Phase 2        │       Phase 3           │
│   Planning      │     Research        │      Synthesis          │
│                 │                     │                         │
│  Query → Plan   │  Parallel Agents    │  Findings → Report      │
│  (configured)   │  (configured)       │  (configured)           │
└─────────────────┴─────────────────────┴─────────────────────────┘
```

## Features

- **Three-Phase Workflow**: Planning → Parallel Research → Synthesis
- **Parallel Execution**: Multiple researcher agents work concurrently
- **Checkpoint Recovery**: Resume interrupted research sessions
- **Multiple Interfaces**: CLI (interactive/batch) and Web UI
- **Multi-Provider Support**: Codex CLI (default), OpenCode, Claude CLI (optional)
- **Language Auto-Detection**: Responds in user's language

## Quick Start

### Prerequisites

Install Codex CLI and authenticate:

```bash
# Authenticate
codex login

# Verify
codex --version
```

Optional (if using OpenCode provider):

```bash
opencode serve --port 4096
```

### Installation

```bash
# Clone and install
git clone <repo-url>
cd deepresearch-orchestrator
pip install -e ".[dev]"
```

### Usage

```bash
# Interactive mode
deep-research

# With query
deep-research "Your research question"

# Auto-confirm plan
deep-research -y "Your research question"

# Batch mode (non-interactive)
deep-research -b "Your research question"

# JSON output
deep-research -b --json "Your research question"

# Resume session
deep-research -r SESSION_ID

# List sessions
deep-research -l
```

See [Usage Guide](docs/usage.md) for complete CLI reference.

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System design and component overview |
| [Usage Guide](docs/usage.md) | Complete CLI and API usage |
| [Configuration](docs/configuration.md) | Environment variables and settings |
| [API Reference](docs/api.md) | REST API and SSE endpoints |
| [Development](docs/development/) | Internal design documents |

## Project Structure

```
src/deep_research/
├── cli/           # Command-line interface
├── api/           # FastAPI REST/SSE server
├── core/agent/    # Agent abstraction layer
│   └── providers/ # Codex CLI, Claude CLI, OpenCode implementations
├── services/      # Orchestrator, session management
├── models/        # Data models
└── agents/        # Prompt templates
```

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_PROVIDER` | `codex_cli` | Agent provider (`codex_cli`, `opencode`, `claude_cli`) |
| `PLANNER_MODEL` | provider default | Model for planning |
| `RESEARCHER_MODEL` | provider default | Model for research |
| `MAX_PARALLEL_AGENTS` | `10` | Concurrent researcher limit |

See [Configuration Guide](docs/configuration.md) for all options.

Model names are provider-specific; see the configuration guide for mappings.

## Ports

| Service | Port |
|---------|------|
| FastAPI Backend | 12050 |
| Next.js Frontend | 12051 |
| OpenCode Server | 4096 |

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests

# Start API server
deep-research-api

# Start web frontend
cd web && npm run dev
```

## Roadmap

### Observability & Analytics

- [ ] **Cost Tracking**: Token usage and API cost statistics per session/agent
- [ ] **Execution Metrics**: Detailed timing breakdown for each phase
- [ ] **Usage Dashboard**: Historical statistics and trends

### CLI/TUI Improvements

- [ ] **Planning Progress**: Show progress during thinking phase (currently only shows during tool calls)
- [ ] **Resume Polish**: Improve UX for resuming at different phases (plan review, mid-research, etc.)
- [ ] **Session Search**: Add search/filter for `deep-research -l` (by query, date, status)
- [ ] **Edge Cases**: Handle various TUI edge cases (terminal resize, long text, etc.)
- [ ] **Error Recovery**: Better error messages and recovery suggestions

### Web UI

- [ ] **Full Testing**: Comprehensive testing of all workflows
- [ ] **Mobile Responsive**: Optimize for mobile devices
- [ ] **Dark Mode**: Theme support

### Architecture Enhancements

- [ ] **Recursive Research**: Allow researchers to spawn sub-agents for deeper investigation
  ```
  Researcher Agent
      │
      ├─→ Sub-query 1 → Sub-researcher
      └─→ Sub-query 2 → Sub-researcher
  ```
- [ ] **Citation Verification**: Dedicated module to verify and format citations
  - Cross-check URLs accessibility
  - Extract exact quotes
  - Generate proper citation format
- [ ] **Quality Assessment**: Score research findings for confidence/completeness
- [ ] **Result Deduplication**: Detect and merge overlapping findings across agents
- [ ] **Adaptive Depth**: Dynamically adjust research depth based on topic complexity
- [ ] **Source Caching**: Cache fetched web pages to reduce redundant requests

### Provider Extensions

- [ ] **Aider Integration**: Add Aider as an agent provider
- [ ] **Local LLMs**: Support for Ollama/vLLM backends
- [ ] **Hybrid Mode**: Mix providers for different agent roles

## License

MIT
