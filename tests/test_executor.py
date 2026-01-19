"""Tests for OpenCode executor."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deep_research.config import reset_settings
from deep_research.services.opencode_executor import (
    OpenCodeExecutor,
    ExecutionResult,
    MessageType,
    StreamMessage,
    create_executor,
    create_planner_executor,
    create_researcher_executor,
    create_synthesizer_executor,
)


class TestStreamMessage:
    """Test StreamMessage dataclass."""

    def test_basic_message(self) -> None:
        """Test creating a basic message."""
        msg = StreamMessage(type=MessageType.ASSISTANT, content="Hello")
        assert msg.type == MessageType.ASSISTANT
        assert msg.content == "Hello"
        assert msg.raw == {}
        assert msg.tool_name is None

    def test_message_with_tool(self) -> None:
        """Test creating message with tool info."""
        msg = StreamMessage(
            type=MessageType.TOOL_USE,
            content="Using webfetch...",
            tool_name="webfetch",
            tool_input={"url": "https://example.com"},
        )
        assert msg.type == MessageType.TOOL_USE
        assert msg.tool_name == "webfetch"


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
            error="Connection failed",
            execution_time=0.5,
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestOpenCodeExecutor:
    """Test OpenCodeExecutor class."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_settings()

    def test_init_with_defaults(self) -> None:
        """Test initializing executor with default settings."""
        executor = OpenCodeExecutor()
        assert executor.model == "opencode/minimax-m2.1-free"
        assert executor._base_url == "http://127.0.0.1:4096"

    def test_init_with_model(self) -> None:
        """Test initializing executor with specific model."""
        executor = OpenCodeExecutor(model="opencode/custom-model")
        assert executor.model == "opencode/custom-model"

    def test_init_with_agent(self) -> None:
        """Test initializing executor with agent."""
        executor = OpenCodeExecutor(agent="researcher")
        assert executor.agent == "researcher"

    def test_parse_model(self) -> None:
        """Test parsing model string."""
        executor = OpenCodeExecutor(model="opencode/minimax-m2.1-free")
        provider_id, model_id = executor._parse_model()
        assert provider_id == "opencode"
        assert model_id == "minimax-m2.1-free"

    def test_parse_model_no_provider(self) -> None:
        """Test parsing model string without provider prefix."""
        executor = OpenCodeExecutor(model="minimax-m2.1")
        provider_id, model_id = executor._parse_model()
        assert provider_id == "opencode"
        assert model_id == "minimax-m2.1"


class TestExecutorFactory:
    """Test executor factory functions."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    def teardown_method(self) -> None:
        """Clean up after each test."""
        reset_settings()

    def test_create_executor(self) -> None:
        """Test creating executor with factory."""
        executor = create_executor()
        assert isinstance(executor, OpenCodeExecutor)

    def test_create_planner_executor(self) -> None:
        """Test creating planner executor."""
        executor = create_planner_executor()
        # Note: agent is None - custom agents not supported via API
        assert executor.model == "opencode/minimax-m2.1-free"

    def test_create_researcher_executor(self) -> None:
        """Test creating researcher executor."""
        executor = create_researcher_executor()
        assert executor.model == "opencode/minimax-m2.1-free"

    def test_create_synthesizer_executor(self) -> None:
        """Test creating synthesizer executor."""
        executor = create_synthesizer_executor()
        assert executor.model == "opencode/minimax-m2.1-free"


@pytest.mark.asyncio
class TestOpenCodeExecutorAsync:
    """Test async methods of OpenCodeExecutor."""

    def setup_method(self) -> None:
        """Reset settings before each test."""
        reset_settings()

    @patch("aiohttp.ClientSession")
    async def test_execute_success(self, mock_session_class) -> None:
        """Test successful execution with mocked HTTP using SSE streaming."""
        # Mock SSE event stream content
        sse_events = [
            b'data: {"type": "message.delta", "content": "Hello, "}\n',
            b'data: {"type": "message.delta", "content": "this is "}\n',
            b'data: {"type": "message.created", "content": "Hello, this is the response."}\n',
            b'data: {"type": "session.completed", "result": {"parts": [{"type": "text", "text": "Hello, this is the response."}]}}\n',
        ]

        # Create async iterator for SSE content
        async def async_iter_lines():
            for line in sse_events:
                yield line

        # Mock SSE response (GET /event)
        mock_sse_response = AsyncMock()
        mock_sse_response.status = 200
        mock_sse_response.content = async_iter_lines()
        mock_sse_response.__aenter__ = AsyncMock(return_value=mock_sse_response)
        mock_sse_response.__aexit__ = AsyncMock()

        # Mock prompt_async response (POST /session/{id}/prompt_async)
        mock_prompt_response = AsyncMock()
        mock_prompt_response.status = 200
        mock_prompt_response.__aenter__ = AsyncMock(return_value=mock_prompt_response)
        mock_prompt_response.__aexit__ = AsyncMock()

        # Mock session create response (POST /session)
        mock_create_response = AsyncMock()
        mock_create_response.status = 200
        mock_create_response.json = AsyncMock(return_value={"id": "test-session-123"})
        mock_create_response.__aenter__ = AsyncMock(return_value=mock_create_response)
        mock_create_response.__aexit__ = AsyncMock()

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session_class.return_value = mock_session

        # Make post return different responses for session create vs prompt_async
        call_count = 0
        def post_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_create_response
            return mock_prompt_response

        mock_session.post = MagicMock(side_effect=post_side_effect)
        mock_session.get = MagicMock(return_value=mock_sse_response)

        executor = OpenCodeExecutor(model="opencode/minimax-m2.1")
        executor._http_session = mock_session

        result = await executor.execute("Test prompt")

        assert result.success is True
        assert "Hello, this is the response." in result.content
