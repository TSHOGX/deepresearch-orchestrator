"""Rich CLI components for the deep research system."""

from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from deep_research.models.research import (
    AgentProgress,
    AgentStatus,
    PlanItem,
    PlanItemStatus,
    ResearchPhase,
    ResearchPlan,
    ResearchSession,
)


class PlanDisplay:
    """Display component for research plans."""

    def __init__(self, console: Console | None = None):
        """Initialize the plan display.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    def render_plan(self, plan: ResearchPlan) -> Panel:
        """Render a research plan as a Rich panel.

        Args:
            plan: The research plan to display.

        Returns:
            Rich Panel containing the plan.
        """
        # Create table for plan items
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=3)
        table.add_column("Topic", style="bold")
        table.add_column("Priority", justify="center", width=8)
        table.add_column("Status", justify="center", width=12)

        for i, item in enumerate(plan.plan_items, 1):
            status_style = self._get_status_style(item.status)
            priority_text = "★" * (6 - item.priority)

            table.add_row(
                str(i),
                item.topic,
                Text(priority_text, style="yellow"),
                Text(item.status.value, style=status_style),
            )

        # Build content
        content = Group(
            Text(f"Understanding: {plan.understanding}\n", style="italic"),
            table,
        )

        if plan.clarifications:
            clarifications = Text("\nClarifications needed:\n", style="yellow")
            for c in plan.clarifications:
                clarifications.append(f"  • {c}\n")
            content = Group(content, clarifications)

        return Panel(
            content,
            title="[bold]Research Plan[/bold]",
            subtitle=f"Estimated time: {plan.estimated_time_minutes} minutes",
            border_style="blue",
        )

    def _get_status_style(self, status: PlanItemStatus) -> str:
        """Get style for status."""
        return {
            PlanItemStatus.PENDING: "dim",
            PlanItemStatus.IN_PROGRESS: "yellow",
            PlanItemStatus.COMPLETED: "green",
            PlanItemStatus.SKIPPED: "dim strikethrough",
        }.get(status, "dim")


class ProgressDisplay:
    """Display component for research progress."""

    def __init__(self, console: Console | None = None):
        """Initialize progress display.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )
        self._task_ids: dict[str, int] = {}

    def start(self) -> None:
        """Start the progress display."""
        self.progress.start()

    def stop(self) -> None:
        """Stop the progress display."""
        self.progress.stop()

    def add_agent(self, agent_id: str, topic: str) -> None:
        """Add an agent to track.

        Args:
            agent_id: The agent ID.
            topic: The research topic.
        """
        task_id = self.progress.add_task(topic, total=100)
        self._task_ids[agent_id] = task_id

    def update_agent(self, progress: AgentProgress) -> None:
        """Update agent progress.

        Args:
            progress: The agent progress.
        """
        if progress.agent_id in self._task_ids:
            task_id = self._task_ids[progress.agent_id]

            description = progress.topic
            if progress.current_action:
                description = f"{progress.topic}: {progress.current_action[:30]}..."

            self.progress.update(
                task_id,
                completed=progress.progress_percent,
                description=description,
            )

    def mark_completed(self, agent_id: str) -> None:
        """Mark an agent as completed.

        Args:
            agent_id: The agent ID.
        """
        if agent_id in self._task_ids:
            task_id = self._task_ids[agent_id]
            self.progress.update(task_id, completed=100)


class ReportDisplay:
    """Display component for research reports."""

    def __init__(self, console: Console | None = None):
        """Initialize report display.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    def render_report(self, report: str) -> None:
        """Render the final report.

        Args:
            report: The markdown report.
        """
        md = Markdown(report)
        self.console.print(
            Panel(
                md,
                title="[bold green]Research Report[/bold green]",
                border_style="green",
                padding=(1, 2),
            )
        )

    def save_report(self, report: str, path: str) -> None:
        """Save report to a file.

        Args:
            report: The markdown report.
            path: File path to save to.
        """
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        self.console.print(f"[green]Report saved to:[/green] {path}")


class StatusDisplay:
    """Display component for session status."""

    def __init__(self, console: Console | None = None):
        """Initialize status display.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    def render_status(self, session: ResearchSession) -> Panel:
        """Render session status.

        Args:
            session: The research session.

        Returns:
            Rich Panel with status.
        """
        phase_styles = {
            ResearchPhase.PLANNING: "yellow",
            ResearchPhase.PLAN_REVIEW: "cyan",
            ResearchPhase.RESEARCHING: "blue",
            ResearchPhase.SYNTHESIZING: "magenta",
            ResearchPhase.COMPLETED: "green",
            ResearchPhase.FAILED: "red",
            ResearchPhase.CANCELLED: "dim",
        }

        style = phase_styles.get(session.phase, "white")

        # Build status info
        lines = [
            f"[bold]Session:[/bold] {session.session_id[:8]}...",
            f"[bold]Phase:[/bold] [{style}]{session.phase.value}[/{style}]",
            f"[bold]Query:[/bold] {session.user_query[:50]}...",
        ]

        if session.plan:
            completed = sum(
                1 for item in session.plan.plan_items
                if item.status == PlanItemStatus.COMPLETED
            )
            total = len(session.plan.plan_items)
            lines.append(f"[bold]Progress:[/bold] {completed}/{total} items")

        if session.error:
            lines.append(f"[bold red]Error:[/bold red] {session.error}")

        content = "\n".join(lines)

        return Panel(
            content,
            title="[bold]Research Status[/bold]",
            border_style=style,
        )


def create_header() -> Panel:
    """Create the CLI header.

    Returns:
        Rich Panel with header.
    """
    header_text = Text()
    header_text.append("Deep Research", style="bold magenta")
    header_text.append(" - Multi-Agent Research System", style="dim")

    return Panel(
        header_text,
        style="bold blue",
        padding=(0, 2),
    )


def prompt_confirm_plan(console: Console, plan: ResearchPlan) -> tuple[bool, list[int] | None]:
    """Prompt user to confirm or modify the plan.

    Args:
        console: Rich console.
        plan: The research plan.

    Returns:
        Tuple of (confirmed, skip_indices).
    """
    plan_display = PlanDisplay(console)
    console.print(plan_display.render_plan(plan))

    console.print("\n[bold]Options:[/bold]")
    console.print("  [green]y[/green] - Confirm and start research")
    console.print("  [yellow]s[/yellow] - Skip specific items (enter numbers)")
    console.print("  [red]n[/red] - Cancel")

    response = console.input("\n[bold]Your choice:[/bold] ").strip().lower()

    if response == "y":
        return True, None
    elif response == "s":
        skip_input = console.input("Enter item numbers to skip (comma-separated): ").strip()
        try:
            skip_indices = [int(x.strip()) - 1 for x in skip_input.split(",")]
            return True, skip_indices
        except ValueError:
            console.print("[red]Invalid input, proceeding with all items[/red]")
            return True, None
    else:
        return False, None


def display_welcome(console: Console) -> None:
    """Display welcome message.

    Args:
        console: Rich console.
    """
    console.print(create_header())
    console.print(
        "\n[dim]Enter your research question and I'll create a comprehensive research plan.[/dim]\n"
    )
