"""
Docker sandbox launching functions.

This module handles Docker container creation and execution for launch command:
- Container creation or resume
- Session recording
- Context recording for Quick Resume
- Docker process handoff
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ... import config, docker, git, sessions
from ...contexts import WorkContext, record_context
from ...output_mode import print_human
from .render import show_launch_panel

if TYPE_CHECKING:
    pass


def launch_sandbox(
    workspace_path: Path | None,
    mount_path: Path | None,
    team: str | None,
    session_name: str | None,
    current_branch: str | None,
    should_continue_session: bool,
    fresh: bool,
    plugin_settings: dict[str, Any] | None = None,
) -> None:
    """
    Execute the Docker sandbox with all configurations applied.

    Handles container creation, session recording, and process handoff.
    Safety-net policy from org config is extracted and mounted read-only.
    Plugin settings are injected to container HOME (not workspace) to prevent
    host Claude from seeing SCC-managed plugins.

    Args:
        workspace_path: Path to the actual workspace for session recording.
        mount_path: Docker mount path (may differ for worktrees).
        team: Team profile name.
        session_name: Optional session name.
        current_branch: Git branch name.
        should_continue_session: Whether to continue existing session.
        fresh: Force new container.
        plugin_settings: Plugin settings dict to inject into container HOME.
            Contains extraKnownMarketplaces and enabledPlugins with absolute
            paths pointing to the bind-mounted workspace.
    """
    # Load org config for safety-net policy injection
    # This is already cached by _configure_team_settings(), so it's a fast read
    org_config = config.load_cached_org_config()

    # Prepare sandbox volume for credential persistence
    docker.prepare_sandbox_volume_for_credentials()

    # Get or create container
    docker_cmd, is_resume = docker.get_or_create_container(
        workspace=mount_path,
        branch=current_branch,
        profile=team,
        force_new=fresh,
        continue_session=should_continue_session,
        env_vars=None,
    )

    # Extract container name for session tracking
    container_name = extract_container_name(docker_cmd, is_resume)

    # Record session and context
    if workspace_path:
        sessions.record_session(
            workspace=str(workspace_path),
            team=team,
            session_name=session_name,
            container_name=container_name,
            branch=current_branch,
        )
        # Record context for quick resume feature
        # Determine repo root (may be same as workspace for non-worktrees)
        repo_root = git.get_worktree_main_repo(workspace_path) or workspace_path
        worktree_name = workspace_path.name
        context = WorkContext(
            team=team,  # Keep None for standalone mode (don't use "base")
            repo_root=repo_root,
            worktree_path=workspace_path,
            worktree_name=worktree_name,
            branch=current_branch,  # For Quick Resume branch highlighting
            last_session_id=session_name,
        )
        # Context recording is best-effort - failure should never block sandbox launch
        # (Quick Resume is a convenience feature, not critical path)
        try:
            record_context(context)
        except (OSError, ValueError) as e:
            import logging

            print_human(
                "[yellow]Warning:[/yellow] Could not save Quick Resume context.",
                highlight=False,
            )
            print_human(f"[dim]{e}[/dim]", highlight=False)
            logging.debug(f"Failed to record context for Quick Resume: {e}")

        if team:
            try:
                config.set_workspace_team(str(workspace_path), team)
            except (OSError, ValueError) as e:
                import logging

                print_human(
                    "[yellow]Warning:[/yellow] Could not save workspace team preference.",
                    highlight=False,
                )
                print_human(f"[dim]{e}[/dim]", highlight=False)
                logging.debug(f"Failed to store workspace team mapping: {e}")

    # Show launch info and execute
    show_launch_panel(
        workspace=workspace_path,
        team=team,
        session_name=session_name,
        branch=current_branch,
        is_resume=is_resume,
    )

    # Pass org_config for safety-net policy injection (mounted read-only)
    # Pass workspace_path as container_workdir so Claude's CWD is the actual workspace
    # (mount_path may be a parent directory for worktree support)
    # Pass plugin_settings for container HOME injection (prevents host leakage)
    docker.run(
        docker_cmd,
        org_config=org_config,
        container_workdir=workspace_path,
        plugin_settings=plugin_settings,
    )


def extract_container_name(docker_cmd: list[str], is_resume: bool) -> str | None:
    """Extract container name from docker command for session tracking."""
    for idx, arg in enumerate(docker_cmd):
        if arg == "--name" and idx + 1 < len(docker_cmd):
            return docker_cmd[idx + 1]
        if arg.startswith("--name="):
            return arg.split("=", 1)[1]

    if is_resume and docker_cmd:
        # For resume, container name is the last arg
        if docker_cmd[-1].startswith("scc-"):
            return docker_cmd[-1]
    return None
