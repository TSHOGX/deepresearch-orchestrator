"""Configuration API endpoints."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from deep_research.config import get_settings

router = APIRouter()


class ConfigResponse(BaseModel):
    """Configuration response model."""

    # API Server
    api_host: str
    api_port: int

    # Model Configuration
    planner_model: str
    researcher_model: str
    synthesizer_model: str

    # Research Settings
    max_parallel_agents: int
    agent_timeout_seconds: int
    checkpoint_interval_seconds: int

    # Logging
    log_level: str


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""

    planner_model: Literal["opus", "sonnet", "haiku"] | None = None
    researcher_model: Literal["opus", "sonnet", "haiku"] | None = None
    synthesizer_model: Literal["opus", "sonnet", "haiku"] | None = None
    max_parallel_agents: int | None = Field(default=None, ge=1, le=50)
    agent_timeout_seconds: int | None = Field(default=None, ge=60, le=1800)
    checkpoint_interval_seconds: int | None = Field(default=None, ge=10, le=300)


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get current configuration.

    Returns:
        Current configuration values.
    """
    settings = get_settings()

    return ConfigResponse(
        api_host=settings.api_host,
        api_port=settings.api_port,
        planner_model=settings.planner_model,
        researcher_model=settings.researcher_model,
        synthesizer_model=settings.synthesizer_model,
        max_parallel_agents=settings.max_parallel_agents,
        agent_timeout_seconds=settings.agent_timeout_seconds,
        checkpoint_interval_seconds=settings.checkpoint_interval_seconds,
        log_level=settings.log_level,
    )


@router.put("", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """Update configuration.

    Note: This only updates the in-memory settings and does not persist changes.
    For persistent changes, update environment variables or .env file.

    Args:
        request: Configuration updates.

    Returns:
        Updated configuration.
    """
    settings = get_settings()

    # Apply updates (runtime only, not persisted)
    if request.planner_model is not None:
        settings.planner_model = request.planner_model
    if request.researcher_model is not None:
        settings.researcher_model = request.researcher_model
    if request.synthesizer_model is not None:
        settings.synthesizer_model = request.synthesizer_model
    if request.max_parallel_agents is not None:
        settings.max_parallel_agents = request.max_parallel_agents
    if request.agent_timeout_seconds is not None:
        settings.agent_timeout_seconds = request.agent_timeout_seconds
    if request.checkpoint_interval_seconds is not None:
        settings.checkpoint_interval_seconds = request.checkpoint_interval_seconds

    return ConfigResponse(
        api_host=settings.api_host,
        api_port=settings.api_port,
        planner_model=settings.planner_model,
        researcher_model=settings.researcher_model,
        synthesizer_model=settings.synthesizer_model,
        max_parallel_agents=settings.max_parallel_agents,
        agent_timeout_seconds=settings.agent_timeout_seconds,
        checkpoint_interval_seconds=settings.checkpoint_interval_seconds,
        log_level=settings.log_level,
    )
