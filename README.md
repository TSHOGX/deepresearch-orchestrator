# Deep Research

Multi-agent deep research system powered by Claude Code CLI.

## Features

- Three-phase research workflow: Planning → Research → Synthesis
- Parallel researcher agents with no upper limit
- Checkpoint recovery for long-running tasks
- Both CLI and Web interfaces
- Real-time SSE streaming for progress updates
- Language auto-detection (English/Chinese)

## Installation

### Backend

```bash
pip install -e ".[dev]"
```

### Web Frontend

```bash
cd web
npm install
```

## Usage

### CLI

```bash
# Interactive mode
deep-research

# With query
deep-research "Your research question"

# Auto-confirm plan
deep-research -y "Your research question"

# Resume session
deep-research -r SESSION_ID

# List sessions
deep-research -l
```

### API Server

```bash
# Start backend (port 12050)
deep-research-api
```

### Web Frontend

```bash
# Start frontend (port 12051)
cd web
npm run dev
```

Then open http://localhost:12051 in your browser.

## Ports

| Service | Port |
|---------|------|
| FastAPI Backend | 12050 |
| Next.js Frontend | 12051 |

## Configuration

Copy `.env.example` to `.env` and customize settings:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `12050` | API server port |
| `PLANNER_MODEL` | `opus` | Model for planning agent |
| `RESEARCHER_MODEL` | `sonnet` | Model for researcher agents |
| `SYNTHESIZER_MODEL` | `opus` | Model for synthesis agent |
| `MAX_PARALLEL_AGENTS` | `10` | Max concurrent research agents |
| `AGENT_TIMEOUT_SECONDS` | `600` | Agent timeout |
| `CHECKPOINT_INTERVAL_SECONDS` | `60` | Checkpoint save interval |

## API Endpoints

### Research

- `POST /api/research/start` - Start new research session
- `GET /api/research/{id}` - Get session status
- `POST /api/research/{id}/confirm` - Confirm research plan
- `POST /api/research/{id}/cancel` - Cancel session
- `POST /api/research/{id}/resume` - Resume session
- `GET /api/research/{id}/report` - Get final report
- `GET /api/research/{id}/stream` - SSE event stream

### Configuration

- `GET /api/config` - Get current configuration
- `PUT /api/config` - Update configuration

### Health

- `GET /health` - Health check
- `GET /ready` - Readiness check

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run backend tests
pytest

# Run linter
ruff check src tests

# Build web frontend
cd web && npm run build
```

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Web/CLI    │────▶│  FastAPI     │────▶│  Claude     │
│  Interface  │◀────│  Backend     │◀────│  Code CLI   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   SQLite     │
                    │  (Sessions   │
                    │ Checkpoints) │
                    └──────────────┘
```

## License

MIT
