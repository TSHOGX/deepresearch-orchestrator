"""Shared type definitions for agent executors.

These types are provider-agnostic and used across all agent implementations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Union


class MessageType(Enum):
    """Types of messages from agent stream output."""

    ASSISTANT = "assistant"
    RESULT = "result"
    SYSTEM = "system"
    ERROR = "error"
    TOOL_USE = "tool_use"


@dataclass
class StreamMessage:
    """A parsed message from agent stream output."""

    type: MessageType
    content: str
    raw: dict = field(default_factory=dict)
    tool_name: str | None = None
    tool_input: dict | None = None


@dataclass
class ExecutionResult:
    """Result of an agent execution."""

    success: bool
    content: str
    messages: list[StreamMessage] = field(default_factory=list)
    error: str | None = None
    execution_time: float = 0.0


# Callback type for streaming messages (can be sync or async)
MessageCallback = Callable[[StreamMessage], Union[None, Awaitable[None]]]
