"""
Worktree package - Typer app definitions and command wiring.

This module contains the Typer app definitions and wires commands from:
- worktree_commands.py: Git worktree management
- container_commands.py: Docker container management
- session_commands.py: Claude Code session management
- context_commands.py: Work context management
"""

from __future__ import annotations

import typer

from .container_commands import (
    container_list_cmd,
    list_cmd,
)
from .context_commands import context_clear_cmd
from .session_commands import session_list_cmd, session_prune_cmd
from .worktree_commands import (
    worktree_create_cmd,
    worktree_enter_cmd,
    worktree_list_cmd,
    worktree_prune_cmd,
    worktree_remove_cmd,
    worktree_select_cmd,
    worktree_switch_cmd,
)

# ─────────────────────────────────────────────────────────────────────────────
# Worktree App
# ─────────────────────────────────────────────────────────────────────────────

worktree_app = typer.Typer(
    name="worktree",
    help="""Manage git worktrees for parallel development.

Shell Integration (add to ~/.bashrc or ~/.zshrc):

  wt() { cd "$(scc worktree switch "$@")" || return 1; }

Examples:

  wt ^           # Switch to main branch
  wt -           # Switch to previous directory
  wt feature-x   # Fuzzy match worktree
""",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@worktree_app.callback(invoke_without_command=True)
def worktree_callback(
    ctx: typer.Context,
    workspace: str = typer.Argument(".", help="Path to the repository"),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Interactive mode: select a worktree"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show git status (staged/modified/untracked)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output"),
) -> None:
    """List worktrees by default.

    This makes `scc worktree` behave like `scc worktree list` for convenience.
    """
    if ctx.invoked_subcommand is None:
        worktree_list_cmd(
            workspace=workspace,
            interactive=interactive,
            verbose=verbose,
            json_output=json_output,
            pretty=pretty,
        )


# Wire worktree commands
worktree_app.command("create")(worktree_create_cmd)
worktree_app.command("list")(worktree_list_cmd)
worktree_app.command("switch")(worktree_switch_cmd)
worktree_app.command("select")(worktree_select_cmd)
worktree_app.command("enter")(worktree_enter_cmd)
worktree_app.command("remove")(worktree_remove_cmd)
worktree_app.command("prune")(worktree_prune_cmd)

# ─────────────────────────────────────────────────────────────────────────────
# Session App (Symmetric Alias)
# ─────────────────────────────────────────────────────────────────────────────

session_app = typer.Typer(
    name="session",
    help="Session management commands.",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)

# Wire session commands
session_app.command("list")(session_list_cmd)
session_app.command("prune")(session_prune_cmd)


@session_app.callback(invoke_without_command=True)
def session_callback(
    ctx: typer.Context,
    limit: int = typer.Option(10, "-n", "--limit", help="Number of sessions to show"),
    team: str | None = typer.Option(None, "-t", "--team", help="Filter by team"),
    all_teams: bool = typer.Option(
        False, "--all", help="Show sessions for all teams (ignore active team)"
    ),
    select: bool = typer.Option(
        False, "--select", "-s", help="Interactive picker to select a session"
    ),
) -> None:
    """List recent sessions (default).

    This makes `scc session` behave like `scc session list` for convenience.
    """
    if ctx.invoked_subcommand is None:
        session_list_cmd(limit=limit, team=team, all_teams=all_teams, select=select)


# ─────────────────────────────────────────────────────────────────────────────
# Container App (Symmetric Alias)
# ─────────────────────────────────────────────────────────────────────────────

container_app = typer.Typer(
    name="container",
    help="Container management commands.",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)

# Wire container commands
container_app.command("list")(container_list_cmd)


@container_app.callback(invoke_without_command=True)
def container_callback(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Interactive mode: select container"
    ),
) -> None:
    """List containers (default).

    This makes `scc container` behave like `scc container list` for convenience.
    """
    if ctx.invoked_subcommand is None:
        list_cmd(interactive=interactive)


# ─────────────────────────────────────────────────────────────────────────────
# Context App (Work Context Management)
# ─────────────────────────────────────────────────────────────────────────────

context_app = typer.Typer(
    name="context",
    help="Work context management commands.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Wire context commands
context_app.command("clear")(context_clear_cmd)
