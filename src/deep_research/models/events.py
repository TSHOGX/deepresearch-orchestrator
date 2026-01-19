"""Event types for SSE streaming."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from deep_research.models.research import (
    AgentProgress,
    AgentResult,
    ResearchPhase,
    ResearchPlan,
)


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Types of SSE events."""

    # Planning phase
    PLAN_PROGRESS = "plan_progress"
    PLAN_DRAFT = "plan_draft"
    PLAN_UPDATED = "plan_updated"

    # Phase transitions
    PHASE_CHANGE = "phase_change"

    # Agent lifecycle
    AGENT_STARTED = "agent_started"
    AGENT_PROGRESS = "agent_progress"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    # Checkpoints
    CHECKPOINT_SAVED = "checkpoint_saved"

    # Synthesis
    SYNTHESIS_STARTED = "synthesis_started"
    SYNTHESIS_PROGRESS = "synthesis_progress"

    # Completion
    REPORT_READY = "report_ready"

    # Errors
    ERROR = "error"

    # System
    HEARTBEAT = "heartbeat"
    SESSION_CANCELLED = "session_cancelled"


class BaseEvent(BaseModel):
    """Base class for all events."""

    event_type: EventType
    session_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Convert to SSE format string."""
        import json

        return f"event: {self.event_type.value}\ndata: {json.dumps(self.model_dump(mode='json'))}\n\n"


class PlanProgressEvent(BaseEvent):
    """Event for planning phase progress updates."""

    event_type: EventType = EventType.PLAN_PROGRESS
    current_action: str = ""


class PlanDraftEvent(BaseEvent):
    """Event when a plan draft is generated."""

    event_type: EventType = EventType.PLAN_DRAFT
    plan: ResearchPlan

    def model_post_init(self, __context: Any) -> None:
        """Set data from plan."""
        self.data = {"plan_items_count": len(self.plan.plan_items)}


class PlanUpdatedEvent(BaseEvent):
    """Event when a plan is updated after user modification."""

    event_type: EventType = EventType.PLAN_UPDATED
    plan: ResearchPlan


class PhaseChangeEvent(BaseEvent):
    """Event when the research phase changes."""

    event_type: EventType = EventType.PHASE_CHANGE
    old_phase: ResearchPhase | None = None
    new_phase: ResearchPhase


class AgentStartedEvent(BaseEvent):
    """Event when an agent starts."""

    event_type: EventType = EventType.AGENT_STARTED
    agent_id: str
    plan_item_id: str
    topic: str


class AgentProgressEvent(BaseEvent):
    """Event for agent progress updates."""

    event_type: EventType = EventType.AGENT_PROGRESS
    progress: AgentProgress


class AgentCompletedEvent(BaseEvent):
    """Event when an agent completes successfully."""

    event_type: EventType = EventType.AGENT_COMPLETED
    result: AgentResult


class AgentFailedEvent(BaseEvent):
    """Event when an agent fails."""

    event_type: EventType = EventType.AGENT_FAILED
    agent_id: str
    error: str


class CheckpointSavedEvent(BaseEvent):
    """Event when a checkpoint is saved."""

    event_type: EventType = EventType.CHECKPOINT_SAVED
    checkpoint_path: str | None = None


class SynthesisStartedEvent(BaseEvent):
    """Event when synthesis begins."""

    event_type: EventType = EventType.SYNTHESIS_STARTED
    total_results: int


class SynthesisProgressEvent(BaseEvent):
    """Event for synthesis progress."""

    event_type: EventType = EventType.SYNTHESIS_PROGRESS
    progress_percent: float = 0.0
    current_action: str = ""


class ReportReadyEvent(BaseEvent):
    """Event when the final report is ready."""

    event_type: EventType = EventType.REPORT_READY
    report_preview: str = ""


class ErrorEvent(BaseEvent):
    """Event for errors."""

    event_type: EventType = EventType.ERROR
    error_code: str = "UNKNOWN"
    error_message: str = ""
    recoverable: bool = True


class HeartbeatEvent(BaseEvent):
    """Heartbeat event to keep connection alive."""

    event_type: EventType = EventType.HEARTBEAT


class SessionCancelledEvent(BaseEvent):
    """Event when a session is cancelled."""

    event_type: EventType = EventType.SESSION_CANCELLED
    reason: str = ""
