"""Data loading wrappers for dashboard tabs."""

from __future__ import annotations

from datetime import datetime

from scc_cli import sessions
from scc_cli.application import dashboard as app_dashboard

from ..list_screen import ListItem
from ..time_format import format_relative_time_from_datetime
from .models import DashboardTab, TabData


def _format_last_used(iso_timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return iso_timestamp
    return format_relative_time_from_datetime(dt)


def _load_status_tab_data(refresh_at: datetime | None = None) -> TabData:
    """Load Status tab data showing quick actions and context."""
    session_service = sessions.get_session_service()
    tab_data = app_dashboard.load_status_tab_data(
        refresh_at=refresh_at,
        session_service=session_service,
        format_last_used=_format_last_used,
    )
    return _to_tab_data(tab_data)


def _load_containers_tab_data() -> TabData:
    """Load Containers tab data showing SCC-managed containers."""
    return _to_tab_data(app_dashboard.load_containers_tab_data())


def _load_sessions_tab_data() -> TabData:
    """Load Sessions tab data showing recent Claude sessions."""
    session_service = sessions.get_session_service()
    tab_data = app_dashboard.load_sessions_tab_data(
        session_service=session_service,
        format_last_used=_format_last_used,
    )
    return _to_tab_data(tab_data)


def _load_worktrees_tab_data(verbose: bool = False) -> TabData:
    """Load Worktrees tab data showing git worktrees."""
    return _to_tab_data(app_dashboard.load_worktrees_tab_data(verbose=verbose))


def _load_all_tab_data(verbose_worktrees: bool = False) -> dict[DashboardTab, TabData]:
    """Load data for all dashboard tabs."""
    session_service = sessions.get_session_service()
    all_tab_data = app_dashboard.load_all_tab_data(
        session_service=session_service,
        format_last_used=_format_last_used,
        verbose_worktrees=verbose_worktrees,
    )
    return {tab: _to_tab_data(tab_data) for tab, tab_data in all_tab_data.items()}


def _to_tab_data(tab_data: app_dashboard.DashboardTabData) -> TabData:
    items = [_to_list_item(item) for item in tab_data.items]
    return TabData(
        tab=tab_data.tab,
        title=tab_data.title,
        items=items,
        count_active=tab_data.count_active,
        count_total=tab_data.count_total,
    )


def _to_list_item(item: app_dashboard.DashboardItem) -> ListItem[app_dashboard.DashboardItem]:
    return ListItem(
        value=item,
        label=item.label,
        description=item.description,
    )
