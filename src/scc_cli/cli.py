#!/usr/bin/env python3
"""
SCC - Sandboxed Claude CLI

A command-line tool for safely running Claude Code in Docker sandboxes
with team-specific configurations and worktree management.

This module serves as the thin orchestrator that composes commands from:
- cli_launch.py: Start command and interactive mode
- cli_worktree.py: Worktree, session, and container management
- cli_config.py: Teams, setup, and configuration commands
- cli_admin.py: Doctor, update, statusline, and stats commands
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_installed_version

import typer
from rich.panel import Panel

from .cli_admin import (
    doctor_cmd,
    stats_app,
    statusline_cmd,
    update_cmd,
)
from .cli_audit import audit_app
from .cli_common import console, state
from .cli_config import (
    config_cmd,
    setup_cmd,
    teams_cmd,
)
from .cli_exceptions import exceptions_app, unblock_cmd

# Import command functions from domain modules
from .cli_launch import start
from .cli_worktree import (
    cleanup_cmd,
    list_cmd,
    prune_cmd,
    sessions_cmd,
    stop_cmd,
    worktree_cmd,
    worktrees_cmd,
)

# ─────────────────────────────────────────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="scc-cli",
    help="Safely run Claude Code with team configurations and worktree management.",
    no_args_is_help=False,
    rich_markup_mode="rich",
)


# ─────────────────────────────────────────────────────────────────────────────
# Global Callback (--debug flag)
# ─────────────────────────────────────────────────────────────────────────────


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Show detailed error information for troubleshooting.",
        is_eager=True,
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        is_eager=True,
    ),
) -> None:
    """
    [bold cyan]SCC[/bold cyan] - Sandboxed Claude CLI

    Safely run Claude Code in Docker sandboxes with team configurations.
    """
    state.debug = debug

    if version:
        try:
            pkg_version = get_installed_version("scc-cli")
        except PackageNotFoundError:
            pkg_version = "unknown"
        console.print(
            Panel(
                f"[cyan]scc-cli[/cyan] [dim]v{pkg_version}[/dim]\n"
                "[dim]Safe development environment manager for Claude Code[/dim]",
                border_style="cyan",
            )
        )
        raise typer.Exit()

    # If no command provided and not showing version, invoke start
    # NOTE: Must pass ALL defaults explicitly - ctx.invoke() doesn't resolve
    # typer.Argument/Option defaults, it passes raw ArgumentInfo/OptionInfo objects
    if ctx.invoked_subcommand is None:
        ctx.invoke(
            start,
            workspace=None,
            team=None,
            session_name=None,
            resume=False,
            select=False,
            continue_session=False,
            worktree_name=None,
            fresh=False,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Register Commands from Domain Modules
# ─────────────────────────────────────────────────────────────────────────────

# Launch commands
app.command()(start)

# Worktree and session commands
app.command(name="worktree")(worktree_cmd)
app.command(name="worktrees")(worktrees_cmd)
app.command(name="cleanup")(cleanup_cmd)
app.command(name="sessions")(sessions_cmd)
app.command(name="list")(list_cmd)
app.command(name="stop")(stop_cmd)
app.command(name="prune")(prune_cmd)

# Configuration commands
app.command(name="teams")(teams_cmd)
app.command(name="setup")(setup_cmd)
app.command(name="config")(config_cmd)

# Admin commands
app.command(name="doctor")(doctor_cmd)
app.command(name="update")(update_cmd)
app.command(name="statusline")(statusline_cmd)

# Add stats sub-app
app.add_typer(stats_app, name="stats")

# Exception management commands
app.add_typer(exceptions_app, name="exceptions")
app.command(name="unblock")(unblock_cmd)

# Audit commands
app.add_typer(audit_app, name="audit")


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
