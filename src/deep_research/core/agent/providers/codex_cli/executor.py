"""Codex CLI executor implementation.

Uses subprocess to call the Codex CLI with JSONL output.
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
    """Map logical model name to Codex CLI model name."""
    models = _config.get("models", {})
    if logical_model in models.values():
        return logical_model
    return models.get(logical_model, logical_model)


def _merge_prompts(system_prompt: str | None, prompt: str) -> str:
    """Merge system and user prompts for Codex CLI."""
    if system_prompt:
        return f"{system_prompt.strip()}\n\n{prompt}"
    return prompt


@AgentRegistry.register("codex_cli", default=True)
class CodexCLIExecutor(AgentExecutor):
    """Executor using Codex CLI subprocess.

    Handles spawning Codex CLI processes, parsing JSONL output,
    and managing timeouts.
    """

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 0.0,
    ):
        """Initialize the executor.

        Args:
            model: Model to use (logical name or direct model id).
            timeout: Timeout in seconds. 0 means no timeout.
        """
        default_model = _config.get("models", {}).get("default", "gpt-5.2")
        self.model = _map_model(model) if model else default_model
        self.timeout = timeout

    def _build_command(self) -> list[str]:
        """Build the Codex CLI command."""
        cli_config = _config.get("cli", {})
        base_args = cli_config.get("base", ["exec", "--json"])
        extra_args = cli_config.get("extra", [])

        cmd = ["codex"] + list(base_args) + list(extra_args) + ["-m", self.model]
        cmd.extend(["--cd", str(Path.cwd())])
        return cmd

    def _format_command_content(
        self,
        command: str,
        status: str | None,
        exit_code: int | None,
        output: str | None,
    ) -> str:
        """Format command execution as human-readable content."""
        if exit_code not in (None, 0):
            prefix = "Command failed"
        elif status == "in_progress":
            prefix = "Running"
        else:
            prefix = "Command finished"

        command_display = command[:120] + "..." if len(command) > 120 else command
        if output:
            output_display = output.strip().splitlines()
            if output_display:
                return f"{prefix}: {command_display}"
        return f"{prefix}: {command_display}"

    def _parse_event(self, event: dict) -> StreamMessage | None:
        """Parse a JSONL event from Codex CLI."""
        event_type = event.get("type", "")

        if event_type in ("item.started", "item.completed"):
            item = event.get("item", {})
            item_type = item.get("type", "")

            if item_type == "agent_message" or "text" in item:
                content = item.get("text", "")
                return StreamMessage(
                    type=MessageType.ASSISTANT,
                    content=content,
                    raw=event,
                )

            if item_type == "command_execution":
                command = item.get("command", "")
                status = item.get("status", "")
                exit_code = item.get("exit_code")
                output = item.get("aggregated_output")
                content = self._format_command_content(command, status, exit_code, output)
                msg_type = MessageType.ERROR if exit_code not in (None, 0) else MessageType.TOOL_USE
                tool_input = {
                    "command": command,
                    "status": status,
                    "exit_code": exit_code,
                }
                if output:
                    tool_input["output"] = output
                return StreamMessage(
                    type=msg_type,
                    content=content,
                    raw=event,
                    tool_name="command_execution",
                    tool_input=tool_input,
                )

            if item_type == "error":
                message = item.get("message") or item.get("error") or json.dumps(item)
                return StreamMessage(
                    type=MessageType.ERROR,
                    content=message,
                    raw=event,
                )

        if event_type == "turn.completed":
            return StreamMessage(
                type=MessageType.SYSTEM,
                content="DONE",
                raw=event,
            )

        if event_type == "error":
            error_info = event.get("error", {})
            message = error_info.get("message", str(event)) if isinstance(error_info, dict) else str(error_info)
            return StreamMessage(
                type=MessageType.ERROR,
                content=message,
                raw=event,
            )

        return None

    async def execute(
        self,
        prompt: str,
        system_prompt: str | None = None,
        on_message: MessageCallback | None = None,
    ) -> ExecutionResult:
        """Execute a Codex CLI command."""
        start_time = time.time()
        cmd = self._build_command()
        messages: list[StreamMessage] = []
        content_parts: list[str] = []
        merged_prompt = _merge_prompts(system_prompt, prompt)

        logger.info(f"Executing Codex CLI with model={self.model}")
        logger.debug(f"Command: {' '.join(cmd[:6])}...")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=10 * 1024 * 1024,  # 10MB
            )

            if process.stdin is not None:
                process.stdin.write(merged_prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()

            async def read_stream() -> None:
                if process.stdout is None:
                    return
                async for line in process.stdout:
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue
                    try:
                        event = json.loads(line_str)
                    except json.JSONDecodeError:
                        logger.debug(f"Failed to parse JSON line: {line_str[:200]}")
                        continue

                    message = self._parse_event(event)
                    if not message:
                        continue

                    messages.append(message)
                    if message.type == MessageType.ASSISTANT and message.content:
                        content_parts.append(message.content)

                    if on_message and message.type in (MessageType.TOOL_USE, MessageType.SYSTEM):
                        result = on_message(message)
                        if inspect.isawaitable(result):
                            await result
                    elif on_message and message.type == MessageType.ASSISTANT:
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
                error="Codex CLI not found. Please ensure 'codex' is installed and in PATH.",
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
        cmd = self._build_command()
        merged_prompt = _merge_prompts(system_prompt, prompt)
        logger.info(f"Streaming Codex CLI with model={self.model}")

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=10 * 1024 * 1024,
            )

            if process.stdin is not None:
                process.stdin.write(merged_prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()

            if process.stdout is None:
                return

            async for line in process.stdout:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    event = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse JSON line: {line_str[:200]}")
                    continue

                message = self._parse_event(event)
                if message:
                    yield message

            await process.wait()

            if process.returncode != 0 and process.stderr:
                stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
                yield StreamMessage(
                    type=MessageType.ERROR,
                    content=f"Process exited with code {process.returncode}: {stderr}",
                )

        except FileNotFoundError:
            yield StreamMessage(
                type=MessageType.ERROR,
                content="Codex CLI not found. Please ensure 'codex' is installed and in PATH.",
            )
        except Exception as e:
            logger.exception("Unexpected error during streaming")
            yield StreamMessage(type=MessageType.ERROR, content=str(e))
