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

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING

from ... import sessions
from ...console import get_err_console

if TYPE_CHECKING:
    from rich.console import Console

from scc_cli.application import dashboard as app_dashboard
from scc_cli.ports.session_models import SessionSummary

from ...confirm import Confirm
from ..chrome import print_with_layout
from ..keys import (
    ContainerActionMenuRequested,
    ContainerRemoveRequested,
    ContainerResumeRequested,
    ContainerStopRequested,
    CreateWorktreeRequested,
    GitInitRequested,
    ProfileMenuRequested,
    RecentWorkspacesRequested,
    RefreshRequested,
    SandboxImportRequested,
    SessionActionMenuRequested,
    SessionResumeRequested,
    SettingsRequested,
    StartRequested,
    StatuslineInstallRequested,
    TeamSwitchRequested,
    VerboseToggleRequested,
    WorktreeActionMenuRequested,
)
from ..list_screen import ListState
from ..time_format import format_relative_time_from_datetime
from ._dashboard import Dashboard
from .loaders import _to_tab_data
from .models import DashboardState


def _format_last_used(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp
    return format_relative_time_from_datetime(dt)


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
        - VerboseToggleRequested: Toggle verbose worktree status display
    """
    from ... import config as scc_config

    # Show one-time onboarding banner for new users
    if not scc_config.has_seen_onboarding():
        _show_onboarding_banner()
        scc_config.mark_onboarding_seen()

    flow_state = app_dashboard.DashboardFlowState()
    session_service = sessions.get_session_service()

    def _load_tabs(
        verbose_worktrees: bool = False,
    ) -> Mapping[
        app_dashboard.DashboardTab,
        app_dashboard.DashboardTabData,
    ]:
        return app_dashboard.load_all_tab_data(
            session_service=session_service,
            format_last_used=_format_last_used,
            verbose_worktrees=verbose_worktrees,
        )

    while True:
        view, flow_state = app_dashboard.build_dashboard_view(
            flow_state,
            _load_tabs,
        )
        tabs = {tab: _to_tab_data(tab_data) for tab, tab_data in view.tabs.items()}
        state = DashboardState(
            active_tab=view.active_tab,
            tabs=tabs,
            list_state=ListState(items=tabs[view.active_tab].items),
            status_message=view.status_message,
            verbose_worktrees=view.verbose_worktrees,
        )

        dashboard = Dashboard(state)
        try:
            dashboard.run()
            break
        except TeamSwitchRequested:
            flow_state, should_exit = _apply_event(flow_state, app_dashboard.TeamSwitchEvent())
            if should_exit:
                break

        except StartRequested as start_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.StartFlowEvent(
                    return_to=_resolve_tab(start_req.return_to),
                    reason=start_req.reason,
                ),
            )
            if should_exit:
                break

        except RefreshRequested as refresh_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.RefreshEvent(return_to=_resolve_tab(refresh_req.return_to)),
            )
            if should_exit:
                break

        except SessionResumeRequested as resume_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SessionResumeEvent(
                    return_to=_resolve_tab(resume_req.return_to),
                    session=resume_req.session,
                ),
            )
            if should_exit:
                break

        except StatuslineInstallRequested as statusline_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.StatuslineInstallEvent(
                    return_to=_resolve_tab(statusline_req.return_to)
                ),
            )
            if should_exit:
                break

        except RecentWorkspacesRequested as recent_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.RecentWorkspacesEvent(return_to=_resolve_tab(recent_req.return_to)),
            )
            if should_exit:
                break

        except GitInitRequested as init_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.GitInitEvent(return_to=_resolve_tab(init_req.return_to)),
            )
            if should_exit:
                break

        except CreateWorktreeRequested as create_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.CreateWorktreeEvent(
                    return_to=_resolve_tab(create_req.return_to),
                    is_git_repo=create_req.is_git_repo,
                ),
            )
            if should_exit:
                break

        except VerboseToggleRequested as verbose_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.VerboseToggleEvent(
                    return_to=_resolve_tab(verbose_req.return_to),
                    verbose=verbose_req.verbose,
                ),
            )
            if should_exit:
                break

        except SettingsRequested as settings_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SettingsEvent(return_to=_resolve_tab(settings_req.return_to)),
            )
            if should_exit:
                break

        except ContainerStopRequested as container_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerStopEvent(
                    return_to=_resolve_tab(container_req.return_to),
                    container_id=container_req.container_id,
                    container_name=container_req.container_name,
                ),
            )
            if should_exit:
                break

        except ContainerResumeRequested as container_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerResumeEvent(
                    return_to=_resolve_tab(container_req.return_to),
                    container_id=container_req.container_id,
                    container_name=container_req.container_name,
                ),
            )
            if should_exit:
                break

        except ContainerRemoveRequested as container_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerRemoveEvent(
                    return_to=_resolve_tab(container_req.return_to),
                    container_id=container_req.container_id,
                    container_name=container_req.container_name,
                ),
            )
            if should_exit:
                break

        except ProfileMenuRequested as profile_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ProfileMenuEvent(return_to=_resolve_tab(profile_req.return_to)),
            )
            if should_exit:
                break

        except SandboxImportRequested as import_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SandboxImportEvent(return_to=_resolve_tab(import_req.return_to)),
            )
            if should_exit:
                break

        except ContainerActionMenuRequested as action_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.ContainerActionMenuEvent(
                    return_to=_resolve_tab(action_req.return_to),
                    container_id=action_req.container_id,
                    container_name=action_req.container_name,
                ),
            )
            if should_exit:
                break

        except SessionActionMenuRequested as action_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.SessionActionMenuEvent(
                    return_to=_resolve_tab(action_req.return_to),
                    session=action_req.session,
                ),
            )
            if should_exit:
                break

        except WorktreeActionMenuRequested as action_req:
            flow_state, should_exit = _apply_event(
                flow_state,
                app_dashboard.WorktreeActionMenuEvent(
                    return_to=_resolve_tab(action_req.return_to),
                    worktree_path=action_req.worktree_path,
                ),
            )
            if should_exit:
                break


def _resolve_tab(tab_name: str | None) -> app_dashboard.DashboardTab:
    if not tab_name:
        return app_dashboard.DashboardTab.STATUS
    try:
        return app_dashboard.DashboardTab[tab_name]
    except KeyError:
        return app_dashboard.DashboardTab.STATUS


def _apply_event(
    state: app_dashboard.DashboardFlowState,
    event: app_dashboard.DashboardEvent,
) -> tuple[app_dashboard.DashboardFlowState, bool]:
    step = app_dashboard.handle_dashboard_event(state, event)
    if isinstance(step, app_dashboard.DashboardFlowOutcome):
        return step.state, step.exit_dashboard
    result = _run_effect(step.effect)
    outcome = app_dashboard.apply_dashboard_effect_result(step.state, step.effect, result)
    return outcome.state, outcome.exit_dashboard


def _run_effect(effect: app_dashboard.DashboardEffect) -> object:
    if isinstance(effect, app_dashboard.TeamSwitchEvent):
        _handle_team_switch()
        return None
    if isinstance(effect, app_dashboard.StartFlowEvent):
        return _handle_start_flow(effect.reason)
    if isinstance(effect, app_dashboard.SessionResumeEvent):
        return _handle_session_resume(effect.session)
    if isinstance(effect, app_dashboard.StatuslineInstallEvent):
        return _handle_statusline_install()
    if isinstance(effect, app_dashboard.RecentWorkspacesEvent):
        return _handle_recent_workspaces()
    if isinstance(effect, app_dashboard.GitInitEvent):
        return _handle_git_init()
    if isinstance(effect, app_dashboard.CreateWorktreeEvent):
        if effect.is_git_repo:
            return _handle_create_worktree()
        return _handle_clone()
    if isinstance(effect, app_dashboard.SettingsEvent):
        return _handle_settings()
    if isinstance(effect, app_dashboard.ContainerStopEvent):
        return _handle_container_stop(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.ContainerResumeEvent):
        return _handle_container_resume(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.ContainerRemoveEvent):
        return _handle_container_remove(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.ProfileMenuEvent):
        return _handle_profile_menu()
    if isinstance(effect, app_dashboard.SandboxImportEvent):
        return _handle_sandbox_import()
    if isinstance(effect, app_dashboard.ContainerActionMenuEvent):
        return _handle_container_action_menu(effect.container_id, effect.container_name)
    if isinstance(effect, app_dashboard.SessionActionMenuEvent):
        return _handle_session_action_menu(effect.session)
    if isinstance(effect, app_dashboard.WorktreeActionMenuEvent):
        return _handle_worktree_action_menu(effect.worktree_path)
    msg = f"Unsupported dashboard effect: {effect}"
    raise ValueError(msg)


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

        available_teams = teams.list_teams(org_config)
        if not available_teams:
            print_with_layout(console, "[yellow]No teams available[/yellow]", max_width=120)
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
            print_with_layout(
                console,
                f"[green]Switched to team: {team_name}[/green]",
                max_width=120,
            )
        # If cancelled, just return to dashboard

    except TeamSwitchRequested:
        # Nested team switch (shouldn't happen, but handle gracefully)
        pass
    except Exception as e:
        print_with_layout(
            console,
            f"[red]Error switching team: {e}[/red]",
            max_width=120,
        )


def _handle_start_flow(reason: str) -> app_dashboard.StartFlowResult:
    """Handle start flow request from dashboard."""
    from ...commands.launch import run_start_wizard_flow

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # Handle worktree-specific start (Enter on worktree in details pane)
    if reason.startswith("worktree:"):
        worktree_path = reason[9:]  # Remove "worktree:" prefix
        return _handle_worktree_start(worktree_path)

    # For empty-state starts, skip Quick Resume (user intent is "create new")
    skip_quick_resume = reason in ("no_containers", "no_sessions")

    # Show contextual message based on reason
    if reason == "no_containers":
        print_with_layout(console, "[dim]Starting a new session...[/dim]")
    elif reason == "no_sessions":
        print_with_layout(console, "[dim]Starting your first session...[/dim]")
    console.print()

    # Run the wizard with allow_back=True for dashboard context
    # Returns: True (success), False (Esc/back), None (q/quit)
    result = run_start_wizard_flow(skip_quick_resume=skip_quick_resume, allow_back=True)
    return app_dashboard.StartFlowResult.from_legacy(result)


def _handle_worktree_start(worktree_path: str) -> app_dashboard.StartFlowResult:
    """Handle starting a session in a specific worktree."""
    from pathlib import Path

    from rich.status import Status

    from ... import config, docker
    from ...application.start_session import (
        StartSessionDependencies,
        StartSessionRequest,
        sync_marketplace_settings_for_start,
    )
    from ...bootstrap import get_default_adapters
    from ...commands.launch import (
        _launch_sandbox,
        _resolve_mount_and_branch,
        _validate_and_resolve_workspace,
    )
    from ...commands.launch.team_settings import _configure_team_settings
    from ...marketplace.materialize import materialize_marketplace
    from ...marketplace.resolve import resolve_effective_config
    from ...theme import Spinners

    console = get_err_console()

    workspace_path = Path(worktree_path)
    workspace_name = workspace_path.name

    # Validate workspace exists
    if not workspace_path.exists():
        console.print(f"[red]Worktree no longer exists: {worktree_path}[/red]")
        return app_dashboard.StartFlowResult.from_legacy(False)

    console.print(f"[cyan]Starting session in:[/cyan] {workspace_name}")
    console.print()

    try:
        # Docker availability check
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            docker.check_docker_available()

        # Validate and resolve workspace
        resolved_path = _validate_and_resolve_workspace(str(workspace_path))
        if resolved_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return app_dashboard.StartFlowResult.from_legacy(False)
        workspace_path = resolved_path

        # Get current team from config
        cfg = config.load_user_config()
        team = cfg.get("selected_profile")
        _configure_team_settings(team, cfg)

        # Sync marketplace settings
        adapters = get_default_adapters()
        start_dependencies = StartSessionDependencies(
            filesystem=adapters.filesystem,
            remote_fetcher=adapters.remote_fetcher,
            clock=adapters.clock,
            git_client=adapters.git_client,
            agent_runner=adapters.agent_runner,
            sandbox_runtime=adapters.sandbox_runtime,
            resolve_effective_config=resolve_effective_config,
            materialize_marketplace=materialize_marketplace,
        )
        start_request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=team,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=team is None,
            dry_run=False,
            allow_suspicious=False,
            org_config=config.load_cached_org_config(),
            org_config_url=None,
        )
        sync_result, _sync_error = sync_marketplace_settings_for_start(
            start_request,
            start_dependencies,
        )
        plugin_settings = sync_result.rendered_settings if sync_result else None

        # Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Show session info
        if team:
            console.print(f"[dim]Team: {team}[/dim]")
        if current_branch:
            console.print(f"[dim]Branch: {current_branch}[/dim]")
        console.print()

        # Launch sandbox
        _launch_sandbox(
            workspace_path=workspace_path,
            mount_path=mount_path,
            team=team,
            session_name=None,  # No specific session name
            current_branch=current_branch,
            should_continue_session=False,
            fresh=False,
            plugin_settings=plugin_settings,
        )
        return app_dashboard.StartFlowResult.from_legacy(True)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        return app_dashboard.StartFlowResult.from_legacy(False)
    except Exception as e:
        console.print(f"[red]Error starting session: {e}[/red]")
        return app_dashboard.StartFlowResult.from_legacy(False)


def _handle_session_resume(session: SessionSummary) -> bool:
    """Resume a Claude Code session from the dashboard.

    This function executes OUTSIDE Rich Live context (the dashboard has
    already exited via the exception unwind before this is called).

    Args:
        session: Session summary containing workspace, team, branch, container_name, etc.

    Returns:
        True if session was resumed successfully, False if resume failed
        (e.g., workspace no longer exists).
    """

    from pathlib import Path

    from rich.status import Status

    from ... import config, docker
    from ...application.start_session import (
        StartSessionDependencies,
        StartSessionRequest,
        sync_marketplace_settings_for_start,
    )
    from ...bootstrap import get_default_adapters
    from ...commands.launch import (
        _launch_sandbox,
        _resolve_mount_and_branch,
        _validate_and_resolve_workspace,
    )
    from ...commands.launch.team_settings import _configure_team_settings
    from ...marketplace.materialize import materialize_marketplace
    from ...marketplace.resolve import resolve_effective_config
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # Extract session info
    workspace = session.workspace
    team = session.team  # May be None for standalone
    session_name = session.name
    branch = session.branch

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
        cfg = config.load_user_config()
        _configure_team_settings(team, cfg)

        # Sync marketplace settings
        adapters = get_default_adapters()
        start_dependencies = StartSessionDependencies(
            filesystem=adapters.filesystem,
            remote_fetcher=adapters.remote_fetcher,
            clock=adapters.clock,
            git_client=adapters.git_client,
            agent_runner=adapters.agent_runner,
            sandbox_runtime=adapters.sandbox_runtime,
            resolve_effective_config=resolve_effective_config,
            materialize_marketplace=materialize_marketplace,
        )
        start_request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=team,
            session_name=session_name,
            resume=True,
            fresh=False,
            offline=False,
            standalone=team is None,
            dry_run=False,
            allow_suspicious=False,
            org_config=config.load_cached_org_config(),
            org_config_url=None,
        )
        sync_result, _sync_error = sync_marketplace_settings_for_start(
            start_request,
            start_dependencies,
        )
        plugin_settings = sync_result.rendered_settings if sync_result else None

        # Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Use session's stored branch if available (more accurate than detected)
        if branch:
            current_branch = branch

        # Show resume info
        workspace_name = workspace_path.name
        print_with_layout(console, f"[cyan]Resuming session:[/cyan] {workspace_name}")
        if team:
            print_with_layout(console, f"[dim]Team: {team}[/dim]")
        if current_branch:
            print_with_layout(console, f"[dim]Branch: {current_branch}[/dim]")
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
            plugin_settings=plugin_settings,
        )
        return True

    except Exception as e:
        console.print(f"[red]Error resuming session: {e}[/red]")
        return False


def _handle_statusline_install() -> bool:
    """Handle statusline installation request from dashboard.

    Installs the Claude Code statusline enhancement using the same logic
    as `scc statusline`. Works cross-platform (Windows, macOS, Linux).

    Returns:
        True if statusline was installed successfully, False otherwise.
    """
    from rich.status import Status

    from ...commands.admin import install_statusline
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    console.print("[cyan]Installing statusline...[/cyan]")
    console.print()

    try:
        with Status(
            "[cyan]Configuring statusline...[/cyan]",
            console=console,
            spinner=Spinners.DOCKER,
        ):
            result = install_statusline()

        if result:
            console.print("[green]✓ Statusline installed successfully![/green]")
            console.print("[dim]Press any key to continue...[/dim]")
        else:
            console.print("[yellow]Statusline installation completed with warnings[/yellow]")

        return result

    except Exception as e:
        console.print(f"[red]Error installing statusline: {e}[/red]")
        return False


def _handle_recent_workspaces() -> str | None:
    """Handle recent workspaces picker from dashboard.

    Shows a picker with recently used workspaces, allowing the user to
    quickly navigate to a previous project.

    Returns:
        Path of selected workspace, or None if cancelled.
    """
    from ...contexts import load_recent_contexts
    from ..picker import pick_context

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        recent = load_recent_contexts()
        if not recent:
            console.print("[yellow]No recent workspaces found[/yellow]")
            console.print(
                "[dim]Start a session with `scc start <path>` to populate this list.[/dim]"
            )
            return None

        selected = pick_context(
            recent,
            title="Recent Workspaces",
            subtitle="Select a workspace",
        )

        if selected:
            return str(selected.worktree_path)
        return None

    except Exception as e:
        console.print(f"[red]Error loading recent workspaces: {e}[/red]")
        return None


def _handle_git_init() -> bool:
    """Handle git init request from dashboard.

    Initializes a new git repository in the current directory,
    optionally creating an initial commit.

    Returns:
        True if git was initialized successfully, False otherwise.
    """
    import os
    import subprocess

    console = get_err_console()
    _prepare_for_nested_ui(console)

    cwd = os.getcwd()
    console.print(f"[cyan]Initializing git repository in:[/cyan] {cwd}")
    console.print()

    try:
        # Run git init
        result = subprocess.run(
            ["git", "init"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        console.print(f"[green]✓ {result.stdout.strip()}[/green]")

        # Optionally create initial commit
        console.print()
        console.print("[dim]Creating initial empty commit...[/dim]")

        # Try to create an empty commit
        try:
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "Initial commit"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            console.print("[green]✓ Initial commit created[/green]")
        except subprocess.CalledProcessError as e:
            # May fail if git identity not configured
            if "user.email" in e.stderr or "user.name" in e.stderr:
                console.print("[yellow]Tip: Configure git identity to enable commits:[/yellow]")
                console.print("  git config user.name 'Your Name'")
                console.print("  git config user.email 'your@email.com'")
            else:
                console.print(
                    f"[yellow]Could not create initial commit: {e.stderr.strip()}[/yellow]"
                )

        console.print()
        console.print("[dim]Press any key to continue...[/dim]")
        return True

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Git init failed: {e.stderr.strip()}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]Git is not installed or not in PATH[/red]")
        return False


def _handle_create_worktree() -> bool:
    """Handle create worktree request from dashboard.

    Prompts for a worktree name and creates a new git worktree.

    Returns:
        True if worktree was created successfully, False otherwise.
    """
    console = get_err_console()
    _prepare_for_nested_ui(console)

    console.print("[cyan]Create new worktree[/cyan]")
    console.print()
    console.print("[dim]Use `scc worktree create <name>` from the terminal for full options.[/dim]")
    console.print("[dim]Press any key to continue...[/dim]")

    # For now, just inform user of CLI option
    # Full interactive creation can be added in a future phase
    return False


def _handle_clone() -> bool:
    """Handle clone request from dashboard.

    Informs user how to clone a repository.

    Returns:
        True if clone was successful, False otherwise.
    """
    console = get_err_console()
    _prepare_for_nested_ui(console)

    console.print("[cyan]Clone a repository[/cyan]")
    console.print()
    console.print("[dim]Use `git clone <url>` to clone a repository, then run `scc` in it.[/dim]")
    console.print("[dim]Press any key to continue...[/dim]")

    # For now, just inform user of git clone option
    # Full interactive clone can be added in a future phase
    return False


def _handle_container_stop(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Stop a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up") is False:
        return True, f"Already stopped: {container_name}"

    with Status(
        f"[cyan]Stopping {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.stop_container(container_id)

    return success, (f"Stopped {container_name}" if success else f"Failed to stop {container_name}")


def _handle_container_resume(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Resume a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return True, f"Already running: {container_name}"

    with Status(
        f"[cyan]Starting {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.resume_container(container_id)

    return success, (
        f"Resumed {container_name}" if success else f"Failed to resume {container_name}"
    )


def _handle_container_remove(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Remove a stopped container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return False, f"Stop {container_name} before deleting"

    with Status(
        f"[cyan]Removing {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.remove_container(container_name or container_id)

    return success, (
        f"Removed {container_name}" if success else f"Failed to remove {container_name}"
    )


def _handle_container_action_menu(container_id: str, container_name: str) -> str | None:
    """Show a container actions menu and execute the selected action."""
    import subprocess

    from ... import docker
    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name) or ""
    is_running = status.startswith("Up")

    items: list[ListItem[str]] = []

    if is_running:
        items.append(
            ListItem(
                value="attach_shell",
                label="Attach shell",
                description="docker exec -it <container> bash",
            )
        )
        items.append(
            ListItem(
                value="stop",
                label="Stop container",
                description="Stop running container",
            )
        )
    else:
        items.append(
            ListItem(
                value="resume",
                label="Resume container",
                description="Start stopped container",
            )
        )
        items.append(
            ListItem(
                value="delete",
                label="Delete container",
                description="Remove stopped container",
            )
        )

    if not items:
        return "No actions available"

    screen = ListScreen(items, title=f"Actions — {container_name}")
    selected = screen.run()
    if not selected:
        return "Cancelled"

    if selected == "attach_shell":
        cmd = ["docker", "exec", "-it", container_name, "bash"]
        result = subprocess.run(cmd)
        return "Shell closed" if result.returncode == 0 else "Shell exited with errors"

    if selected == "stop":
        _, message = _handle_container_stop(container_id, container_name)
        return message

    if selected == "resume":
        _, message = _handle_container_resume(container_id, container_name)
        return message

    if selected == "delete":
        _, message = _handle_container_remove(container_id, container_name)
        return message

    return None


def _handle_session_action_menu(session: SessionSummary) -> str | None:
    """Show a session actions menu and execute the selected action."""
    from ... import sessions as session_store
    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    items: list[ListItem[str]] = [
        ListItem(value="resume", label="Resume session", description="Continue this session"),
    ]

    items.append(
        ListItem(
            value="remove",
            label="Remove from history",
            description="Does not delete any containers",
        )
    )

    screen = ListScreen(items, title="Session Actions")
    selected = screen.run()
    if not selected:
        return "Cancelled"

    if selected == "resume":
        try:
            success = _handle_session_resume(session)
            return "Resumed session" if success else "Resume failed"
        except Exception:
            return "Resume failed"

    if selected == "remove":
        workspace = session.workspace
        branch = session.branch
        if not workspace:
            return "Missing workspace"
        removed = session_store.remove_session(workspace, branch)
        return "Removed from history" if removed else "No matching session found"

    return None


def _handle_worktree_action_menu(worktree_path: str) -> str | None:
    """Show a worktree actions menu and execute the selected action."""
    import subprocess
    from pathlib import Path

    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    items: list[ListItem[str]] = [
        ListItem(value="start", label="Start session here", description="Launch Claude"),
        ListItem(
            value="open_shell",
            label="Open shell",
            description="cd into this worktree",
        ),
        ListItem(
            value="remove",
            label="Remove worktree",
            description="git worktree remove <path>",
        ),
    ]

    screen = ListScreen(items, title=f"Worktree Actions — {Path(worktree_path).name}")
    selected = screen.run()
    if not selected:
        return "Cancelled"

    if selected == "start":
        # Reuse worktree start flow directly
        result = _handle_worktree_start(worktree_path)
        if result.decision is app_dashboard.StartFlowDecision.QUIT:
            return "Cancelled"
        if result.decision is app_dashboard.StartFlowDecision.LAUNCHED:
            return "Started session"
        return "Start cancelled"

    if selected == "open_shell":
        console.print(f"[cyan]cd {worktree_path}[/cyan]")
        console.print("[dim]Copy/paste to jump into this worktree.[/dim]")
        return "Path copied to screen"

    if selected == "remove":
        if not Confirm.ask(
            "[yellow]Remove this worktree? This cannot be undone.[/yellow]",
            default=False,
        ):
            return "Cancelled"
        try:
            subprocess.run(["git", "worktree", "remove", "--force", worktree_path], check=True)
            return "Worktree removed"
        except Exception:
            return "Failed to remove worktree"

    return None


def _handle_settings() -> str | None:
    """Handle settings and maintenance screen request from dashboard.

    Shows the settings and maintenance TUI, allowing users to perform
    maintenance operations like clearing cache, pruning sessions, etc.

    Returns:
        Success message string if an action was performed, None if cancelled.
    """
    from ..settings import run_settings_screen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        return run_settings_screen()
    except Exception as e:
        console.print(f"[red]Error in settings screen: {e}[/red]")
        return None


def _handle_profile_menu() -> str | None:
    """Handle profile quick menu request from dashboard.

    Shows a quick menu with profile actions: save, apply, diff, settings.

    Returns:
        Success message string if an action was performed, None if cancelled.
    """
    from pathlib import Path

    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    items: list[ListItem[str]] = [
        ListItem(
            value="save",
            label="Save current settings",
            description="Capture workspace settings to profile",
        ),
        ListItem(
            value="apply",
            label="Apply saved profile",
            description="Restore settings from profile",
        ),
        ListItem(
            value="diff",
            label="Show diff",
            description="Compare profile vs workspace",
        ),
        ListItem(
            value="settings",
            label="Open in Settings",
            description="Full profile management",
        ),
    ]

    screen = ListScreen(items, title="[cyan]Profile[/cyan]")
    selected = screen.run()

    if not selected:
        return None

    # Import profile functions
    from ...core.personal_profiles import (
        compute_fingerprints,
        load_personal_profile,
        load_workspace_mcp,
        load_workspace_settings,
        merge_personal_mcp,
        merge_personal_settings,
        save_applied_state,
        save_personal_profile,
        write_workspace_mcp,
        write_workspace_settings,
    )

    workspace = Path.cwd()

    if selected == "save":
        try:
            settings = load_workspace_settings(workspace)
            mcp = load_workspace_mcp(workspace)
            save_personal_profile(workspace, settings, mcp)
            return "Profile saved"
        except Exception as e:
            console.print(f"[red]Save failed: {e}[/red]")
            return "Profile save failed"

    if selected == "apply":
        profile = load_personal_profile(workspace)
        if not profile:
            console.print("[yellow]No profile saved for this workspace[/yellow]")
            return "No profile to apply"
        try:
            # Load current workspace settings
            current_settings = load_workspace_settings(workspace) or {}
            current_mcp = load_workspace_mcp(workspace) or {}

            # Merge profile into workspace
            if profile.settings:
                merged_settings = merge_personal_settings(
                    workspace, current_settings, profile.settings
                )
                write_workspace_settings(workspace, merged_settings)

            if profile.mcp:
                merged_mcp = merge_personal_mcp(current_mcp, profile.mcp)
                write_workspace_mcp(workspace, merged_mcp)

            # Update applied state
            fingerprints = compute_fingerprints(workspace)
            save_applied_state(workspace, profile.profile_id, fingerprints)

            return "Profile applied"
        except Exception as e:
            console.print(f"[red]Apply failed: {e}[/red]")
            return "Profile apply failed"

    if selected == "diff":
        profile = load_personal_profile(workspace)
        if not profile:
            console.print("[yellow]No profile saved for this workspace[/yellow]")
            return "No profile to compare"

        # Show structured diff overlay
        from rich import box
        from rich.panel import Panel

        from ...core.personal_profiles import (
            compute_structured_diff,
            load_workspace_mcp,
            load_workspace_settings,
        )

        current_settings = load_workspace_settings(workspace) or {}
        current_mcp = load_workspace_mcp(workspace) or {}

        diff = compute_structured_diff(
            workspace_settings=current_settings,
            profile_settings=profile.settings,
            workspace_mcp=current_mcp,
            profile_mcp=profile.mcp,
        )

        if diff.is_empty:
            console.print("[green]✓ Profile is in sync with workspace[/green]")
            return "Profile in sync"

        # Build diff content
        lines: list[str] = []
        current_section = ""
        indicators = {
            "added": "[green]+[/green]",
            "removed": "[red]−[/red]",
            "modified": "[yellow]~[/yellow]",
        }
        section_names = {
            "plugins": "plugins",
            "mcp_servers": "mcp_servers",
            "marketplaces": "marketplaces",
        }

        for item in diff.items[:12]:  # Smart fallback: limit to 12 items
            if item.section != current_section:
                if current_section:
                    lines.append("")
                lines.append(f"  [bold]{section_names.get(item.section, item.section)}[/bold]")
                current_section = item.section
            indicator = indicators.get(item.status, " ")
            modifier = "  [dim](modified)[/dim]" if item.status == "modified" else ""
            lines.append(f"    {indicator} {item.name}{modifier}")

        if diff.total_count > 12:
            lines.append("")
            lines.append(f"  [dim]+ {diff.total_count - 12} more...[/dim]")

        lines.append("")
        lines.append(f"  [dim]{diff.total_count} difference(s)[/dim]")

        console.print()
        console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Profile Diff[/bold]",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        return "Diff shown"

    if selected == "settings":
        # Open settings TUI on Profiles tab
        from ..settings import run_settings_screen

        return run_settings_screen(initial_category="PROFILES")

    return None


def _handle_sandbox_import() -> str | None:
    """Handle sandbox plugin import request from dashboard.

    Detects plugins installed in the sandbox but not in the workspace settings,
    and prompts the user to import them.

    Returns:
        Success message string if imports were made, None if cancelled or no imports.
    """
    import os
    from pathlib import Path

    from ...core.personal_profiles import (
        compute_sandbox_import_candidates,
        load_workspace_settings,
        merge_sandbox_imports,
        write_workspace_settings,
    )
    from ...docker.launch import get_sandbox_settings

    console = get_err_console()
    _prepare_for_nested_ui(console)

    workspace = Path(os.getcwd())

    # Get current workspace settings
    workspace_settings = load_workspace_settings(workspace) or {}

    # Get sandbox settings from Docker volume
    console.print("[dim]Checking sandbox for plugin changes...[/dim]")
    sandbox_settings = get_sandbox_settings()

    if not sandbox_settings:
        console.print("[yellow]No sandbox settings found.[/yellow]")
        console.print("[dim]Start a session first to create sandbox settings.[/dim]")
        return None

    # Compute what's in sandbox but not in workspace
    missing_plugins, missing_marketplaces = compute_sandbox_import_candidates(
        workspace_settings, sandbox_settings
    )

    if not missing_plugins and not missing_marketplaces:
        console.print("[green]✓ No new plugins to import.[/green]")
        console.print("[dim]Workspace is in sync with sandbox.[/dim]")
        return "No imports needed"

    # Show preview of what will be imported
    console.print()
    console.print("[yellow]Sandbox plugins available for import:[/yellow]")
    if missing_plugins:
        for plugin in missing_plugins:
            console.print(f"  [cyan]+[/cyan] {plugin}")
    if missing_marketplaces:
        for name in sorted(missing_marketplaces.keys()):
            console.print(f"  [cyan]+[/cyan] marketplace: {name}")
    console.print()

    # Confirm import
    if not Confirm.ask("Import these into workspace settings?", default=True):
        return None

    # Merge and write to workspace settings
    try:
        merged_settings = merge_sandbox_imports(
            workspace_settings, missing_plugins, missing_marketplaces
        )
        write_workspace_settings(workspace, merged_settings)

        total = len(missing_plugins) + len(missing_marketplaces)
        console.print(f"[green]✓ Imported {total} item(s) to workspace settings.[/green]")
        return f"Imported {total} plugin(s)"

    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        return "Import failed"


def _show_onboarding_banner() -> None:
    """Show one-time onboarding banner for new users.

    Displays a brief tip about `scc worktree enter` as the recommended
    way to switch worktrees without shell configuration.

    Waits for user to press any key before continuing.
    """
    import readchar
    from rich import box
    from rich.panel import Panel

    console = get_err_console()

    # Create a compact onboarding message
    message = (
        "[bold cyan]Welcome to SCC![/bold cyan]\n\n"
        "[yellow]Tip:[/yellow] Use [bold]scc worktree enter[/bold] to switch worktrees.\n"
        "No shell setup required — just type [dim]exit[/dim] to return.\n\n"
        "[dim]Press [bold]?[/bold] anytime for help, or any key to continue...[/dim]"
    )

    console.print()
    print_with_layout(
        console,
        Panel(
            message,
            title="[bold]Getting Started[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
        ),
        max_width=120,
        constrain=True,
    )
    console.print()

    # Wait for any key
    readchar.readkey()
