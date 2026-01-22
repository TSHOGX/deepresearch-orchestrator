"""Agent providers package.

Importing this module registers all available providers with the AgentRegistry.
"""

# Import providers to trigger registration via @AgentRegistry.register decorator
from . import codex_cli  # noqa: F401
from . import claude_cli  # noqa: F401
from . import opencode  # noqa: F401

__all__ = ["codex_cli", "claude_cli", "opencode"]
