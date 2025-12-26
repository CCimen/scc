"""
Settings rendering for Claude Code integration.

This module provides the bridge between SCC's marketplace/plugin management
and Claude Code's settings.local.json format. Key responsibilities:

1. render_settings() - Convert effective plugins to Claude settings format
2. merge_settings() - Non-destructive merge preserving user customizations
3. check_conflicts() - Detect conflicts between user and team settings

Per RQ-11: All paths must be relative for Docker sandbox compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scc_cli.marketplace.constants import MANAGED_STATE_FILE

# ─────────────────────────────────────────────────────────────────────────────
# Render Settings
# ─────────────────────────────────────────────────────────────────────────────


def render_settings(
    effective_plugins: dict[str, Any],
    materialized_marketplaces: dict[str, Any],
) -> dict[str, Any]:
    """Render effective plugins and marketplaces to Claude settings format.

    Creates a settings.local.json compatible structure with:
    - extraKnownMarketplaces: Array of marketplace configs with type and path
    - enabledPlugins: Array of plugin references (name@marketplace)

    Args:
        effective_plugins: Result from compute_effective_plugins()
            - enabled: Set of enabled plugin references
            - extra_marketplaces: List of marketplace IDs to enable
        materialized_marketplaces: Dict mapping name to MaterializedMarketplace-like dicts
            - relative_path: Path relative to project root
            - source_type: Type of source (github, git, directory, url)

    Returns:
        Dict with Claude Code settings structure:
            {
                "extraKnownMarketplaces": [...],
                "enabledPlugins": [...]
            }
    """
    settings: dict[str, Any] = {}

    # Build extraKnownMarketplaces array
    extra_marketplaces: list[dict[str, str]] = []
    for name, marketplace_data in materialized_marketplaces.items():
        # Get the relative path from the materialized data
        relative_path = marketplace_data.get("relative_path", "")

        # All local marketplaces use type: directory
        # This is because they've been cloned/downloaded to a local path
        extra_marketplaces.append(
            {
                "type": "directory",
                "path": relative_path,
            }
        )

    settings["extraKnownMarketplaces"] = extra_marketplaces

    # Build enabledPlugins array
    enabled = effective_plugins.get("enabled", set())
    # Convert set to sorted list for consistent output
    if isinstance(enabled, set):
        settings["enabledPlugins"] = sorted(list(enabled))
    else:
        settings["enabledPlugins"] = list(enabled)

    return settings


# ─────────────────────────────────────────────────────────────────────────────
# Merge Settings (Non-Destructive)
# ─────────────────────────────────────────────────────────────────────────────


def _load_settings(project_dir: Path) -> dict[str, Any]:
    """Load existing settings.local.json if it exists."""
    settings_path = project_dir / ".claude" / "settings.local.json"
    if settings_path.exists():
        try:
            result: dict[str, Any] = json.loads(settings_path.read_text())
            return result
        except json.JSONDecodeError:
            return {}
    return {}


def _load_managed_state(project_dir: Path) -> dict[str, Any]:
    """Load the SCC managed state tracking file."""
    managed_path = project_dir / ".claude" / MANAGED_STATE_FILE
    if managed_path.exists():
        try:
            result: dict[str, Any] = json.loads(managed_path.read_text())
            return result
        except json.JSONDecodeError:
            return {}
    return {}


def merge_settings(
    project_dir: Path,
    new_settings: dict[str, Any],
) -> dict[str, Any]:
    """Non-destructively merge new settings with existing user settings.

    This function implements RQ-7 from the research document:
    - Preserves user-added plugins and marketplaces
    - Removes old SCC-managed entries before adding new ones
    - Uses .scc-managed.json to track what SCC has added

    Algorithm:
        1. Load existing settings.local.json
        2. Load .scc-managed.json to know what was previously SCC-managed
        3. Remove previously managed plugins and marketplaces
        4. Add all new plugins and marketplaces from new_settings
        5. Return merged result (caller responsible for writing)

    Args:
        project_dir: Project root directory
        new_settings: New settings from render_settings()

    Returns:
        Merged settings dict ready to write to settings.local.json
    """
    existing = _load_settings(project_dir)
    managed = _load_managed_state(project_dir)

    # Get what was previously managed by SCC
    managed_plugins = set(managed.get("managed_plugins", []))
    managed_marketplaces = set(managed.get("managed_marketplaces", []))

    # Start with existing settings
    merged = dict(existing)

    # ─────────────────────────────────────────────────────────────────────────
    # Process enabledPlugins
    # ─────────────────────────────────────────────────────────────────────────

    # Get existing plugins, removing old SCC-managed ones
    existing_plugins = set(existing.get("enabledPlugins", []))
    # Remove old managed plugins
    remaining_user_plugins = existing_plugins - managed_plugins

    # Add new plugins from this render
    new_plugins = set(new_settings.get("enabledPlugins", []))
    merged_plugins = remaining_user_plugins | new_plugins

    # Deduplicate and sort
    merged["enabledPlugins"] = sorted(list(merged_plugins))

    # ─────────────────────────────────────────────────────────────────────────
    # Process extraKnownMarketplaces
    # ─────────────────────────────────────────────────────────────────────────

    existing_marketplaces = existing.get("extraKnownMarketplaces", [])

    # Filter out old SCC-managed marketplaces
    remaining_user_marketplaces = [
        m for m in existing_marketplaces if m.get("path", "") not in managed_marketplaces
    ]

    # Add new marketplaces from this render
    new_marketplaces = new_settings.get("extraKnownMarketplaces", [])

    # Merge: user marketplaces first, then new ones
    # Deduplicate by path
    seen_paths: set[str] = set()
    merged_marketplaces: list[dict[str, str]] = []

    for m in remaining_user_marketplaces:
        path = m.get("path", "")
        if path not in seen_paths:
            merged_marketplaces.append(m)
            seen_paths.add(path)

    for m in new_marketplaces:
        path = m.get("path", "")
        if path not in seen_paths:
            merged_marketplaces.append(m)
            seen_paths.add(path)

    merged["extraKnownMarketplaces"] = merged_marketplaces

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Conflict Detection
# ─────────────────────────────────────────────────────────────────────────────


def check_conflicts(
    existing_plugins: list[str],
    blocked_plugins: list[dict[str, Any]],
) -> list[str]:
    """Check for conflicts between user plugins and team security policy.

    Generates human-readable warnings when a user has installed plugins
    that would be blocked by the team's security policy.

    Args:
        existing_plugins: List of plugin references from user's current settings
        blocked_plugins: List of blocked plugin dicts from EffectivePlugins.blocked
            Each dict has: plugin_id, reason, pattern

    Returns:
        List of warning strings for display to user
    """
    warnings: list[str] = []

    # Build a set of blocked plugin IDs for fast lookup
    blocked_ids = {b.get("plugin_id", "") for b in blocked_plugins}

    for plugin in existing_plugins:
        if plugin in blocked_ids:
            # Find the block details
            for blocked in blocked_plugins:
                if blocked.get("plugin_id") == plugin:
                    reason = blocked.get("reason", "Blocked by policy")
                    pattern = blocked.get("pattern", "")
                    warnings.append(
                        f"⚠️ Plugin '{plugin}' is blocked by team policy: {reason} "
                        f"(matched pattern: {pattern})"
                    )
                    break

    return warnings
