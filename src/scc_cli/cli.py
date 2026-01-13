#!/usr/bin/env python3
"""
SCC - Sandboxed Claude CLI

A command-line tool for safely running Claude Code in Docker sandboxes
with team-specific configurations and worktree management.

This module serves as the thin orchestrator that composes commands from:
- commands/launch.py: Start command and interactive mode
- commands/worktree.py: Worktree, session, and container management
- commands/config.py: Teams, setup, and configuration commands
- commands/admin.py: Doctor, update, statusline, and stats commands
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_installed_version

import typer

from .cli_common import console, state
from .commands.admin import (
    doctor_cmd,
    stats_app,
    status_cmd,
    statusline_cmd,
    update_cmd,
)
from .commands.audit import audit_app
from .commands.config import (
    config_cmd,
    setup_cmd,
)
from .commands.exceptions import exceptions_app, unblock_cmd
from .commands.init import init_cmd

# Import command functions from domain modules
from .commands.launch import start
from .commands.org import org_app
from .commands.profile import profile_app
from .commands.reset import reset_cmd
from .commands.support import support_app
from .commands.team import team_app
from .commands.worktree import (
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
    context_settings={"help_option_names": ["-h", "--help"]},
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

        from rich.prompt import Prompt

        from . import config as scc_config
        from . import setup as scc_setup
        from .services.workspace import resolve_launch_context
        from .ui.gate import is_interactive_allowed

        # Use strong-signal resolver (git or .scc.yaml) for parity with 'scc start'
        # Weak markers (package.json, etc.) are NOT used for auto-launch
        cwd = Path.cwd()
        result = resolve_launch_context(cwd, workspace_arg=None)
        workspace_detected = result is not None and result.is_auto_eligible()

        if is_interactive_allowed():
            # If no org is configured and standalone isn't explicit, offer setup
            user_cfg = scc_config.load_user_config()
            org_source = user_cfg.get("organization_source") or {}
            has_org = bool(org_source.get("url"))
            if not has_org and not user_cfg.get("standalone"):
                choice = Prompt.ask(
                    "[yellow]No organization configured.[/yellow] Choose setup mode",
                    choices=["setup", "standalone", "quit"],
                    default="setup",
                )
                if choice == "setup":
                    if not scc_setup.run_setup_wizard(console):
                        raise typer.Exit(0)
                elif choice == "standalone":
                    user_cfg["standalone"] = True
                    scc_config.save_user_config(user_cfg)
                else:
                    raise typer.Exit(0)

                # Setup complete - return to prompt
                return

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
                    non_interactive=False,
                    debug=False,
                    allow_suspicious_workspace=False,
                )
            else:
                # Always show dashboard in interactive mode
                from .ui.dashboard import run_dashboard

                run_dashboard()
        else:
            # Non-interactive - invoke start with defaults (will fail F1/F2 if no signal)
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
                non_interactive=False,
                debug=False,
                allow_suspicious_workspace=False,
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
app.add_typer(profile_app, name="profile", rich_help_panel=PANEL_CONFIG)
app.command(name="setup", rich_help_panel=PANEL_CONFIG)(setup_cmd)
app.command(name="config", rich_help_panel=PANEL_CONFIG)(config_cmd)
app.command(name="init", rich_help_panel=PANEL_CONFIG)(init_cmd)

# Admin commands
app.command(name="doctor", rich_help_panel=PANEL_ADMIN)(doctor_cmd)
app.command(name="update", rich_help_panel=PANEL_ADMIN)(update_cmd)
app.command(name="status", rich_help_panel=PANEL_ADMIN)(status_cmd)
app.command(name="statusline", rich_help_panel=PANEL_ADMIN)(statusline_cmd)
app.command(name="reset", rich_help_panel=PANEL_ADMIN)(reset_cmd)

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
# Shell Completion
# ─────────────────────────────────────────────────────────────────────────────


def completion_cmd(
    shell: str = typer.Argument(
        ...,
        help="Shell type (bash, zsh, fish).",
    ),
) -> None:
    """Generate shell completion script.

    Prints the completion script to stdout for the specified shell.

    \b
    Installation:
      # Bash (add to ~/.bashrc)
      eval "$(scc completion bash)"

      # Zsh (add to ~/.zshrc)
      eval "$(scc completion zsh)"

      # Fish (add to ~/.config/fish/completions/scc.fish)
      scc completion fish > ~/.config/fish/completions/scc.fish
    """
    import click.shell_completion as shell_completion

    shell_lower = shell.lower()
    prog_name = "scc"
    complete_var = f"_{prog_name.upper().replace('-', '_')}_COMPLETE"
    complete_func = f"_{prog_name.replace('-', '_')}_completion"

    template_vars = {
        "complete_var": complete_var,
        "prog_name": prog_name,
        "complete_func": complete_func,
    }

    if shell_lower == "bash":
        source = shell_completion._SOURCE_BASH
        script = source % template_vars
        console.print(script, highlight=False)
    elif shell_lower == "zsh":
        source = shell_completion._SOURCE_ZSH
        script = source % template_vars
        console.print(script, highlight=False)
    elif shell_lower == "fish":
        source = shell_completion._SOURCE_FISH
        script = source % template_vars
        console.print(script, highlight=False)
    else:
        console.print(f"[red]Unknown shell: {shell}[/red]")
        console.print("[dim]Supported shells: bash, zsh, fish[/dim]")
        raise typer.Exit(1)


# Register completion command
app.command(name="completion", rich_help_panel=PANEL_ADMIN)(completion_cmd)


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
