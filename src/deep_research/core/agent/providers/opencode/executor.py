"""OpenCode SDK executor implementation.

Uses HTTP API to communicate with OpenCode server for agent execution.
"""

import asyncio
import inspect
import json
import logging
import time
from pathlib import Path
from typing import AsyncIterator

import aiohttp
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


def _get_server_url() -> str:
    """Get OpenCode server URL from config."""
    server = _config.get("server", {})
    host = server.get("host", "127.0.0.1")
    port = server.get("port", 4096)
    return f"http://{host}:{port}"


def _map_model(logical_model: str) -> str:
    """Map logical model name to OpenCode model name."""
    models = _config.get("models", {})
    if logical_model in models.values():
        return logical_model
    return models.get(logical_model, logical_model)


@AgentRegistry.register("opencode")
class OpenCodeExecutor(AgentExecutor):
    """Executor using OpenCode SDK HTTP API.

    Connects to a running OpenCode server to execute prompts
    with support for streaming events and tool usage.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 600.0,
    ):
        """Initialize the executor.

        Args:
            model: Model ID (logical name or provider/model-id format).
            timeout: Timeout in seconds. 0 means default timeout.
        """
        self.model = _map_model(model) if model else _config["models"].get("minimax", "opencode/minimax-m2.1-free")
        self.timeout = timeout if timeout > 0 else 600.0
        self._base_url = _get_server_url()
        self._session_id: str | None = None
        self._http_session: aiohttp.ClientSession | None = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        return self._http_session

    async def _ensure_session(self) -> str:
        """Ensure we have an active OpenCode session."""
        if self._session_id:
            return self._session_id

        http = await self._get_http_session()
        async with http.post(f"{self._base_url}/session", json={}) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Failed to create session: {resp.status} {error_text}")
            data = await resp.json()
            self._session_id = data.get("id")
            logger.info(f"Created OpenCode session: {self._session_id}")
            return self._session_id

    def _parse_response_part(self, part: dict) -> StreamMessage | None:
        """Parse a response part into StreamMessage."""
        part_type = part.get("type", "")

        if part_type == "text":
            return StreamMessage(
                type=MessageType.ASSISTANT,
                content=part.get("text", ""),
                raw=part,
            )
        elif part_type == "tool":
            tool_name = part.get("tool_name", part.get("name", ""))
            tool_input = part.get("tool_input", part.get("input", {}))
            content = self._format_tool_content(tool_name, tool_input)
            return StreamMessage(
                type=MessageType.TOOL_USE,
                content=content,
                raw=part,
                tool_name=tool_name,
                tool_input=tool_input,
            )
        return None

    def _format_tool_content(self, tool_name: str, tool_input: dict) -> str:
        """Format tool use as human-readable content."""
        if "webfetch" in tool_name.lower() or "websearch" in tool_name.lower():
            query = tool_input.get("query", tool_input.get("url", ""))
            prefix = "Searching/Fetching"
            return f"{prefix}: {query[:50]}..." if len(query) > 50 else f"{prefix}: {query}"
        return f"Using {tool_name}..."

    def _parse_model(self) -> tuple[str, str]:
        """Parse model string into provider_id and model_id."""
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

        Uses SSE streaming to get progress updates during execution.
        """
        start_time = time.time()
        messages: list[StreamMessage] = []
        content_parts: list[str] = []

        provider_id, model_id = self._parse_model()
        logger.info(f"Executing OpenCode with model={self.model}")

        try:
            session_id = await self._ensure_session()
            http = await self._get_http_session()

            body = {
                "model": {"providerID": provider_id, "modelID": model_id},
                "parts": [{"type": "text", "text": prompt}],
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
                        success=False, content="", messages=messages,
                        error=f"Failed to send prompt: {resp.status} {error_text}",
                        execution_time=time.time() - start_time,
                    )

            # Subscribe to SSE events for real-time streaming
            logger.debug(f"Subscribing to SSE events for session {session_id}")

            async with http.get(
                f"{self._base_url}/event",
                params={"session": session_id},
            ) as resp:
                logger.debug(f"SSE connection status: {resp.status}")
                async for line in resp.content:
                    line_str = line.decode("utf-8", errors="replace").strip()

                    if not line_str or line_str.startswith(":"):
                        continue

                    if line_str.startswith("data:"):
                        line_str = line_str[5:].strip()
                    if not line_str:
                        continue

                    try:
                        event = json.loads(line_str)
                        event_type = event.get("type", "")
                        logger.debug(f"SSE event: type={event_type}")

                        if event_type == "message.part.updated":
                            # Streaming text chunk
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
                            for part in info.get("parts") or []:
                                part_type = part.get("type", "")
                                if part_type == "text":
                                    text = part.get("text", "")
                                    if text and text not in content_parts:
                                        content_parts.append(text)
                                        # Don't call on_message for final text - it's not progress
                                elif part_type in ("tool-invocation", "tool"):
                                    # Tool use is progress - show it
                                    tool_name = part.get("name", part.get("tool", ""))
                                    tool_input = part.get("input", {})
                                    tool_content = self._format_tool_content(tool_name, tool_input)
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
                            logger.debug("Session idle - execution complete")
                            break

                        elif event_type == "session.status":
                            status = event.get("status", "")
                            if status in ("idle", "completed"):
                                logger.debug(f"Session status: {status}")
                                break

                        elif event_type == "session.error":
                            error_info = event.get("error", {})
                            error_msg = error_info.get("message", str(event)) if isinstance(error_info, dict) else str(error_info)
                            return ExecutionResult(
                                success=False, content="".join(content_parts),
                                messages=messages, error=error_msg,
                                execution_time=time.time() - start_time,
                            )

                        elif event_type == "server.connected":
                            logger.debug("SSE connected to OpenCode server")
                            continue

                    except json.JSONDecodeError:
                        logger.debug(f"Non-JSON event line: {line_str[:50]}")
                        continue

            return ExecutionResult(
                success=True,
                content="".join(content_parts),
                messages=messages,
                execution_time=time.time() - start_time,
            )

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error during execution: {e}")
            return ExecutionResult(
                success=False, content="".join(content_parts), messages=messages,
                error=f"Connection error: {e}. Is OpenCode server running?",
                execution_time=time.time() - start_time,
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False, content="".join(content_parts), messages=messages,
                error=f"Execution timed out after {self.timeout} seconds",
                execution_time=time.time() - start_time,
            )
        except Exception as e:
            logger.exception("Unexpected error during execution")
            return ExecutionResult(
                success=False, content="".join(content_parts), messages=messages,
                error=str(e), execution_time=time.time() - start_time,
            )

    async def execute_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> AsyncIterator[StreamMessage]:
        """Execute and yield messages via SSE."""
        provider_id, model_id = self._parse_model()
        logger.info(f"Streaming OpenCode with model={self.model}")

        try:
            session_id = await self._ensure_session()
            http = await self._get_http_session()

            body = {
                "model": {"providerID": provider_id, "modelID": model_id},
                "parts": [{"type": "text", "text": prompt}],
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

            # Subscribe to events
            async with http.get(
                f"{self._base_url}/event",
                params={"session": session_id},
            ) as resp:
                async for line in resp.content:
                    msg = self._parse_sse_line(line)
                    if msg:
                        if msg.type == MessageType.SYSTEM and msg.content == "DONE":
                            break
                        yield msg

        except aiohttp.ClientError as e:
            yield StreamMessage(
                type=MessageType.ERROR,
                content=f"Connection error: {e}. Is OpenCode server running?",
            )
        except Exception as e:
            logger.exception("Unexpected error during streaming")
            yield StreamMessage(type=MessageType.ERROR, content=str(e))

    def _parse_sse_line(self, line: bytes) -> StreamMessage | None:
        """Parse SSE line into StreamMessage."""
        line_str = line.decode("utf-8", errors="replace").strip()
        if not line_str or line_str.startswith(":"):
            return None

        if line_str.startswith("data:"):
            line_str = line_str[5:].strip()
        if not line_str:
            return None

        try:
            event = json.loads(line_str)
            event_type = event.get("type", "")

            if event_type == "message.part.updated":
                # Streaming text chunk
                delta = event.get("delta", "")
                part = event.get("part", {})
                content = delta or part.get("text", "") or part.get("content", "")
                if content:
                    return StreamMessage(
                        type=MessageType.ASSISTANT,
                        content=content,
                        raw=event,
                    )
            elif event_type == "message.updated":
                # Full message update
                info = event.get("info", {})
                parts = info.get("parts", [])
                for part in parts:
                    if part.get("type") == "text":
                        return StreamMessage(
                            type=MessageType.ASSISTANT,
                            content=part.get("text", ""),
                            raw=event,
                        )
            elif event_type in ("session.idle", "session.status"):
                status = event.get("status", "idle")
                if status in ("idle", "completed"):
                    return StreamMessage(
                        type=MessageType.SYSTEM,
                        content="DONE",
                        raw=event,
                    )
            elif event_type == "session.error":
                error_info = event.get("error", {})
                error_msg = error_info.get("message", str(event)) if isinstance(error_info, dict) else str(error_info)
                return StreamMessage(
                    type=MessageType.ERROR,
                    content=error_msg,
                    raw=event,
                )
        except json.JSONDecodeError:
            logger.debug(f"Non-JSON event line: {line_str[:50]}")
        return None

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
