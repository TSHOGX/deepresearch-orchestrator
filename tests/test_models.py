"""Tests for research data models."""

from datetime import datetime, timezone

import pytest

from deep_research.models.research import (
    AgentProgress,
    AgentResult,
    AgentStatus,
    Checkpoint,
    ConfirmPlanRequest,
    PlanItem,
    PlanItemStatus,
    ResearchPhase,
    ResearchPlan,
    ResearchSession,
    ResearchSessionResponse,
    Source,
    StartResearchRequest,
)


class TestPlanItem:
    """Test PlanItem model."""

    def test_default_values(self) -> None:
        """Test PlanItem with default values."""
        item = PlanItem(topic="Test topic", description="Test description")

        assert item.topic == "Test topic"
        assert item.description == "Test description"
        assert item.priority == 1
        assert item.status == PlanItemStatus.PENDING
        assert len(item.id) == 8  # UUID prefix

    def test_with_all_fields(self) -> None:
        """Test PlanItem with all fields."""
        item = PlanItem(
            id="test123",
            topic="AI Research",
            description="Research AI trends",
            scope="Focus on LLMs",
            priority=2,
            key_questions=["What are key trends?", "What are limitations?"],
            suggested_sources=["arxiv.org", "papers.google.com"],
            status=PlanItemStatus.IN_PROGRESS,
        )

        assert item.id == "test123"
        assert item.priority == 2
        assert len(item.key_questions) == 2
        assert item.status == PlanItemStatus.IN_PROGRESS


class TestResearchPlan:
    """Test ResearchPlan model."""

    def test_create_plan(self) -> None:
        """Test creating a research plan."""
        plan = ResearchPlan(
            understanding="User wants to understand AI",
            plan_items=[
                PlanItem(topic="Topic 1", description="Desc 1"),
                PlanItem(topic="Topic 2", description="Desc 2"),
            ],
        )

        assert plan.understanding == "User wants to understand AI"
        assert len(plan.plan_items) == 2

    def test_get_pending_items(self) -> None:
        """Test getting pending items."""
        plan = ResearchPlan(
            understanding="Test",
            plan_items=[
                PlanItem(id="1", topic="T1", description="D1", status=PlanItemStatus.PENDING),
                PlanItem(id="2", topic="T2", description="D2", status=PlanItemStatus.COMPLETED),
                PlanItem(id="3", topic="T3", description="D3", status=PlanItemStatus.PENDING),
            ],
        )

        pending = plan.get_pending_items()
        assert len(pending) == 2
        assert all(item.status == PlanItemStatus.PENDING for item in pending)

    def test_get_item_by_id(self) -> None:
        """Test getting item by ID."""
        plan = ResearchPlan(
            understanding="Test",
            plan_items=[
                PlanItem(id="abc", topic="Topic A", description="Desc A"),
                PlanItem(id="def", topic="Topic B", description="Desc B"),
            ],
        )

        item = plan.get_item_by_id("abc")
        assert item is not None
        assert item.topic == "Topic A"

        missing = plan.get_item_by_id("xyz")
        assert missing is None

    def test_update_item_status(self) -> None:
        """Test updating item status."""
        plan = ResearchPlan(
            understanding="Test",
            plan_items=[PlanItem(id="abc", topic="Topic", description="Desc")],
        )

        success = plan.update_item_status("abc", PlanItemStatus.COMPLETED)
        assert success is True
        assert plan.plan_items[0].status == PlanItemStatus.COMPLETED

        fail = plan.update_item_status("xyz", PlanItemStatus.COMPLETED)
        assert fail is False


class TestAgentProgress:
    """Test AgentProgress model."""

    def test_default_progress(self) -> None:
        """Test agent progress with defaults."""
        progress = AgentProgress(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Research topic",
        )

        assert progress.status == AgentStatus.PENDING
        assert progress.progress_percent == 0.0
        assert progress.started_at is None

    def test_running_progress(self) -> None:
        """Test agent progress while running."""
        progress = AgentProgress(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Research topic",
            status=AgentStatus.RUNNING,
            current_action="Searching web",
            tool_name="WebSearch",
            progress_percent=50.0,
            started_at=datetime.now(timezone.utc),
        )

        assert progress.status == AgentStatus.RUNNING
        assert progress.progress_percent == 50.0
        assert progress.started_at is not None


class TestAgentResult:
    """Test AgentResult model."""

    def test_basic_result(self) -> None:
        """Test basic agent result."""
        result = AgentResult(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Test topic",
            findings="Found important information",
        )

        assert result.confidence == 0.8  # default
        assert result.sources == []

    def test_result_with_sources(self) -> None:
        """Test agent result with sources."""
        result = AgentResult(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Test topic",
            findings="Found data",
            sources=[
                Source(url="https://example.com", title="Example", reliability="high"),
                Source(title="Book reference", snippet="Page 42"),
            ],
            confidence=0.9,
        )

        assert len(result.sources) == 2
        assert result.sources[0].reliability == "high"


