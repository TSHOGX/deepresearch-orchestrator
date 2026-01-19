"""OpenCode SDK executor for running AI agents.

Replaces Claude CLI subprocess execution with OpenCode SDK HTTP API.
"""

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Awaitable, Callable, Union

import aiohttp

from deep_research.config import get_settings

logger = logging.getLogger(__name__)

# Type for callback that can be sync or async
MessageCallback = Callable[["StreamMessage"], Union[None, Awaitable[None]]]


class MessageType(Enum):
    """Types of messages from OpenCode stream output."""

    ASSISTANT = "assistant"
    RESULT = "result"
    SYSTEM = "system"
    ERROR = "error"
    TOOL_USE = "tool_use"


@dataclass
class StreamMessage:
    """A parsed message from OpenCode stream output."""

    type: MessageType
    content: str
    raw: dict = field(default_factory=dict)
    tool_name: str | None = None
    tool_input: dict | None = None


@dataclass
class ExecutionResult:
    """Result of an OpenCode execution."""

    success: bool
    content: str
    messages: list[StreamMessage] = field(default_factory=list)
    error: str | None = None
    execution_time: float = 0.0


class OpenCodeExecutor:
    """Executor using OpenCode SDK HTTP API.

    Connects to a running OpenCode server to execute prompts
    with support for streaming events and tool usage.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 600.0,
        agent: str | None = None,
    ):
        """Initialize the executor.

        Args:
            model: Model ID in format "provider/model-id" (e.g., "opencode/minimax-m2.1").
                   If None, uses config default.
            timeout: Timeout in seconds. 0 means no timeout.
            agent: Optional agent name defined in opencode.json (planner, researcher, synthesizer).
        """
        settings = get_settings()
        self.model = model or settings.researcher_model
        self.timeout = timeout if timeout > 0 else 600.0
        self.agent = agent
        self._base_url = f"http://{settings.opencode_host}:{settings.opencode_port}"
        self._session_id: str | None = None
        self._http_session: aiohttp.ClientSession | None = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def _ensure_session(self) -> str:
        """Ensure we have an active OpenCode session.

        Returns:
            Session ID.
        """
        if self._session_id:
            return self._session_id

        http = await self._get_http_session()
        # Note: Don't pass custom agent names - OpenCode API only supports built-in agents
        body = {}

        async with http.post(f"{self._base_url}/session", json=body) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Failed to create session: {resp.status} {error_text}")
            data = await resp.json()
            self._session_id = data.get("id")
            logger.info(f"Created OpenCode session: {self._session_id}")
            return self._session_id

    def _parse_model(self) -> tuple[str, str]:
        """Parse model string into provider_id and model_id.

        Returns:
            Tuple of (provider_id, model_id).
        """
        if "/" in self.model:
            parts = self.model.split("/", 1)
            return parts[0], parts[1]
        return "opencode", self.model

    async def execute(
        self,
        prompt: str,
        system_prompt: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> ExecutionResult:
        """Execute a prompt via OpenCode with real-time streaming.

        Uses SSE streaming to get real-time progress updates while executing.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional system prompt.
            on_message: Optional callback for each streamed message (can be sync or async).
                       Called in real-time as messages arrive.

        Returns:
            ExecutionResult with success status and content.
        """
        start_time = time.time()
        messages: list[StreamMessage] = []
        content_parts: list[str] = []

        provider_id, model_id = self._parse_model()
        logger.info(f"Executing OpenCode with model={self.model}, agent={self.agent}")

        try:
            session_id = await self._ensure_session()
            http = await self._get_http_session()

            # Build message payload
            body = {
                "model": {
                    "providerID": provider_id,
                    "modelID": model_id,
                },
                "parts": [
                    {"type": "text", "text": prompt}
                ],
            }

            if system_prompt:
                body["system"] = system_prompt

            # Send prompt asynchronously (non-blocking)
            async with http.post(
                f"{self._base_url}/session/{session_id}/prompt_async",
                json=body,
            ) as resp:
                if resp.status not in (200, 204):
                    error_text = await resp.text()
                    return ExecutionResult(
                        success=False,
                        content="",
                        messages=messages,
                        error=f"Failed to send prompt: {resp.status} {error_text}",
                        execution_time=time.time() - start_time,
                    )

            # Subscribe to SSE events for real-time streaming
            import json as json_module

            logger.debug(f"Subscribing to SSE events for session {session_id}")

            async with http.get(
                f"{self._base_url}/event",
                params={"session": session_id},
            ) as resp:
                logger.debug(f"SSE connection status: {resp.status}")
                async for line in resp.content:
                    line_str = line.decode("utf-8", errors="replace").strip()

                    # Skip empty lines and SSE comments
                    if not line_str or line_str.startswith(":"):
                        continue

                    # Parse SSE data prefix
                    if line_str.startswith("data:"):
                        line_str = line_str[5:].strip()

                    if not line_str:
                        continue

                    try:
                        event = json_module.loads(line_str)
                        event_type = event.get("type", "")
                        logger.debug(f"SSE event received: type={event_type}, keys={list(event.keys())}")

                        if event_type == "message.part.updated":
                            # Streaming text chunk - this is the main streaming event
                            delta = event.get("delta", "")
                            part = event.get("part", {})
                            content = delta or part.get("text", "") or part.get("content", "")

                            if content and on_message:
                                msg = StreamMessage(
                                    type=MessageType.ASSISTANT,
                                    content=content,
                                    raw=event,
                                )
                                result = on_message(msg)
                                if inspect.isawaitable(result):
                                    await result

                        elif event_type == "message.updated":
                            # Full message update - extract final content, don't call on_message
                            # (on_message is for progress updates, not final content)
                            info = event.get("info", {})
                            parts = info.get("parts", [])
                            for part in parts:
                                part_type = part.get("type", "")
                                if part_type == "text":
                                    text = part.get("text", "")
                                    if text and text not in content_parts:
                                        content_parts.append(text)
                                        # Don't call on_message for final text - it's not progress
                                elif part_type == "tool-invocation" or part_type == "tool":
                                    # Tool use is progress - show it
                                    tool_name = part.get("name", part.get("tool", ""))
                                    tool_input = part.get("input", {})

                                    # Create human-readable content for tool use
                                    if "webfetch" in tool_name.lower() or "websearch" in tool_name.lower():
                                        query = tool_input.get("query", tool_input.get("url", ""))
                                        tool_content = f"Searching: {query[:50]}..." if len(query) > 50 else f"Searching: {query}"
                                    elif "read" in tool_name.lower():
                                        path = tool_input.get("path", tool_input.get("file_path", ""))
                                        tool_content = f"Reading: {path[:50]}..." if len(path) > 50 else f"Reading: {path}"
                                    else:
                                        tool_content = f"Using {tool_name}..."

                                    tool_msg = StreamMessage(
                                        type=MessageType.TOOL_USE,
                                        content=tool_content,
                                        raw=event,
                                        tool_name=tool_name,
                                        tool_input=tool_input,
                                    )
                                    messages.append(tool_msg)
                                    if on_message:
                                        result = on_message(tool_msg)
                                        if inspect.isawaitable(result):
                                            await result

                        elif event_type == "session.idle":
                            # Session finished
                            logger.debug("Session idle - execution complete")
                            break

                        elif event_type == "session.status":
                            # Session status update - check if completed
                            status = event.get("status", "")
                            if status in ("idle", "completed"):
                                logger.debug(f"Session status: {status} - execution complete")
                                break

                        elif event_type == "session.error":
                            error_info = event.get("error", {})
                            error_msg = error_info.get("message", str(event)) if isinstance(error_info, dict) else str(error_info)
                            return ExecutionResult(
                                success=False,
                                content="".join(content_parts),
                                messages=messages,
                                error=error_msg,
                                execution_time=time.time() - start_time,
                            )

                        elif event_type == "server.connected":
                            # Initial connection event - ignore
                            logger.debug("SSE connected to OpenCode server")
                            continue

                    except json_module.JSONDecodeError:
                        logger.debug(f"Non-JSON event line: {line_str[:50]}")
                        continue

            final_content = "".join(content_parts)
            return ExecutionResult(
                success=True,
                content=final_content,
                messages=messages,
                execution_time=time.time() - start_time,
            )

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during execution: {e}")
            return ExecutionResult(
                success=False,
                content="".join(content_parts),
                messages=messages,
                error=f"Connection error: {e}. Is OpenCode server running? (opencode serve)",
                execution_time=time.time() - start_time,
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                content="".join(content_parts),
                messages=messages,
                error=f"Execution timed out after {self.timeout} seconds",
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
        """Execute a prompt and yield messages as they arrive via SSE.

        Args:
            prompt: The prompt to send.
            system_prompt: Optional system prompt.

        Yields:
            StreamMessage objects as they are received.
        """
        provider_id, model_id = self._parse_model()
        logger.info(f"Streaming OpenCode with model={self.model}")

        try:
            session_id = await self._ensure_session()
            http = await self._get_http_session()

            # First send the message (async, non-blocking)
            body = {
                "model": {
                    "providerID": provider_id,
                    "modelID": model_id,
                },
                "parts": [
                    {"type": "text", "text": prompt}
                ],
            }

            if system_prompt:
                body["system"] = system_prompt

            # Send prompt asynchronously
            async with http.post(
                f"{self._base_url}/session/{session_id}/prompt_async",
                json=body,
            ) as resp:
                if resp.status not in (200, 204):
                    error_text = await resp.text()
                    yield StreamMessage(
                        type=MessageType.ERROR,
                        content=f"Failed to send prompt: {resp.status} {error_text}",
                    )
                    return

            # Subscribe to events for this session
            async with http.get(
                f"{self._base_url}/event",
                params={"session": session_id},
            ) as resp:
                async for line in resp.content:
                    line_str = line.decode("utf-8", errors="replace").strip()

                    # Skip empty lines and SSE prefixes
                    if not line_str or line_str.startswith(":"):
                        continue

                    # Parse SSE data
                    if line_str.startswith("data:"):
                        line_str = line_str[5:].strip()

                    if not line_str:
                        continue

                    try:
                        import json
                        event = json.loads(line_str)
                        event_type = event.get("type", "")

                        if event_type == "message.created":
                            content = event.get("content", "")
                            yield StreamMessage(
                                type=MessageType.ASSISTANT,
                                content=content,
                                raw=event,
                            )
                        elif event_type == "session.completed":
                            break
                        elif event_type == "session.error":
                            yield StreamMessage(
                                type=MessageType.ERROR,
                                content=str(event),
                                raw=event,
                            )
                            break
                    except json.JSONDecodeError:
                        logger.debug(f"Non-JSON event line: {line_str[:50]}")
                        continue

        except aiohttp.ClientError as e:
            yield StreamMessage(
                type=MessageType.ERROR,
                content=f"Connection error: {e}. Is OpenCode server running?",
            )
        except Exception as e:
            logger.exception("Unexpected error during streaming")
            yield StreamMessage(
                type=MessageType.ERROR,
                content=str(e),
            )

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    async def __aenter__(self) -> "OpenCodeExecutor":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()


def create_executor(
    model: str | None = None,
    timeout: float = 0.0,
    agent: str | None = None,
) -> OpenCodeExecutor:
    """Factory function to create an OpenCodeExecutor.

    Args:
        model: Model ID in format "provider/model-id".
        timeout: Timeout in seconds. 0 means default timeout.
        agent: Optional agent name.

    Returns:
        Configured OpenCodeExecutor instance.
    """
    return OpenCodeExecutor(model=model, timeout=timeout, agent=agent)


def create_planner_executor() -> OpenCodeExecutor:
    """Create an executor configured for the planner agent."""
    settings = get_settings()
    return OpenCodeExecutor(
        model=settings.planner_model,
        timeout=0,
        # Don't use custom agent name - use system prompt in orchestrator instead
    )


def create_researcher_executor() -> OpenCodeExecutor:
    """Create an executor configured for researcher agents.

    Note: webfetch is handled by OpenCode server based on permissions in opencode.json
    """
    settings = get_settings()
    return OpenCodeExecutor(
        model=settings.researcher_model,
        timeout=0,
    )


def create_synthesizer_executor() -> OpenCodeExecutor:
    """Create an executor configured for the synthesizer agent."""
    settings = get_settings()
    return OpenCodeExecutor(
        model=settings.synthesizer_model,
        timeout=0,
    )
