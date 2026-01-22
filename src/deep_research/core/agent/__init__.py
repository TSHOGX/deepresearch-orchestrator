"""Core agent abstraction layer.

This module provides a unified interface for different agent providers
(Codex CLI, Claude CLI, OpenCode, etc.) to be used interchangeably.
"""

from .base import AgentExecutor
from .factory import AgentRegistry, AgentRole
from .types import (
    ExecutionResult,
    MessageCallback,
    MessageType,
    StreamMessage,
)

# Import providers to trigger registration
from . import providers  # noqa: F401

# Re-export convenience factory functions from the active provider module
# These will be set up after providers are registered
_executor_factories = {}


def _get_settings():
    """Lazy import to avoid circular dependencies."""
    from deep_research.config import get_settings
    return get_settings()


def create_executor(role: AgentRole, provider: str | None = None) -> AgentExecutor:
    """Create an executor for the specified role.

    Args:
        role: The agent role (PLANNER, RESEARCHER, SYNTHESIZER).
        provider: Provider name. If None, uses the configured default.

    Returns:
        Configured AgentExecutor instance.
    """
    settings = _get_settings()
    role_provider_map = {
        AgentRole.PLANNER: settings.planner_provider,
        AgentRole.RESEARCHER: settings.researcher_provider,
        AgentRole.SYNTHESIZER: settings.synthesizer_provider,
    }
    role_provider = role_provider_map.get(role)
    provider = provider or role_provider or settings.agent_provider

    # Get role-specific model from settings
    model_map = {
        AgentRole.PLANNER: settings.planner_model,
        AgentRole.RESEARCHER: settings.researcher_model,
        AgentRole.SYNTHESIZER: settings.synthesizer_model,
    }

    provider_cls = AgentRegistry.get(provider)
    return provider_cls(model=model_map[role])


def create_planner_executor(provider: str | None = None) -> AgentExecutor:
    """Create an executor for the planner agent."""
    return create_executor(AgentRole.PLANNER, provider)


def create_researcher_executor(provider: str | None = None) -> AgentExecutor:
    """Create an executor for researcher agents."""
    return create_executor(AgentRole.RESEARCHER, provider)


def create_synthesizer_executor(provider: str | None = None) -> AgentExecutor:
    """Create an executor for the synthesizer agent."""
    return create_executor(AgentRole.SYNTHESIZER, provider)


__all__ = [
    # Base classes
    "AgentExecutor",
    "AgentRegistry",
    "AgentRole",
    # Types
    "ExecutionResult",
    "MessageCallback",
    "MessageType",
    "StreamMessage",
    # Factory functions
    "create_executor",
    "create_planner_executor",
    "create_researcher_executor",
    "create_synthesizer_executor",
]
