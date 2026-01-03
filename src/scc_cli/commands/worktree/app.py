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
)
from .context_commands import context_clear_cmd
from .session_commands import session_list_cmd
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
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
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
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Wire session commands
session_app.command("list")(session_list_cmd)

# ─────────────────────────────────────────────────────────────────────────────
# Container App (Symmetric Alias)
# ─────────────────────────────────────────────────────────────────────────────

container_app = typer.Typer(
    name="container",
    help="Container management commands.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Wire container commands
container_app.command("list")(container_list_cmd)

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
