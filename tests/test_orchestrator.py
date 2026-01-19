"""Tests for research orchestrator."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deep_research.models.research import (
    PlanItem,
    PlanItemStatus,
    ResearchPhase,
    ResearchPlan,
    ResearchSession,
)
from deep_research.core.agent import ExecutionResult
from deep_research.services.event_bus import EventBus
from deep_research.services.orchestrator import ResearchOrchestrator
from deep_research.services.session_manager import SessionManager


@pytest.fixture
async def session_manager(tmp_path: Path) -> SessionManager:
    """Create a session manager with temporary database."""
    db_path = tmp_path / "test_sessions.db"
    manager = SessionManager(db_path=db_path)
    await manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture
def event_bus() -> EventBus:
    """Create an event bus."""
    return EventBus()


@pytest.fixture
def orchestrator(session_manager: SessionManager, event_bus: EventBus) -> ResearchOrchestrator:
    """Create an orchestrator with mocked dependencies."""
    return ResearchOrchestrator(
        session_manager=session_manager,
        event_bus=event_bus,
    )


class TestPlanParsing:
    """Test plan parsing logic."""

    def test_parse_valid_plan_json(self, orchestrator: ResearchOrchestrator) -> None:
        """Test parsing valid JSON plan response."""
        content = '''
        Here's the research plan:

        ```json
        {
          "understanding": "User wants to understand renewable energy",
          "clarifications": [],
          "plan_items": [
            {
              "id": "item1",
              "topic": "Solar Energy",
              "description": "Research solar power technology",
              "scope": "Focus on residential",
              "priority": 1,
              "key_questions": ["What is efficiency?"],
              "suggested_sources": ["DOE reports"]
            },
            {
              "id": "item2",
              "topic": "Wind Energy",
              "description": "Research wind power",
              "priority": 2
            }
          ],
          "estimated_time_minutes": 45
        }
        ```
        '''

        plan = orchestrator._parse_plan_response(content)

        assert plan.understanding == "User wants to understand renewable energy"
        assert len(plan.plan_items) == 2
        assert plan.plan_items[0].topic == "Solar Energy"
        assert plan.plan_items[0].priority == 1
        assert len(plan.plan_items[0].key_questions) == 1
        assert plan.estimated_time_minutes == 45

    def test_parse_invalid_json_raises_error(self, orchestrator: ResearchOrchestrator) -> None:
        """Test that invalid JSON raises ValueError instead of fallback."""
        content = "This is just text without any JSON"

        with pytest.raises(ValueError, match="Could not find JSON"):
            orchestrator._parse_plan_response(content)

    def test_parse_malformed_json_raises_error(self, orchestrator: ResearchOrchestrator) -> None:
        """Test that malformed JSON raises ValueError."""
        # Incomplete JSON without closing brace won't match the regex
        content = '{"understanding": "test", "plan_items": [{"topic": '

        # This triggers "Could not find JSON" because the regex requires matching braces
        with pytest.raises(ValueError, match="Could not find JSON"):
            orchestrator._parse_plan_response(content)

    def test_parse_invalid_json_syntax_raises_error(self, orchestrator: ResearchOrchestrator) -> None:
        """Test that syntactically invalid JSON raises ValueError."""
        # This has matching braces but invalid JSON syntax
        content = '{"understanding": "test", "plan_items": [{"topic": invalid}]}'

        with pytest.raises(ValueError, match="Failed to parse planner response as JSON"):
            orchestrator._parse_plan_response(content)

    def test_parse_clarification_response(self, orchestrator: ResearchOrchestrator) -> None:
        """Test parsing clarification mode response."""
        content = '''
        {
          "mode": "clarification",
          "understanding": "User wants to research e-commerce",
          "clarifications": ["Which platform?", "B2B or B2C?"]
        }
        '''

        result = orchestrator._parse_plan_response(content)

        assert isinstance(result, list)
        assert len(result) == 2
        assert "Which platform?" in result
        assert "B2B or B2C?" in result

    def test_parse_plan_from_code_block(self, orchestrator: ResearchOrchestrator) -> None:
        """Test parsing JSON from markdown code block."""
        content = '''Here is your plan:

```json
{
  "mode": "plan",
  "understanding": "Research renewable energy",
  "plan_items": [
    {
      "topic": "Solar Energy",
      "description": "Research solar",
      "priority": 1
    }
  ],
  "estimated_time_minutes": 30
}
```

Let me know if you have questions.'''

        result = orchestrator._parse_plan_response(content)

        assert isinstance(result, ResearchPlan)
        assert result.understanding == "Research renewable energy"
        assert len(result.plan_items) == 1
        assert result.plan_items[0].topic == "Solar Energy"


class TestResearcherResponseParsing:
    """Test researcher response parsing."""

    def test_parse_valid_researcher_json(
        self, orchestrator: ResearchOrchestrator
    ) -> None:
        """Test parsing valid researcher response."""
        result = ExecutionResult(
            success=True,
            content='''
            {
              "findings": "Solar energy has grown significantly",
              "sources": [
                {
                  "url": "https://example.com/solar",
                  "title": "Solar Report",
                  "snippet": "Key findings",
                  "reliability": "high"
                }
              ],
              "confidence": 0.9,
              "limitations": "Limited to 2023 data"
            }
            ''',
            execution_time=5.0,
        )

        agent_result = orchestrator._parse_researcher_response(
            "agent-1", "item-1", "Solar Energy", result
        )

        assert agent_result.agent_id == "agent-1"
        assert agent_result.topic == "Solar Energy"
        assert "Solar energy has grown" in agent_result.findings
        assert len(agent_result.sources) == 1
        assert agent_result.sources[0].reliability == "high"
        assert agent_result.confidence == 0.9

    def test_parse_plain_text_response(
        self, orchestrator: ResearchOrchestrator
    ) -> None:
        """Test parsing plain text response without JSON."""
        result = ExecutionResult(
            success=True,
            content="Solar energy is a rapidly growing sector with many benefits...",
            execution_time=3.0,
        )

        agent_result = orchestrator._parse_researcher_response(
            "agent-1", "item-1", "Solar Energy", result
        )

        assert agent_result.agent_id == "agent-1"
        assert "Solar energy is a rapidly" in agent_result.findings
        assert agent_result.confidence == 0.7  # Default fallback


class TestSessionManagement:
    """Test session management in orchestrator."""

    @pytest.mark.asyncio
    async def test_start_research_creates_session(
        self,
        orchestrator: ResearchOrchestrator,
        session_manager: SessionManager,
    ) -> None:
        """Test that start_research creates a new session."""
        session = await orchestrator.start_research("What is AI?")

        assert session.session_id is not None
        assert session.user_query == "What is AI?"
        assert session.phase == ResearchPhase.PLANNING
        assert session.detected_language == "en"

        # Verify saved in database
        saved = await session_manager.get_session(session.session_id)
        assert saved is not None
        assert saved.user_query == "What is AI?"

    @pytest.mark.asyncio
    async def test_start_research_detects_chinese(
        self,
        orchestrator: ResearchOrchestrator,
    ) -> None:
        """Test language detection for Chinese query."""
        session = await orchestrator.start_research("人工智能的最新发展是什么？")

        assert session.detected_language == "zh"

    @pytest.mark.asyncio
    async def test_confirm_plan(
        self,
        orchestrator: ResearchOrchestrator,
        session_manager: SessionManager,
    ) -> None:
        """Test confirming a research plan."""
        # Create session with plan
        session = await orchestrator.start_research("Test query")
        session.plan = ResearchPlan(
            understanding="Test",
            plan_items=[
                PlanItem(id="item1", topic="Topic 1", description="Desc 1"),
                PlanItem(id="item2", topic="Topic 2", description="Desc 2"),
            ],
        )
        await session_manager.update_session(session)

        # Confirm with skip
        session = await orchestrator.confirm_plan(session, skip_items=["item1"])

        assert session.plan is not None
        assert session.plan.plan_items[0].status == PlanItemStatus.SKIPPED
        assert session.plan.plan_items[1].status == PlanItemStatus.PENDING

    @pytest.mark.asyncio
    async def test_confirm_plan_without_plan_raises(
        self,
        orchestrator: ResearchOrchestrator,
    ) -> None:
        """Test that confirming without a plan raises error."""
        session = await orchestrator.start_research("Test")

        with pytest.raises(ValueError, match="No plan to confirm"):
            await orchestrator.confirm_plan(session)


class TestEventEmission:
    """Test event emission during workflow."""

    @pytest.mark.asyncio
    async def test_phase_change_events(
        self,
        orchestrator: ResearchOrchestrator,
        event_bus: EventBus,
    ) -> None:
        """Test that phase changes emit events."""
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe_all(handler)

        session = await orchestrator.start_research("Test query")

        # Simulate phase change
        await orchestrator._emit_phase_change(
            session, ResearchPhase.PLANNING, ResearchPhase.RESEARCHING
        )

        # Check events were emitted
        assert len(received_events) >= 1
        phase_events = [e for e in received_events if hasattr(e, "new_phase")]
        assert len(phase_events) >= 1

    @pytest.mark.asyncio
    async def test_error_events(
        self,
        orchestrator: ResearchOrchestrator,
        event_bus: EventBus,
    ) -> None:
        """Test that errors emit events."""
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe_all(handler)

        session = await orchestrator.start_research("Test query")

        await orchestrator._emit_error(session, "TEST_ERROR", "Test error message")

        error_events = [e for e in received_events if hasattr(e, "error_code")]
        assert len(error_events) == 1
        assert error_events[0].error_code == "TEST_ERROR"


class TestWorkflowControl:
    """Test workflow control methods."""

    def test_cancel_sets_flag(self, orchestrator: ResearchOrchestrator) -> None:
        """Test that cancel sets the cancelled flag."""
        assert orchestrator._cancelled is False

        orchestrator.cancel()

        assert orchestrator._cancelled is True

    @pytest.mark.asyncio
    async def test_resume_nonexistent_session(
        self, orchestrator: ResearchOrchestrator
    ) -> None:
        """Test resuming a session that doesn't exist."""
        result = await orchestrator.resume_session("nonexistent-id")
        assert result is None
