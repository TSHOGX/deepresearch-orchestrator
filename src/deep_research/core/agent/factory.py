"""Agent factory and registry.

Provides a registry for agent providers and factory functions to create executors.
"""

from enum import Enum
from typing import Type

from .base import AgentExecutor


class AgentRole(Enum):
    """Agent roles in the research workflow."""

    PLANNER = "planner"
    RESEARCHER = "researcher"
    SYNTHESIZER = "synthesizer"


class AgentRegistry:
    """Agent provider registry.

    Manages registration and retrieval of agent provider classes.
    """

    _providers: dict[str, Type[AgentExecutor]] = {}
    _default: str | None = None

    @classmethod
    def register(cls, name: str, *, default: bool = False):
        """Register decorator for agent providers.

        Args:
            name: Provider name (e.g., "claude_cli", "opencode").
            default: Whether this is the default provider.

        Returns:
            Decorator function.
        """
        def decorator(provider_cls: Type[AgentExecutor]):
            cls._providers[name] = provider_cls
            if default:
                cls._default = name
            return provider_cls
        return decorator

    @classmethod
    def get(cls, name: str | None = None) -> Type[AgentExecutor]:
        """Get a provider class by name.

        Args:
            name: Provider name. If None, returns the default provider.

        Returns:
            The provider class.

        Raises:
            ValueError: If the provider is not found.
        """
        name = name or cls._default
        if name is None:
            raise ValueError("No default provider registered")
        if name not in cls._providers:
            available = list(cls._providers.keys())
            raise ValueError(f"Unknown provider: {name}. Available: {available}")
        return cls._providers[name]

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def get_default(cls) -> str | None:
        """Get the default provider name."""
        return cls._default
