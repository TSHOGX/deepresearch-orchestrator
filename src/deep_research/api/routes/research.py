"""Research API endpoints."""

import asyncio
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from deep_research.models.events import BaseEvent
from deep_research.models.research import (
    ConfirmPlanRequest,
    ResearchPhase,
    ResearchSessionResponse,
    StartResearchRequest,
)
from deep_research.services.event_bus import get_event_bus
from deep_research.services.orchestrator import ResearchOrchestrator
from deep_research.services.session_manager import get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/start", response_model=ResearchSessionResponse)
async def start_research(
    request: StartResearchRequest,
    background_tasks: BackgroundTasks,
) -> ResearchSessionResponse:
    """Start a new research session.

    Args:
        request: The research request with query.
        background_tasks: Background task manager.

    Returns:
        The created session information.
    """
    orchestrator = ResearchOrchestrator()

    # Start session and run planning
    session = await orchestrator.start_research(
        query=request.query,
        language=request.language,
    )

    # Run planning phase in background
    async def run_planning() -> None:
        try:
            await orchestrator.run_planning_phase(session)
        except Exception as e:
            logger.error(f"Planning failed: {e}")

    background_tasks.add_task(run_planning)

    return ResearchSessionResponse.from_session(session)


@router.get("/{session_id}", response_model=ResearchSessionResponse)
async def get_session(session_id: str) -> ResearchSessionResponse:
    """Get a research session by ID.

    Args:
        session_id: The session ID.

    Returns:
        The session information.
    """
    manager = await get_session_manager()
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return ResearchSessionResponse.from_session(session)


@router.post("/{session_id}/confirm", response_model=ResearchSessionResponse)
async def confirm_plan(
    session_id: str,
    request: ConfirmPlanRequest,
    background_tasks: BackgroundTasks,
) -> ResearchSessionResponse:
    """Confirm or modify a research plan.

    Args:
        session_id: The session ID.
        request: Confirmation request with optional modifications.
        background_tasks: Background task manager.

    Returns:
        Updated session information.
    """
    manager = await get_session_manager()
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.phase != ResearchPhase.PLAN_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Session is in {session.phase.value} phase, not plan_review",
        )

    orchestrator = ResearchOrchestrator(session_manager=manager)

    if not request.confirmed:
        return ResearchSessionResponse.from_session(session)

    # Apply modifications and confirm
    await orchestrator.confirm_plan(
        session,
        modifications=request.modifications,
        skip_items=request.skip_items,
    )

    # Run research and synthesis in background
    async def run_research_and_synthesis() -> None:
        try:
            await orchestrator.run_research_phase(session)
            await orchestrator.run_synthesis_phase(session)
        except Exception as e:
            logger.error(f"Research/Synthesis failed: {e}")
            session.error = str(e)
            session.update_phase(ResearchPhase.FAILED)
            await manager.update_session(session)

    background_tasks.add_task(run_research_and_synthesis)

    return ResearchSessionResponse.from_session(session)


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str) -> dict:
    """Cancel a research session.

    Args:
        session_id: The session ID.

    Returns:
        Cancellation status.
    """
    manager = await get_session_manager()
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.phase in (ResearchPhase.COMPLETED, ResearchPhase.FAILED, ResearchPhase.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Session already in terminal state: {session.phase.value}",
        )

    session.update_phase(ResearchPhase.CANCELLED)
    await manager.update_session(session)

    return {"status": "cancelled", "session_id": session_id}


@router.post("/{session_id}/resume", response_model=ResearchSessionResponse)
async def resume_session(
    session_id: str,
    background_tasks: BackgroundTasks,
) -> ResearchSessionResponse:
    """Resume a session from its last checkpoint.

    Args:
        session_id: The session ID.
        background_tasks: Background task manager.

    Returns:
        Resumed session information.
    """
    orchestrator = ResearchOrchestrator()
    session = await orchestrator.resume_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or no checkpoint available",
        )

    # Continue from current phase
    async def continue_workflow() -> None:
        manager = await get_session_manager()
        try:
            if session.phase == ResearchPhase.PLAN_REVIEW:
                # Wait for user to confirm
                pass
            elif session.phase == ResearchPhase.RESEARCHING:
                await orchestrator.run_research_phase(session)
                await orchestrator.run_synthesis_phase(session)
            elif session.phase == ResearchPhase.SYNTHESIZING:
                await orchestrator.run_synthesis_phase(session)
        except Exception as e:
            logger.error(f"Resume failed: {e}")
            session.error = str(e)
            session.update_phase(ResearchPhase.FAILED)
            await manager.update_session(session)

    if session.phase not in (
        ResearchPhase.COMPLETED,
        ResearchPhase.FAILED,
        ResearchPhase.CANCELLED,
        ResearchPhase.PLAN_REVIEW,
    ):
        background_tasks.add_task(continue_workflow)

    return ResearchSessionResponse.from_session(session)


@router.get("/{session_id}/report")
async def get_report(session_id: str) -> dict:
    """Get the final research report.

    Args:
        session_id: The session ID.

    Returns:
        The final report content.
    """
    manager = await get_session_manager()
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.phase != ResearchPhase.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Session is in {session.phase.value} phase",
        )

    if not session.final_report:
        raise HTTPException(status_code=404, detail="Report not available")

    return {
        "session_id": session_id,
        "report": session.final_report,
        "format": "markdown",
    }


@router.get("/{session_id}/stream")
async def stream_events(session_id: str) -> EventSourceResponse:
    """Stream real-time events for a session.

    Args:
        session_id: The session ID.

    Returns:
        SSE event stream.
    """
    manager = await get_session_manager()
    session = await manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    event_bus = get_event_bus()

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events."""
        queue = await event_bus.create_session_stream(session_id)

        try:
            while True:
                try:
                    # Wait for events with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    yield {
                        "event": event.event_type.value,
                        "data": event.model_dump_json(),
                    }

                    # Check for terminal events
                    if event.event_type.value in (
                        "report_ready",
                        "error",
                        "session_cancelled",
                    ):
                        # Give client time to receive, then close
                        await asyncio.sleep(1)
                        break

                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield {
                        "event": "heartbeat",
                        "data": '{"type": "heartbeat"}',
                    }

        finally:
            await event_bus.close_session_stream(session_id)

    return EventSourceResponse(event_generator())


@router.get("")
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    phase: str | None = None,
) -> dict:
    """List research sessions.

    Args:
        limit: Maximum number of sessions.
        offset: Number to skip.
        phase: Optional phase filter.

    Returns:
        List of sessions.
    """
    manager = await get_session_manager()

    phase_filter = None
    if phase:
        try:
            phase_filter = ResearchPhase(phase)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid phase: {phase}")

    sessions = await manager.list_sessions(limit=limit, offset=offset, phase=phase_filter)

    return {
        "sessions": [ResearchSessionResponse.from_session(s).model_dump() for s in sessions],
        "count": len(sessions),
        "limit": limit,
        "offset": offset,
    }
