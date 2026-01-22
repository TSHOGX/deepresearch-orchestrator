"""Tests for core agent abstraction layer."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from deep_research.config import reset_settings
from deep_research.core.agent import (
    AgentExecutor,
    AgentRegistry,
    AgentRole,
    ExecutionResult,
    MessageType,
    StreamMessage,
    create_executor,
    create_planner_executor,
    create_researcher_executor,
    create_synthesizer_executor,
)


class TestMessageType:
    """Test MessageType enum."""

    def test_message_types(self) -> None:
        """Test all message types exist."""
        assert MessageType.ASSISTANT.value == "assistant"
        assert MessageType.RESULT.value == "result"
        assert MessageType.SYSTEM.value == "system"
        assert MessageType.ERROR.value == "error"
        assert MessageType.TOOL_USE.value == "tool_use"


class TestStreamMessage:
    """Test StreamMessage dataclass."""

    def test_basic_message(self) -> None:
        """Test creating a basic message."""
        msg = StreamMessage(type=MessageType.ASSISTANT, content="Hello")
        assert msg.type == MessageType.ASSISTANT
        assert msg.content == "Hello"
        assert msg.raw == {}
        assert msg.tool_name is None
        assert msg.tool_input is None

    def test_message_with_tool(self) -> None:
        """Test creating message with tool info."""
        msg = StreamMessage(
            type=MessageType.TOOL_USE,
            content="Searching...",
            tool_name="WebSearch",
            tool_input={"query": "test"},
        )
        assert msg.type == MessageType.TOOL_USE
        assert msg.tool_name == "WebSearch"
        assert msg.tool_input == {"query": "test"}

    def test_message_with_raw(self) -> None:
        """Test creating message with raw data."""
        raw_data = {"type": "assistant", "content": "test"}
        msg = StreamMessage(
            type=MessageType.ASSISTANT,
            content="test",
            raw=raw_data,
        )
        assert msg.raw == raw_data


class TestExecutionResult:
    """Test ExecutionResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful result."""
        result = ExecutionResult(
            success=True, content="Hello", messages=[], execution_time=1.5
        )
        assert result.success is True
        assert result.content == "Hello"
        assert result.error is None
        assert result.execution_time == 1.5

    def test_failed_result(self) -> None:
        """Test creating a failed result."""
        result = ExecutionResult(
            success=False,
            content="",
            messages=[],
            error="Connection failed",
            execution_time=0.5,
        )
        assert result.success is False
        assert result.error == "Connection failed"

    def test_result_with_messages(self) -> None:
        """Test result with messages list."""
        msgs = [
            StreamMessage(type=MessageType.ASSISTANT, content="Hello"),
            StreamMessage(type=MessageType.RESULT, content="Done"),
        ]
        result = ExecutionResult(success=True, content="Done", messages=msgs)
        assert len(result.messages) == 2


class TestAgentRole:
    """Test AgentRole enum."""

    def test_roles(self) -> None:
        """Test all roles exist."""
        assert AgentRole.PLANNER.value == "planner"
        assert AgentRole.RESEARCHER.value == "researcher"
        assert AgentRole.SYNTHESIZER.value == "synthesizer"


class TestAgentRegistry:
    """Test AgentRegistry class."""

    def test_list_providers(self) -> None:
        """Test listing registered providers."""
        providers = AgentRegistry.list_providers()
        assert "codex_cli" in providers
        assert "claude_cli" in providers
        assert "opencode" in providers

    def test_get_default_provider(self) -> None:
        """Test getting default provider."""
        default = AgentRegistry.get_default()
        assert default == "codex_cli"

    def test_get_provider_by_name(self) -> None:
        """Test getting provider by name."""
        provider_cls = AgentRegistry.get("codex_cli")
        assert provider_cls is not None
        assert issubclass(provider_cls, AgentExecutor)

    def test_get_unknown_provider(self) -> None:
        """Test getting unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider"):
            AgentRegistry.get("unknown_provider")


class TestFactoryFunctions:
    """Test factory functions."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_settings()

    def test_create_executor_planner(self) -> None:
        """Test creating planner executor."""
        executor = create_executor(AgentRole.PLANNER)
        assert isinstance(executor, AgentExecutor)

    def test_create_executor_researcher(self) -> None:
        """Test creating researcher executor."""
        executor = create_executor(AgentRole.RESEARCHER)
        assert isinstance(executor, AgentExecutor)

    def test_create_executor_synthesizer(self) -> None:
        """Test creating synthesizer executor."""
        executor = create_executor(AgentRole.SYNTHESIZER)
        assert isinstance(executor, AgentExecutor)

    def test_create_planner_executor(self) -> None:
        """Test convenience function for planner."""
        executor = create_planner_executor()
        assert isinstance(executor, AgentExecutor)

    def test_create_researcher_executor(self) -> None:
        """Test convenience function for researcher."""
        executor = create_researcher_executor()
        assert isinstance(executor, AgentExecutor)

    def test_create_synthesizer_executor(self) -> None:
        """Test convenience function for synthesizer."""
        executor = create_synthesizer_executor()
        assert isinstance(executor, AgentExecutor)

    def test_create_executor_with_specific_provider(self) -> None:
        """Test creating executor with specific provider."""
        executor = create_executor(AgentRole.PLANNER, provider="opencode")
        assert isinstance(executor, AgentExecutor)
        # Verify it's the OpenCode executor
        assert executor.__class__.__name__ == "OpenCodeExecutor"

    def test_create_executor_with_claude_cli(self) -> None:
        """Test creating executor with claude_cli provider."""
        executor = create_executor(AgentRole.RESEARCHER, provider="claude_cli")
        assert isinstance(executor, AgentExecutor)
        assert executor.__class__.__name__ == "ClaudeCLIExecutor"

    def test_create_executor_with_codex_cli(self) -> None:
        """Test creating executor with codex_cli provider."""
        executor = create_executor(AgentRole.RESEARCHER, provider="codex_cli")
        assert isinstance(executor, AgentExecutor)
        assert executor.__class__.__name__ == "CodexCLIExecutor"

    def test_role_specific_provider_override(self) -> None:
        """Test role-specific provider override via settings."""
        os.environ["PLANNER_PROVIDER"] = "opencode"
        reset_settings()

        try:
            executor = create_executor(AgentRole.PLANNER)
            assert executor.__class__.__name__ == "OpenCodeExecutor"
        finally:
            os.environ.pop("PLANNER_PROVIDER", None)
            reset_settings()
