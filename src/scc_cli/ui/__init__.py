"""SCC Interactive UI Package.

Public API for building interactive terminal experiences that share
consistent chrome, keybindings, and behavior patterns.

This package provides:
- Gate: Interactivity policy enforcement (JSON mode, CI detection, TTY checks)
- Pickers: High-level selection wrappers for domain objects
- ListScreen: Core navigation engine for building custom screens
- Dashboard: Tabbed navigation for the main SCC view

Usage Tiers:

Tier 1 - High-level (recommended for CLI commands):
    >>> from scc_cli.ui import InteractivityContext, pick_team, TeamSwitchRequested
    >>> ctx = InteractivityContext.create(json_mode=False)
    >>> if ctx.allows_prompt():
    ...     try:
    ...         team = pick_team(teams)
    ...     except TeamSwitchRequested:
    ...         # Handle team switch request
    ...         pass

Tier 2 - Advanced building blocks (supported, but may evolve):
    >>> from scc_cli.ui import ListScreen, ListItem, ListMode
    >>> items = [ListItem(value=x, label=x.name) for x in data]
    >>> screen = ListScreen(items, title="Custom Picker")
    >>> selected = screen.run()

Internal modules (not part of public API, may change without notice):
    - chrome: Layout rendering primitives (Chrome, ChromeConfig, FooterHint)
    - keys: Key mapping internals (Action, ActionType, KeyReader)
    Import directly from submodules if needed:
    >>> from scc_cli.ui.keys import ActionType  # Internal use only
    >>> from scc_cli.ui.chrome import Chrome    # Internal use only
"""

from __future__ import annotations

# Dashboard: Main tabbed navigation view
from .dashboard import run_dashboard

# =============================================================================
# Tier 1: High-level API (recommended for most uses)
# =============================================================================
# Gate: Interactivity policy enforcement
from .gate import (
    InteractivityContext,
    InteractivityMode,
    is_interactive_allowed,
    require_selection_or_prompt,
)

# Help: Mode-aware help overlay (user-facing)
from .help import (
    HelpMode,
    show_help_overlay,
)

# =============================================================================
# Tier 2: Advanced building blocks (supported, but may evolve)
# =============================================================================
# ListScreen: Core navigation engine
from .list_screen import (
    ListItem,
    ListMode,
    ListScreen,
    ListState,
)

# Pickers: Domain-specific selection workflows
from .picker import (
    TeamSwitchRequested,
    pick_container,
    pick_containers,
    pick_context,
    pick_session,
    pick_team,
    pick_worktree,
)

# Prompts: Simple Rich-based user input utilities
from .prompts import (
    prompt_custom_workspace,
    prompt_repo_url,
    render_error,
    select_session,
    select_team,
)

# =============================================================================
# Package metadata
# =============================================================================

__version__ = "0.1.0"

__all__ = [
    # Tier 1: High-level API
    "InteractivityContext",
    "InteractivityMode",
    "is_interactive_allowed",
    "require_selection_or_prompt",
    "TeamSwitchRequested",
    "pick_container",
    "pick_containers",
    "pick_context",
    "pick_session",
    "pick_team",
    "pick_worktree",
    "run_dashboard",
    "HelpMode",
    "show_help_overlay",
    # Tier 2: Advanced building blocks
    "ListItem",
    "ListMode",
    "ListScreen",
    "ListState",
    # Prompts: Simple Rich-based user input utilities
    "prompt_custom_workspace",
    "prompt_repo_url",
    "render_error",
    "select_session",
    "select_team",
]
