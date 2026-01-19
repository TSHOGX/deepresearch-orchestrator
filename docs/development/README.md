# Development Documentation

This directory contains development plans, design documents, and internal technical documentation.

## Document Index

### Phase 1: Initial Design (Archive)

The original design documents from the initial development phase:

- [deepresearch-plan.md](./archive/deepresearch-plan.md) - Complete system design plan including architecture, workflows, and implementation timeline
- [deepresearch-test-plan.md](./archive/deepresearch-test-plan.md) - Testing and validation methodology
- [TODO.md](./archive/TODO.md) - Original development task tracking

### Phase 2: Core Agent Refactoring

- [core-agent-refactor-plan.md](./core-agent-refactor-plan.md) - Agent abstraction layer refactoring to support multiple providers (Claude CLI, OpenCode, etc.)

## Development History

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | Completed | Initial implementation with Claude CLI |
| Phase 2 | Completed | Agent abstraction layer for multi-provider support |
| Phase 3 | Active | OpenCode integration and optimization |

## Architecture Evolution

```
Phase 1: Direct Claude CLI Integration
┌─────────────┐
│ Orchestrator │──────▶ Claude CLI (subprocess)
└─────────────┘

Phase 2: Abstracted Provider Layer
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│ Orchestrator │──▶│ AgentExecutor │──▶│ Claude CLI      │
└─────────────┘    │  (Abstract)   │    │ OpenCode        │
                   └──────────────┘    │ ... (extensible)│
                                       └─────────────────┘
```
