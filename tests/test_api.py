"""Tests for API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport

from deep_research.api.app import app
from deep_research.config import reset_settings
from deep_research.services.session_manager import reset_session_manager


@pytest.fixture(autouse=True)
async def cleanup():
    """Clean up after each test."""
    yield
    reset_settings()
    await reset_session_manager()


@pytest.fixture
async def client() -> AsyncClient:
    """Create test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        """Test health endpoint returns healthy."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_readiness_check(self, client: AsyncClient) -> None:
        """Test readiness endpoint."""
        response = await client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True


class TestConfigEndpoints:
    """Test configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_config(self, client: AsyncClient) -> None:
        """Test getting configuration."""
        response = await client.get("/api/config")

        assert response.status_code == 200
        data = response.json()

        assert data["api_port"] == 12050
        assert data["planner_model"] == "opus"
        assert data["researcher_model"] == "sonnet"
        assert data["synthesizer_model"] == "sonnet"
        assert data["max_parallel_agents"] == 10

    @pytest.mark.asyncio
    async def test_update_config(self, client: AsyncClient) -> None:
        """Test updating configuration."""
        response = await client.put(
            "/api/config",
            json={
                "planner_model": "sonnet",
                "max_parallel_agents": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["planner_model"] == "sonnet"
        assert data["max_parallel_agents"] == 5

    @pytest.mark.asyncio
    async def test_update_config_validation(self, client: AsyncClient) -> None:
        """Test configuration validation."""
        response = await client.put(
            "/api/config",
            json={
                "max_parallel_agents": 100,  # Exceeds max of 50
            },
        )

        assert response.status_code == 422  # Validation error


class TestResearchEndpoints:
    """Test research API endpoints."""

    @pytest.mark.asyncio
    async def test_start_research(self, client: AsyncClient) -> None:
        """Test starting a research session."""
        response = await client.post(
            "/api/research/start",
            json={"query": "What are the benefits of renewable energy?"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "session_id" in data
        assert data["phase"] == "planning"

    @pytest.mark.asyncio
    async def test_start_research_with_language(self, client: AsyncClient) -> None:
        """Test starting research with specified language."""
        response = await client.post(
            "/api/research/start",
            json={
                "query": "What is AI?",
                "language": "zh",
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_session(self, client: AsyncClient) -> None:
        """Test getting a session."""
        # Create session first
        create_response = await client.post(
            "/api/research/start",
            json={"query": "Test query"},
        )
        session_id = create_response.json()["session_id"]

        # Get session
        response = await client.get(f"/api/research/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, client: AsyncClient) -> None:
        """Test getting a session that doesn't exist."""
        response = await client.get("/api/research/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_session(self, client: AsyncClient) -> None:
        """Test cancelling a session."""
        # Create session
        create_response = await client.post(
            "/api/research/start",
            json={"query": "Test query"},
        )
        session_id = create_response.json()["session_id"]

        # Cancel it
        response = await client.post(f"/api/research/{session_id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_completed_session_fails(self, client: AsyncClient) -> None:
        """Test that cancelling a completed session fails."""
        # Create and cancel session
        create_response = await client.post(
            "/api/research/start",
            json={"query": "Test query"},
        )
        session_id = create_response.json()["session_id"]
        await client.post(f"/api/research/{session_id}/cancel")

        # Try to cancel again
        response = await client.post(f"/api/research/{session_id}/cancel")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_sessions(self, client: AsyncClient) -> None:
        """Test listing sessions."""
        # Create a few sessions
        for i in range(3):
            await client.post(
                "/api/research/start",
                json={"query": f"Test query {i}"},
            )

        response = await client.get("/api/research")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) >= 3

    @pytest.mark.asyncio
    async def test_list_sessions_with_limit(self, client: AsyncClient) -> None:
        """Test listing sessions with limit."""
        # Create sessions
        for i in range(5):
            await client.post(
                "/api/research/start",
                json={"query": f"Test query {i}"},
            )

        response = await client.get("/api/research?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) == 2

    @pytest.mark.asyncio
    async def test_get_report_not_ready(self, client: AsyncClient) -> None:
        """Test getting report when not ready."""
        # Create session
        create_response = await client.post(
            "/api/research/start",
            json={"query": "Test query"},
        )
        session_id = create_response.json()["session_id"]

        # Try to get report
        response = await client.get(f"/api/research/{session_id}/report")

        assert response.status_code == 400  # Not ready

    @pytest.mark.asyncio
    async def test_resume_nonexistent_session(self, client: AsyncClient) -> None:
        """Test resuming a nonexistent session."""
        response = await client.post("/api/research/nonexistent-id/resume")

        assert response.status_code == 404
