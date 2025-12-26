"""
Provide Rich panel components for consistent UI across the CLI.

Define reusable panel factories for info, warning, success, and error messages
with standardized styling and structure.
"""

from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def create_info_panel(title: str, content: str, subtitle: str = "") -> Panel:
    """Create an info panel with cyan styling.

    Args:
        title: Panel title text.
        content: Main content text.
        subtitle: Optional dimmed subtitle text.

    Returns:
        Rich Panel with cyan border and styling.
    """
    body = Text()
    body.append(content)
    if subtitle:
        body.append("\n")
        body.append(subtitle, style="dim")
    return Panel(
        body,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )


def create_warning_panel(title: str, message: str, hint: str = "") -> Panel:
    """Create a warning panel with yellow styling.

    Args:
        title: Panel title text (will have warning icon prepended).
        message: Main warning message.
        hint: Optional action hint text.

    Returns:
        Rich Panel with yellow border and styling.
    """
    body = Text()
    body.append(message, style="bold")
    if hint:
        body.append("\n\n")
        body.append("-> ", style="dim")
        body.append(hint, style="yellow")
    return Panel(
        body,
        title=f"[bold yellow]{title}[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    )


def create_success_panel(title: str, items: dict[str, str]) -> Panel:
    """Create a success panel with key-value summary.

    Args:
        title: Panel title text (will have checkmark icon prepended).
        items: Dictionary of key-value pairs to display.

    Returns:
        Rich Panel with green border and key-value grid.
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    for key, value in items.items():
        grid.add_row(f"{key}:", str(value))

    return Panel(
        grid,
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        padding=(0, 1),
    )


def create_error_panel(title: str, message: str, hint: str = "") -> Panel:
    """Create an error panel with red styling.

    Args:
        title: Panel title text (will have error icon prepended).
        message: Main error message.
        hint: Optional fix/action hint text.

    Returns:
        Rich Panel with red border and styling.
    """
    body = Text()
    body.append(message, style="bold")
    if hint:
        body.append("\n\n")
        body.append("-> ", style="dim")
        body.append(hint, style="red")
    return Panel(
        body,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=(0, 1),
    )
