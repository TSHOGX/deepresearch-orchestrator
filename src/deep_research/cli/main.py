"""CLI main entry point."""

import argparse
import asyncio
import json as json_lib
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt

from deep_research.cli.components import (
    ClarificationDisplay,
    PlanDisplay,
    ProgressDisplay,
    ReportDisplay,
    StatusDisplay,
    display_welcome,
    prompt_confirm_plan,
    sanitize_input,
)
from deep_research.config import get_settings
from deep_research.models.events import EventType
from deep_research.models.research import AgentStatus, PlanItemStatus, ResearchPhase, ResearchPlan
from deep_research.services.event_bus import get_event_bus
from deep_research.services.orchestrator import ResearchOrchestrator
from deep_research.services.session_manager import get_session_manager, reset_session_manager


console = Console()
logger = logging.getLogger(__name__)


async def run_interactive_research(
    query: str,
    auto_confirm: bool = False,
    batch_mode: bool = False,
    output_file: str | None = None,
    json_output: bool = False,
) -> int:
    """Run an interactive research session.

    Args:
        query: The research query.
        auto_confirm: If True, automatically confirm the plan.
        batch_mode: If True, run in non-interactive batch mode.
        output_file: Output file path for the report.
        json_output: If True, output results in JSON format.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    import time

    start_time = time.time()
    settings = get_settings()
    settings.ensure_directories()

    orchestrator = ResearchOrchestrator()
    event_bus = get_event_bus()

    # In batch mode, force auto_confirm and use simple output
    if batch_mode:
        auto_confirm = True

    # Helper for output (batch mode uses simple print, otherwise Rich)
    # In JSON mode, progress goes to stderr to keep stdout clean for JSON
    def log_info(msg: str) -> None:
        if json_output:
            print(f"[INFO] {msg}", file=sys.stderr, flush=True)
        elif batch_mode:
            print(f"[INFO] {msg}", flush=True)
        else:
            console.print(f"[bold blue]{msg}[/bold blue]")

    def log_phase(phase: str, msg: str) -> None:
        if json_output:
            print(f"[{phase}] {msg}", file=sys.stderr, flush=True)
        elif batch_mode:
            print(f"[{phase}] {msg}", flush=True)
        else:
            console.print(f"[yellow]{phase}:[/yellow] {msg}")

    def log_error(msg: str) -> None:
        # Errors always go to stderr
        if batch_mode or json_output:
            print(f"[ERROR] {msg}", file=sys.stderr, flush=True)
        else:
            console.print(f"[red]{msg}[/red]")

    # Initialize display components (only used in non-batch mode)
    progress_display = None
    report_display = None
    status_display = None
    plan_display = None

    if not batch_mode:
        progress_display = ProgressDisplay(console)
        report_display = ReportDisplay(console)
        status_display = StatusDisplay(console)
        plan_display = PlanDisplay(console)
        clarification_display = ClarificationDisplay(console)

    try:
        # Start research
        log_info("Starting research...")
        session = await orchestrator.start_research(query)

        # Planning phase with clarification loop
        log_phase("Phase 1", "Planning research strategy...")

        # Track current planning action for display
        planning_status = {"action": "Analyzing query..."}

        async def run_planning_with_progress():
            """Run planning phase with progress event subscription."""
            if not batch_mode:
                # Subscribe to planning progress events
                async def handle_plan_progress(event):
                    if event.event_type == EventType.PLAN_PROGRESS:
                        planning_status["action"] = event.current_action

                unsubscribe = event_bus.subscribe_all(handle_plan_progress, session_id=session.session_id)
                try:
                    return await orchestrator.run_planning_phase(session, batch_mode=batch_mode)
                finally:
                    unsubscribe()
            else:
                return await orchestrator.run_planning_phase(session, batch_mode=batch_mode)

        while True:
            try:
                if not batch_mode:
                    # Use Live display for planning progress
                    from rich.spinner import Spinner
                    from rich.text import Text

                    result = None
                    planning_error = None

                    async def do_planning():
                        nonlocal result, planning_error
                        try:
                            result = await run_planning_with_progress()
                        except Exception as e:
                            planning_error = e

                    # Start planning task
                    planning_task = asyncio.create_task(do_planning())

                    # Update spinner while planning
                    with Live(console=console, refresh_per_second=4) as live:
                        while not planning_task.done():
                            action = planning_status["action"]
                            display_action = f" {action[:60]}..." if len(action) > 60 else f" {action}"
                            spinner = Spinner("dots", text=Text(display_action, style="dim"))
                            live.update(spinner)
                            await asyncio.sleep(0.1)

                    await planning_task

                    if planning_error:
                        raise planning_error
                else:
                    result = await orchestrator.run_planning_phase(session, batch_mode=batch_mode)
            except ValueError as e:
                # JSON parsing error - fail fast
                log_error(f"Failed to parse planner response: {e}")
                return 1

            if isinstance(result, list):
                # Got clarifications - need user input
                if batch_mode:
                    # In batch mode, this shouldn't happen due to batch_mode prompt
                    # but if it does, just log and retry (the prompt should prevent this)
                    log_error("Unexpected clarification request in batch mode")
                    return 1

                # Interactive mode: show clarifications and get answers
                console.print(clarification_display.render_clarifications(result))
                answers = clarification_display.prompt_answers(result)

                # Add to session history and retry planning
                session.clarification_history.extend(answers)
                manager = await get_session_manager()
                await manager.update_session(session)

                log_info("Retrying planning with clarification answers...")
                continue

            # Got a ResearchPlan - exit loop
            break

        if session.plan is None:
            log_error("Failed to create research plan")
            return 1

        # Show plan and get confirmation (only once, in prompt_confirm_plan)
        if batch_mode:
            # Batch/JSON mode: output plan info to stderr
            out = sys.stderr if json_output else sys.stdout
            print(f"\n[PLAN] Generated {len(session.plan.plan_items)} research items:", file=out, flush=True)
            for i, item in enumerate(session.plan.plan_items, 1):
                print(f"  {i}. {item.topic}", file=out, flush=True)

        if not auto_confirm:
            # Plan confirmation loop with feedback support
            while True:
                # prompt_confirm_plan will render the plan
                confirmed, skip_indices, feedback = prompt_confirm_plan(console, session.plan)

                if feedback:
                    # User provided feedback - add to clarification history and re-plan
                    console.print("\n[cyan]Refining plan based on your feedback...[/cyan]\n")
                    session.clarification_history.append(("User feedback on plan", feedback))
                    manager = await get_session_manager()
                    await manager.update_session(session)

                    # Clear the current plan and re-run planning
                    session.plan = None
                    try:
                        result = await orchestrator.run_planning_phase(session, batch_mode=False)
                    except ValueError as e:
                        log_error(f"Failed to parse planner response: {e}")
                        return 1

                    if isinstance(result, list):
                        # Got clarifications - show and collect answers
                        console.print(clarification_display.render_clarifications(result))
                        answers = clarification_display.prompt_answers(result)
                        session.clarification_history.extend(answers)
                        await manager.update_session(session)

                        log_info("Retrying planning with clarification answers...")
                        result = await orchestrator.run_planning_phase(session, batch_mode=False)

                    if session.plan is None:
                        log_error("Failed to create refined research plan")
                        return 1

                    # Loop back to show new plan and get confirmation
                    continue

                if not confirmed:
                    console.print("[yellow]Research cancelled.[/yellow]")
                    session.update_phase(ResearchPhase.CANCELLED)
                    manager = await get_session_manager()
                    await manager.update_session(session)
                    return 1

                # User confirmed - apply skips and exit loop
                if skip_indices:
                    skip_ids = [
                        session.plan.plan_items[i].id
                        for i in skip_indices
                        if 0 <= i < len(session.plan.plan_items)
                    ]
                    await orchestrator.confirm_plan(session, skip_items=skip_ids)
                else:
                    await orchestrator.confirm_plan(session)
                break  # Exit confirmation loop
        else:
            await orchestrator.confirm_plan(session)

        # Research phase
        log_phase("Phase 2", "Researching...")

        if not batch_mode and progress_display:
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
        else:
            # Batch mode: simple progress logging
            completed_count = 0
            total_items = len([i for i in session.plan.plan_items if i.status != "skipped"])
            out = sys.stderr if json_output else sys.stdout

            async def handle_batch_progress(event):
                nonlocal completed_count
                if event.event_type == EventType.AGENT_COMPLETED:
                    completed_count += 1
                    print(f"  Progress: {completed_count}/{total_items} agents completed", file=out, flush=True)

            unsubscribe = event_bus.subscribe_all(handle_batch_progress, session_id=session.session_id)

            try:
                await orchestrator.run_research_phase(session)
            finally:
                unsubscribe()

        # Synthesis phase
        log_phase("Phase 3", "Synthesizing findings...")

        if not batch_mode:
            with console.status("[bold green]Generating report...[/bold green]"):
                await orchestrator.run_synthesis_phase(session)
        else:
            await orchestrator.run_synthesis_phase(session)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Handle output
        if session.final_report:
            # Determine output filename
            if output_file:
                filename = output_file
            else:
                filename = str(settings.reports_dir / f"research_report_{session.session_id[:8]}.md")

            if json_output:
                # JSON output mode - also save report file
                Path(filename).write_text(session.final_report, encoding="utf-8")
                print(f"[SAVED] Report saved to: {filename}", file=sys.stderr, flush=True)

                # JSON output mode
                result = {
                    "session_id": session.session_id,
                    "query": query,
                    "status": session.phase.value,
                    "plan": {
                        "plan_items": [
                            {
                                "id": item.id,
                                "topic": item.topic,
                                "description": item.description,
                                "status": item.status.value if hasattr(item.status, 'value') else item.status,
                            }
                            for item in session.plan.plan_items
                        ]
                    } if session.plan else None,
                    "findings": [
                        {
                            "agent_id": result.agent_id,
                            "topic": result.topic,
                            "content": result.findings,
                        }
                        for result in session.agent_results
                    ],
                    "report": session.final_report,
                    "report_file": filename,
                    "execution_time_seconds": round(execution_time, 2),
                    "created_at": session.created_at.isoformat(),
                }
                print(json_lib.dumps(result, ensure_ascii=False, indent=2), flush=True)
                print(f"[COMPLETE] Research finished in {execution_time:.1f}s", file=sys.stderr, flush=True)
            else:
                # Display/save report
                if not batch_mode and report_display:
                    console.print("\n")
                    report_display.render_report(session.final_report)

                    # Offer to save
                    save = sanitize_input(Prompt.ask(
                        "\n[bold]Save report to file?[/bold]",
                        choices=["y", "n"],
                        default="y",
                    ))

                    if save == "y":
                        report_display.save_report(session.final_report, filename)
                else:
                    # Batch mode: auto-save
                    Path(filename).write_text(session.final_report, encoding="utf-8")
                    print(f"[SAVED] Report saved to: {filename}", flush=True)

            if not batch_mode and not json_output:
                console.print("\n[bold green]Research complete![/bold green]")
                if status_display:
                    console.print(status_display.render_status(session))
            elif not json_output:
                print(f"[COMPLETE] Research finished in {execution_time:.1f}s", flush=True)

            return 0
        else:
            log_error("No report generated")
            return 1

    except KeyboardInterrupt:
        if batch_mode or json_output:
            print("[INTERRUPTED] Research interrupted by user", file=sys.stderr, flush=True)
        else:
            console.print("\n[yellow]Research interrupted.[/yellow]")
        orchestrator.cancel()
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        if batch_mode or json_output:
            print(f"[ERROR] {e}", file=sys.stderr)
        else:
            console.print(f"\n[red]Error: {e}[/red]")
        logger.exception("Research failed")
        return 1


def _display_and_save_report(console: Console, session_id: str, report: str) -> None:
    """Display report and offer to save it.

    Args:
        console: Rich console instance.
        session_id: Session ID for default filename.
        report: The markdown report content.
    """
    report_display = ReportDisplay(console)
    report_display.render_report(report)

    # Offer to save
    save = sanitize_input(Prompt.ask(
        "\n[bold]Save report to file?[/bold]",
        choices=["y", "n"],
        default="y",
    ))

    if save == "y":
        settings = get_settings()
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        filename = str(settings.reports_dir / f"research_report_{session_id[:8]}.md")
        report_display.save_report(report, filename)


async def resume_session(session_id: str) -> None:
    """Resume a previous research session with the same UI as a fresh run.

    Args:
        session_id: The session ID to resume.
    """
    import time

    start_time = time.time()

    console.print(f"\n[bold blue]Resuming session {session_id}...[/bold blue]\n")

    orchestrator = ResearchOrchestrator()
    event_bus = get_event_bus()
    session = await orchestrator.resume_session(session_id)

    if not session:
        console.print("[red]Session not found or no checkpoint available.[/red]")
        return

    # Initialize display components
    progress_display = ProgressDisplay(console)
    report_display = ReportDisplay(console)
    status_display = StatusDisplay(console)
    plan_display = PlanDisplay(console)
    clarification_display = ClarificationDisplay(console)

    # Show current session status
    console.print(status_display.render_status(session))

    # Check for completed session - either by phase OR by having a final report
    if session.phase == ResearchPhase.COMPLETED or session.final_report:
        console.print("\n[bold green]✓ Phase 1: Planning[/bold green] - Completed")
        if session.plan:
            console.print(plan_display.render_plan(session.plan))

        console.print("[bold green]✓ Phase 2: Research[/bold green] - Completed")
        if session.agent_results:
            console.print(f"  [dim]{len(session.agent_results)} research items completed[/dim]")

        console.print("[bold green]✓ Phase 3: Synthesis[/bold green] - Completed")

        console.print("\n[green]Session already completed.[/green]")
        if session.final_report:
            _display_and_save_report(console, session.session_id, session.final_report)
        else:
            console.print("[yellow]Note: Session marked complete but no report found.[/yellow]")
        return

    elif session.phase in (ResearchPhase.FAILED, ResearchPhase.CANCELLED):
        console.print(f"\n[yellow]Session is in {session.phase.value} state.[/yellow]")
        if session.error:
            console.print(f"[red]Error: {session.error}[/red]")
        return

    try:
        # === Phase 1: Planning ===
        if session.phase in (ResearchPhase.PLANNING, ResearchPhase.PLAN_REVIEW):
            if session.phase == ResearchPhase.PLANNING:
                console.print("\n[yellow]Phase 1:[/yellow] Continuing planning phase...")

                # Track current planning action for display
                planning_status = {"action": "Analyzing query..."}

                async def run_resume_planning_with_progress():
                    """Run planning phase with progress event subscription."""
                    async def handle_plan_progress(event):
                        if event.event_type == EventType.PLAN_PROGRESS:
                            planning_status["action"] = event.current_action

                    unsubscribe = event_bus.subscribe_all(handle_plan_progress, session_id=session.session_id)
                    try:
                        return await orchestrator.run_planning_phase(session, batch_mode=False)
                    finally:
                        unsubscribe()

                while True:
                    try:
                        # Use Live display for planning progress
                        from rich.spinner import Spinner
                        from rich.text import Text

                        result = None
                        planning_error = None

                        async def do_resume_planning():
                            nonlocal result, planning_error
                            try:
                                result = await run_resume_planning_with_progress()
                            except Exception as e:
                                planning_error = e

                        # Start planning task
                        planning_task = asyncio.create_task(do_resume_planning())

                        # Update spinner while planning
                        with Live(console=console, refresh_per_second=4) as live:
                            while not planning_task.done():
                                action = planning_status["action"]
                                display_action = f" {action[:60]}..." if len(action) > 60 else f" {action}"
                                spinner = Spinner("dots", text=Text(display_action, style="dim"))
                                live.update(spinner)
                                await asyncio.sleep(0.1)

                        await planning_task

                        if planning_error:
                            raise planning_error
                    except ValueError as e:
                        console.print(f"[red]Failed to parse planner response: {e}[/red]")
                        return

                    if isinstance(result, list):
                        # Got clarifications - need user input
                        console.print(clarification_display.render_clarifications(result))
                        answers = clarification_display.prompt_answers(result)
                        session.clarification_history.extend(answers)
                        manager = await get_session_manager()
                        await manager.update_session(session)
                        console.print("[cyan]Retrying planning with clarification answers...[/cyan]")
                        continue
                    break

            # Now in PLAN_REVIEW phase - show plan and confirm
            console.print("\n[bold green]✓ Phase 1: Planning[/bold green] - Completed")

            if session.plan:
                # Plan confirmation loop with feedback support
                while True:
                    confirmed, skip_indices, feedback = prompt_confirm_plan(console, session.plan)

                    if feedback:
                        console.print("\n[cyan]Refining plan based on your feedback...[/cyan]\n")
                        session.clarification_history.append(("User feedback on plan", feedback))
                        manager = await get_session_manager()
                        await manager.update_session(session)

                        session.plan = None
                        try:
                            result = await orchestrator.run_planning_phase(session, batch_mode=False)
                        except ValueError as e:
                            console.print(f"[red]Failed to parse planner response: {e}[/red]")
                            return

                        if isinstance(result, list):
                            console.print(clarification_display.render_clarifications(result))
                            answers = clarification_display.prompt_answers(result)
                            session.clarification_history.extend(answers)
                            await manager.update_session(session)
                            await orchestrator.run_planning_phase(session, batch_mode=False)

                        if session.plan is None:
                            console.print("[red]Failed to create refined research plan[/red]")
                            return
                        continue

                    if not confirmed:
                        console.print("[yellow]Research cancelled.[/yellow]")
                        session.update_phase(ResearchPhase.CANCELLED)
                        manager = await get_session_manager()
                        await manager.update_session(session)
                        return

                    # User confirmed
                    if skip_indices:
                        skip_ids = [
                            session.plan.plan_items[i].id
                            for i in skip_indices
                            if 0 <= i < len(session.plan.plan_items)
                        ]
                        await orchestrator.confirm_plan(session, skip_items=skip_ids)
                    else:
                        await orchestrator.confirm_plan(session)
                    break
        else:
            # Already past planning phase - show completed planning info
            console.print("\n[bold green]✓ Phase 1: Planning[/bold green] - Completed")
            if session.plan:
                console.print(plan_display.render_plan(session.plan))

        # === Phase 2: Research ===
        if session.phase in (ResearchPhase.PLANNING, ResearchPhase.PLAN_REVIEW, ResearchPhase.RESEARCHING):
            console.print("\n[yellow]Phase 2:[/yellow] Researching...")

            if session.plan:
                progress_display.start()

                # Add all agents to progress display
                completed_agent_ids = {r.agent_id for r in session.agent_results}

                for item in session.plan.plan_items:
                    if item.status.value == "skipped":
                        continue
                    agent_id = f"researcher-{item.id}"
                    progress_display.add_agent(agent_id, item.topic)

                    # Mark already completed agents
                    if agent_id in completed_agent_ids or item.status == PlanItemStatus.COMPLETED:
                        progress_display.mark_completed(agent_id)

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

            console.print("[bold green]✓ Phase 2: Research[/bold green] - Completed")
        else:
            # Already past research phase
            console.print("[bold green]✓ Phase 2: Research[/bold green] - Completed")
            if session.agent_results:
                console.print(f"  [dim]{len(session.agent_results)} research items completed[/dim]")

        # === Phase 3: Synthesis ===
        if session.phase in (ResearchPhase.PLANNING, ResearchPhase.PLAN_REVIEW,
                              ResearchPhase.RESEARCHING, ResearchPhase.SYNTHESIZING):
            console.print("\n[yellow]Phase 3:[/yellow] Synthesizing findings...")

            with console.status("[bold green]Generating report...[/bold green]"):
                await orchestrator.run_synthesis_phase(session)

            console.print("[bold green]✓ Phase 3: Synthesis[/bold green] - Completed")

        # Calculate execution time
        execution_time = time.time() - start_time

        # Show final report
        if session.final_report:
            console.print(f"\n[bold green]Research complete![/bold green] (resumed session, {execution_time:.1f}s)")
            _display_and_save_report(console, session.session_id, session.final_report)
        else:
            console.print("[red]No report generated[/red]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Research interrupted.[/yellow]")
        orchestrator.cancel()
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")


async def list_sessions(use_pager: bool = True) -> None:
    """List recent research sessions.

    Args:
        use_pager: If True, use a pager for scrollable output (like less).
    """
    import os
    from datetime import timezone

    manager = await get_session_manager()
    sessions = await manager.list_sessions(limit=50)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    from rich.table import Table

    table = Table(title=f"Total Sessions: {len(sessions)}", expand=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Query", ratio=1)
    table.add_column("Phase", no_wrap=True)
    table.add_column("Created", no_wrap=True)

    for session in sessions:
        phase_style = {
            ResearchPhase.COMPLETED: "green",
            ResearchPhase.FAILED: "red",
            ResearchPhase.CANCELLED: "dim",
        }.get(session.phase, "yellow")

        # Convert UTC to local time for display
        created_at = session.created_at
        if created_at.tzinfo is None:
            # Assume UTC if no timezone info
            created_at = created_at.replace(tzinfo=timezone.utc)
        local_time = created_at.astimezone()

        table.add_row(
            session.session_id[:8],
            session.user_query,
            f"[{phase_style}]{session.phase.value}[/{phase_style}]",
            local_time.strftime("%Y-%m-%d %H:%M"),
        )

    # Use pager for scrollable output (like less/bat)
    if use_pager:
        os.environ.setdefault("LESS", "-RX")
        with console.pager(styles=True):
            console.print(table)
            console.print("\n[dim]Tip: Use short ID to resume, e.g., deep-research -r <ID>[/dim]")
    else:
        console.print(table)
        console.print("[dim]Tip: Use short ID to resume, e.g., deep-research -r <ID>[/dim]")


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
        help="List recent sessions (use --no-pager to disable scrolling)",
    )
    parser.add_argument(
        "--no-pager",
        action="store_true",
        help="Disable pager for --list output (useful for piping)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help="Batch mode: no interactive prompts, auto-save report",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Output file for the report (default: auto-generated)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format (for programmatic use)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    async def async_main() -> int:
        if args.list:
            await list_sessions(use_pager=not args.no_pager)
            return 0
        elif args.resume:
            await resume_session(args.resume)
            return 0
        else:
            # Batch mode validation
            if args.batch and not args.query:
                print("[ERROR] Query is required in batch mode", file=sys.stderr)
                return 1

            # Only show welcome in non-batch mode
            if not args.batch and not args.json:
                display_welcome(console)

            query = args.query
            if not query:
                query = sanitize_input(Prompt.ask("[bold]Enter your research question[/bold]"))

            # Sanitize query in case it comes from args with ANSI sequences
            query = sanitize_input(query).strip()
            if query:
                return await run_interactive_research(
                    query,
                    auto_confirm=args.auto_confirm,
                    batch_mode=args.batch,
                    output_file=args.output,
                    json_output=args.json,
                )
            else:
                if args.batch:
                    print("[ERROR] No query provided", file=sys.stderr)
                else:
                    console.print("[red]No query provided.[/red]")
                return 1

    async def run_with_cleanup() -> int:
        """Run async_main with proper cleanup of global resources."""
        try:
            return await async_main()
        finally:
            # Close the session manager's database connection to release threads
            await reset_session_manager()

    try:
        exit_code = asyncio.run(run_with_cleanup())
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
