"""Rich CLI components for the deep research system."""

import re
from typing import Any

from rich.console import Console, Group


# ANSI escape sequence pattern - matches control sequences including:
# - CSI sequences: ESC [ ... (letter) - covers focus events ^[[I, ^[[O etc
# - SS2/SS3: ESC N, ESC O
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b[NO]")
INLINE_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_input(text: str) -> str:
    """Remove ANSI escape sequences from user input.

    Terminal focus events (like clicking elsewhere) can inject escape
    sequences like ^[[I (focus in) and ^[[O (focus out) into input.
    This function strips them out.

    Args:
        text: Raw input text.

    Returns:
        Cleaned text with ANSI sequences removed.
    """
    return ANSI_ESCAPE_RE.sub("", text)


def normalize_progress_text(text: str) -> str:
    """Normalize progress text for single-line display."""
    if not text:
        return ""
    return INLINE_WHITESPACE_RE.sub(" ", text.strip())


def truncate_progress_text(text: str, max_width: int) -> str:
    """Truncate text to a display width using Rich's cell width logic."""
    if max_width <= 0:
        return ""
    rich_text = Text(text)
    if rich_text.cell_len > max_width:
        rich_text.truncate(max_width, overflow="ellipsis")
    return rich_text.plain
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
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


class ClarificationDisplay:
    """Display component for clarification questions."""

    def __init__(self, console: Console | None = None):
        """Initialize the clarification display.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()

    def render_clarifications(self, clarifications: list[str], understanding: str = "") -> Panel:
        """Render clarification questions as a Rich panel.

        Args:
            clarifications: List of clarification questions.
            understanding: Optional current understanding to display.

        Returns:
            Rich Panel containing the clarifications.
        """
        content_parts = []

        if understanding:
            content_parts.append(Text(f"Current understanding: {understanding}\n\n", style="italic"))

        content_parts.append(Text("Please answer the following questions to help focus the research:\n\n", style="yellow"))

        for i, question in enumerate(clarifications, 1):
            content_parts.append(Text(f"  {i}. {question}\n", style="bold"))

        return Panel(
            Group(*content_parts),
            title="[bold yellow]Clarification Needed[/bold yellow]",
            border_style="yellow",
        )

    def prompt_answers(self, clarifications: list[str]) -> list[tuple[str, str]]:
        """Prompt user to answer each clarification question.

        Args:
            clarifications: List of clarification questions.

        Returns:
            List of (question, answer) tuples.
        """
        answers = []
        self.console.print("\n[bold]Please answer each question (press Enter to skip):[/bold]\n")

        for i, question in enumerate(clarifications, 1):
            self.console.print(f"[cyan]Q{i}:[/cyan] {question}")
            answer = sanitize_input(self.console.input("[green]A:[/green] ")).strip()
            if answer:
                answers.append((question, answer))
            else:
                answers.append((question, "(skipped)"))
            self.console.print()

        return answers


class ProgressDisplay:
    """Display component for research progress.
    
    Shows a spinner with topic name (cyan) and current action (dim) for each agent.
    No progress percentage - users can interrupt manually if needed.
    """

    def __init__(self, console: Console | None = None):
        """Initialize progress display.

        Args:
            console: Rich console instance.
        """
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.fields[topic]}[/]", overflow="ellipsis", no_wrap=True),
            TextColumn("[dim]{task.description}[/]", overflow="ellipsis", no_wrap=True),
            console=self.console,
            expand=True,
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
        task_id = self.progress.add_task("Starting...", topic=topic)
        self._task_ids[agent_id] = task_id

    def update_agent(self, progress: AgentProgress) -> None:
        """Update agent progress.

        Args:
            progress: The agent progress.
        """
        if progress.agent_id in self._task_ids:
            task_id = self._task_ids[progress.agent_id]
            action = normalize_progress_text(progress.current_action or "")
            self.progress.update(task_id, description=action or "Working...")

    def mark_completed(self, agent_id: str) -> None:
        """Mark an agent as completed.

        Args:
            agent_id: The agent ID.
        """
        if agent_id in self._task_ids:
            task_id = self._task_ids[agent_id]
            self.progress.update(task_id, description="[green]✓ Completed[/]")


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


def prompt_confirm_plan(console: Console, plan: ResearchPlan) -> tuple[bool, list[int] | None, str | None]:
    """Prompt user to confirm or modify the plan.

    Args:
        console: Rich console.
        plan: The research plan.

    Returns:
        Tuple of (confirmed, skip_indices, feedback).
        - confirmed: True if user wants to proceed
        - skip_indices: List of item indices to skip (0-indexed), or None
        - feedback: User feedback string to refine plan, or None
    """
    plan_display = PlanDisplay(console)
    console.print(plan_display.render_plan(plan))

    console.print("\n[bold]Options:[/bold]")
    console.print("  [green]y[/green] - Confirm and start research")
    console.print("  [yellow]s[/yellow] - Skip specific items (enter numbers)")
    console.print("  [cyan]f[/cyan] - Provide feedback to refine the plan")
    console.print("  [red]n[/red] - Cancel")

    response = sanitize_input(console.input("\n[bold]Your choice:[/bold] ")).strip().lower()

    if response == "y":
        return True, None, None
    elif response == "s":
        skip_input = sanitize_input(console.input("Enter item numbers to skip (comma-separated): ")).strip()
        try:
            skip_indices = [int(x.strip()) - 1 for x in skip_input.split(",")]
            return True, skip_indices, None
        except ValueError:
            console.print("[red]Invalid input, proceeding with all items[/red]")
            return True, None, None
    elif response == "f":
        console.print("\n[cyan]Enter your feedback to help refine the research plan:[/cyan]")
        feedback = sanitize_input(console.input("[cyan]Feedback:[/cyan] ")).strip()
        if feedback:
            return False, None, feedback
        else:
            console.print("[yellow]No feedback provided, please choose another option.[/yellow]")
            return prompt_confirm_plan(console, plan)  # Recurse to show options again
    else:
        return False, None, None


def display_welcome(console: Console) -> None:
    """Display welcome message.

    Args:
        console: Rich console.
    """
    console.print(create_header())
    console.print(
        "\n[dim]Enter your research question and I'll create a comprehensive research plan.[/dim]\n"
    )
