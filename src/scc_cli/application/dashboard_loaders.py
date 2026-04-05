"""Dashboard tab data loaders.

Each loader fetches data from services/infrastructure and returns
application-layer view models. Container data is mapped to
ContainerSummary to avoid coupling to docker.core.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from scc_cli.application.sessions import SessionService
from scc_cli.ports.session_models import SessionFilter
from scc_cli.services.git.worktree import WorktreeInfo

from .dashboard_models import (
    ContainerItem,
    ContainerSummary,
    DashboardItem,
    DashboardTab,
    DashboardTabData,
    PlaceholderItem,
    PlaceholderKind,
    SessionItem,
    StatusAction,
    StatusItem,
    WorktreeItem,
)


def load_status_tab_data(
    refresh_at: datetime | None = None,
    *,
    session_service: SessionService,
    format_last_used: Callable[[str], str] | None = None,
) -> DashboardTabData:
    """Load Status tab data showing quick actions and context."""
    import os
    from pathlib import Path

    from scc_cli import config
    from scc_cli.core.personal_profiles import get_profile_status
    from scc_cli.docker import core as docker_core

    _ = refresh_at

    items: list[DashboardItem] = []

    items.append(
        StatusItem(
            label="New session",
            description="",
            action=StatusAction.START_SESSION,
        )
    )

    try:
        recent_result = session_service.list_recent(SessionFilter(limit=1, include_all=True))
        recent_session = recent_result.sessions[0] if recent_result.sessions else None
        if recent_session:
            workspace = recent_session.workspace
            workspace_name = workspace.split("/")[-1] if workspace else "unknown"
            last_used = recent_session.last_used
            last_used_display = ""
            if last_used:
                last_used_display = format_last_used(last_used) if format_last_used else last_used
            desc_parts = [workspace_name]
            if recent_session.branch:
                desc_parts.append(str(recent_session.branch))
            if last_used_display:
                desc_parts.append(last_used_display)
            items.append(
                StatusItem(
                    label="Resume last",
                    description=" · ".join(desc_parts),
                    action=StatusAction.RESUME_SESSION,
                    session=recent_session,
                )
            )
    except Exception:
        pass

    try:
        user_config = config.load_user_config()
        team = user_config.get("selected_profile")
        org_source = user_config.get("organization_source")

        if team:
            items.append(
                StatusItem(
                    label=f"Team: {team}",
                    description="",
                    action=StatusAction.SWITCH_TEAM,
                )
            )
        else:
            items.append(
                StatusItem(
                    label="Team: none",
                    description="",
                    action=StatusAction.SWITCH_TEAM,
                )
            )

        try:
            workspace_path = Path(os.getcwd())
            profile_status = get_profile_status(workspace_path)

            if profile_status.exists:
                if profile_status.import_count > 0:
                    profile_label = f"Profile: saved · ↓ {profile_status.import_count} importable"
                elif profile_status.has_drift:
                    profile_label = "Profile: saved · ◇ drifted"
                else:
                    profile_label = "Profile: saved · ✓ synced"
                items.append(
                    StatusItem(
                        label=profile_label,
                        description="",
                        action=StatusAction.OPEN_PROFILE,
                    )
                )
            else:
                items.append(
                    StatusItem(
                        label="Profile: none",
                        description="",
                        action=StatusAction.OPEN_PROFILE,
                    )
                )
        except Exception:
            pass

        if org_source and isinstance(org_source, dict):
            org_url = org_source.get("url", "")
            if org_url:
                org_name = None
                try:
                    org_config = config.load_cached_org_config()
                    if org_config:
                        org_name = org_config.get("organization", {}).get("name")
                except Exception:
                    org_name = None

                if not org_name:
                    org_name = org_url.replace("https://", "").replace("http://", "").split("/")[0]

                items.append(
                    StatusItem(
                        label=f"Organization: {org_name}",
                        description="",
                    )
                )
        elif user_config.get("standalone"):
            items.append(
                StatusItem(
                    label="Mode: standalone",
                    description="",
                )
            )

    except Exception:
        items.append(
            StatusItem(
                label="Config: error",
                description="",
            )
        )

    try:
        containers = docker_core.list_scc_containers()
        running = sum(1 for container in containers if "Up" in container.status)
        total = len(containers)
        items.append(
            StatusItem(
                label=f"Containers: {running}/{total} running",
                description="",
                action=StatusAction.OPEN_TAB,
                action_tab=DashboardTab.CONTAINERS,
            )
        )
    except Exception:
        pass

    items.append(
        StatusItem(
            label="Settings",
            description="",
            action=StatusAction.OPEN_SETTINGS,
        )
    )

    return DashboardTabData(
        tab=DashboardTab.STATUS,
        title="Status",
        items=items,
        count_active=len(items),
        count_total=len(items),
    )


def _container_info_to_summary(info: object) -> ContainerSummary:
    """Map a docker.core.ContainerInfo to the application-layer ContainerSummary."""
    return ContainerSummary(
        id=info.id,  # type: ignore[attr-defined]
        name=info.name,  # type: ignore[attr-defined]
        status=info.status,  # type: ignore[attr-defined]
        profile=getattr(info, "profile", None),
        workspace=getattr(info, "workspace", None),
        branch=getattr(info, "branch", None),
        created=getattr(info, "created", None),
    )


def load_containers_tab_data() -> DashboardTabData:
    """Load Containers tab data showing SCC-managed containers."""
    from scc_cli.docker import core as docker_core

    items: list[DashboardItem] = []

    try:
        containers = docker_core.list_scc_containers()
        running_count = 0

        for container in containers:
            is_running = "Up" in container.status if container.status else False
            if is_running:
                running_count += 1
            label = container.name
            summary = _container_info_to_summary(container)
            description = _format_container_description(summary)
            items.append(ContainerItem(label=label, description=description, container=summary))

        if not items:
            items.append(
                PlaceholderItem(
                    label="No containers",
                    description="Press 'n' to start or run `scc start <path>`",
                    kind=PlaceholderKind.NO_CONTAINERS,
                    startable=True,
                )
            )

        return DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=items,
            count_active=running_count,
            count_total=len(containers),
        )

    except Exception:
        return DashboardTabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[
                PlaceholderItem(
                    label="Error",
                    description="Unable to query Docker",
                    kind=PlaceholderKind.ERROR,
                )
            ],
            count_active=0,
            count_total=0,
        )


def load_sessions_tab_data(
    *,
    session_service: SessionService,
    format_last_used: Callable[[str], str] | None = None,
) -> DashboardTabData:
    """Load Sessions tab data showing recent sessions."""
    items: list[DashboardItem] = []

    try:
        recent_result = session_service.list_recent(SessionFilter(limit=20, include_all=True))
        recent = recent_result.sessions

        for session in recent:
            desc_parts = []

            if session.team:
                desc_parts.append(str(session.team))
            if session.branch:
                desc_parts.append(str(session.branch))
            if session.last_used:
                desc_parts.append(
                    format_last_used(session.last_used) if format_last_used else session.last_used
                )

            items.append(
                SessionItem(
                    label=session.name or "Unnamed",
                    description=" · ".join(desc_parts),
                    session=session,
                )
            )

        if not items:
            items.append(
                PlaceholderItem(
                    label="No sessions",
                    description="Press Enter to start",
                    kind=PlaceholderKind.NO_SESSIONS,
                    startable=True,
                )
            )

        return DashboardTabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=items,
            count_active=len(recent),
            count_total=len(recent),
        )

    except Exception:
        return DashboardTabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=[
                PlaceholderItem(
                    label="Error",
                    description="Unable to load sessions",
                    kind=PlaceholderKind.ERROR,
                )
            ],
            count_active=0,
            count_total=0,
        )


def load_worktrees_tab_data(verbose: bool = False) -> DashboardTabData:
    """Load Worktrees tab data showing git worktrees."""
    import os
    from pathlib import Path

    from scc_cli.services.git.worktree import get_worktree_status, get_worktrees_data

    items: list[DashboardItem] = []

    try:
        cwd = Path(os.getcwd())
        worktrees = get_worktrees_data(cwd)
        current_path = os.path.realpath(cwd)

        for worktree in worktrees:
            if os.path.realpath(worktree.path) == current_path:
                worktree.is_current = True

            if verbose:
                staged, modified, untracked, timed_out = get_worktree_status(worktree.path)
                worktree.staged_count = staged
                worktree.modified_count = modified
                worktree.untracked_count = untracked
                worktree.status_timed_out = timed_out
                worktree.has_changes = (staged + modified + untracked) > 0

        current_count = sum(1 for worktree in worktrees if worktree.is_current)

        for worktree in worktrees:
            description = _format_worktree_description(worktree, verbose=verbose)
            items.append(
                WorktreeItem(
                    label=Path(worktree.path).name,
                    description=description,
                    path=worktree.path,
                )
            )

        if not items:
            items.append(
                PlaceholderItem(
                    label="No worktrees",
                    description="Press w for recent · i to init · c to clone",
                    kind=PlaceholderKind.NO_WORKTREES,
                )
            )

        return DashboardTabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=items,
            count_active=current_count,
            count_total=len(worktrees),
        )

    except Exception:
        return DashboardTabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=[
                PlaceholderItem(
                    label="Not available",
                    description="Press w for recent · i to init · c to clone",
                    kind=PlaceholderKind.NO_GIT,
                )
            ],
            count_active=0,
            count_total=0,
        )


def load_all_tab_data(
    *,
    session_service: SessionService,
    format_last_used: Callable[[str], str] | None = None,
    verbose_worktrees: bool = False,
) -> Mapping[DashboardTab, DashboardTabData]:
    """Load data for all dashboard tabs."""
    return {
        DashboardTab.STATUS: load_status_tab_data(
            session_service=session_service,
            format_last_used=format_last_used,
        ),
        DashboardTab.CONTAINERS: load_containers_tab_data(),
        DashboardTab.SESSIONS: load_sessions_tab_data(
            session_service=session_service,
            format_last_used=format_last_used,
        ),
        DashboardTab.WORKTREES: load_worktrees_tab_data(verbose=verbose_worktrees),
    }


def _format_container_description(container: ContainerSummary) -> str:
    desc_parts: list[str] = []

    if container.workspace:
        workspace_name = container.workspace.split("/")[-1]
        desc_parts.append(workspace_name)

    if container.status:
        time_str = _extract_container_time(container.status)
        if container.status.startswith("Up"):
            desc_parts.append(f"● {time_str}")
        else:
            desc_parts.append("○ stopped")

    return " · ".join(desc_parts)


def _extract_container_time(status: str) -> str:
    import re

    match = re.search(r"Up\s+(.+)", status)
    if match:
        return match.group(1)
    return status


def _format_worktree_description(worktree: WorktreeInfo, *, verbose: bool) -> str:
    from scc_cli import git

    desc_parts: list[str] = []
    if worktree.branch:
        desc_parts.append(git.get_display_branch(worktree.branch))

    if verbose:
        if worktree.status_timed_out:
            desc_parts.append("status timeout")
        else:
            status_parts = []
            if worktree.staged_count > 0:
                status_parts.append(f"+{worktree.staged_count}")
            if worktree.modified_count > 0:
                status_parts.append(f"!{worktree.modified_count}")
            if worktree.untracked_count > 0:
                status_parts.append(f"?{worktree.untracked_count}")
            if status_parts:
                desc_parts.append(" ".join(status_parts))
            elif not worktree.has_changes:
                desc_parts.append("clean")
    elif worktree.has_changes:
        desc_parts.append("modified")

    if worktree.is_current:
        desc_parts.append("(current)")

    return "  ".join(desc_parts)
