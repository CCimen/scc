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

from .errors import SCCError
from .exit_codes import EXIT_CANCELLED
from .output_mode import is_json_command_mode, is_json_mode
from .panels import create_warning_panel
from .ui.prompts import render_error

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
err_console = Console(stderr=True)


class AppState:
    """Global application state for CLI flags."""

    debug: bool = False


state = AppState()


# ─────────────────────────────────────────────────────────────────────────────
# Error Boundary Decorator
# ─────────────────────────────────────────────────────────────────────────────


def handle_errors(func: F) -> F:
    """Catch SCCError exceptions and render user-friendly error output.

    Wrap CLI command functions to provide consistent error handling:
    - SCCError: Render with render_error and exit with error's exit_code
    - KeyboardInterrupt: Print cancellation message and exit 130
    - Other exceptions: Show warning panel (or full traceback with --debug)

    Args:
        func: The CLI command function to wrap.

    Returns:
        Wrapped function with error handling.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except SCCError as e:
            if is_json_command_mode():
                raise
            target_console = err_console if is_json_mode() else console
            render_error(target_console, e, debug=state.debug)
            raise typer.Exit(e.exit_code)
        except KeyboardInterrupt:
            if is_json_command_mode():
                raise
            target_console = err_console if is_json_mode() else console
            target_console.print("\n[dim]Operation cancelled.[/dim]")
            raise typer.Exit(EXIT_CANCELLED)
        except (typer.Exit, SystemExit):
            # Let typer exits pass through
            raise
        except Exception as e:
            if is_json_command_mode():
                raise
            # Unexpected errors
            target_console = err_console if is_json_mode() else console
            if state.debug:
                target_console.print_exception()
            else:
                target_console.print(
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
    """Render a table that adapts to terminal width.

    Display base columns on narrow terminals, adding extra columns when
    terminal width exceeds WIDE_MODE_THRESHOLD.

    Args:
        title: Table title displayed above the table.
        columns: Base columns as list of (header, style) tuples.
        rows: Data rows where each row contains values for all columns
            (base + wide). Extra values are ignored on narrow terminals.
        wide_columns: Additional columns shown only on wide terminals.
    """
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
