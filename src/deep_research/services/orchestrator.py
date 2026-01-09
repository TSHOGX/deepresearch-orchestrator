"""Research workflow orchestrator."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from deep_research.agents.prompts import PromptBuilder, detect_language
from deep_research.config import get_settings
from deep_research.models.events import (
    AgentCompletedEvent,
    AgentFailedEvent,
    AgentProgressEvent,
    AgentStartedEvent,
    CheckpointSavedEvent,
    ErrorEvent,
    PhaseChangeEvent,
    PlanDraftEvent,
    ReportReadyEvent,
    SynthesisProgressEvent,
    SynthesisStartedEvent,
)
from deep_research.models.research import (
    AgentProgress,
    AgentResult,
    AgentStatus,
    PlanItem,
    PlanItemStatus,
    ResearchPhase,
    ResearchPlan,
    ResearchSession,
    Source,
)
from deep_research.services.agent_executor import (
    ClaudeExecutor,
    ExecutionResult,
    StreamMessage,
    create_planner_executor,
    create_researcher_executor,
    create_synthesizer_executor,
)
from deep_research.services.event_bus import EventBus, get_event_bus
from deep_research.services.session_manager import SessionManager, get_session_manager

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class ResearchOrchestrator:
    """Orchestrates the three-phase research workflow.

    Phases:
    1. Planning - Generate a research plan from user query
    2. Research - Execute parallel researcher agents
    3. Synthesis - Combine findings into a final report
    """

    def __init__(
        self,
        session_manager: SessionManager | None = None,
        event_bus: EventBus | None = None,
    ):
        """Initialize the orchestrator.

        Args:
            session_manager: Session manager instance. Uses global if None.
            event_bus: Event bus instance. Uses global if None.
        """
        self._session_manager = session_manager
        self._event_bus = event_bus
        self._checkpoint_task: asyncio.Task | None = None
        self._cancelled = False

    async def _get_session_manager(self) -> SessionManager:
        """Get the session manager instance."""
        if self._session_manager is None:
            self._session_manager = await get_session_manager()
        return self._session_manager

    def _get_event_bus(self) -> EventBus:
        """Get the event bus instance."""
        if self._event_bus is None:
            self._event_bus = get_event_bus()
        return self._event_bus

    async def start_research(self, query: str, language: str | None = None) -> ResearchSession:
        """Start a new research session.

        Args:
            query: The user's research query.
            language: Preferred language. Auto-detected if None.

        Returns:
            The created research session.
        """
        # Detect language if not provided
        if language is None:
            language = detect_language(query)

        # Create session
        session = ResearchSession(
            user_query=query,
            detected_language=language,
            phase=ResearchPhase.PLANNING,
        )

        # Save to database
        manager = await self._get_session_manager()
        await manager.create_session(session)

        logger.info(f"Started research session {session.session_id}")
        return session

    async def run_planning_phase(self, session: ResearchSession) -> ResearchPlan:
        """Run the planning phase to generate a research plan.

        Args:
            session: The research session.

        Returns:
            The generated research plan.
        """
        logger.info(f"Starting planning phase for session {session.session_id}")

        # Update phase
        session.update_phase(ResearchPhase.PLANNING)
        await self._emit_phase_change(session, None, ResearchPhase.PLANNING)

        # Build prompts
        prompt_builder = PromptBuilder(language=session.detected_language)
        system_prompt, user_prompt = prompt_builder.build_planner_prompts(session.user_query)

        # Execute planner
        executor = create_planner_executor()
        result = await executor.execute(user_prompt, system_prompt)

        if not result.success:
            error_msg = f"Planning failed: {result.error}"
            logger.error(error_msg)
            await self._emit_error(session, "PLANNING_FAILED", error_msg)
            raise RuntimeError(error_msg)

        # Parse the plan from result
        plan = self._parse_plan_response(result.content)
        session.plan = plan

        # Update session
        manager = await self._get_session_manager()
        await manager.update_session(session)

        # Emit event
        await self._get_event_bus().publish(
            PlanDraftEvent(session_id=session.session_id, plan=plan)
        )

        # Move to plan review phase
        session.update_phase(ResearchPhase.PLAN_REVIEW)
        await manager.update_session(session)
        await self._emit_phase_change(session, ResearchPhase.PLANNING, ResearchPhase.PLAN_REVIEW)

        logger.info(f"Planning complete with {len(plan.plan_items)} items")
        return plan

    def _parse_plan_response(self, content: str) -> ResearchPlan:
        """Parse the planner's response into a ResearchPlan.

        Args:
            content: Raw response content.

        Returns:
            Parsed ResearchPlan.
        """
        # Try to extract JSON from the response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            # Fallback: create a simple plan
            logger.warning("Could not parse JSON from planner response, using fallback")
            return ResearchPlan(
                understanding="Unable to parse structured plan",
                plan_items=[
                    PlanItem(
                        topic="General Research",
                        description=content[:500],
                    )
                ],
            )

        try:
            data = json.loads(json_match.group())

            plan_items = []
            for item_data in data.get("plan_items", []):
                plan_items.append(
                    PlanItem(
                        id=item_data.get("id", str(uuid4())[:8]),
                        topic=item_data.get("topic", "Unknown"),
                        description=item_data.get("description", ""),
                        scope=item_data.get("scope", ""),
                        priority=item_data.get("priority", 1),
                        key_questions=item_data.get("key_questions", []),
                        suggested_sources=item_data.get("suggested_sources", []),
                    )
                )

            return ResearchPlan(
                understanding=data.get("understanding", ""),
                clarifications=data.get("clarifications", []),
                plan_items=plan_items,
                estimated_time_minutes=data.get("estimated_time_minutes", 30),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error parsing plan JSON: {e}")
            return ResearchPlan(
                understanding=content[:500],
                plan_items=[
                    PlanItem(
                        topic="Research",
                        description="Conduct general research on the topic",
                    )
                ],
            )

    async def confirm_plan(
        self,
        session: ResearchSession,
        modifications: list[PlanItem] | None = None,
        skip_items: list[str] | None = None,
    ) -> ResearchSession:
        """Confirm the research plan, optionally with modifications.

        Args:
            session: The research session.
            modifications: Optional modified plan items.
            skip_items: Optional list of item IDs to skip.

        Returns:
            Updated session.
        """
        if session.plan is None:
            raise ValueError("No plan to confirm")

        # Apply modifications
        if modifications:
            session.plan.plan_items = modifications

        # Mark skipped items
        if skip_items:
            for item_id in skip_items:
                session.plan.update_item_status(item_id, PlanItemStatus.SKIPPED)

        # Update session
        manager = await self._get_session_manager()
        await manager.update_session(session)

        logger.info(f"Plan confirmed for session {session.session_id}")
        return session

    async def run_research_phase(self, session: ResearchSession) -> list[AgentResult]:
        """Run the research phase with parallel agents.

        Args:
            session: The research session.

        Returns:
            List of agent results.
        """
        if session.plan is None:
            raise ValueError("No plan available for research")

        logger.info(f"Starting research phase for session {session.session_id}")

        # Update phase
        session.update_phase(ResearchPhase.RESEARCHING)
        manager = await self._get_session_manager()
        await manager.update_session(session)
        await self._emit_phase_change(session, ResearchPhase.PLAN_REVIEW, ResearchPhase.RESEARCHING)

        # Start checkpoint task
        self._start_checkpoint_task(session)

        try:
            # Get pending items
            pending_items = session.plan.get_pending_items()
            settings = get_settings()

            # Run agents in parallel with limit
            semaphore = asyncio.Semaphore(settings.max_parallel_agents)
            tasks = []

            for item in pending_items:
                task = asyncio.create_task(
                    self._run_researcher_with_semaphore(session, item, semaphore)
                )
                tasks.append(task)

            # Wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            agent_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Researcher failed: {result}")
                elif isinstance(result, AgentResult):
                    agent_results.append(result)
                    session.add_agent_result(result)

            # Update session
            await manager.update_session(session)
            return agent_results

        finally:
            self._stop_checkpoint_task()

    async def _run_researcher_with_semaphore(
        self,
        session: ResearchSession,
        item: PlanItem,
        semaphore: asyncio.Semaphore,
    ) -> AgentResult:
        """Run a single researcher agent with semaphore control.

        Args:
            session: The research session.
            item: The plan item to research.
            semaphore: Semaphore for concurrency control.

        Returns:
            The agent result.
        """
        async with semaphore:
            return await self._run_single_researcher(session, item)

    async def _run_single_researcher(
        self,
        session: ResearchSession,
        item: PlanItem,
    ) -> AgentResult:
        """Run a single researcher agent.

        Args:
            session: The research session.
            item: The plan item to research.

        Returns:
            The agent result.
        """
        agent_id = f"researcher-{item.id}"
        start_time = utc_now()

        # Update item status
        if session.plan:
            session.plan.update_item_status(item.id, PlanItemStatus.IN_PROGRESS)

        # Create progress tracking
        progress = AgentProgress(
            agent_id=agent_id,
            plan_item_id=item.id,
            topic=item.topic,
            status=AgentStatus.RUNNING,
            started_at=start_time,
        )
        session.update_agent_progress(progress)

        # Emit start event
        await self._get_event_bus().publish(
            AgentStartedEvent(
                session_id=session.session_id,
                agent_id=agent_id,
                plan_item_id=item.id,
                topic=item.topic,
            )
        )

        try:
            # Build prompts
            prompt_builder = PromptBuilder(language=session.detected_language)
            system_prompt, user_prompt = prompt_builder.build_researcher_prompts(
                topic=item.topic,
                description=item.description,
                key_questions=item.key_questions,
                suggested_sources=item.suggested_sources,
            )

            # Execute researcher
            executor = create_researcher_executor()

            async def on_message(msg: StreamMessage) -> None:
                """Handle streaming messages."""
                progress.current_action = msg.content[:100] if msg.content else ""
                progress.progress_percent = min(progress.progress_percent + 5, 90)
                await self._get_event_bus().publish(
                    AgentProgressEvent(
                        session_id=session.session_id,
                        progress=progress,
                    )
                )

            result = await executor.execute(user_prompt, system_prompt, on_message=on_message)

            if not result.success:
                raise RuntimeError(result.error or "Research failed")

            # Parse result
            agent_result = self._parse_researcher_response(
                agent_id, item.id, item.topic, result
            )

            # Update status
            progress.status = AgentStatus.COMPLETED
            progress.progress_percent = 100.0
            progress.completed_at = utc_now()
            session.update_agent_progress(progress)

            if session.plan:
                session.plan.update_item_status(item.id, PlanItemStatus.COMPLETED)

            # Emit completion event
            await self._get_event_bus().publish(
                AgentCompletedEvent(
                    session_id=session.session_id,
                    result=agent_result,
                )
            )

            logger.info(f"Researcher {agent_id} completed")
            return agent_result

        except Exception as e:
            logger.error(f"Researcher {agent_id} failed: {e}")

            progress.status = AgentStatus.FAILED
            progress.error = str(e)
            progress.completed_at = utc_now()
            session.update_agent_progress(progress)

            await self._get_event_bus().publish(
                AgentFailedEvent(
                    session_id=session.session_id,
                    agent_id=agent_id,
                    error=str(e),
                )
            )

            # Return a minimal result for failed agent
            return AgentResult(
                agent_id=agent_id,
                plan_item_id=item.id,
                topic=item.topic,
                findings=f"Research failed: {e}",
                confidence=0.0,
                execution_time=(utc_now() - start_time).total_seconds(),
            )

    def _parse_researcher_response(
        self,
        agent_id: str,
        plan_item_id: str,
        topic: str,
        result: ExecutionResult,
    ) -> AgentResult:
        """Parse researcher response into AgentResult.

        Args:
            agent_id: The agent ID.
            plan_item_id: The plan item ID.
            topic: The research topic.
            result: The execution result.

        Returns:
            Parsed AgentResult.
        """
        content = result.content

        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                data = json.loads(json_match.group())

                sources = []
                for src in data.get("sources", []):
                    sources.append(
                        Source(
                            url=src.get("url"),
                            title=src.get("title", "Unknown"),
                            snippet=src.get("snippet", ""),
                            reliability=src.get("reliability", "medium"),
                        )
                    )

                return AgentResult(
                    agent_id=agent_id,
                    plan_item_id=plan_item_id,
                    topic=topic,
                    findings=data.get("findings", content),
                    sources=sources,
                    confidence=data.get("confidence", 0.8),
                    raw_notes=content,
                    execution_time=result.execution_time,
                )
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback: use raw content
        return AgentResult(
            agent_id=agent_id,
            plan_item_id=plan_item_id,
            topic=topic,
            findings=content,
            confidence=0.7,
            raw_notes=content,
            execution_time=result.execution_time,
        )

    async def run_synthesis_phase(self, session: ResearchSession) -> str:
        """Run the synthesis phase to create the final report.

        Args:
            session: The research session.

        Returns:
            The final report as markdown.
        """
        logger.info(f"Starting synthesis phase for session {session.session_id}")

        # Update phase
        session.update_phase(ResearchPhase.SYNTHESIZING)
        manager = await self._get_session_manager()
        await manager.update_session(session)
        await self._emit_phase_change(
            session, ResearchPhase.RESEARCHING, ResearchPhase.SYNTHESIZING
        )

        # Emit synthesis started
        await self._get_event_bus().publish(
            SynthesisStartedEvent(
                session_id=session.session_id,
                total_results=len(session.agent_results),
            )
        )

        # Build prompts
        prompt_builder = PromptBuilder(language=session.detected_language)
        research_results = [
            {
                "topic": r.topic,
                "findings": r.findings,
                "confidence": r.confidence,
                "sources": [s.model_dump() for s in r.sources],
                "key_insights": [],  # Could extract from findings
            }
            for r in session.agent_results
        ]

        system_prompt, user_prompt = prompt_builder.build_synthesizer_prompts(
            original_query=session.user_query,
            research_results=research_results,
        )

        # Execute synthesizer
        executor = create_synthesizer_executor()

        progress_pct = 0.0

        async def on_message(msg: StreamMessage) -> None:
            nonlocal progress_pct
            progress_pct = min(progress_pct + 2, 95)
            await self._get_event_bus().publish(
                SynthesisProgressEvent(
                    session_id=session.session_id,
                    progress_percent=progress_pct,
                    current_action="Generating report...",
                )
            )

        result = await executor.execute(user_prompt, system_prompt, on_message=on_message)

        if not result.success:
            error_msg = f"Synthesis failed: {result.error}"
            logger.error(error_msg)
            await self._emit_error(session, "SYNTHESIS_FAILED", error_msg)
            raise RuntimeError(error_msg)

        # Store report
        session.final_report = result.content
        session.update_phase(ResearchPhase.COMPLETED)
        await manager.update_session(session)

        # Emit completion
        await self._emit_phase_change(
            session, ResearchPhase.SYNTHESIZING, ResearchPhase.COMPLETED
        )
        await self._get_event_bus().publish(
            ReportReadyEvent(
                session_id=session.session_id,
                report_preview=result.content[:500] if result.content else "",
            )
        )

        logger.info(f"Synthesis complete for session {session.session_id}")
        return result.content

    async def run_full_workflow(
        self,
        query: str,
        language: str | None = None,
        auto_confirm: bool = False,
    ) -> ResearchSession:
        """Run the complete research workflow.

        Args:
            query: The research query.
            language: Preferred language.
            auto_confirm: If True, automatically confirm the plan.

        Returns:
            The completed session.
        """
        # Start session
        session = await self.start_research(query, language)

        try:
            # Planning phase
            await self.run_planning_phase(session)

            # Auto-confirm or wait
            if auto_confirm:
                await self.confirm_plan(session)
            else:
                # In non-auto mode, caller should confirm
                return session

            # Research phase
            await self.run_research_phase(session)

            # Synthesis phase
            await self.run_synthesis_phase(session)

            return session

        except Exception as e:
            logger.error(f"Workflow failed for session {session.session_id}: {e}")
            session.error = str(e)
            session.update_phase(ResearchPhase.FAILED)

            manager = await self._get_session_manager()
            await manager.update_session(session)

            await self._emit_error(session, "WORKFLOW_FAILED", str(e))
            raise

    async def resume_session(self, session_id: str) -> ResearchSession | None:
        """Resume a session from its last checkpoint.

        Args:
            session_id: The session ID to resume.

        Returns:
            The restored session or None.
        """
        manager = await self._get_session_manager()
        session = await manager.restore_from_checkpoint(session_id)

        if session:
            logger.info(f"Resumed session {session_id} from checkpoint")

        return session

    def cancel(self) -> None:
        """Cancel the current workflow."""
        self._cancelled = True
        self._stop_checkpoint_task()

    def _start_checkpoint_task(self, session: ResearchSession) -> None:
        """Start periodic checkpoint saving."""
        settings = get_settings()
        interval = settings.checkpoint_interval_seconds

        async def checkpoint_loop() -> None:
            manager = await self._get_session_manager()
            while not self._cancelled:
                await asyncio.sleep(interval)
                if self._cancelled:
                    break
                try:
                    await manager.save_checkpoint(session)
                    await self._get_event_bus().publish(
                        CheckpointSavedEvent(session_id=session.session_id)
                    )
                except Exception as e:
                    logger.warning(f"Failed to save checkpoint: {e}")

        self._checkpoint_task = asyncio.create_task(checkpoint_loop())

    def _stop_checkpoint_task(self) -> None:
        """Stop the checkpoint task."""
        if self._checkpoint_task:
            self._checkpoint_task.cancel()
            self._checkpoint_task = None

    async def _emit_phase_change(
        self,
        session: ResearchSession,
        old_phase: ResearchPhase | None,
        new_phase: ResearchPhase,
    ) -> None:
        """Emit a phase change event."""
        await self._get_event_bus().publish(
            PhaseChangeEvent(
                session_id=session.session_id,
                old_phase=old_phase,
                new_phase=new_phase,
            )
        )

    async def _emit_error(
        self,
        session: ResearchSession,
        error_code: str,
        error_message: str,
    ) -> None:
        """Emit an error event."""
        await self._get_event_bus().publish(
            ErrorEvent(
                session_id=session.session_id,
                error_code=error_code,
                error_message=error_message,
            )
        )


async def get_orchestrator() -> ResearchOrchestrator:
    """Get an orchestrator instance."""
    return ResearchOrchestrator()
