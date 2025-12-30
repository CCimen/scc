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

from .cli_admin import (
    doctor_cmd,
    stats_app,
    status_cmd,
    statusline_cmd,
    update_cmd,
)
from .cli_audit import audit_app
from .cli_common import console, state
from .cli_config import (
    config_cmd,
    setup_cmd,
)
from .cli_exceptions import exceptions_app, unblock_cmd
from .cli_init import init_cmd

# Import command functions from domain modules
from .cli_launch import start
from .cli_org import org_app
from .cli_support import support_app
from .cli_team import team_app
from .cli_worktree import (
    container_app,
    context_app,
    list_cmd,
    prune_cmd,
    session_app,
    sessions_cmd,
    stop_cmd,
    worktree_app,
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
    interactive: bool = typer.Option(
        False,
        "-i",
        "--interactive",
        help="Force interactive workspace picker (shortcut for 'scc start -i').",
    ),
) -> None:
    """
    [bold cyan]SCC[/bold cyan] - Sandboxed Claude CLI

    Safely run Claude Code in Docker sandboxes with team configurations.
    """
    state.debug = debug

    if version:
        from .ui.branding import get_version_header

        try:
            pkg_version = get_installed_version("scc-cli")
        except PackageNotFoundError:
            pkg_version = "unknown"
        console.print(get_version_header(pkg_version))
        raise typer.Exit()

    # If no command provided and not showing version, use context-aware routing
    if ctx.invoked_subcommand is None:
        from pathlib import Path

        from .ui.gate import is_interactive_allowed
        from .ui.wizard import _is_valid_workspace

        # Context detection: check if CWD is a valid workspace
        cwd = Path.cwd()
        workspace_detected = _is_valid_workspace(cwd)

        if is_interactive_allowed():
            if interactive:
                # -i flag: force interactive workspace picker via start -i
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
                    install_deps=False,
                    offline=False,
                    standalone=False,
                    dry_run=False,
                    json_output=False,
                    pretty=False,
                )
            elif workspace_detected:
                # User is in a valid workspace → use smart start flow
                # This shows Quick Resume (if sessions exist) or launches immediately
                ctx.invoke(
                    start,
                    workspace=str(cwd),
                    team=None,
                    session_name=None,
                    resume=False,
                    select=False,
                    continue_session=False,
                    worktree_name=None,
                    fresh=False,
                    install_deps=False,
                    offline=False,
                    standalone=False,
                    dry_run=False,
                    json_output=False,
                    pretty=False,
                )
            else:
                # No workspace context (e.g., $HOME) → show dashboard
                from .ui.dashboard import run_dashboard

                run_dashboard()
        else:
            # Non-interactive - invoke start with defaults
            # NOTE: Must pass ALL defaults explicitly - ctx.invoke() doesn't resolve
            # typer.Argument/Option defaults, it passes raw ArgumentInfo/OptionInfo
            ctx.invoke(
                start,
                workspace=str(cwd) if workspace_detected else None,
                team=None,
                session_name=None,
                resume=False,
                select=False,
                continue_session=False,
                worktree_name=None,
                fresh=False,
                install_deps=False,
                offline=False,
                standalone=False,
                dry_run=False,
                json_output=False,
                pretty=False,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Help Panel Group Names
# ─────────────────────────────────────────────────────────────────────────────

PANEL_SESSION = "Session Management"
PANEL_WORKSPACE = "Workspace"
PANEL_CONFIG = "Configuration"
PANEL_ADMIN = "Administration"
PANEL_GOVERNANCE = "Governance"

# ─────────────────────────────────────────────────────────────────────────────
# Register Commands from Domain Modules
# ─────────────────────────────────────────────────────────────────────────────

# Launch commands
app.command(rich_help_panel=PANEL_SESSION)(start)

# Worktree command group
app.add_typer(worktree_app, name="worktree", rich_help_panel=PANEL_WORKSPACE)

# Session and container commands
app.command(name="sessions", rich_help_panel=PANEL_SESSION)(sessions_cmd)
app.command(name="list", rich_help_panel=PANEL_SESSION)(list_cmd)
app.command(name="stop", rich_help_panel=PANEL_SESSION)(stop_cmd)
app.command(name="prune", rich_help_panel=PANEL_SESSION)(prune_cmd)

# Configuration commands
app.add_typer(team_app, name="team", rich_help_panel=PANEL_CONFIG)
app.command(name="setup", rich_help_panel=PANEL_CONFIG)(setup_cmd)
app.command(name="config", rich_help_panel=PANEL_CONFIG)(config_cmd)
app.command(name="init", rich_help_panel=PANEL_CONFIG)(init_cmd)

# Admin commands
app.command(name="doctor", rich_help_panel=PANEL_ADMIN)(doctor_cmd)
app.command(name="update", rich_help_panel=PANEL_ADMIN)(update_cmd)
app.command(name="status", rich_help_panel=PANEL_ADMIN)(status_cmd)
app.command(name="statusline", rich_help_panel=PANEL_ADMIN)(statusline_cmd)

# Add stats sub-app
app.add_typer(stats_app, name="stats", rich_help_panel=PANEL_ADMIN)

# Exception management commands
app.add_typer(exceptions_app, name="exceptions", rich_help_panel=PANEL_GOVERNANCE)
app.command(name="unblock", rich_help_panel=PANEL_GOVERNANCE)(unblock_cmd)

# Audit commands
app.add_typer(audit_app, name="audit", rich_help_panel=PANEL_GOVERNANCE)

# Support commands
app.add_typer(support_app, name="support", rich_help_panel=PANEL_GOVERNANCE)

# Org admin commands
app.add_typer(org_app, name="org", rich_help_panel=PANEL_GOVERNANCE)

# Symmetric alias apps (Phase 8)
app.add_typer(session_app, name="session", rich_help_panel=PANEL_WORKSPACE)
app.add_typer(container_app, name="container", rich_help_panel=PANEL_WORKSPACE)
app.add_typer(context_app, name="context", rich_help_panel=PANEL_WORKSPACE)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