class TestResearchSession:
    """Test ResearchSession model."""

    def test_create_session(self) -> None:
        """Test creating a research session."""
        session = ResearchSession(user_query="What is AI?")

        assert session.user_query == "What is AI?"
        assert session.phase == ResearchPhase.PLANNING
        assert session.plan is None
        assert len(session.session_id) > 0

    def test_update_phase(self) -> None:
        """Test updating session phase."""
        session = ResearchSession(user_query="Test query")
        original_updated = session.updated_at

        session.update_phase(ResearchPhase.RESEARCHING)

        assert session.phase == ResearchPhase.RESEARCHING
        assert session.updated_at >= original_updated
        assert session.completed_at is None

        session.update_phase(ResearchPhase.COMPLETED)
        assert session.completed_at is not None

    def test_add_agent_result(self) -> None:
        """Test adding agent result."""
        session = ResearchSession(user_query="Test")
        result = AgentResult(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Topic",
            findings="Findings",
        )

        session.add_agent_result(result)

        assert len(session.agent_results) == 1
        assert session.agent_results[0].agent_id == "agent-1"

    def test_update_agent_progress(self) -> None:
        """Test updating agent progress."""
        session = ResearchSession(user_query="Test")
        progress = AgentProgress(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Topic",
            status=AgentStatus.RUNNING,
        )

        session.update_agent_progress(progress)

        assert "agent-1" in session.agent_progress
        assert session.agent_progress["agent-1"].status == AgentStatus.RUNNING

    def test_to_checkpoint(self) -> None:
        """Test creating checkpoint from session."""
        session = ResearchSession(
            user_query="Test query",
            detected_language="zh",
        )
        session.plan = ResearchPlan(
            understanding="Test",
            plan_items=[PlanItem(topic="T", description="D")],
        )
        session.add_agent_result(
            AgentResult(
                agent_id="a1",
                plan_item_id="p1",
                topic="T",
                findings="F",
            )
        )

        checkpoint = session.to_checkpoint()

        assert checkpoint.session_id == session.session_id
        assert checkpoint.phase == session.phase
        assert checkpoint.plan is not None
        assert "a1" in checkpoint.completed_agents
        assert checkpoint.metadata["detected_language"] == "zh"

    def test_from_checkpoint(self) -> None:
        """Test restoring session from checkpoint."""
        checkpoint = Checkpoint(
            session_id="test-session",
            phase=ResearchPhase.RESEARCHING,
            plan=ResearchPlan(
                understanding="Test",
                plan_items=[PlanItem(topic="T", description="D")],
            ),
            completed_agents=["a1"],
            agent_results=[
                AgentResult(
                    agent_id="a1",
                    plan_item_id="p1",
                    topic="T",
                    findings="F",
                )
            ],
            pending_agents=["a2"],
            metadata={"user_query": "Original query", "detected_language": "en"},
        )

        session = ResearchSession.from_checkpoint(checkpoint)

        assert session.session_id == "test-session"
        assert session.user_query == "Original query"
        assert session.phase == ResearchPhase.RESEARCHING
        assert session.plan is not None
        assert len(session.agent_results) == 1


class TestRequestModels:
    """Test API request models."""

    def test_start_research_request(self) -> None:
        """Test start research request."""
        request = StartResearchRequest(query="What is machine learning?")
        assert request.query == "What is machine learning?"
        assert request.language is None

    def test_confirm_plan_request(self) -> None:
        """Test confirm plan request."""
        request = ConfirmPlanRequest(confirmed=True)
        assert request.confirmed is True
        assert request.modifications is None

        request_with_skip = ConfirmPlanRequest(
            confirmed=True, skip_items=["item-1", "item-2"]
        )
        assert request_with_skip.skip_items == ["item-1", "item-2"]


class TestResponseModels:
    """Test API response models."""

    def test_session_response_from_session(self) -> None:
        """Test creating response from session."""
        session = ResearchSession(user_query="Test")
        session.plan = ResearchPlan(
            understanding="Test",
            plan_items=[
                PlanItem(topic="T1", description="D1"),
                PlanItem(topic="T2", description="D2"),
            ],
        )
        session.add_agent_result(
            AgentResult(
                agent_id="a1",
                plan_item_id="p1",
                topic="T",
                findings="F",
            )
        )

        response = ResearchSessionResponse.from_session(session)

        assert response.session_id == session.session_id
        assert response.completed_agents == 1
        assert response.total_agents == 2
