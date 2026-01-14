"""Data loading functions for dashboard tabs.

This module contains functions to load data for each dashboard tab:
- Status: System overview (team, organization, counts)
- Containers: Docker containers managed by SCC
- Sessions: Recent Claude sessions
- Worktrees: Git worktrees in current repository

Each loader function returns a TabData instance ready for display.
Loaders handle errors gracefully, returning placeholder items on failure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..list_screen import ListItem
from .models import DashboardTab, TabData


def _load_status_tab_data(refresh_at: datetime | None = None) -> TabData:
    """Load Status tab data showing quick actions and context.

    The Status tab displays:
    - Primary actions (start session, resume)
    - Current team and organization context
    - Personal profile status
    - Quick access to settings & maintenance

    Diagnostic info (Docker, Sandbox, Statusline) is in `scc doctor`.

    Returns:
        TabData with status items.
    """
    # Import here to avoid circular imports
    import os
    from pathlib import Path

    from ... import config, sessions
    from ...core.personal_profiles import get_profile_status
    from ...docker import core as docker_core

    # Suppress unused import warning - refresh_at kept for API compatibility
    _ = refresh_at

    items: list[ListItem[Any]] = []

    # Start new session (primary action)
    items.append(
        ListItem(
            value="start_session",
            label="New session",
            description="",
        )
    )

    # Resume last session (quick action)
    try:
        recent_session = sessions.get_most_recent()
        if recent_session:
            workspace = recent_session.get("workspace", "")
            workspace_name = workspace.split("/")[-1] if workspace else "unknown"
            last_used = recent_session.get("last_used")
            last_used_display = ""
            if last_used:
                try:
                    dt = datetime.fromisoformat(last_used)
                    last_used_display = sessions.format_relative_time(dt)
                except ValueError:
                    last_used_display = last_used
            # Build middot-separated description for scannability
            desc_parts = [workspace_name]
            if recent_session.get("branch"):
                desc_parts.append(str(recent_session.get("branch")))
            if last_used_display:
                desc_parts.append(last_used_display)
            items.append(
                ListItem(
                    value={"_action": "resume_last_session", "session": recent_session},
                    label="Resume last",
                    description=" · ".join(desc_parts),
                )
            )
    except Exception:
        pass

    # Load current team info
    try:
        user_config = config.load_user_config()
        team = user_config.get("selected_profile")
        org_source = user_config.get("organization_source")

        if team:
            items.append(
                ListItem(
                    value="team",
                    label=f"Team: {team}",
                    description="",
                )
            )
        else:
            items.append(
                ListItem(
                    value="team",
                    label="Team: none",
                    description="",
                )
            )

        # Profile status (with inline indicators)
        # Format: "Profile: saved · ✓ synced" following Team pattern
        try:
            workspace = Path(os.getcwd())
            profile_status = get_profile_status(workspace)

            if profile_status.exists:
                # Build middot-separated status indicators
                if profile_status.import_count > 0:
                    # Imports available takes priority
                    profile_label = f"Profile: saved · ↓ {profile_status.import_count} importable"
                elif profile_status.has_drift:
                    profile_label = "Profile: saved · ◇ drifted"
                else:
                    profile_label = "Profile: saved · ✓ synced"
                items.append(
                    ListItem(
                        value="profile",
                        label=profile_label,
                        description="",
                    )
                )
            else:
                items.append(
                    ListItem(
                        value="profile",
                        label="Profile: none",
                        description="",
                    )
                )
        except Exception:
            pass  # Don't show if profile check fails

        # Organization/sync status
        if org_source and isinstance(org_source, dict):
            org_url = org_source.get("url", "")
            if org_url:
                # Get org name, fallback to domain
                org_name = None
                try:
                    org_config = config.load_cached_org_config()
                    if org_config:
                        org_name = org_config.get("organization", {}).get("name")
                except Exception:
                    org_name = None

                if not org_name:
                    # Extract domain as fallback
                    org_name = org_url.replace("https://", "").replace("http://", "").split("/")[0]

                items.append(
                    ListItem(
                        value="organization",
                        label=f"Organization: {org_name}",
                        description="",
                    )
                )
        elif user_config.get("standalone"):
            items.append(
                ListItem(
                    value="organization",
                    label="Mode: standalone",
                    description="",
                )
            )

    except Exception:
        items.append(
            ListItem(
                value="config_error",
                label="Config: error",
                description="",
            )
        )

    # Container count (summary - details in Containers tab)
    try:
        containers = docker_core.list_scc_containers()
        running = sum(1 for c in containers if "Up" in c.status)
        total = len(containers)
        items.append(
            ListItem(
                value="containers",
                label=f"Containers: {running}/{total} running",
                description="",
            )
        )
    except Exception:
        pass  # Don't show if Docker unavailable

    # Settings shortcut
    items.append(
        ListItem(
            value="settings",
            label="Settings",
            description="",
        )
    )

    return TabData(
        tab=DashboardTab.STATUS,
        title="Status",
        items=items,
        count_active=len(items),
        count_total=len(items),
    )


def _load_containers_tab_data() -> TabData:
    """Load Containers tab data showing SCC-managed containers.

    Returns:
        TabData with container list items.
    """
    from ...docker import core as docker_core
    from ..formatters import format_container

    items: list[ListItem[Any]] = []

    try:
        containers = docker_core.list_scc_containers()
        running_count = 0

        for container in containers:
            is_running = "Up" in container.status if container.status else False
            if is_running:
                running_count += 1

            items.append(format_container(container))

        if not items:
            items.append(
                ListItem(
                    value="no_containers",
                    label="No containers",
                    description="Press 'n' to start or run `scc start <path>`",
                )
            )

        return TabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=items,
            count_active=running_count,
            count_total=len(containers),
        )

    except Exception:
        return TabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[
                ListItem(
                    value="error",
                    label="Error",
                    description="Unable to query Docker",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_sessions_tab_data() -> TabData:
    """Load Sessions tab data showing recent Claude sessions.

    Returns:
        TabData with session list items. Each ListItem.value contains
        the raw session dict for access in the details pane.
    """
    from ... import sessions

    items: list[ListItem[dict[str, Any]]] = []

    try:
        recent = sessions.list_recent(limit=20)

        for session in recent:
            name = session.get("name", "Unnamed")
            desc_parts = []

            if session.get("team"):
                desc_parts.append(str(session["team"]))
            if session.get("branch"):
                desc_parts.append(str(session["branch"]))
            if session.get("last_used"):
                desc_parts.append(str(session["last_used"]))

            # Store full session dict for details pane access
            # Use middot separators for scannability
            items.append(
                ListItem(
                    value=session,
                    label=name,
                    description=" · ".join(desc_parts),
                )
            )

        if not items:
            # Placeholder with sentinel dict (startable: True enables Enter action)
            items.append(
                ListItem(
                    value={"_placeholder": "no_sessions", "_startable": True},
                    label="No sessions",
                    description="Press Enter to start",
                )
            )

        return TabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=items,
            count_active=len(recent),
            count_total=len(recent),
        )

    except Exception:
        return TabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=[
                ListItem(
                    value="error",
                    label="Error",
                    description="Unable to load sessions",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_worktrees_tab_data(verbose: bool = False) -> TabData:
    """Load Worktrees tab data showing git worktrees.

    Worktrees are loaded from the current working directory if it's a git repo.

    Args:
        verbose: If True, fetch git status for each worktree (slower but shows
            staged/modified/untracked counts with +N/!N/?N indicators).

    Returns:
        TabData with worktree list items.
    """
    import os
    from pathlib import Path

    from ... import git

    items: list[ListItem[str]] = []

    try:
        cwd = Path(os.getcwd())
        worktrees = git.list_worktrees(cwd)
        current_count = 0

        # If verbose, fetch status for each worktree
        if verbose:
            for wt in worktrees:
                staged, modified, untracked, timed_out = git.get_worktree_status(wt.path)
                wt.staged_count = staged
                wt.modified_count = modified
                wt.untracked_count = untracked
                wt.status_timed_out = timed_out
                wt.has_changes = (staged + modified + untracked) > 0

        for wt in worktrees:
            if wt.is_current:
                current_count += 1

            desc_parts = []
            if wt.branch:
                desc_parts.append(wt.branch)

            # Show status markers when verbose
            if verbose:
                if wt.status_timed_out:
                    desc_parts.append("…")  # Timeout indicator
                else:
                    status_parts = []
                    if wt.staged_count > 0:
                        status_parts.append(f"+{wt.staged_count}")
                    if wt.modified_count > 0:
                        status_parts.append(f"!{wt.modified_count}")
                    if wt.untracked_count > 0:
                        status_parts.append(f"?{wt.untracked_count}")
                    if status_parts:
                        desc_parts.append(" ".join(status_parts))
                    elif not wt.has_changes:
                        desc_parts.append(".")  # Clean indicator
            elif wt.has_changes:
                desc_parts.append("*modified")

            if wt.is_current:
                desc_parts.append("(current)")

            items.append(
                ListItem(
                    value=wt.path,
                    label=Path(wt.path).name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            items.append(
                ListItem(
                    value="no_worktrees",
                    label="No worktrees",
                    description="Press 'w' recent | 'i' init | 'c' clone",
                )
            )

        return TabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=items,
            count_active=current_count,
            count_total=len(worktrees),
        )

    except Exception:
        return TabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=[
                ListItem(
                    value="no_git",
                    label="Not available",
                    description="Press 'w' recent | 'i' init | 'c' clone",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_all_tab_data(verbose_worktrees: bool = False) -> dict[DashboardTab, TabData]:
    """Load data for all dashboard tabs.

    Args:
        verbose_worktrees: If True, fetch git status for each worktree
            (shows +N/!N/?N indicators but takes longer).

    Returns:
        Dictionary mapping each tab to its data.
    """
    return {
        DashboardTab.STATUS: _load_status_tab_data(),
        DashboardTab.CONTAINERS: _load_containers_tab_data(),
        DashboardTab.SESSIONS: _load_sessions_tab_data(),
        DashboardTab.WORKTREES: _load_worktrees_tab_data(verbose=verbose_worktrees),
    }
