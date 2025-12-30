"""
Provide Rich panel components for consistent UI across the CLI.

Define reusable panel factories for info, warning, success, and error messages
with standardized styling and structure.

All colors are sourced from ui/theme.py design tokens for consistency.
"""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scc_cli.theme import Borders, Colors


def create_info_panel(title: str, content: str, subtitle: str = "") -> Panel:
    """Create an info panel with brand styling.

    Args:
        title: Panel title text.
        content: Main content text.
        subtitle: Optional dimmed subtitle text.

    Returns:
        Rich Panel with brand color border and styling.
    """
    body = Text()
    body.append(content)
    if subtitle:
        body.append("\n")
        body.append(subtitle, style=Colors.SECONDARY)
    return Panel(
        body,
        title=f"[{Colors.BRAND_BOLD}]{title}[/{Colors.BRAND_BOLD}]",
        border_style=Borders.PANEL_INFO,
        padding=(0, 1),
    )


def create_warning_panel(title: str, message: str, hint: str = "") -> Panel:
    """Create a warning panel with warning styling.

    Args:
        title: Panel title text (will have warning icon prepended).
        message: Main warning message.
        hint: Optional action hint text.

    Returns:
        Rich Panel with warning color border and styling.
    """
    body = Text()
    body.append(message, style="bold")
    if hint:
        body.append("\n\n")
        body.append("-> ", style=Colors.SECONDARY)
        body.append(hint, style=Colors.WARNING)
    return Panel(
        body,
        title=f"[{Colors.WARNING_BOLD}]{title}[/{Colors.WARNING_BOLD}]",
        border_style=Borders.PANEL_WARNING,
        padding=(0, 1),
    )


def create_success_panel(title: str, items: dict[str, str]) -> Panel:
    """Create a success panel with key-value summary.

    Args:
        title: Panel title text (will have checkmark icon prepended).
        items: Dictionary of key-value pairs to display.

    Returns:
        Rich Panel with success color border and key-value grid.
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=Colors.SECONDARY, no_wrap=True)
    grid.add_column(style=Colors.PRIMARY)

    for key, value in items.items():
        grid.add_row(f"{key}:", str(value))

    return Panel(
        grid,
        title=f"[{Colors.SUCCESS_BOLD}]{title}[/{Colors.SUCCESS_BOLD}]",
        border_style=Borders.PANEL_SUCCESS,
        padding=(0, 1),
    )


def create_error_panel(title: str, message: str, hint: str = "") -> Panel:
    """Create an error panel with error styling.

    Args:
        title: Panel title text (will have error icon prepended).
        message: Main error message.
        hint: Optional fix/action hint text.

    Returns:
        Rich Panel with error color border and styling.
    """
    body = Text()
    body.append(message, style="bold")
    if hint:
        body.append("\n\n")
        body.append("-> ", style=Colors.SECONDARY)
        body.append(hint, style=Colors.ERROR)
    return Panel(
        body,
        title=f"[{Colors.ERROR_BOLD}]{title}[/{Colors.ERROR_BOLD}]",
        border_style=Borders.PANEL_ERROR,
        padding=(0, 1),
    )
