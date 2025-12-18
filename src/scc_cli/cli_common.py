"""
CLI Common Utilities.

Shared utilities, constants, and decorators used across all CLI modules.
This module is extracted to prevent circular imports and enable clean composition.
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from . import ui
from .errors import SCCError
from .panels import create_warning_panel

F = TypeVar("F", bound=Callable[..., Any])

# ─────────────────────────────────────────────────────────────────────────────
# Display Constants
# ─────────────────────────────────────────────────────────────────────────────

# Maximum length for displaying file paths before truncation
MAX_DISPLAY_PATH_LENGTH = 50
# Characters to keep when truncating (MAX - 3 for "...")
PATH_TRUNCATE_LENGTH = 47
# Terminal width threshold for wide mode tables
WIDE_MODE_THRESHOLD = 110


# ─────────────────────────────────────────────────────────────────────────────
# Shared Console and State
# ─────────────────────────────────────────────────────────────────────────────

console = Console()


class AppState:
    """Global application state for CLI flags."""

    debug: bool = False


state = AppState()


# ─────────────────────────────────────────────────────────────────────────────
# Error Boundary Decorator
# ─────────────────────────────────────────────────────────────────────────────


def handle_errors(func: F) -> F:
    """Decorator to catch SCCError and render beautifully."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except SCCError as e:
            ui.render_error(console, e, debug=state.debug)
            raise typer.Exit(e.exit_code)
        except KeyboardInterrupt:
            console.print("\n[dim]Operation cancelled.[/dim]")
            raise typer.Exit(130)
        except (typer.Exit, SystemExit):
            # Let typer exits pass through
            raise
        except Exception as e:
            # Unexpected errors
            if state.debug:
                console.print_exception()
            else:
                console.print(
                    create_warning_panel(
                        "Unexpected Error",
                        str(e),
                        "Run with --debug for full traceback",
                    )
                )
            raise typer.Exit(5)

    return cast(F, wrapper)


# ─────────────────────────────────────────────────────────────────────────────
# UI Helpers (Consistent Aesthetic)
# ─────────────────────────────────────────────────────────────────────────────


def render_responsive_table(
    title: str,
    columns: list[tuple[str, str]],  # (header, style)
    rows: list[list[str]],
    wide_columns: list[tuple[str, str]] | None = None,  # Extra columns for wide mode
) -> None:
    """Render a table that adapts to terminal width."""
    width = console.width
    wide_mode = width >= WIDE_MODE_THRESHOLD

    table = Table(
        title=f"[bold cyan]{title}[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True,
        show_lines=False,
    )

    # Add base columns
    for header, style in columns:
        table.add_column(header, style=style)

    # Add extra columns in wide mode
    if wide_mode and wide_columns:
        for header, style in wide_columns:
            table.add_column(header, style=style)

    # Add rows
    for row in rows:
        if wide_mode and wide_columns:
            table.add_row(*row)
        else:
            # Truncate to base columns only
            table.add_row(*row[: len(columns)])

    console.print()
    console.print(table)
    console.print()
