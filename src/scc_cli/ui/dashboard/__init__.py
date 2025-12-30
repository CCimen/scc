"""Dashboard package for SCC CLI interactive interface.

This package provides the tabbed dashboard interface shown when running
`scc` with no arguments in an interactive terminal.

Public API:
    run_dashboard: Entry point for the dashboard UI
    Dashboard: Main dashboard class for direct instantiation
    DashboardTab: Enum of available tabs
    DashboardState: State management for the dashboard
    TabData: Data container for individual tabs
    TAB_ORDER: Canonical ordering of tabs

Module structure:
    models.py: Data models (DashboardTab, TabData, DashboardState)
    loaders.py: Tab data loading functions
    _dashboard.py: Dashboard class implementation
    orchestrator.py: Entry point and flow handlers

Example:
    >>> from scc_cli.ui.dashboard import run_dashboard
    >>> run_dashboard()  # Interactive dashboard
"""

from .loaders import (
    _load_all_tab_data,
    _load_containers_tab_data,
    _load_sessions_tab_data,
    _load_status_tab_data,
    _load_worktrees_tab_data,
)
from .models import TAB_ORDER, DashboardState, DashboardTab, TabData
from .orchestrator import _prepare_for_nested_ui, run_dashboard

# Lazy import for Dashboard to avoid circular imports
# (Dashboard depends on models, but models doesn't depend on Dashboard)


def __getattr__(name: str) -> object:
    """Lazy import for Dashboard class."""
    if name == "Dashboard":
        from ._dashboard import Dashboard

        return Dashboard
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


__all__ = [
    "Dashboard",
    "DashboardState",
    "DashboardTab",
    "TAB_ORDER",
    "TabData",
    "_load_all_tab_data",
    "_load_containers_tab_data",
    "_load_sessions_tab_data",
    "_load_status_tab_data",
    "_load_worktrees_tab_data",
    "_prepare_for_nested_ui",
    "run_dashboard",
]
