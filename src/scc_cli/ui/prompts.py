"""Simple Rich-based prompts for CLI interactions.

This module provides straightforward prompt utilities for user input that don't
require full TUI screens. For more complex interactive pickers with keyboard
navigation, see picker.py and wizard.py.

Functions:
    render_error: Display an SCCError with user-friendly formatting
    select_session: Interactive session selection from a list
    select_team: Interactive team selection menu
    prompt_custom_workspace: Prompt for custom workspace path
    prompt_repo_url: Prompt for Git repository URL
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from scc_cli.theme import Borders, Colors

if TYPE_CHECKING:
    from scc_cli.errors import SCCError


def render_error(console: Console, error: "SCCError", debug: bool = False) -> None:
    """Render an error with user-friendly formatting.

    Philosophy: "One message, one action"
    - Display what went wrong (user_message)
    - Display what to do next (suggested_action)
    - Display debug info only if --debug flag is used

    Args:
        console: Rich console for output.
        error: The SCCError to render.
        debug: Whether to show debug context.
    """
    lines = []

    # Main error message
    lines.append(f"[bold]{error.user_message}[/bold]")

    # Suggested action (if available)
    if error.suggested_action:
        lines.append("")
        lines.append(f"[{Colors.SECONDARY}]->[/{Colors.SECONDARY}] {error.suggested_action}")

    # Debug context (only with --debug)
    if debug and error.debug_context:
        lines.append("")
        lines.append(f"[{Colors.SECONDARY}]--- Debug Info ---[/{Colors.SECONDARY}]")
        lines.append(f"[{Colors.SECONDARY}]{error.debug_context}[/{Colors.SECONDARY}]")
    elif error.debug_context and not debug:
        lines.append("")
        lines.append(
            f"[{Colors.SECONDARY}]Run with --debug for technical details[/{Colors.SECONDARY}]"
        )

    # Create panel with error styling
    panel = Panel(
        "\n".join(lines),
        title=f"[{Colors.ERROR_BOLD}]Error[/{Colors.ERROR_BOLD}]",
        border_style=Borders.PANEL_ERROR,
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()


def select_session(console: Console, sessions_list: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Display an interactive session selection menu.

    Args:
        console: Rich console for output.
        sessions_list: List of session dicts with 'name', 'workspace', 'last_used', etc.

    Returns:
        Selected session dict or None if cancelled.
    """
    if not sessions_list:
        console.print(f"[{Colors.WARNING}]No sessions available.[/{Colors.WARNING}]")
        return None

    console.print(f"\n[{Colors.BRAND_BOLD}]Select a session:[/{Colors.BRAND_BOLD}]\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style=Colors.WARNING, width=4)
    table.add_column("Name", style=Colors.BRAND)
    table.add_column("Workspace", style=Colors.PRIMARY)
    table.add_column("Last Used", style=Colors.SECONDARY)

    for i, session in enumerate(sessions_list, 1):
        name = session.get("name", "-")
        workspace = session.get("workspace", "-")
        last_used = session.get("last_used", "-")
        table.add_row(f"[{i}]", name, workspace, last_used)

    table.add_row("[0]", "<- Cancel", "", "")

    console.print(table)

    valid_choices = [str(i) for i in range(0, len(sessions_list) + 1)]
    choice = IntPrompt.ask(
        f"\n[{Colors.BRAND}]Select session[/{Colors.BRAND}]",
        default=1,
        choices=valid_choices,
    )

    if choice == 0:
        return None

    return sessions_list[choice - 1]


def select_team(console: Console, cfg: dict[str, Any]) -> str | None:
    """Display an interactive team selection menu and return the chosen team.

    Args:
        console: Rich console for output.
        cfg: Configuration dict containing 'profiles' key with team definitions.

    Returns:
        Selected team name or None if no teams available.
    """
    teams: dict[str, Any] = cfg.get("profiles", {})
    team_list: list[str] = list(teams.keys())

    if not team_list:
        return None

    console.print(f"\n[{Colors.BRAND_BOLD}]Select your team:[/{Colors.BRAND_BOLD}]\n")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Option", style=Colors.WARNING, width=4)
    table.add_column("Team", style=Colors.BRAND)
    table.add_column("Description", style=Colors.PRIMARY)

    for i, team_name in enumerate(team_list, 1):
        team_info = teams[team_name]
        desc = team_info.get("description", "")
        table.add_row(f"[{i}]", team_name, desc)

    console.print(table)

    choice = IntPrompt.ask(
        f"\n[{Colors.BRAND}]Select team[/{Colors.BRAND}]",
        default=1,
        choices=[str(i) for i in range(1, len(team_list) + 1)],
    )

    selected = team_list[choice - 1]
    console.print(f"\n[{Colors.SUCCESS}]Selected: {selected}[/{Colors.SUCCESS}]")

    return selected


def prompt_custom_workspace(console: Console) -> str | None:
    """Prompt the user to enter a custom workspace path.

    Args:
        console: Rich console for output.

    Returns:
        Resolved absolute path string, or None if cancelled or path invalid.
    """
    path = Prompt.ask(f"\n[{Colors.BRAND}]Enter workspace path[/{Colors.BRAND}]")

    if not path:
        return None

    expanded = Path(path).expanduser().resolve()

    if not expanded.exists():
        console.print(f"[{Colors.ERROR}]Path does not exist: {expanded}[/{Colors.ERROR}]")
        if Confirm.ask(f"[{Colors.BRAND}]Create this directory?[/{Colors.BRAND}]", default=False):
            expanded.mkdir(parents=True, exist_ok=True)
            return str(expanded)
        return None

    return str(expanded)


def prompt_repo_url(console: Console) -> str:
    """Prompt the user to enter a Git repository URL.

    Args:
        console: Rich console for output.

    Returns:
        The entered URL string (may be empty if user pressed Enter).
    """
    url = Prompt.ask(f"\n[{Colors.BRAND}]Repository URL (HTTPS or SSH)[/{Colors.BRAND}]")
    return url
