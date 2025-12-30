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

from typing import Any

from ..list_screen import ListItem
from .models import DashboardTab, TabData


def _load_status_tab_data() -> TabData:
    """Load Status tab data showing system overview.

    The Status tab displays:
    - Current team and organization info
    - Sync status with remote config
    - Resource counts for quick overview

    Returns:
        TabData with status summary items.
    """
    # Import here to avoid circular imports
    from ... import config, sessions
    from ...docker import core as docker_core

    items: list[ListItem[str]] = []

    # Load current team info
    try:
        user_config = config.load_user_config()
        team = user_config.get("selected_profile")
        org_source = user_config.get("organization_source")

        if team:
            items.append(
                ListItem(
                    value="team",
                    label="Team",
                    description=str(team),
                )
            )
        else:
            items.append(
                ListItem(
                    value="team",
                    label="Team",
                    description="No team selected",
                )
            )

        # Organization/sync status
        if org_source and isinstance(org_source, dict):
            org_url = org_source.get("url", "")
            if org_url:
                # Extract domain for display
                domain = org_url.replace("https://", "").replace("http://", "").split("/")[0]
                items.append(
                    ListItem(
                        value="organization",
                        label="Organization",
                        description=domain,
                    )
                )
        elif user_config.get("standalone"):
            items.append(
                ListItem(
                    value="organization",
                    label="Mode",
                    description="Standalone (no remote config)",
                )
            )

    except Exception:
        items.append(
            ListItem(
                value="config_error",
                label="Configuration",
                description="Error loading config",
            )
        )

    # Load container count
    try:
        containers = docker_core.list_scc_containers()
        running = sum(1 for c in containers if "Up" in c.status)
        total = len(containers)
        items.append(
            ListItem(
                value="containers",
                label="Containers",
                description=f"{running} running, {total} total",
            )
        )
    except Exception:
        items.append(
            ListItem(
                value="containers",
                label="Containers",
                description="Unable to query Docker",
            )
        )

    # Load session count
    try:
        recent_sessions = sessions.list_recent(limit=100)
        session_count = len(recent_sessions)
        items.append(
            ListItem(
                value="sessions",
                label="Sessions",
                description=f"{session_count} recorded",
            )
        )
    except Exception:
        items.append(
            ListItem(
                value="sessions",
                label="Sessions",
                description="Error loading sessions",
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

    items: list[ListItem[str]] = []

    try:
        containers = docker_core.list_scc_containers()
        running_count = 0

        for container in containers:
            is_running = "Up" in container.status
            if is_running:
                running_count += 1

            # Build description from available info
            desc_parts = []
            if container.profile:
                desc_parts.append(container.profile)
            if container.workspace:
                # Show just the workspace name
                workspace_name = container.workspace.split("/")[-1]
                desc_parts.append(workspace_name)
            if container.status:
                # Simplify status (e.g., "Up 2 hours" → "Up 2h")
                status_short = container.status.replace(" hours", "h").replace(" hour", "h")
                status_short = status_short.replace(" minutes", "m").replace(" minute", "m")
                status_short = status_short.replace(" days", "d").replace(" day", "d")
                desc_parts.append(status_short)

            items.append(
                ListItem(
                    value=container.id,
                    label=container.name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            items.append(
                ListItem(
                    value="no_containers",
                    label="No containers",
                    description="Run 'scc start' to create one",
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
            items.append(
                ListItem(
                    value=session,
                    label=name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            # Placeholder with sentinel dict (startable: True enables Enter action)
            items.append(
                ListItem(
                    value={"_placeholder": "no_sessions", "_startable": True},
                    label="No sessions",
                    description="Start a session with 'scc start'",
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


def _load_worktrees_tab_data() -> TabData:
    """Load Worktrees tab data showing git worktrees.

    Worktrees are loaded from the current working directory if it's a git repo.

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

        for wt in worktrees:
            if wt.is_current:
                current_count += 1

            desc_parts = []
            if wt.branch:
                desc_parts.append(wt.branch)
            if wt.has_changes:
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
                    description="Not in a git repository",
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
                    description="Not in a git repository",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_all_tab_data() -> dict[DashboardTab, TabData]:
    """Load data for all dashboard tabs.

    Returns:
        Dictionary mapping each tab to its data.
    """
    return {
        DashboardTab.STATUS: _load_status_tab_data(),
        DashboardTab.CONTAINERS: _load_containers_tab_data(),
        DashboardTab.SESSIONS: _load_sessions_tab_data(),
        DashboardTab.WORKTREES: _load_worktrees_tab_data(),
    }
