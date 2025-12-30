"""Orchestration functions for the dashboard module.

This module contains the entry point and flow handlers:
- run_dashboard: Main entry point for `scc` with no arguments
- _handle_team_switch: Team picker integration
- _handle_start_flow: Start wizard integration
- _handle_session_resume: Session resume logic

The orchestrator manages the dashboard lifecycle including intent exceptions
that exit the Rich Live context before handling nested UI components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...console import get_err_console

if TYPE_CHECKING:
    from rich.console import Console

from ..keys import (
    RefreshRequested,
    SessionResumeRequested,
    StartRequested,
    TeamSwitchRequested,
)
from ..list_screen import ListState
from ._dashboard import Dashboard
from .loaders import _load_all_tab_data
from .models import DashboardState, DashboardTab


def run_dashboard() -> None:
    """Run the main SCC dashboard.

    This is the entry point for `scc` with no arguments in a TTY.
    It loads current resource data and displays the interactive dashboard.

    Handles intent exceptions by executing the requested flow outside the
    Rich Live context (critical to avoid nested Live conflicts), then
    reloading the dashboard with restored tab state.

    Intent Exceptions:
        - TeamSwitchRequested: Show team picker, reload with new team
        - StartRequested: Run start wizard, return to source tab with fresh data
        - RefreshRequested: Reload tab data, return to source tab
    """
    # Track which tab to restore after flow (uses .name for stability)
    restore_tab: str | None = None
    # Toast message to show on next dashboard iteration (e.g., "Start cancelled")
    toast_message: str | None = None

    while True:
        # Load real data for all tabs
        tabs = _load_all_tab_data()

        # Determine initial tab (restore previous or default to STATUS)
        initial_tab = DashboardTab.STATUS
        if restore_tab:
            # Find tab by name (stable identifier)
            for tab in DashboardTab:
                if tab.name == restore_tab:
                    initial_tab = tab
                    break
            restore_tab = None  # Clear after use

        state = DashboardState(
            active_tab=initial_tab,
            tabs=tabs,
            list_state=ListState(items=tabs[initial_tab].items),
            status_message=toast_message,  # Show any pending toast
        )
        toast_message = None  # Clear after use

        dashboard = Dashboard(state)
        try:
            dashboard.run()
            break  # Normal exit (q or Esc)
        except TeamSwitchRequested:
            # User pressed 't' - show team picker then reload dashboard
            _handle_team_switch()
            # Loop continues to reload dashboard with new team

        except StartRequested as start_req:
            # User pressed Enter on startable placeholder
            # Execute start flow OUTSIDE Rich Live (critical: avoids nested Live)
            restore_tab = start_req.return_to
            result = _handle_start_flow(start_req.reason)

            if result is None:
                # User pressed q: quit app entirely
                break

            if result is False:
                # User pressed Esc: go back to dashboard, show toast
                toast_message = "Start cancelled"
            # Loop continues to reload dashboard with fresh data

        except RefreshRequested as refresh_req:
            # User pressed 'r' - just reload data
            restore_tab = refresh_req.return_to
            # Loop continues with fresh data (no additional action needed)

        except SessionResumeRequested as resume_req:
            # User pressed Enter on a session item → resume it
            restore_tab = resume_req.return_to
            success = _handle_session_resume(resume_req.session)

            if not success:
                # Resume failed (e.g., missing workspace) - show toast
                toast_message = "Session resume failed"
            else:
                # Successfully launched - exit dashboard
                # (container is running, user is now in Claude)
                break


def _prepare_for_nested_ui(console: Console) -> None:
    """Prepare terminal state for launching nested UI components.

    Restores cursor visibility, ensures clean newline, and flushes
    any buffered input to prevent ghost keypresses from Rich Live context.

    This should be called before launching any interactive picker or wizard
    from the dashboard to ensure clean terminal state.

    Args:
        console: Rich Console instance for terminal operations.
    """
    import io
    import sys

    # Restore cursor (Rich Live may hide it)
    console.show_cursor(True)
    console.print()  # Ensure clean newline

    # Flush buffered input (best-effort, Unix only)
    try:
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (
        ModuleNotFoundError,  # Windows - no termios module
        OSError,  # Redirected stdin, no TTY
        ValueError,  # Invalid file descriptor
        TypeError,  # Mock stdin without fileno
        io.UnsupportedOperation,  # Stdin without fileno support
    ):
        pass  # Non-Unix or non-TTY environment - safe to ignore


def _handle_team_switch() -> None:
    """Handle team switch request from dashboard.

    Shows the team picker and switches team if user selects one.
    """
    from ... import config, teams
    from ..picker import pick_team

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        # Load config and org config for team list
        cfg = config.load_user_config()
        org_config = config.load_cached_org_config()

        available_teams = teams.list_teams(cfg, org_config=org_config)
        if not available_teams:
            console.print("[yellow]No teams available[/yellow]")
            return

        # Get current team for marking
        current_team = cfg.get("selected_profile")

        selected = pick_team(
            available_teams,
            current_team=str(current_team) if current_team else None,
            title="Switch Team",
        )

        if selected:
            # Update team selection
            team_name = selected.get("name", "")
            cfg["selected_profile"] = team_name
            config.save_user_config(cfg)
            console.print(f"[green]Switched to team: {team_name}[/green]")
        # If cancelled, just return to dashboard

    except TeamSwitchRequested:
        # Nested team switch (shouldn't happen, but handle gracefully)
        pass
    except Exception as e:
        console.print(f"[red]Error switching team: {e}[/red]")


def _handle_start_flow(reason: str) -> bool | None:
    """Handle start flow request from dashboard.

    Runs the interactive start wizard and launches a sandbox if user completes it.
    Executes OUTSIDE Rich Live context (the dashboard has already exited
    via the exception unwind before this is called).

    Three-state return contract:
    - True: Sandbox launched successfully
    - False: User pressed Esc (back to dashboard)
    - None: User pressed q (quit app entirely)

    Args:
        reason: Why the start flow was triggered (e.g., "no_containers", "no_sessions").
            Used for logging/analytics and to determine skip_quick_resume.

    Returns:
        True if wizard completed successfully, False if user wants to go back,
        None if user wants to quit entirely.
    """
    from ...cli_launch import run_start_wizard_flow

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # For empty-state starts, skip Quick Resume (user intent is "create new")
    skip_quick_resume = reason in ("no_containers", "no_sessions")

    # Show contextual message based on reason
    if reason == "no_containers":
        console.print("[dim]Starting a new session...[/dim]")
    elif reason == "no_sessions":
        console.print("[dim]Starting your first session...[/dim]")
    console.print()

    # Run the wizard with allow_back=True for dashboard context
    # Returns: True (success), False (Esc/back), None (q/quit)
    return run_start_wizard_flow(skip_quick_resume=skip_quick_resume, allow_back=True)


def _handle_session_resume(session: dict[str, Any]) -> bool:
    """Handle session resume request from dashboard.

    Resumes an existing session by launching the Docker container with
    the stored workspace, team, and branch configuration.

    This function executes OUTSIDE Rich Live context (the dashboard has
    already exited via the exception unwind before this is called).

    Args:
        session: Session dict containing workspace, team, branch, container_name, etc.

    Returns:
        True if session was resumed successfully, False if resume failed
        (e.g., workspace no longer exists).
    """
    from pathlib import Path

    from rich.status import Status

    from ... import config, docker
    from ...cli_launch import (
        _configure_team_settings,
        _launch_sandbox,
        _resolve_mount_and_branch,
        _sync_marketplace_settings,
        _validate_and_resolve_workspace,
    )
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # Extract session info
    workspace = session.get("workspace", "")
    team = session.get("team")  # May be None for standalone
    session_name = session.get("name")
    branch = session.get("branch")

    if not workspace:
        console.print("[red]Session has no workspace path[/red]")
        return False

    # Validate workspace still exists
    workspace_path = Path(workspace)
    if not workspace_path.exists():
        console.print(f"[red]Workspace no longer exists: {workspace}[/red]")
        console.print("[dim]The session may have been deleted or moved.[/dim]")
        return False

    try:
        # Docker availability check
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            docker.check_docker_available()

        # Validate and resolve workspace (we know it exists from earlier check)
        resolved_path = _validate_and_resolve_workspace(str(workspace_path))
        if resolved_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return False
        workspace_path = resolved_path

        # Configure team settings
        cfg = config.load_config()
        _configure_team_settings(team, cfg)

        # Sync marketplace settings
        _sync_marketplace_settings(workspace_path, team)

        # Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Use session's stored branch if available (more accurate than detected)
        if branch:
            current_branch = branch

        # Show resume info
        workspace_name = workspace_path.name
        console.print(f"[cyan]Resuming session:[/cyan] {workspace_name}")
        if team:
            console.print(f"[dim]Team: {team}[/dim]")
        if current_branch:
            console.print(f"[dim]Branch: {current_branch}[/dim]")
        console.print()

        # Launch sandbox with resume flag
        _launch_sandbox(
            workspace_path=workspace_path,
            mount_path=mount_path,
            team=team,
            session_name=session_name,
            current_branch=current_branch,
            should_continue_session=True,  # Resume existing container
            fresh=False,
        )
        return True

    except Exception as e:
        console.print(f"[red]Error resuming session: {e}[/red]")
        return False
