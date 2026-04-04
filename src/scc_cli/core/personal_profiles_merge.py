"""Merge, diff, and sandbox-import logic for personal profiles.

Split from personal_profiles.py to reduce module size and remove the
core→marketplace boundary violation. The ``merge_personal_settings``
function now accepts a ``managed_state_loader`` callable instead of
importing ``load_managed_state`` from the marketplace package.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from scc_cli import config as config_module
from scc_cli.core.enums import DiffItemSection, DiffItemStatus


@dataclass
class DiffItem:
    """A single diff item for the TUI overlay."""

    name: str
    status: DiffItemStatus  # ADDED (+), REMOVED (-), MODIFIED (~)
    section: DiffItemSection  # PLUGINS, MCP_SERVERS, MARKETPLACES


@dataclass
class StructuredDiff:
    """Structured diff for TUI display."""

    items: list[DiffItem]
    total_count: int

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


def _normalize_plugins(value: Any) -> dict[str, bool]:
    if isinstance(value, list):
        return {str(p): True for p in value}
    if isinstance(value, dict):
        return {str(k): bool(v) for k, v in value.items()}
    return {}


def _normalize_marketplaces(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def merge_personal_settings(
    workspace: Path,
    existing: dict[str, Any],
    personal: dict[str, Any],
    *,
    managed_state_loader: Callable[[Path], Any] | None = None,
) -> dict[str, Any]:
    """Merge personal settings without overwriting user customizations.

    - Personal overrides may replace team-managed entries
    - Existing user edits are preserved

    Args:
        workspace: Workspace directory path.
        existing: Current workspace settings.
        personal: Personal profile settings to merge.
        managed_state_loader: Callable that loads managed state for a workspace.
            When ``None``, falls back to ``marketplace.managed.load_managed_state``.
    """
    if managed_state_loader is None:
        raise ValueError(
            "managed_state_loader is required — pass marketplace.managed.load_managed_state "
            "from the application layer"
        )

    managed = managed_state_loader(workspace)
    managed_plugins = set(managed.managed_plugins)
    managed_marketplaces = set(managed.managed_marketplaces)

    merged = dict(existing)

    existing_plugins_raw = existing.get("enabledPlugins", {})
    if isinstance(existing_plugins_raw, list):
        existing_plugins: dict[str, bool] = {p: True for p in existing_plugins_raw}
    else:
        existing_plugins = dict(existing_plugins_raw)

    personal_plugins_raw = personal.get("enabledPlugins", {})
    if isinstance(personal_plugins_raw, list):
        personal_plugins = {p: True for p in personal_plugins_raw}
    else:
        personal_plugins = dict(personal_plugins_raw)

    for plugin, enabled in personal_plugins.items():
        if plugin in managed_plugins or plugin not in existing_plugins:
            existing_plugins[plugin] = enabled

    merged["enabledPlugins"] = existing_plugins

    existing_marketplaces = existing.get("extraKnownMarketplaces", {})
    if isinstance(existing_marketplaces, list):
        existing_marketplaces = {}

    personal_marketplaces = personal.get("extraKnownMarketplaces", {})
    if isinstance(personal_marketplaces, list):
        personal_marketplaces = {}

    for name, config in personal_marketplaces.items():
        if name not in existing_marketplaces:
            existing_marketplaces[name] = config
            continue

        source = existing_marketplaces.get(name, {}).get("source", {})
        path = source.get("path", "")
        if path in managed_marketplaces:
            existing_marketplaces[name] = config

    merged["extraKnownMarketplaces"] = existing_marketplaces

    for key, value in personal.items():
        if key in {"enabledPlugins", "extraKnownMarketplaces"}:
            continue
        if key not in merged:
            merged[key] = value
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key not in merged[key]:
                    merged[key][sub_key] = sub_value

    return merged


def merge_personal_mcp(existing: dict[str, Any], personal: dict[str, Any]) -> dict[str, Any]:
    if not personal:
        return existing
    if not existing:
        return personal
    merged = json.loads(json.dumps(personal))
    config_module.deep_merge(merged, existing)
    if isinstance(merged, dict):
        return cast(dict[str, Any], merged)
    return {}


def compute_sandbox_import_candidates(
    workspace_settings: dict[str, Any] | None,
    sandbox_settings: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any]]:
    """Return plugins/marketplaces present in sandbox settings but missing in workspace."""
    if not sandbox_settings:
        return [], {}

    workspace_settings = workspace_settings or {}

    workspace_plugins = _normalize_plugins(workspace_settings.get("enabledPlugins"))
    sandbox_plugins = _normalize_plugins(sandbox_settings.get("enabledPlugins"))
    missing_plugins = sorted([p for p in sandbox_plugins if p not in workspace_plugins])

    workspace_marketplaces = _normalize_marketplaces(
        workspace_settings.get("extraKnownMarketplaces")
    )
    sandbox_marketplaces = _normalize_marketplaces(sandbox_settings.get("extraKnownMarketplaces"))
    missing_marketplaces = {
        name: config
        for name, config in sandbox_marketplaces.items()
        if name not in workspace_marketplaces
    }

    return missing_plugins, missing_marketplaces


def merge_sandbox_imports(
    workspace_settings: dict[str, Any],
    missing_plugins: list[str],
    missing_marketplaces: dict[str, Any],
) -> dict[str, Any]:
    if not missing_plugins and not missing_marketplaces:
        return workspace_settings

    merged = dict(workspace_settings)

    plugins_value = merged.get("enabledPlugins")
    if isinstance(plugins_value, list):
        plugins_map = {str(p): True for p in plugins_value}
    elif isinstance(plugins_value, dict):
        plugins_map = dict(plugins_value)
    else:
        plugins_map = {}

    for plugin in missing_plugins:
        plugins_map[plugin] = True
    if plugins_map:
        merged["enabledPlugins"] = plugins_map

    marketplaces_value = merged.get("extraKnownMarketplaces")
    if isinstance(marketplaces_value, dict):
        marketplaces_map = dict(marketplaces_value)
    else:
        marketplaces_map = {}
    marketplaces_map.update(missing_marketplaces)
    if marketplaces_map:
        merged["extraKnownMarketplaces"] = marketplaces_map

    return merged


def build_diff_text(label: str, before: dict[str, Any], after: dict[str, Any]) -> str:
    import difflib

    before_text = json.dumps(before, indent=2, sort_keys=True).splitlines()
    after_text = json.dumps(after, indent=2, sort_keys=True).splitlines()
    diff_lines = difflib.unified_diff(
        before_text,
        after_text,
        fromfile=f"{label} (current)",
        tofile=f"{label} (personal)",
        lineterm="",
    )
    return "\n".join(diff_lines)


def compute_structured_diff(
    workspace_settings: dict[str, Any] | None,
    profile_settings: dict[str, Any] | None,
    workspace_mcp: dict[str, Any] | None,
    profile_mcp: dict[str, Any] | None,
) -> StructuredDiff:
    """Compute structured diff between workspace and profile for TUI display.

    Args:
        workspace_settings: Current workspace settings (settings.local.json)
        profile_settings: Saved profile settings
        workspace_mcp: Current workspace MCP config (.mcp.json)
        profile_mcp: Saved profile MCP config

    Returns:
        StructuredDiff with items showing additions, removals, modifications
    """
    items: list[DiffItem] = []

    workspace_settings = workspace_settings or {}
    profile_settings = profile_settings or {}
    workspace_mcp = workspace_mcp or {}
    profile_mcp = profile_mcp or {}

    # Compare plugins
    ws_plugins = _normalize_plugins(workspace_settings.get("enabledPlugins"))
    prof_plugins = _normalize_plugins(profile_settings.get("enabledPlugins"))

    # Plugins in profile but not workspace (would be added on apply)
    for plugin in sorted(prof_plugins.keys()):
        if plugin not in ws_plugins:
            items.append(
                DiffItem(name=plugin, status=DiffItemStatus.ADDED, section=DiffItemSection.PLUGINS)
            )

    # Plugins in workspace but not profile (would be removed on apply)
    for plugin in sorted(ws_plugins.keys()):
        if plugin not in prof_plugins:
            items.append(
                DiffItem(
                    name=plugin, status=DiffItemStatus.REMOVED, section=DiffItemSection.PLUGINS
                )
            )

    # Compare marketplaces
    ws_markets = _normalize_marketplaces(workspace_settings.get("extraKnownMarketplaces"))
    prof_markets = _normalize_marketplaces(profile_settings.get("extraKnownMarketplaces"))

    for name in sorted(prof_markets.keys()):
        if name not in ws_markets:
            items.append(
                DiffItem(
                    name=name, status=DiffItemStatus.ADDED, section=DiffItemSection.MARKETPLACES
                )
            )
        elif prof_markets[name] != ws_markets[name]:
            items.append(
                DiffItem(
                    name=name, status=DiffItemStatus.MODIFIED, section=DiffItemSection.MARKETPLACES
                )
            )

    for name in sorted(ws_markets.keys()):
        if name not in prof_markets:
            items.append(
                DiffItem(
                    name=name, status=DiffItemStatus.REMOVED, section=DiffItemSection.MARKETPLACES
                )
            )

    # Compare MCP servers
    ws_servers = workspace_mcp.get("mcpServers", {})
    prof_servers = profile_mcp.get("mcpServers", {})

    for name in sorted(prof_servers.keys()):
        if name not in ws_servers:
            items.append(
                DiffItem(
                    name=name, status=DiffItemStatus.ADDED, section=DiffItemSection.MCP_SERVERS
                )
            )
        elif prof_servers[name] != ws_servers[name]:
            items.append(
                DiffItem(
                    name=name, status=DiffItemStatus.MODIFIED, section=DiffItemSection.MCP_SERVERS
                )
            )

    for name in sorted(ws_servers.keys()):
        if name not in prof_servers:
            items.append(
                DiffItem(
                    name=name, status=DiffItemStatus.REMOVED, section=DiffItemSection.MCP_SERVERS
                )
            )

    return StructuredDiff(items=items, total_count=len(items))
