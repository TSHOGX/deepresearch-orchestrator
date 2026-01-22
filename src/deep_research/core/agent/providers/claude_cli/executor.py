"""Claude CLI executor implementation.

Uses subprocess to call the Claude CLI for agent execution.
"""

import asyncio
import inspect
import json
import logging
import time
from pathlib import Path
from typing import AsyncIterator

import yaml

from deep_research.core.agent.base import AgentExecutor
from deep_research.core.agent.factory import AgentRegistry
from deep_research.core.agent.types import (
    ExecutionResult,
    MessageCallback,
    MessageType,
    StreamMessage,
)

logger = logging.getLogger(__name__)

# Load provider config
_config_path = Path(__file__).parent / "config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)


def _map_model(logical_model: str) -> str:
    """Map logical model name to Claude CLI model name."""
    models = _config.get("models", {})
    # If it's already a valid model name, return as-is
    if logical_model in models.values():
        return logical_model
    # Otherwise try to map it
    return models.get(logical_model, logical_model)


@AgentRegistry.register("claude_cli")
class ClaudeCLIExecutor(AgentExecutor):
    """Executor using Claude CLI subprocess.

    Handles spawning Claude CLI processes, parsing stream-json output,
    and managing timeouts.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 0.0,
    ):
        """Initialize the executor.

        Args:
            model: Model to use (opus/sonnet/haiku or logical name).
            timeout: Timeout in seconds. 0 means no timeout.
        """
        self.model = _map_model(model) if model else "sonnet"
        self.timeout = timeout

    def _build_command(
        self,
        prompt: str,
        system_prompt: str | None = None,
        streaming: bool = True,
    ) -> list[str]:
        """Build the Claude CLI command."""
        cli_config = _config.get("cli", {})
        args = cli_config.get("streaming" if streaming else "non_streaming", [])

        cmd = ["claude"] + list(args) + ["--model", self.model]

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        cmd.append("--")
        cmd.append(prompt)
        return cmd

    def _parse_stream_line(self, line: str) -> StreamMessage | None:
        """Parse a single line of stream-json output."""
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
            return self._parse_assistant_message(data)
        elif msg_type == "content_block_delta":
            return self._parse_content_delta(data)
        elif msg_type == "result":
            return self._parse_result_message(data)
        elif msg_type == "error":
            return self._parse_error_message(data)
        elif msg_type == "system":
            return StreamMessage(
                type=MessageType.SYSTEM,
                content=data.get("message", ""),
                raw=data,
            )

        logger.debug(f"Unknown message type: {msg_type}")
        return None

    def _parse_assistant_message(self, data: dict) -> StreamMessage | None:
        """Parse assistant message with content blocks."""
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
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        content = self._format_tool_content(tool_name, tool_input)

        msg_type = MessageType.TOOL_USE if tool_name else MessageType.ASSISTANT
        return StreamMessage(
            type=msg_type,
            content=content,
            raw=data,
            tool_name=tool_name,
            tool_input=tool_input,
        )

    def _format_tool_content(self, tool_name: str, tool_input: dict) -> str:
        """Format tool use as human-readable content."""
        if tool_name == "WebSearch":
            query = tool_input.get("query", "")
            return f"Searching: {query[:50]}..." if len(query) > 50 else f"Searching: {query}"
        elif tool_name == "WebFetch":
            url = tool_input.get("url", "")
            return f"Fetching: {url[:50]}..." if len(url) > 50 else f"Fetching: {url}"
        return f"Using {tool_name}..."

    def _parse_content_delta(self, data: dict) -> StreamMessage | None:
        """Parse streaming content delta."""
        delta = data.get("delta", {})
        if delta.get("type") == "text_delta":
            return StreamMessage(
                type=MessageType.ASSISTANT,
                content=delta.get("text", ""),
                raw=data,
            )
        return None

    def _parse_result_message(self, data: dict) -> StreamMessage:
        """Parse final result message."""
        result = data.get("result", "")
        return StreamMessage(
            type=MessageType.RESULT,
            content=result if isinstance(result, str) else json.dumps(result),
            raw=data,
        )

    def _parse_error_message(self, data: dict) -> StreamMessage:
        """Parse error message."""
        return StreamMessage(
            type=MessageType.ERROR,
            content=data.get("error", {}).get("message", str(data)),
            raw=data,
        )

    async def execute(
        self,
        prompt: str,
        system_prompt: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> ExecutionResult:
        """Execute a Claude CLI command."""
        start_time = time.time()
        cmd = self._build_command(prompt, system_prompt, streaming=True)
        messages: list[StreamMessage] = []
        content_parts: list[str] = []

        logger.info(f"Executing Claude CLI with model={self.model}")
        logger.debug(f"Command: {' '.join(cmd[:6])}...")

        try:
            # Use larger limit to handle large JSON lines from Claude CLI
            # Default is 64KB, but tool results can be much larger
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=10 * 1024 * 1024,  # 10MB
            )

            async def read_stream() -> None:
                if process.stdout is None:
                    return
                async for line in process.stdout:
                    line_str = line.decode("utf-8", errors="replace")
                    message = self._parse_stream_line(line_str)
                    if message:
                        messages.append(message)
                        if message.content:
                            content_parts.append(message.content)

                        # Only call on_message for progress-worthy events:
                        # - Tool use (shows what tool is being used)
                        # - Streaming text deltas (for content_block_delta)
                        # Skip final result/assistant messages to avoid showing JSON
                        if on_message and message.type in (MessageType.TOOL_USE, MessageType.SYSTEM):
                            result = on_message(message)
                            if inspect.isawaitable(result):
                                await result
                        elif on_message and message.type == MessageType.ASSISTANT:
                            # Only show non-JSON content as progress
                            content = message.content or ""
                            if not content.strip().startswith(("{", "[")):
                                result = on_message(message)
                                if inspect.isawaitable(result):
                                    await result

            try:
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
        """Execute and yield messages as they arrive."""
        cmd = self._build_command(prompt, system_prompt, streaming=True)
        logger.info(f"Streaming Claude CLI with model={self.model}")

        try:
            # Use larger limit to handle large JSON lines from Claude CLI
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=10 * 1024 * 1024,  # 10MB
            )

            if process.stdout is None:
                return

            async for line in process.stdout:
                line_str = line.decode("utf-8", errors="replace")
                message = self._parse_stream_line(line_str)
                if message:
                    yield message

            await process.wait()

        except FileNotFoundError:
            yield StreamMessage(
                type=MessageType.ERROR,
                content="Claude CLI not found. Please ensure 'claude' is installed and in PATH.",
            )
