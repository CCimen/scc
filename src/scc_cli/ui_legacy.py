"""
Provide terminal UI components using the Rich library.

Render error panels, success messages, interactive prompts, and selection menus
for the SCC CLI. All UI output is styled for a consistent user experience.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

if TYPE_CHECKING:
    from .errors import SCCError


def render_error(console: Console, error: "SCCError", debug: bool = False) -> None:
    """
    Render an error with user-friendly formatting.

    Philosophy: "One message, one action"
    - Display what went wrong (user_message)
    - Display what to do next (suggested_action)
    - Display debug info only if --debug flag is used
    """

    # Build error display
    lines = []

    # Main error message
    lines.append(f"[bold]{error.user_message}[/bold]")

    # Suggested action (if available)
    if error.suggested_action:
        lines.append("")
        lines.append(f"[dim]→[/dim] {error.suggested_action}")

    # Debug context (only with --debug)
    if debug and error.debug_context:
        lines.append("")
        lines.append("[dim]─── Debug Info ───[/dim]")
        lines.append(f"[dim]{error.debug_context}[/dim]")
    elif error.debug_context and not debug:
        lines.append("")
        lines.append("[dim]Run with --debug for technical details[/dim]")

    # Create panel with error styling
    panel = Panel(
        "\n".join(lines),
        title="[bold red]Error[/bold red]",
        border_style="red",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()


def render_warning(console: Console, message: str, suggestion: str = "") -> None:
    """Render a warning message panel to the console."""
    lines = [f"[bold]{message}[/bold]"]
    if suggestion:
        lines.append("")
        lines.append(f"[dim]→[/dim] {suggestion}")

    panel = Panel(
        "\n".join(lines),
        title="[bold yellow]Warning[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()


def render_success(console: Console, message: str, details: str = "") -> None:
    """Render a success message panel to the console."""
    lines = [f"[bold]{message}[/bold]"]
    if details:
        lines.append("")
        lines.append(f"[dim]{details}[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="[bold green]Success[/bold green]",
        border_style="green",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()


LOGO = """
╔═══════════════════════════════════════════════════════════════╗
║    ____   ____ ____                                           ║
║   / ___| / ___/ ___|                                          ║
║   \\___ \\| |  | |                                              ║
║    ___) | |__| |___                                           ║
║   |____/ \\____\\____|   Sandboxed Claude CLI                   ║
║                                                               ║
║              Claude Code Environment Manager                  ║
╚═══════════════════════════════════════════════════════════════╝
"""

LOGO_SIMPLE = """
┌─────────────────────────────────────────────────────┐
│  SCC - Sandboxed Claude CLI                         │
│  Safe development environment manager               │
└─────────────────────────────────────────────────────┘
"""


def show_header(console: Console) -> None:
    """Display the application header on the console."""
    console.print(LOGO_SIMPLE, style="cyan")


def select_team(console: Console, cfg: dict[str, Any]) -> str | None:
    """Display an interactive team selection menu and return the chosen team."""

    teams: dict[str, Any] = cfg.get("profiles", {})
    team_list: list[str] = list(teams.keys())

    console.print("\n[bold cyan]Select your team:[/bold cyan]\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Team", style="cyan")
    table.add_column("Description", style="white")

    for i, team_name in enumerate(team_list, 1):
        team_info = teams[team_name]
        desc = team_info.get("description", "")
        table.add_row(f"[{i}]", team_name, desc)

    console.print(table)

    choice = IntPrompt.ask(
        "\n[cyan]Select team[/cyan]",
        default=1,
        choices=[str(i) for i in range(1, len(team_list) + 1)],
    )

    selected = team_list[choice - 1]
    console.print(f"\n[green]✓ Selected: {selected}[/green]")

    return selected


def prompt_custom_workspace(console: Console) -> str | None:
    """Prompt the user to enter a custom workspace path."""

    path = Prompt.ask("\n[cyan]Enter workspace path[/cyan]")

    if not path:
        return None

    expanded = Path(path).expanduser().resolve()

    if not expanded.exists():
        console.print(f"[red]Path does not exist: {expanded}[/red]")
        if Confirm.ask("[cyan]Create this directory?[/cyan]", default=False):
            expanded.mkdir(parents=True, exist_ok=True)
            return str(expanded)
        return None

    return str(expanded)


def prompt_repo_url(console: Console) -> str:
    """Prompt the user to enter a Git repository URL."""

    url = Prompt.ask("\n[cyan]Repository URL (HTTPS or SSH)[/cyan]")
    return url


def show_launch_info(console: Console, workspace: Path, team: str, session_name: str) -> None:
    """Display launch information before starting Claude Code."""

    console.print("\n")

    info_text = []
    info_text.append(f"[cyan]Workspace:[/cyan] {workspace or 'None'}")
    info_text.append(f"[cyan]Team:[/cyan] {team or 'base'}")
    if session_name:
        info_text.append(f"[cyan]Session:[/cyan] {session_name}")

    panel = Panel(
        "\n".join(info_text),
        title="[bold green]Launching Claude Code[/bold green]",
        border_style="green",
    )
    console.print(panel)

    console.print("\n[yellow]Starting Docker sandbox...[/yellow]\n")


def select_session(console: Console, sessions_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Display an interactive session selection menu.

    Args:
        console: Rich console for output
        sessions_list: List of session dicts with 'name', 'workspace', 'last_used', etc.

    Returns:
        Selected session dict or None if cancelled.
    """
    if not sessions_list:
        console.print("[yellow]No sessions available.[/yellow]")
        return None

    console.print("\n[bold cyan]Select a session:[/bold cyan]\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Workspace", style="white")
    table.add_column("Last Used", style="dim")

    for i, session in enumerate(sessions_list, 1):
        name = session.get("name", "-")
        workspace = session.get("workspace", "-")
        last_used = session.get("last_used", "-")
        table.add_row(f"[{i}]", name, workspace, last_used)

    table.add_row("[0]", "← Cancel", "", "")

    console.print(table)

    valid_choices = [str(i) for i in range(0, len(sessions_list) + 1)]
    choice = IntPrompt.ask(
        "\n[cyan]Select session[/cyan]",
        default=1,
        choices=valid_choices,
    )

    if choice == 0:
        return None

    return sessions_list[choice - 1]


def show_worktree_options(console: Console, workspace: Path) -> str | None:
    """Display worktree options menu during an active session."""

    console.print("\n[bold cyan]Worktree Options:[/bold cyan]\n")

    options = [
        ("create", "➕ Create new worktree"),
        ("list", "📋 List worktrees"),
        ("switch", "🔄 Switch to worktree"),
        ("cleanup", "🗑️  Clean up worktree"),
        ("back", "← Back"),
    ]

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Action", style="cyan")

    for i, (key, name) in enumerate(options, 1):
        table.add_row(f"[{i}]", name)

    console.print(table)

    valid_choices = [str(i) for i in range(1, len(options) + 1)]
    choice = IntPrompt.ask(
        "\n[cyan]Select option[/cyan]",
        default=1,
        choices=valid_choices,
    )

    return options[choice - 1][0]
