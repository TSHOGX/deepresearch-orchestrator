"""Tests for event system."""

import asyncio

import pytest

from deep_research.models.events import (
    AgentCompletedEvent,
    AgentProgressEvent,
    AgentStartedEvent,
    BaseEvent,
    ErrorEvent,
    EventType,
    HeartbeatEvent,
    PhaseChangeEvent,
    PlanDraftEvent,
    ReportReadyEvent,
)
from deep_research.models.research import (
    AgentProgress,
    AgentResult,
    AgentStatus,
    PlanItem,
    ResearchPhase,
    ResearchPlan,
)
from deep_research.services.event_bus import EventBus, get_event_bus, reset_event_bus


class TestEventTypes:
    """Test event model classes."""

    def test_base_event(self) -> None:
        """Test base event creation."""
        event = HeartbeatEvent(session_id="test-session")

        assert event.session_id == "test-session"
        assert event.event_type == EventType.HEARTBEAT
        assert event.timestamp is not None

    def test_event_to_sse(self) -> None:
        """Test SSE format conversion."""
        event = HeartbeatEvent(session_id="test-session")
        sse = event.to_sse()

        assert "event: heartbeat\n" in sse
        assert "data:" in sse
        assert "test-session" in sse
        assert sse.endswith("\n\n")

    def test_plan_draft_event(self) -> None:
        """Test plan draft event."""
        plan = ResearchPlan(
            understanding="Test understanding",
            plan_items=[
                PlanItem(topic="Topic 1", description="Desc 1"),
                PlanItem(topic="Topic 2", description="Desc 2"),
            ],
        )
        event = PlanDraftEvent(session_id="test", plan=plan)

        assert event.event_type == EventType.PLAN_DRAFT
        assert event.data["plan_items_count"] == 2

    def test_phase_change_event(self) -> None:
        """Test phase change event."""
        event = PhaseChangeEvent(
            session_id="test",
            old_phase=ResearchPhase.PLANNING,
            new_phase=ResearchPhase.RESEARCHING,
        )

        assert event.event_type == EventType.PHASE_CHANGE
        assert event.old_phase == ResearchPhase.PLANNING
        assert event.new_phase == ResearchPhase.RESEARCHING

    def test_agent_started_event(self) -> None:
        """Test agent started event."""
        event = AgentStartedEvent(
            session_id="test",
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Research topic",
        )

        assert event.event_type == EventType.AGENT_STARTED
        assert event.agent_id == "agent-1"

    def test_agent_progress_event(self) -> None:
        """Test agent progress event."""
        progress = AgentProgress(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Topic",
            status=AgentStatus.RUNNING,
            progress_percent=50.0,
        )
        event = AgentProgressEvent(session_id="test", progress=progress)

        assert event.event_type == EventType.AGENT_PROGRESS
        assert event.progress.progress_percent == 50.0

    def test_agent_completed_event(self) -> None:
        """Test agent completed event."""
        result = AgentResult(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Topic",
            findings="Important findings",
        )
        event = AgentCompletedEvent(session_id="test", result=result)

        assert event.event_type == EventType.AGENT_COMPLETED
        assert event.result.findings == "Important findings"

    def test_error_event(self) -> None:
        """Test error event."""
        event = ErrorEvent(
            session_id="test",
            error_code="TIMEOUT",
            error_message="Agent timed out",
            recoverable=True,
        )

        assert event.event_type == EventType.ERROR
        assert event.error_code == "TIMEOUT"
        assert event.recoverable is True

    def test_report_ready_event(self) -> None:
        """Test report ready event."""
        event = ReportReadyEvent(
            session_id="test",
            report_preview="# Research Report\n\nSummary...",
        )

        assert event.event_type == EventType.REPORT_READY
        assert "Research Report" in event.report_preview


