"""Help overlay for interactive UI screens.

Provides mode-aware help that shows only keys relevant to the current screen.
The overlay is triggered by pressing '?' and dismissed by any key.

Key categories shown per mode:
- ALL: Navigation (↑↓/j/k), typing to filter, backspace, t for teams
- PICKER: Enter to select, Esc to cancel
- MULTI_SELECT: Space to toggle, a to toggle all, Enter to confirm, Esc to cancel
- DASHBOARD: Tab/Shift+Tab for tabs, Enter for details, q to quit

Example:
    >>> from scc_cli.ui.help import show_help_overlay
    >>> from scc_cli.ui.list_screen import ListMode
    >>> show_help_overlay(ListMode.SINGLE_SELECT)
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from rich.console import RenderableType


class HelpMode(Enum):
    """Screen mode for help overlay customization."""

    PICKER = auto()  # Single-select picker (team, worktree, etc.)
    MULTI_SELECT = auto()  # Multi-select list (containers, etc.)
    DASHBOARD = auto()  # Tabbed dashboard view


# Key help entries: (key_display, description, modes_where_shown)
# If modes is empty tuple, shown in all modes
_HELP_ENTRIES: list[tuple[str, str, tuple[HelpMode, ...]]] = [
    # Navigation - shown in all modes
    ("↑ / k", "Move cursor up", ()),
    ("↓ / j", "Move cursor down", ()),
    # Filtering - shown in all modes
    ("type", "Filter items by text", ()),
    ("Backspace", "Delete filter character", ()),
    # Selection - mode-specific
    ("Enter", "Select item", (HelpMode.PICKER,)),
    ("Space", "Toggle selection", (HelpMode.MULTI_SELECT,)),
    ("a", "Toggle all items", (HelpMode.MULTI_SELECT,)),
    ("Enter", "Confirm selection", (HelpMode.MULTI_SELECT,)),
    ("Enter", "View details", (HelpMode.DASHBOARD,)),
    # Tab navigation - dashboard only
    ("Tab", "Next tab", (HelpMode.DASHBOARD,)),
    ("Shift+Tab", "Previous tab", (HelpMode.DASHBOARD,)),
    # Team switching - shown in all modes
    ("t", "Switch team", ()),
    # Exit - mode-specific
    ("Esc", "Cancel / go back", (HelpMode.PICKER, HelpMode.MULTI_SELECT)),
    ("q", "Quit", (HelpMode.DASHBOARD,)),
    # Help - shown in all modes
    ("?", "Show this help", ()),
]


def get_help_entries(mode: HelpMode) -> list[tuple[str, str]]:
    """Get help entries filtered for a specific mode.

    Args:
        mode: The current screen mode.

    Returns:
        List of (key, description) tuples for the given mode.
    """
    entries: list[tuple[str, str]] = []
    for key, desc, modes in _HELP_ENTRIES:
        if not modes or mode in modes:
            entries.append((key, desc))
    return entries


def render_help_content(mode: HelpMode) -> RenderableType:
    """Render help content for a given mode.

    Args:
        mode: The current screen mode.

    Returns:
        A Rich renderable with the help content.
    """
    entries = get_help_entries(mode)

    table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
    table.add_column("Key", style="cyan bold", width=12)
    table.add_column("Action", style="dim")

    for key, desc in entries:
        table.add_row(key, desc)

    # Mode indicator
    mode_name = {
        HelpMode.PICKER: "Picker",
        HelpMode.MULTI_SELECT: "Multi-Select",
        HelpMode.DASHBOARD: "Dashboard",
    }.get(mode, "Unknown")

    footer = Text()
    footer.append("\n")
    footer.append("Press any key to dismiss", style="dim italic")

    from rich.console import Group

    return Panel(
        Group(table, footer),
        title=f"[bold]Keyboard Shortcuts[/bold] │ {mode_name}",
        title_align="left",
        border_style="blue",
        padding=(1, 2),
    )


def show_help_overlay(mode: HelpMode, console: Console | None = None) -> None:
    """Display help overlay and wait for any key to dismiss.

    Args:
        mode: The current screen mode (affects which keys are shown).
        console: Optional console to use. If None, creates a new one.
    """
    if console is None:
        console = Console()

    content = render_help_content(mode)
    console.print(content)

    # Wait for any key to dismiss
    from .keys import read_key

    read_key()
