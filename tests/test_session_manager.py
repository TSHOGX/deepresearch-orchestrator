"""Tests for session manager."""

import asyncio
from pathlib import Path

import pytest

from deep_research.models.research import (
    AgentProgress,
    AgentResult,
    AgentStatus,
    PlanItem,
    ResearchPhase,
    ResearchPlan,
    ResearchSession,
)
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
def sample_session() -> ResearchSession:
    """Create a sample research session."""
    return ResearchSession(
        user_query="What are the benefits of renewable energy?",
        detected_language="en",
    )


@pytest.fixture
def sample_session_with_plan() -> ResearchSession:
    """Create a sample session with a research plan."""
    session = ResearchSession(
        user_query="Research AI trends",
        detected_language="en",
        phase=ResearchPhase.RESEARCHING,
    )
    session.plan = ResearchPlan(
        understanding="User wants to understand AI trends",
        plan_items=[
            PlanItem(
                id="item-1",
                topic="Machine Learning",
                description="Research ML trends",
            ),
            PlanItem(
                id="item-2",
                topic="Natural Language Processing",
                description="Research NLP developments",
            ),
        ],
    )
    return session


class TestSessionManager:
    """Test SessionManager class."""

    @pytest.mark.asyncio
    async def test_create_and_get_session(
        self, session_manager: SessionManager, sample_session: ResearchSession
    ) -> None:
        """Test creating and retrieving a session."""
        created = await session_manager.create_session(sample_session)
        assert created.session_id == sample_session.session_id

        retrieved = await session_manager.get_session(sample_session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id
        assert retrieved.user_query == sample_session.user_query
        assert retrieved.phase == ResearchPhase.PLANNING

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(
        self, session_manager: SessionManager
    ) -> None:
        """Test getting a session that doesn't exist."""
        result = await session_manager.get_session("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_session(
        self, session_manager: SessionManager, sample_session: ResearchSession
    ) -> None:
        """Test updating a session."""
        await session_manager.create_session(sample_session)

        # Update the session
        sample_session.update_phase(ResearchPhase.RESEARCHING)
        sample_session.plan = ResearchPlan(
            understanding="Test understanding",
            plan_items=[PlanItem(topic="Test", description="Test desc")],
        )
        await session_manager.update_session(sample_session)

        # Verify update
        retrieved = await session_manager.get_session(sample_session.session_id)
        assert retrieved is not None
        assert retrieved.phase == ResearchPhase.RESEARCHING
        assert retrieved.plan is not None
        assert len(retrieved.plan.plan_items) == 1

    @pytest.mark.asyncio
    async def test_update_session_with_results(
        self, session_manager: SessionManager, sample_session_with_plan: ResearchSession
    ) -> None:
        """Test updating session with agent results."""
        session = sample_session_with_plan
        await session_manager.create_session(session)

        # Add agent progress
        progress = AgentProgress(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Machine Learning",
            status=AgentStatus.RUNNING,
            progress_percent=50.0,
        )
        session.update_agent_progress(progress)

        # Add agent result
        result = AgentResult(
            agent_id="agent-1",
            plan_item_id="item-1",
            topic="Machine Learning",
            findings="ML is advancing rapidly",
            confidence=0.9,
        )
        session.add_agent_result(result)

        await session_manager.update_session(session)

        # Verify
        retrieved = await session_manager.get_session(session.session_id)
        assert retrieved is not None
        assert len(retrieved.agent_results) == 1
        assert retrieved.agent_results[0].findings == "ML is advancing rapidly"
        assert "agent-1" in retrieved.agent_progress
        assert retrieved.agent_progress["agent-1"].progress_percent == 50.0

    @pytest.mark.asyncio
    async def test_delete_session(
        self, session_manager: SessionManager, sample_session: ResearchSession
    ) -> None:
        """Test deleting a session."""
        await session_manager.create_session(sample_session)

        deleted = await session_manager.delete_session(sample_session.session_id)
        assert deleted is True

        retrieved = await session_manager.get_session(sample_session.session_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(
        self, session_manager: SessionManager
    ) -> None:
        """Test deleting a nonexistent session."""
        deleted = await session_manager.delete_session("nonexistent-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_sessions(
        self, session_manager: SessionManager
    ) -> None:
        """Test listing sessions."""
        # Create multiple sessions
        for i in range(5):
            session = ResearchSession(
                user_query=f"Query {i}",
            )
            await session_manager.create_session(session)

        sessions = await session_manager.list_sessions()
        assert len(sessions) == 5

    @pytest.mark.asyncio
    async def test_list_sessions_with_limit(
        self, session_manager: SessionManager
    ) -> None:
        """Test listing sessions with limit."""
        for i in range(5):
            session = ResearchSession(user_query=f"Query {i}")
            await session_manager.create_session(session)

        sessions = await session_manager.list_sessions(limit=3)
        assert len(sessions) == 3

    @pytest.mark.asyncio
    async def test_list_sessions_by_phase(
        self, session_manager: SessionManager
    ) -> None:
        """Test listing sessions filtered by phase."""
        # Create sessions in different phases
        session1 = ResearchSession(user_query="Query 1")
        session1.update_phase(ResearchPhase.PLANNING)
        await session_manager.create_session(session1)

        session2 = ResearchSession(user_query="Query 2")
        session2.update_phase(ResearchPhase.COMPLETED)
        await session_manager.create_session(session2)

        session3 = ResearchSession(user_query="Query 3")
        session3.update_phase(ResearchPhase.COMPLETED)
        await session_manager.create_session(session3)

        planning = await session_manager.list_sessions(phase=ResearchPhase.PLANNING)
        completed = await session_manager.list_sessions(phase=ResearchPhase.COMPLETED)

        assert len(planning) == 1
        assert len(completed) == 2


class TestCheckpoints:
    """Test checkpoint functionality."""

    @pytest.mark.asyncio
    async def test_save_and_get_checkpoint(
        self, session_manager: SessionManager, sample_session_with_plan: ResearchSession
    ) -> None:
        """Test saving and retrieving a checkpoint."""
        session = sample_session_with_plan
        await session_manager.create_session(session)

        checkpoint_id = await session_manager.save_checkpoint(session)
        assert checkpoint_id is not None

        checkpoint = await session_manager.get_latest_checkpoint(session.session_id)
        assert checkpoint is not None
        assert checkpoint.session_id == session.session_id
        assert checkpoint.phase == session.phase

    @pytest.mark.asyncio
    async def test_get_checkpoint_nonexistent(
        self, session_manager: SessionManager
    ) -> None:
        """Test getting checkpoint for nonexistent session."""
        checkpoint = await session_manager.get_latest_checkpoint("nonexistent")
        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_multiple_checkpoints(
        self, session_manager: SessionManager, sample_session_with_plan: ResearchSession
    ) -> None:
        """Test saving multiple checkpoints."""
        session = sample_session_with_plan
        await session_manager.create_session(session)

        # Save first checkpoint
        await session_manager.save_checkpoint(session)

        # Update and save second checkpoint
        session.add_agent_result(
            AgentResult(
                agent_id="a1",
                plan_item_id="p1",
                topic="T",
                findings="F",
            )
        )
        await session_manager.save_checkpoint(session)

        checkpoints = await session_manager.list_checkpoints(session.session_id)
        assert len(checkpoints) == 2

        # Latest checkpoint should have the result
        latest = checkpoints[0]
        assert len(latest.agent_results) == 1

    @pytest.mark.asyncio
    async def test_restore_from_checkpoint(
        self, session_manager: SessionManager, sample_session_with_plan: ResearchSession
    ) -> None:
        """Test restoring a session from checkpoint."""
        session = sample_session_with_plan
        await session_manager.create_session(session)
        await session_manager.save_checkpoint(session)

        restored = await session_manager.restore_from_checkpoint(session.session_id)
        assert restored is not None
        assert restored.session_id == session.session_id
        assert restored.phase == session.phase
        assert restored.plan is not None

    @pytest.mark.asyncio
    async def test_restore_nonexistent_checkpoint(
        self, session_manager: SessionManager
    ) -> None:
        """Test restoring from nonexistent checkpoint."""
        restored = await session_manager.restore_from_checkpoint("nonexistent")
        assert restored is None

    @pytest.mark.asyncio
    async def test_cleanup_old_checkpoints(
        self, session_manager: SessionManager, sample_session_with_plan: ResearchSession
    ) -> None:
        """Test cleaning up old checkpoints."""
        session = sample_session_with_plan
        await session_manager.create_session(session)

        # Create 10 checkpoints
        for _ in range(10):
            await session_manager.save_checkpoint(session)

        # Cleanup, keeping only 3
        deleted = await session_manager.cleanup_old_checkpoints(
            session.session_id, keep_count=3
        )
        assert deleted == 7

        remaining = await session_manager.list_checkpoints(session.session_id)
        assert len(remaining) == 3

    @pytest.mark.asyncio
    async def test_delete_session_deletes_checkpoints(
        self, session_manager: SessionManager, sample_session_with_plan: ResearchSession
    ) -> None:
        """Test that deleting session also deletes its checkpoints."""
        session = sample_session_with_plan
        await session_manager.create_session(session)
        await session_manager.save_checkpoint(session)
        await session_manager.save_checkpoint(session)

        await session_manager.delete_session(session.session_id)

        checkpoints = await session_manager.list_checkpoints(session.session_id)
        assert len(checkpoints) == 0
