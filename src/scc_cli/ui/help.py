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


# Mapping from HelpMode enum to string mode names used in KEYBINDING_DOCS
_MODE_NAMES: dict[HelpMode, str] = {
    HelpMode.PICKER: "PICKER",
    HelpMode.MULTI_SELECT: "MULTI_SELECT",
    HelpMode.DASHBOARD: "DASHBOARD",
}


def get_help_entries(mode: HelpMode) -> list[tuple[str, str]]:
    """Get help entries filtered for a specific mode.

    This function uses KEYBINDING_DOCS from keys.py as the single source
    of truth for keybinding documentation.

    Args:
        mode: The current screen mode.

    Returns:
        List of (key, description) tuples for the given mode.
    """
    from .keys import get_keybindings_for_mode

    mode_name = _MODE_NAMES[mode]
    return get_keybindings_for_mode(mode_name)


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
