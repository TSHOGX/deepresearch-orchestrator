"""Tests for Claude CLI executor."""

import json
import os

import pytest

from deep_research.config import reset_settings
from deep_research.services.agent_executor import (
    ClaudeExecutor,
    ExecutionResult,
    MessageType,
    StreamMessage,
    create_executor,
    create_planner_executor,
    create_researcher_executor,
    create_synthesizer_executor,
)


class TestStreamMessageParsing:
    """Test stream message parsing."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_settings()
        os.environ.pop("RESEARCHER_MODEL", None)

    def test_parse_assistant_message(self) -> None:
        """Test parsing assistant message with content."""
        executor = ClaudeExecutor()
        line = json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Hello, I can help you research that."}
                    ]
                },
            }
        )

        result = executor._parse_stream_line(line)

        assert result is not None
        assert result.type == MessageType.ASSISTANT
        assert result.content == "Hello, I can help you research that."

    def test_parse_content_block_delta(self) -> None:
        """Test parsing streaming content delta."""
        executor = ClaudeExecutor()
        line = json.dumps(
            {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "partial"}}
        )

        result = executor._parse_stream_line(line)

        assert result is not None
        assert result.type == MessageType.ASSISTANT
        assert result.content == "partial"

    def test_parse_result_message(self) -> None:
        """Test parsing result message."""
        executor = ClaudeExecutor()
        line = json.dumps({"type": "result", "result": "Final answer", "cost_usd": 0.01})

        result = executor._parse_stream_line(line)

        assert result is not None
        assert result.type == MessageType.RESULT
        assert result.content == "Final answer"

    def test_parse_error_message(self) -> None:
        """Test parsing error message."""
        executor = ClaudeExecutor()
        line = json.dumps({"type": "error", "error": {"message": "Something went wrong"}})

        result = executor._parse_stream_line(line)

        assert result is not None
        assert result.type == MessageType.ERROR
        assert result.content == "Something went wrong"

    def test_parse_system_message(self) -> None:
        """Test parsing system message."""
        executor = ClaudeExecutor()
        line = json.dumps({"type": "system", "message": "System initialized"})

        result = executor._parse_stream_line(line)

        assert result is not None
        assert result.type == MessageType.SYSTEM
        assert result.content == "System initialized"

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON returns None."""
        executor = ClaudeExecutor()
        result = executor._parse_stream_line("not valid json")
        assert result is None

    def test_parse_empty_line(self) -> None:
        """Test parsing empty line returns None."""
        executor = ClaudeExecutor()
        result = executor._parse_stream_line("")
        assert result is None
        result = executor._parse_stream_line("   ")
        assert result is None

    def test_parse_unknown_type(self) -> None:
        """Test parsing unknown message type returns None."""
        executor = ClaudeExecutor()
        line = json.dumps({"type": "unknown_type", "data": "something"})
        result = executor._parse_stream_line(line)
        assert result is None


class TestCommandBuilding:
    """Test command building."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_settings()

    def test_basic_command(self) -> None:
        """Test building a basic command."""
        executor = ClaudeExecutor(model="sonnet")
        cmd = executor._build_command("Hello world")

        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert "stream-json" in cmd
        assert "--model" in cmd
        assert "sonnet" in cmd
        assert cmd[-1] == "Hello world"

    def test_command_with_system_prompt(self) -> None:
        """Test building command with system prompt."""
        executor = ClaudeExecutor(model="opus")
        cmd = executor._build_command("Hello", system_prompt="You are a researcher")

        assert "--system-prompt" in cmd
        idx = cmd.index("--system-prompt")
        assert cmd[idx + 1] == "You are a researcher"

    def test_command_without_system_prompt(self) -> None:
        """Test building command without system prompt."""
        executor = ClaudeExecutor()
        cmd = executor._build_command("Hello")

        assert "--system-prompt" not in cmd


class TestExecutorFactory:
    """Test executor factory functions."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_settings()
        for var in ["PLANNER_MODEL", "RESEARCHER_MODEL", "SYNTHESIZER_MODEL"]:
            os.environ.pop(var, None)

    def test_create_executor_with_defaults(self) -> None:
        """Test creating executor with default settings."""
        executor = create_executor()
        assert executor.model == "sonnet"  # Default researcher model

    def test_create_executor_with_model(self) -> None:
        """Test creating executor with specific model."""
        executor = create_executor(model="opus")
        assert executor.model == "opus"

    def test_create_planner_executor(self) -> None:
        """Test creating planner executor uses opus."""
        executor = create_planner_executor()
        assert executor.model == "opus"

    def test_create_researcher_executor(self) -> None:
        """Test creating researcher executor uses sonnet."""
        executor = create_researcher_executor()
        assert executor.model == "sonnet"

    def test_create_synthesizer_executor(self) -> None:
        """Test creating synthesizer executor uses opus."""
        executor = create_synthesizer_executor()
        assert executor.model == "opus"

    def test_create_executor_with_custom_timeout(self) -> None:
        """Test creating executor with custom timeout."""
        executor = create_executor(timeout=600)
        assert executor.timeout == 600


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

    def test_failed_result(self) -> None:
        """Test creating a failed result."""
        result = ExecutionResult(
            success=False,
            content="",
            messages=[],
            error="Timeout",
            execution_time=300.0,
        )
        assert result.success is False
        assert result.error == "Timeout"


class TestStreamMessage:
    """Test StreamMessage dataclass."""

    def test_basic_message(self) -> None:
        """Test creating a basic message."""
        msg = StreamMessage(type=MessageType.ASSISTANT, content="Hello")
        assert msg.type == MessageType.ASSISTANT
        assert msg.content == "Hello"
        assert msg.raw == {}
        assert msg.tool_name is None

    def test_message_with_raw_data(self) -> None:
        """Test creating message with raw data."""
        raw = {"type": "assistant", "data": "extra"}
        msg = StreamMessage(type=MessageType.ASSISTANT, content="Hello", raw=raw)
        assert msg.raw == raw
