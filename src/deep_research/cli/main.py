"""CLI main entry point."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt

from deep_research.cli.components import (
    PlanDisplay,
    ProgressDisplay,
    ReportDisplay,
    StatusDisplay,
    display_welcome,
    prompt_confirm_plan,
)
from deep_research.config import get_settings
from deep_research.models.events import EventType
from deep_research.models.research import AgentStatus, ResearchPhase
from deep_research.services.event_bus import get_event_bus
from deep_research.services.orchestrator import ResearchOrchestrator
from deep_research.services.session_manager import get_session_manager


console = Console()
logger = logging.getLogger(__name__)


async def run_interactive_research(query: str, auto_confirm: bool = False) -> None:
    """Run an interactive research session.

    Args:
        query: The research query.
        auto_confirm: If True, automatically confirm the plan.
    """
    settings = get_settings()
    settings.ensure_directories()

    orchestrator = ResearchOrchestrator()
    progress_display = ProgressDisplay(console)
    report_display = ReportDisplay(console)
    status_display = StatusDisplay(console)
    plan_display = PlanDisplay(console)

    event_bus = get_event_bus()

    try:
        # Start research
        console.print("\n[bold blue]Starting research...[/bold blue]\n")
        session = await orchestrator.start_research(query)

        # Planning phase
        console.print("[yellow]Phase 1:[/yellow] Planning research strategy...")
        await orchestrator.run_planning_phase(session)

        if session.plan is None:
            console.print("[red]Failed to create research plan[/red]")
            return

        # Show plan and get confirmation
        console.print(plan_display.render_plan(session.plan))

        if not auto_confirm:
            confirmed, skip_indices = prompt_confirm_plan(console, session.plan)

            if not confirmed:
                console.print("[yellow]Research cancelled.[/yellow]")
                session.update_phase(ResearchPhase.CANCELLED)
                manager = await get_session_manager()
                await manager.update_session(session)
                return

            # Apply skips
            if skip_indices:
                skip_ids = [
                    session.plan.plan_items[i].id
                    for i in skip_indices
                    if 0 <= i < len(session.plan.plan_items)
                ]
                await orchestrator.confirm_plan(session, skip_items=skip_ids)
            else:
                await orchestrator.confirm_plan(session)
        else:
            await orchestrator.confirm_plan(session)

        # Research phase
        console.print("\n[yellow]Phase 2:[/yellow] Researching...")

        progress_display.start()

        # Add agents to progress display
        for item in session.plan.plan_items:
            if item.status != "skipped":
                progress_display.add_agent(f"researcher-{item.id}", item.topic)

        # Subscribe to progress events
        async def handle_progress(event):
            if event.event_type == EventType.AGENT_PROGRESS:
                progress_display.update_agent(event.progress)
            elif event.event_type == EventType.AGENT_COMPLETED:
                progress_display.mark_completed(event.result.agent_id)

        unsubscribe = event_bus.subscribe_all(handle_progress, session_id=session.session_id)

        try:
            await orchestrator.run_research_phase(session)
        finally:
            unsubscribe()
            progress_display.stop()

        # Synthesis phase
        console.print("\n[yellow]Phase 3:[/yellow] Synthesizing findings...")

        with console.status("[bold green]Generating report...[/bold green]"):
            await orchestrator.run_synthesis_phase(session)

        # Display report
        if session.final_report:
            console.print("\n")
            report_display.render_report(session.final_report)

            # Offer to save
            save = Prompt.ask(
                "\n[bold]Save report to file?[/bold]",
                choices=["y", "n"],
                default="y",
            )

            if save == "y":
                filename = f"research_report_{session.session_id[:8]}.md"
                report_display.save_report(session.final_report, filename)

        console.print("\n[bold green]Research complete![/bold green]")
        console.print(status_display.render_status(session))

    except KeyboardInterrupt:
        console.print("\n[yellow]Research interrupted.[/yellow]")
        orchestrator.cancel()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        logger.exception("Research failed")


async def resume_session(session_id: str) -> None:
    """Resume a previous research session.

    Args:
        session_id: The session ID to resume.
    """
    console.print(f"\n[bold blue]Resuming session {session_id}...[/bold blue]\n")

    orchestrator = ResearchOrchestrator()
    session = await orchestrator.resume_session(session_id)

    if not session:
        console.print("[red]Session not found or no checkpoint available.[/red]")
        return

    status_display = StatusDisplay(console)
    console.print(status_display.render_status(session))

    if session.phase == ResearchPhase.COMPLETED:
        console.print("[green]Session already completed.[/green]")
        if session.final_report:
            report_display = ReportDisplay(console)
            report_display.render_report(session.final_report)
    elif session.phase in (ResearchPhase.FAILED, ResearchPhase.CANCELLED):
        console.print(f"[yellow]Session is in {session.phase.value} state.[/yellow]")
    else:
        console.print("[yellow]Continuing research...[/yellow]")
        # Continue workflow based on current phase
        try:
            if session.phase == ResearchPhase.PLAN_REVIEW:
                # Need to confirm plan
                if session.plan:
                    confirmed, skip_indices = prompt_confirm_plan(console, session.plan)
                    if confirmed:
                        await orchestrator.confirm_plan(session)
                        await orchestrator.run_research_phase(session)
                        await orchestrator.run_synthesis_phase(session)
            elif session.phase == ResearchPhase.RESEARCHING:
                await orchestrator.run_research_phase(session)
                await orchestrator.run_synthesis_phase(session)
            elif session.phase == ResearchPhase.SYNTHESIZING:
                await orchestrator.run_synthesis_phase(session)

            if session.final_report:
                report_display = ReportDisplay(console)
                report_display.render_report(session.final_report)

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


async def list_sessions() -> None:
    """List recent research sessions."""
    manager = await get_session_manager()
    sessions = await manager.list_sessions(limit=10)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    from rich.table import Table

    table = Table(title="Recent Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Query")
    table.add_column("Phase")
    table.add_column("Created")

    for session in sessions:
        phase_style = {
            ResearchPhase.COMPLETED: "green",
            ResearchPhase.FAILED: "red",
            ResearchPhase.CANCELLED: "dim",
        }.get(session.phase, "yellow")

        table.add_row(
            session.session_id[:8],
            session.user_query[:40] + ("..." if len(session.user_query) > 40 else ""),
            f"[{phase_style}]{session.phase.value}[/{phase_style}]",
            session.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Deep Research - Multi-Agent Research System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "query",
        nargs="?",
        help="Research query (interactive prompt if not provided)",
    )
    parser.add_argument(
        "--auto-confirm",
        "-y",
        action="store_true",
        help="Automatically confirm the research plan",
    )
    parser.add_argument(
        "--resume",
        "-r",
        metavar="SESSION_ID",
        help="Resume a previous session",
    )
    parser.add_argument(
        "--list",
        "-l",
        action="store_true",
        help="List recent sessions",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def async_main() -> None:
        if args.list:
            await list_sessions()
        elif args.resume:
            await resume_session(args.resume)
        else:
            display_welcome(console)

            query = args.query
            if not query:
                query = Prompt.ask("[bold]Enter your research question[/bold]")

            if query.strip():
                await run_interactive_research(query, auto_confirm=args.auto_confirm)
            else:
                console.print("[red]No query provided.[/red]")

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
