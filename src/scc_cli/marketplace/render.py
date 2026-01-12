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
    path_prefix: str = "",
) -> dict[str, Any]:
    """Render effective plugins and marketplaces to Claude settings format.

    Creates a settings.local.json compatible structure with:
    - extraKnownMarketplaces: Object mapping marketplace names to source configs
    - enabledPlugins: Object mapping plugin references to boolean enable state

    CRITICAL: Uses canonical_name (from marketplace.json) NOT alias name (from org config).
    Claude Code looks up marketplaces by the 'name' field in marketplace.json,
    not by the key used in the SCC org config.

    Args:
        effective_plugins: Result from compute_effective_plugins()
            - enabled: Set of enabled plugin references (using alias names)
            - extra_marketplaces: List of marketplace IDs to enable
        materialized_marketplaces: Dict mapping alias name to MaterializedMarketplace-like dicts
            - relative_path: Path relative to project root
            - source_type: Type of source (github, git, directory, url)
            - canonical_name: The actual name from marketplace.json (what Claude Code sees)
        path_prefix: Optional prefix to prepend to marketplace paths. When settings
            will be written to container HOME (not workspace), this should be the
            container's workspace mount path (e.g., "/workspace") so paths resolve
            correctly. Example: relative_path ".claude/.scc-marketplaces/foo"
            becomes "/workspace/.claude/.scc-marketplaces/foo".

    Returns:
        Dict with Claude Code settings structure:
            {
                "extraKnownMarketplaces": {
                    "canonical-marketplace-name": {
                        "source": {"source": "directory", "path": "..."}
                    }
                },
                "enabledPlugins": {"plugin@canonical-marketplace-name": true, ...}
            }
    """
    settings: dict[str, Any] = {}

    # Build alias -> canonical name mapping
    alias_to_canonical: dict[str, str] = {}
    for alias_name, marketplace_data in materialized_marketplaces.items():
        canonical_name = marketplace_data.get("canonical_name", alias_name)
        alias_to_canonical[alias_name] = canonical_name

    # Build extraKnownMarketplaces as OBJECT with CANONICAL marketplace names as keys
    # Claude Code expects: {"canonical-name": {"source": {"source": "directory", "path": "..."}}}
    extra_marketplaces: dict[str, dict[str, Any]] = {}
    for alias_name, marketplace_data in materialized_marketplaces.items():
        # Get the relative path from the materialized data
        relative_path = marketplace_data.get("relative_path", "")
        # Use canonical name as the key - this is what Claude Code expects
        canonical_name = marketplace_data.get("canonical_name", alias_name)

        # Apply path prefix if provided (for container HOME settings)
        # When settings are in container HOME, we need absolute paths since
        # relative paths won't resolve from ~/ context
        if path_prefix:
            # Combine prefix with relative path, handling double slashes
            full_path = f"{path_prefix.rstrip('/')}/{relative_path.lstrip('/')}"
        else:
            full_path = relative_path

        # All local marketplaces use source.source: directory
        # This is because they've been cloned/downloaded to a local path
        extra_marketplaces[canonical_name] = {
            "source": {
                "source": "directory",
                "path": full_path,
            }
        }

    settings["extraKnownMarketplaces"] = extra_marketplaces

    # Build enabledPlugins as OBJECT with plugin references as keys
    # Claude Code expects: {"plugin@canonical-marketplace-name": true, ...}
    # We need to translate alias marketplace names to canonical names
    enabled = effective_plugins.get("enabled", set())
    enabled_plugins: dict[str, bool] = {}
    for plugin_ref in enabled:
        plugin_str = str(plugin_ref)
        # Translate marketplace alias to canonical name in plugin reference
        if "@" in plugin_str:
            plugin_name, alias_name = plugin_str.rsplit("@", 1)
            canonical_name = alias_to_canonical.get(alias_name, alias_name)
            translated_ref = f"{plugin_name}@{canonical_name}"
            enabled_plugins[translated_ref] = True
        else:
            # No marketplace specified, keep as-is
            enabled_plugins[plugin_str] = True

    settings["enabledPlugins"] = enabled_plugins

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
    # Process enabledPlugins (object format: {"plugin@market": true, ...})
    # ─────────────────────────────────────────────────────────────────────────

    existing_plugins_raw = existing.get("enabledPlugins", {})

    # Handle legacy array format by converting to object format
    if isinstance(existing_plugins_raw, list):
        # Legacy array format - convert to object with all true
        existing_plugins_obj: dict[str, bool] = {p: True for p in existing_plugins_raw}
    else:
        existing_plugins_obj = dict(existing_plugins_raw)

    # Remove old SCC-managed plugins
    remaining_user_plugins: dict[str, bool] = {}
    for plugin, enabled in existing_plugins_obj.items():
        if plugin not in managed_plugins:
            remaining_user_plugins[plugin] = enabled

    # Add new plugins from this render (always enabled=True for SCC-managed)
    new_plugins_obj = new_settings.get("enabledPlugins", {})
    if isinstance(new_plugins_obj, list):
        # Handle if someone passes array format
        new_plugins_obj = {p: True for p in new_plugins_obj}

    # Merge: user plugins take precedence for existing keys, then add new ones
    merged_plugins: dict[str, bool] = dict(remaining_user_plugins)
    for plugin, enabled in new_plugins_obj.items():
        if plugin not in merged_plugins:
            merged_plugins[plugin] = enabled

    merged["enabledPlugins"] = merged_plugins

    # ─────────────────────────────────────────────────────────────────────────
    # Process extraKnownMarketplaces (object format)
    # ─────────────────────────────────────────────────────────────────────────

    existing_marketplaces = existing.get("extraKnownMarketplaces", {})

    # Handle legacy array format by converting to object format
    if isinstance(existing_marketplaces, list):
        # Legacy array format - skip it (will be replaced)
        existing_marketplaces = {}

    # Filter out old SCC-managed marketplaces by checking path in source
    remaining_user_marketplaces: dict[str, Any] = {}
    for name, config in existing_marketplaces.items():
        source = config.get("source", {})
        path = source.get("path", "")
        if path not in managed_marketplaces:
            remaining_user_marketplaces[name] = config

    # Add new marketplaces from this render
    new_marketplaces = new_settings.get("extraKnownMarketplaces", {})

    # Merge: user marketplaces take precedence, then add new ones
    merged_marketplaces: dict[str, Any] = dict(remaining_user_marketplaces)
    for name, config in new_marketplaces.items():
        if name not in merged_marketplaces:
            merged_marketplaces[name] = config

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
