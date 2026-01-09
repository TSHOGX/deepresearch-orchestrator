# Deep Research

Multi-agent deep research system powered by Claude Code CLI.

## Features

- Three-phase research workflow: Planning → Research → Synthesis
- Parallel researcher agents with no upper limit
- Checkpoint recovery for long-running tasks
- Both CLI and Web interfaces

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

### CLI

```bash
deep-research "Your research question"
```

### API Server

```bash
deep-research-api
```

Server runs on port 12050 by default.

## Configuration

Copy `.env.example` to `.env` and customize settings:

```bash
cp .env.example .env
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src tests
```

## License

MIT