class TestEventBus:
    """Test EventBus class."""

    def setup_method(self) -> None:
        """Reset event bus before each test."""
        reset_event_bus()

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self) -> None:
        """Test basic publish/subscribe."""
        bus = EventBus()
        received_events: list[BaseEvent] = []

        async def handler(event: BaseEvent) -> None:
            received_events.append(event)

        bus.subscribe(EventType.HEARTBEAT, handler)

        event = HeartbeatEvent(session_id="test")
        await bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].session_id == "test"

    @pytest.mark.asyncio
    async def test_unsubscribe(self) -> None:
        """Test unsubscribing from events."""
        bus = EventBus()
        received_events: list[BaseEvent] = []

        async def handler(event: BaseEvent) -> None:
            received_events.append(event)

        unsubscribe = bus.subscribe(EventType.HEARTBEAT, handler)

        # First event should be received
        await bus.publish(HeartbeatEvent(session_id="test1"))
        assert len(received_events) == 1

        # Unsubscribe
        unsubscribe()

        # Second event should not be received
        await bus.publish(HeartbeatEvent(session_id="test2"))
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_session_specific_subscription(self) -> None:
        """Test session-specific subscriptions."""
        bus = EventBus()
        session1_events: list[BaseEvent] = []
        session2_events: list[BaseEvent] = []

        async def handler1(event: BaseEvent) -> None:
            session1_events.append(event)

        async def handler2(event: BaseEvent) -> None:
            session2_events.append(event)

        bus.subscribe(EventType.HEARTBEAT, handler1, session_id="session-1")
        bus.subscribe(EventType.HEARTBEAT, handler2, session_id="session-2")

        await bus.publish(HeartbeatEvent(session_id="session-1"))
        await bus.publish(HeartbeatEvent(session_id="session-2"))

        assert len(session1_events) == 1
        assert len(session2_events) == 1
        assert session1_events[0].session_id == "session-1"
        assert session2_events[0].session_id == "session-2"

    @pytest.mark.asyncio
    async def test_subscribe_all(self) -> None:
        """Test subscribing to all event types."""
        bus = EventBus()
        received_events: list[BaseEvent] = []

        async def handler(event: BaseEvent) -> None:
            received_events.append(event)

        unsubscribe = bus.subscribe_all(handler)

        await bus.publish(HeartbeatEvent(session_id="test"))
        await bus.publish(ErrorEvent(session_id="test", error_message="test"))

        assert len(received_events) == 2

        unsubscribe()
        await bus.publish(HeartbeatEvent(session_id="test"))
        assert len(received_events) == 2

    @pytest.mark.asyncio
    async def test_session_stream(self) -> None:
        """Test session event streaming via queue."""
        bus = EventBus()

        queue = await bus.create_session_stream("test-session")

        await bus.publish(HeartbeatEvent(session_id="test-session"))
        await bus.publish(HeartbeatEvent(session_id="test-session"))

        # Events should be in queue
        event1 = queue.get_nowait()
        event2 = queue.get_nowait()

        assert event1.event_type == EventType.HEARTBEAT
        assert event2.event_type == EventType.HEARTBEAT

    @pytest.mark.asyncio
    async def test_close_session_stream(self) -> None:
        """Test closing a session stream."""
        bus = EventBus()

        await bus.create_session_stream("test-session")
        assert bus.get_session_queue("test-session") is not None

        await bus.close_session_stream("test-session")
        assert bus.get_session_queue("test-session") is None

    @pytest.mark.asyncio
    async def test_handler_exception_doesnt_break_publishing(self) -> None:
        """Test that handler exceptions don't break other handlers."""
        bus = EventBus()
        received_events: list[BaseEvent] = []

        async def bad_handler(event: BaseEvent) -> None:
            raise Exception("Handler error")

        async def good_handler(event: BaseEvent) -> None:
            received_events.append(event)

        bus.subscribe(EventType.HEARTBEAT, bad_handler)
        bus.subscribe(EventType.HEARTBEAT, good_handler)

        # Should not raise, and good_handler should still receive event
        await bus.publish(HeartbeatEvent(session_id="test"))
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_global_event_bus(self) -> None:
        """Test global event bus singleton."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()

        assert bus1 is bus2

        reset_event_bus()
        bus3 = get_event_bus()

        assert bus1 is not bus3

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Test clearing the event bus."""
        bus = EventBus()
        received = []

        async def handler(event: BaseEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.HEARTBEAT, handler)
        await bus.create_session_stream("test")

        await bus.clear()

        await bus.publish(HeartbeatEvent(session_id="test"))
        assert len(received) == 0
        assert bus.get_session_queue("test") is None
