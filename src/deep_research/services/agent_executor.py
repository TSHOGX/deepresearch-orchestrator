"""Claude CLI executor for running Claude Code agents."""

import asyncio
import inspect
import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Awaitable, Callable, Union

from deep_research.config import get_settings

logger = logging.getLogger(__name__)

# Type for callback that can be sync or async
MessageCallback = Callable[["StreamMessage"], Union[None, Awaitable[None]]]


class MessageType(Enum):
    """Types of messages from Claude CLI stream output."""

    ASSISTANT = "assistant"
    RESULT = "result"
    SYSTEM = "system"
    ERROR = "error"


@dataclass
class StreamMessage:
    """A parsed message from Claude CLI stream output."""

    type: MessageType
    content: str
    raw: dict = field(default_factory=dict)
    tool_name: str | None = None
    tool_input: dict | None = None


@dataclass
class ExecutionResult:
    """Result of a Claude CLI execution."""

    success: bool
    content: str
    messages: list[StreamMessage] = field(default_factory=list)
    error: str | None = None
    execution_time: float = 0.0


class ClaudeExecutor:
    """Executor for Claude Code CLI commands.

    Handles spawning Claude CLI processes, parsing stream-json output,
    and managing timeouts.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: int | None = None,
        json_schema: dict | None = None,
        allowed_tools: list[str] | None = None,
    ):
        """Initialize the executor.

        Args:
            model: Model to use (opus/sonnet/haiku). If None, uses config default.
            timeout: Timeout in seconds. 0 means no timeout. If None, uses config default.
            json_schema: Optional JSON schema for structured output enforcement.
            allowed_tools: Optional list of tools to enable (e.g. ["WebSearch", "WebFetch"]).
        """
        settings = get_settings()
        self.model = model or settings.researcher_model
        self.timeout = timeout if timeout is not None else settings.agent_timeout_seconds
        self.json_schema = json_schema
        self.allowed_tools = allowed_tools

    def _build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build the Claude CLI command.

        Args:
            prompt: The user prompt to send.
            system_prompt: Optional system prompt.

        Returns:
            Command as list of arguments.
        """
        cmd = [
            "claude",
            "--print",
            "--verbose",
            "--output-format",
            "stream-json",
            "--model",
            self.model,
        ]

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        if self.json_schema:
            cmd.extend(["--json-schema", json.dumps(self.json_schema)])

        if self.allowed_tools:
            # Use --tools to specify available tools (not --allowedTools which is for restrictions)
            cmd.extend(["--tools", ",".join(self.allowed_tools)])
            # Bypass permission prompts for non-interactive use
            cmd.extend(["--permission-mode", "bypassPermissions"])

        # Use '--' to signal end of options before the prompt
        # This prevents options like --tools from consuming the prompt
        cmd.append("--")
        cmd.append(prompt)
        return cmd

    def _parse_stream_line(self, line: str) -> StreamMessage | None:
        """Parse a single line of stream-json output.

        Args:
            line: Raw line from stdout.

        Returns:
            Parsed StreamMessage or None if line is invalid.
        """
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON line: {line[:100]}")
            return None

        msg_type = data.get("type", "")

        if msg_type == "assistant":
            # Assistant message with content
            content = ""
            tool_name = None
            tool_input = None
            if "message" in data:
                message = data["message"]
                if "content" in message and isinstance(message["content"], list):
                    for block in message["content"]:
                        if block.get("type") == "text":
                            content += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            # Extract tool use info for progress display
                            tool_name = block.get("name", "")
                            tool_input = block.get("input", {})
                            # Create a human-readable content for tool use
                            if tool_name == "WebSearch":
                                query = tool_input.get("query", "")
                                content = f"Searching: {query[:50]}..." if len(query) > 50 else f"Searching: {query}"
                            elif tool_name == "WebFetch":
                                url = tool_input.get("url", "")
                                content = f"Fetching: {url[:50]}..." if len(url) > 50 else f"Fetching: {url}"
                            else:
                                content = f"Using {tool_name}..."
            return StreamMessage(
                type=MessageType.ASSISTANT,
                content=content,
                raw=data,
                tool_name=tool_name,
                tool_input=tool_input,
            )

        elif msg_type == "content_block_delta":
            # Streaming content delta
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                return StreamMessage(
                    type=MessageType.ASSISTANT,
                    content=delta.get("text", ""),
                    raw=data,
                )

        elif msg_type == "result":
            # Final result
            result = data.get("result", "")
            cost_usd = data.get("cost_usd", 0)
            return StreamMessage(
                type=MessageType.RESULT,
                content=result if isinstance(result, str) else json.dumps(result),
                raw=data,
            )

        elif msg_type == "error":
            # Error message
            return StreamMessage(
                type=MessageType.ERROR,
                content=data.get("error", {}).get("message", str(data)),
                raw=data,
            )

        elif msg_type == "system":
            # System message
            return StreamMessage(
                type=MessageType.SYSTEM,
                content=data.get("message", ""),
                raw=data,
            )

        # Unknown message type - log but don't fail
        logger.debug(f"Unknown message type: {msg_type}")
        return None

    async def execute(
        self,
        prompt: str,
        system_prompt: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> ExecutionResult:
        """Execute a Claude CLI command.

        Args:
            prompt: The prompt to send to Claude.
            system_prompt: Optional system prompt.
            on_message: Optional callback for each streamed message (can be sync or async).

        Returns:
            ExecutionResult with success status and content.
        """
        import time

        start_time = time.time()
        cmd = self._build_command(prompt, system_prompt)
        messages: list[StreamMessage] = []
        content_parts: list[str] = []

        logger.info(f"Executing Claude CLI with model={self.model}")
        logger.debug(f"Command: {' '.join(cmd[:6])}...")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def read_stream() -> None:
                """Read and parse the stdout stream."""
                if process.stdout is None:
                    return

                async for line in process.stdout:
                    line_str = line.decode("utf-8", errors="replace")
                    message = self._parse_stream_line(line_str)

                    if message:
                        messages.append(message)
                        if message.content:
                            content_parts.append(message.content)
                        if on_message:
                            # Handle both sync and async callbacks
                            result = on_message(message)
                            if inspect.isawaitable(result):
                                await result

            try:
                # If timeout is 0, run without timeout (user can interrupt manually)
                if self.timeout > 0:
                    await asyncio.wait_for(read_stream(), timeout=self.timeout)
                else:
                    await read_stream()
                await process.wait()
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ExecutionResult(
                    success=False,
                    content="".join(content_parts),
                    messages=messages,
                    error=f"Execution timed out after {self.timeout} seconds",
                    execution_time=time.time() - start_time,
                )

            # Check for errors
            if process.returncode != 0:
                stderr = ""
                if process.stderr:
                    stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
                return ExecutionResult(
                    success=False,
                    content="".join(content_parts),
                    messages=messages,
                    error=f"Process exited with code {process.returncode}: {stderr}",
                    execution_time=time.time() - start_time,
                )

            # Check for error messages in stream
            error_messages = [m for m in messages if m.type == MessageType.ERROR]
            if error_messages:
                return ExecutionResult(
                    success=False,
                    content="".join(content_parts),
                    messages=messages,
                    error=error_messages[0].content,
                    execution_time=time.time() - start_time,
                )

            return ExecutionResult(
                success=True,
                content="".join(content_parts),
                messages=messages,
                execution_time=time.time() - start_time,
            )

        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                content="",
                messages=[],
                error="Claude CLI not found. Please ensure 'claude' is installed and in PATH.",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            logger.exception("Unexpected error during execution")
            return ExecutionResult(
                success=False,
                content="".join(content_parts),
                messages=messages,
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def execute_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StreamMessage]:
        """Execute a Claude CLI command and yield messages as they arrive.

        Args:
            prompt: The prompt to send to Claude.
            system_prompt: Optional system prompt.

        Yields:
            StreamMessage objects as they are received.
        """
        cmd = self._build_command(prompt, system_prompt)
        logger.info(f"Streaming Claude CLI with model={self.model}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            if process.stdout is None:
                return

            async def stream_with_timeout() -> AsyncIterator[StreamMessage]:
                """Stream with timeout handling."""
                if process.stdout is None:
                    return

                try:
                    async for line in process.stdout:
                        line_str = line.decode("utf-8", errors="replace")
                        message = self._parse_stream_line(line_str)
                        if message:
                            yield message
                except asyncio.CancelledError:
                    process.kill()
                    raise

            try:
                async for message in asyncio.timeout(self.timeout).__aenter__().__anext__(
                    stream_with_timeout()
                ):
                    yield message
            except (asyncio.TimeoutError, StopAsyncIteration):
                pass

            await process.wait()

        except FileNotFoundError:
            yield StreamMessage(
                type=MessageType.ERROR,
                content="Claude CLI not found. Please ensure 'claude' is installed and in PATH.",
            )


def create_executor(
    model: str | None = None,
    timeout: int | None = None,
    json_schema: dict | None = None,
    allowed_tools: list[str] | None = None,
) -> ClaudeExecutor:
    """Factory function to create a ClaudeExecutor.

    Args:
        model: Model to use (opus/sonnet/haiku).
        timeout: Timeout in seconds. 0 means no timeout.
        json_schema: Optional JSON schema for structured output.
        allowed_tools: Optional list of tools to enable.

    Returns:
        Configured ClaudeExecutor instance.
    """
    return ClaudeExecutor(model=model, timeout=timeout, json_schema=json_schema, allowed_tools=allowed_tools)


def create_planner_executor(json_schema: dict | None = None) -> ClaudeExecutor:
    """Create an executor configured for the planner agent.

    Args:
        json_schema: Optional JSON schema for structured output.
    """
    settings = get_settings()
    return ClaudeExecutor(model=settings.planner_model, timeout=0, json_schema=json_schema)


def create_researcher_executor() -> ClaudeExecutor:
    """Create an executor configured for researcher agents.
    
    Enables WebSearch and WebFetch tools for research tasks.
    """
    settings = get_settings()
    return ClaudeExecutor(
        model=settings.researcher_model,
        timeout=0,
        allowed_tools=["WebSearch", "WebFetch"],
    )


def create_synthesizer_executor() -> ClaudeExecutor:
    """Create an executor configured for the synthesizer agent.
    
    No tools needed - just text synthesis from research findings.
    """
    settings = get_settings()
    return ClaudeExecutor(model=settings.synthesizer_model, timeout=0)
