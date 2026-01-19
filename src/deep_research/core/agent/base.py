"""Agent executor abstract base class.

All agent providers must inherit from AgentExecutor and implement the abstract methods.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from .types import ExecutionResult, MessageCallback, StreamMessage


class AgentExecutor(ABC):
    """Agent executor abstract base class.

    All agent providers must inherit this class and implement abstract methods.
    """

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        system_prompt: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> ExecutionResult:
        """Execute a single request.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional system prompt.
            on_message: Optional callback for each streamed message.

        Returns:
            ExecutionResult with success status and content.
        """
        pass

    @abstractmethod
    async def execute_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StreamMessage]:
        """Execute a prompt and yield messages as they arrive.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional system prompt.

        Yields:
            StreamMessage objects as they are received.
        """
        pass

    async def close(self) -> None:
        """Release resources (optional implementation)."""
        pass

    async def __aenter__(self) -> "AgentExecutor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()
