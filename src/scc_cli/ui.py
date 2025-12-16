"""
UI components using Rich library.
"""

from pathlib import Path
from typing import TYPE_CHECKING

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
    - Show what went wrong (user_message)
    - Show what to do next (suggested_action)
    - Show debug info only if --debug flag is used
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
    """Render a warning message."""
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
    """Render a success message."""
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


def show_header(console: Console):
    """Display the application header."""
    console.print(LOGO_SIMPLE, style="cyan")


def select_team(console: Console, cfg: dict) -> str | None:
    """Interactive team selection."""

    teams = cfg.get("profiles", {})
    team_list = list(teams.keys())

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


def select_workspace_source(console: Console, cfg: dict, team: str) -> str:
    """Select where to get the workspace from."""

    console.print("\n[bold cyan]Where is your project?[/bold cyan]\n")

    options = [
        ("recent", "📂 Recent workspaces", "Continue working on a previous project"),
        ("custom", "📁 Enter path", "Specify a local directory path"),
        ("clone", "🔗 Clone repository", "Clone a Git repository"),
    ]

    # Add team repos if available
    team_config = cfg.get("profiles", {}).get(team, {})
    if team_config.get("repositories"):
        options.insert(1, ("team_repos", "🏢 Team repositories", "Choose from team's common repos"))

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")

    for i, (key, name, desc) in enumerate(options, 1):
        table.add_row(f"[{i}]", name, desc)

    table.add_row("[0]", "❌ Cancel", "Exit without starting")

    console.print(table)

    valid_choices = [str(i) for i in range(0, len(options) + 1)]
    choice = IntPrompt.ask(
        "\n[cyan]Select option[/cyan]",
        default=1,
        choices=valid_choices,
    )

    if choice == 0:
        return "cancel"

    return options[choice - 1][0]


def select_recent_workspace(console: Console, cfg: dict) -> str | None:
    """Select from recent workspaces."""
    from . import sessions

    recent = sessions.list_recent(10)

    if not recent:
        console.print("[yellow]No recent workspaces found.[/yellow]")
        return prompt_custom_workspace(console)

    console.print("\n[bold cyan]Recent workspaces:[/bold cyan]\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Workspace", style="cyan")
    table.add_column("Last Used", style="white")

    for i, session in enumerate(recent, 1):
        table.add_row(f"[{i}]", session["workspace"], session["last_used"])

    table.add_row("[0]", "← Back", "")

    console.print(table)

    valid_choices = [str(i) for i in range(0, len(recent) + 1)]
    choice = IntPrompt.ask(
        "\n[cyan]Select workspace[/cyan]",
        default=1,
        choices=valid_choices,
    )

    if choice == 0:
        return None

    return recent[choice - 1]["workspace"]


def select_team_repo(console: Console, cfg: dict, team: str) -> str | None:
    """Select from team's common repositories."""

    team_config = cfg.get("profiles", {}).get(team, {})
    repos = team_config.get("repositories", [])

    if not repos:
        console.print("[yellow]No team repositories configured.[/yellow]")
        return prompt_custom_workspace(console)

    console.print("\n[bold cyan]Team repositories:[/bold cyan]\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Repository", style="cyan")
    table.add_column("Description", style="white")

    for i, repo in enumerate(repos, 1):
        name = repo.get("name", repo.get("url", "Unknown"))
        desc = repo.get("description", "")
        table.add_row(f"[{i}]", name, desc)

    table.add_row("[0]", "← Back", "")

    console.print(table)

    valid_choices = [str(i) for i in range(0, len(repos) + 1)]
    choice = IntPrompt.ask(
        "\n[cyan]Select repository[/cyan]",
        default=1,
        choices=valid_choices,
    )

    if choice == 0:
        return None

    selected_repo = repos[choice - 1]

    # Check if already cloned locally
    local_path = selected_repo.get("local_path")
    if local_path and Path(local_path).expanduser().exists():
        return local_path

    # Need to clone
    from . import git

    workspace_base = cfg.get("workspace_base", "~/projects")
    return git.clone_repo(selected_repo["url"], workspace_base)


def prompt_custom_workspace(console: Console) -> str | None:
    """Prompt for a custom workspace path."""

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
    """Prompt for a Git repository URL."""

    url = Prompt.ask("\n[cyan]Repository URL (HTTPS or SSH)[/cyan]")
    return url


def show_launch_info(console: Console, workspace: Path, team: str, session_name: str):
    """Display info before launching Claude Code."""

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


def show_worktree_options(console: Console, workspace: Path) -> str | None:
    """Show worktree options during an active session."""

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
