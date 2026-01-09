"""Session and checkpoint management using SQLite."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from deep_research.config import get_settings
from deep_research.models.research import (
    Checkpoint,
    ResearchPhase,
    ResearchSession,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class SessionManager:
    """Manages research sessions and checkpoints using SQLite."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize the session manager.

        Args:
            db_path: Path to SQLite database. Uses config default if None.
        """
        if db_path is None:
            settings = get_settings()
            db_path = settings.database_path
        self.db_path = Path(db_path)
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the database and create tables if needed."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with self._lock:
            self._db = await aiosqlite.connect(str(self.db_path))
            self._db.row_factory = aiosqlite.Row

            # Create sessions table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_query TEXT NOT NULL,
                    detected_language TEXT DEFAULT 'en',
                    phase TEXT NOT NULL,
                    plan_json TEXT,
                    agent_progress_json TEXT,
                    agent_results_json TEXT,
                    final_report TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)

            # Create checkpoints table
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    checkpoint_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Create index for faster checkpoint lookups
            await self._db.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_session
                ON checkpoints(session_id, created_at DESC)
            """)

            await self._db.commit()
            logger.info(f"Database initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        async with self._lock:
            if self._db:
                await self._db.close()
                self._db = None

    async def _ensure_connected(self) -> aiosqlite.Connection:
        """Ensure database is connected."""
        if self._db is None:
            await self.initialize()
        return self._db  # type: ignore

    async def create_session(self, session: ResearchSession) -> ResearchSession:
        """Create a new research session.

        Args:
            session: The session to create.

        Returns:
            The created session.
        """
        db = await self._ensure_connected()

        async with self._lock:
            await db.execute(
                """
                INSERT INTO sessions (
                    session_id, user_query, detected_language, phase,
                    plan_json, agent_progress_json, agent_results_json,
                    final_report, error, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.user_query,
                    session.detected_language,
                    session.phase.value,
                    session.plan.model_dump_json() if session.plan else None,
                    json.dumps({k: v.model_dump(mode="json") for k, v in session.agent_progress.items()}),
                    json.dumps([r.model_dump(mode="json") for r in session.agent_results]),
                    session.final_report,
                    session.error,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.completed_at.isoformat() if session.completed_at else None,
                ),
            )
            await db.commit()

        logger.info(f"Created session {session.session_id}")
        return session

    async def get_session(self, session_id: str) -> ResearchSession | None:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            The session or None if not found.
        """
        db = await self._ensure_connected()

        async with db.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        return self._row_to_session(row)

    async def update_session(self, session: ResearchSession) -> ResearchSession:
        """Update an existing session.

        Args:
            session: The session to update.

        Returns:
            The updated session.
        """
        db = await self._ensure_connected()

        async with self._lock:
            await db.execute(
                """
                UPDATE sessions SET
                    phase = ?,
                    plan_json = ?,
                    agent_progress_json = ?,
                    agent_results_json = ?,
                    final_report = ?,
                    error = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE session_id = ?
                """,
                (
                    session.phase.value,
                    session.plan.model_dump_json() if session.plan else None,
                    json.dumps({k: v.model_dump(mode="json") for k, v in session.agent_progress.items()}),
                    json.dumps([r.model_dump(mode="json") for r in session.agent_results]),
                    session.final_report,
                    session.error,
                    session.updated_at.isoformat(),
                    session.completed_at.isoformat() if session.completed_at else None,
                    session.session_id,
                ),
            )
            await db.commit()

        logger.debug(f"Updated session {session.session_id}")
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its checkpoints.

        Args:
            session_id: The session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        db = await self._ensure_connected()

        async with self._lock:
            # Delete checkpoints first (foreign key)
            await db.execute(
                "DELETE FROM checkpoints WHERE session_id = ?",
                (session_id,),
            )

            cursor = await db.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            await db.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info(f"Deleted session {session_id}")
        return deleted

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        phase: ResearchPhase | None = None,
    ) -> list[ResearchSession]:
        """List sessions with optional filtering.

        Args:
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.
            phase: Optional phase filter.

        Returns:
            List of sessions.
        """
        db = await self._ensure_connected()

        if phase:
            query = """
                SELECT * FROM sessions WHERE phase = ?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """
            params = (phase.value, limit, offset)
        else:
            query = """
                SELECT * FROM sessions
                ORDER BY created_at DESC LIMIT ? OFFSET ?
            """
            params = (limit, offset)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_session(row) for row in rows]

    async def save_checkpoint(self, session: ResearchSession) -> str:
        """Save a checkpoint for a session.

        Args:
            session: The session to checkpoint.

        Returns:
            The checkpoint ID.
        """
        db = await self._ensure_connected()
        checkpoint = session.to_checkpoint()

        async with self._lock:
            cursor = await db.execute(
                """
                INSERT INTO checkpoints (session_id, checkpoint_json, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    session.session_id,
                    checkpoint.model_dump_json(),
                    checkpoint.checkpoint_time.isoformat(),
                ),
            )
            await db.commit()

        checkpoint_id = str(cursor.lastrowid)
        logger.info(f"Saved checkpoint {checkpoint_id} for session {session.session_id}")
        return checkpoint_id

    async def get_latest_checkpoint(self, session_id: str) -> Checkpoint | None:
        """Get the latest checkpoint for a session.

        Args:
            session_id: The session ID.

        Returns:
            The latest checkpoint or None.
        """
        db = await self._ensure_connected()

        async with db.execute(
            """
            SELECT checkpoint_json FROM checkpoints
            WHERE session_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        return Checkpoint.model_validate_json(row["checkpoint_json"])

    async def list_checkpoints(self, session_id: str) -> list[Checkpoint]:
        """List all checkpoints for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of checkpoints, newest first.
        """
        db = await self._ensure_connected()

        async with db.execute(
            """
            SELECT checkpoint_json FROM checkpoints
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [Checkpoint.model_validate_json(row["checkpoint_json"]) for row in rows]

    async def restore_from_checkpoint(self, session_id: str) -> ResearchSession | None:
        """Restore a session from its latest checkpoint.

        Args:
            session_id: The session ID.

        Returns:
            The restored session or None if no checkpoint exists.
        """
        checkpoint = await self.get_latest_checkpoint(session_id)
        if not checkpoint:
            logger.warning(f"No checkpoint found for session {session_id}")
            return None

        session = ResearchSession.from_checkpoint(checkpoint)
        logger.info(f"Restored session {session_id} from checkpoint")
        return session

    async def cleanup_old_checkpoints(
        self, session_id: str, keep_count: int = 5
    ) -> int:
        """Remove old checkpoints, keeping only the most recent ones.

        Args:
            session_id: The session ID.
            keep_count: Number of checkpoints to keep.

        Returns:
            Number of checkpoints deleted.
        """
        db = await self._ensure_connected()

        async with self._lock:
            # Get IDs to keep
            async with db.execute(
                """
                SELECT id FROM checkpoints
                WHERE session_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (session_id, keep_count),
            ) as cursor:
                keep_ids = [row["id"] for row in await cursor.fetchall()]

            if not keep_ids:
                return 0

            # Delete all except kept
            placeholders = ",".join("?" * len(keep_ids))
            cursor = await db.execute(
                f"""
                DELETE FROM checkpoints
                WHERE session_id = ? AND id NOT IN ({placeholders})
                """,
                (session_id, *keep_ids),
            )
            await db.commit()

        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old checkpoints for session {session_id}")
        return deleted

    def _row_to_session(self, row: aiosqlite.Row) -> ResearchSession:
        """Convert a database row to a ResearchSession.

        Args:
            row: Database row.

        Returns:
            ResearchSession instance.
        """
        from deep_research.models.research import (
            AgentProgress,
            AgentResult,
            ResearchPlan,
        )

        plan = None
        if row["plan_json"]:
            plan = ResearchPlan.model_validate_json(row["plan_json"])

        agent_progress = {}
        if row["agent_progress_json"]:
            progress_data = json.loads(row["agent_progress_json"])
            agent_progress = {
                k: AgentProgress.model_validate(v) for k, v in progress_data.items()
            }

        agent_results = []
        if row["agent_results_json"]:
            results_data = json.loads(row["agent_results_json"])
            agent_results = [AgentResult.model_validate(r) for r in results_data]

        return ResearchSession(
            session_id=row["session_id"],
            user_query=row["user_query"],
            detected_language=row["detected_language"],
            phase=ResearchPhase(row["phase"]),
            plan=plan,
            agent_progress=agent_progress,
            agent_results=agent_results,
            final_report=row["final_report"],
            error=row["error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
        )


# Global session manager instance
_session_manager: SessionManager | None = None


async def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
        await _session_manager.initialize()
    return _session_manager


async def reset_session_manager() -> None:
    """Reset the global session manager instance."""
    global _session_manager
    if _session_manager:
        await _session_manager.close()
    _session_manager = None
