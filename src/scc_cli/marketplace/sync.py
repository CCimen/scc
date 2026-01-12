"""
Marketplace sync orchestration for Claude Code integration.

This module provides the high-level sync_marketplace_settings() function that
orchestrates the full pipeline:
1. Parse org config
2. Compute effective plugins for team
3. Materialize required marketplaces
4. Render settings to Claude format
5. Merge with existing user settings (non-destructive)
6. Save managed state tracking
7. Write settings.local.json

This is the main entry point for integrating marketplace functionality
into the start command.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scc_cli.marketplace.adapter import translate_org_config
from scc_cli.marketplace.managed import ManagedState, save_managed_state
from scc_cli.marketplace.materialize import MaterializationError, materialize_marketplace
from scc_cli.marketplace.normalize import matches_pattern
from scc_cli.marketplace.render import check_conflicts, merge_settings, render_settings
from scc_cli.marketplace.resolve import resolve_effective_config
from scc_cli.marketplace.schema import (
    MarketplaceSource,
    OrganizationConfig,
)


class SyncError(Exception):
    """Error during marketplace sync operation."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


class SyncResult:
    """Result of a marketplace sync operation."""

    def __init__(
        self,
        success: bool,
        plugins_enabled: list[str] | None = None,
        marketplaces_materialized: list[str] | None = None,
        warnings: list[str] | None = None,
        settings_path: Path | None = None,
        rendered_settings: dict[str, Any] | None = None,
    ) -> None:
        self.success = success
        self.plugins_enabled = plugins_enabled or []
        self.marketplaces_materialized = marketplaces_materialized or []
        self.warnings = warnings or []
        self.settings_path = settings_path
        # Computed settings dict for container injection (when write_to_workspace=False)
        self.rendered_settings = rendered_settings


def sync_marketplace_settings(
    project_dir: Path,
    org_config_data: dict[str, Any],
    team_id: str | None = None,
    org_config_url: str | None = None,
    force_refresh: bool = False,
    dry_run: bool = False,
    write_to_workspace: bool = True,
    container_path_prefix: str = "",
) -> SyncResult:
    """Sync marketplace settings for a project.

    Orchestrates the full pipeline:
    1. Parse and validate org config
    2. Compute effective plugins for team
    3. Materialize required marketplaces
    4. Render settings to Claude format
    5. Merge with existing user settings (non-destructive)
    6. Save managed state tracking
    7. Write settings.local.json (unless dry_run or write_to_workspace=False)

    Args:
        project_dir: Project root directory
        org_config_data: Parsed org config dictionary
        team_id: Team profile ID (uses defaults if None)
        org_config_url: URL where org config was fetched (for tracking)
        force_refresh: Force re-materialization of marketplaces
        dry_run: If True, compute but don't write files
        write_to_workspace: If False, skip writing settings.local.json
            and instead return rendered_settings for container injection.
            This prevents host Claude from seeing container-only plugins.
        container_path_prefix: Path prefix for marketplace paths in container.
            When set (e.g., "/workspace"), paths become absolute container paths
            like "/workspace/.claude/.scc-marketplaces/...". Required when
            write_to_workspace=False since settings will be in container HOME.

    Returns:
        SyncResult with success status and details. When write_to_workspace=False,
        rendered_settings contains the computed settings for container injection.

    Raises:
        SyncError: On validation or processing errors
        TeamNotFoundError: If team_id not found in config
    """
    warnings: list[str] = []

    # ── Step 1: Parse org config ─────────────────────────────────────────────
    # Translate external format (JSON Schema) to internal format (Pydantic)
    try:
        internal_data = translate_org_config(org_config_data)
        org_config = OrganizationConfig.model_validate(internal_data)
    except Exception as e:
        raise SyncError(f"Invalid org config: {e}") from e

    # ── Step 2: Resolve effective config (federation-aware) ────────────────────
    if team_id is None:
        raise SyncError("team_id is required for marketplace sync")

    # Use resolve_effective_config for federation support (T2a-24)
    # This handles both inline and federated teams uniformly
    effective_config = resolve_effective_config(org_config, team_id=team_id)

    # Convert to Phase 1 format for backward compatibility
    effective, effective_marketplaces = effective_config.to_phase1_format()

    # Check for blocked plugins that user has installed
    # First, check if org-enabled plugins were blocked
    if effective.blocked:
        existing = _load_existing_plugins(project_dir)
        conflict_warnings = check_conflicts(
            existing_plugins=existing,
            blocked_plugins=[
                {"plugin_id": b.plugin_id, "reason": b.reason, "pattern": b.pattern}
                for b in effective.blocked
            ],
        )
        warnings.extend(conflict_warnings)

    # Also check user's existing plugins against security.blocked_plugins patterns
    security = org_config.security
    if security and security.blocked_plugins:
        existing = _load_existing_plugins(project_dir)
        blocked_reason = security.blocked_reason or "Blocked by organization policy"
        for plugin in existing:
            for pattern in security.blocked_plugins:
                if matches_pattern(plugin, pattern):
                    warnings.append(
                        f"⚠️ Plugin '{plugin}' is blocked by team policy: {blocked_reason} "
                        f"(matched pattern: {pattern})"
                    )
                    break  # Only one warning per plugin

    # ── Step 3: Materialize required marketplaces ────────────────────────────
    materialized: dict[str, Any] = {}
    marketplaces_used = set()

    # Determine which marketplaces are needed
    for plugin_ref in effective.enabled:
        if "@" in plugin_ref:
            marketplace_name = plugin_ref.split("@")[1]
            marketplaces_used.add(marketplace_name)

    # Also include any extra marketplaces from the effective result
    for marketplace_name in effective.extra_marketplaces:
        marketplaces_used.add(marketplace_name)

    # Materialize each marketplace
    for marketplace_name in marketplaces_used:
        # Skip implicit marketplaces (claude-plugins-official)
        from scc_cli.marketplace.constants import IMPLICIT_MARKETPLACES

        if marketplace_name in IMPLICIT_MARKETPLACES:
            continue

        # Find source configuration from effective marketplaces (includes team sources for federated)
        # This is the key change for T2a-24: effective_marketplaces comes from resolve_effective_config
        source = effective_marketplaces.get(marketplace_name)
        if source is None:
            # Fallback to org config lookup for backwards compatibility
            source = _find_marketplace_source(org_config, marketplace_name)
        if source is None:
            warnings.append(f"Marketplace '{marketplace_name}' not found in org config")
            continue

        try:
            result = materialize_marketplace(
                name=marketplace_name,
                source=source,
                project_dir=project_dir,
                force_refresh=force_refresh,
            )
            materialized[marketplace_name] = {
                "relative_path": result.relative_path,
                "source_type": result.source_type,
                "canonical_name": result.canonical_name,  # Critical for alias → canonical translation
            }
        except MaterializationError as e:
            warnings.append(f"Failed to materialize '{marketplace_name}': {e}")

    # ── Step 3b: Check for canonical name collisions ────────────────────────
    # Multiple aliases resolving to the same canonical name is a configuration error
    canonical_to_aliases: dict[str, list[str]] = {}
    for alias_name, data in materialized.items():
        canonical = data.get("canonical_name", alias_name)
        if canonical not in canonical_to_aliases:
            canonical_to_aliases[canonical] = []
        canonical_to_aliases[canonical].append(alias_name)

    for canonical, aliases in canonical_to_aliases.items():
        if len(aliases) > 1:
            raise SyncError(
                f"Canonical name collision: marketplace.json name '{canonical}' "
                f"is used by multiple org config entries: {', '.join(aliases)}. "
                f"Each marketplace must have a unique canonical name.",
                details={"canonical_name": canonical, "conflicting_aliases": aliases},
            )

    # ── Step 4: Render settings ──────────────────────────────────────────────
    effective_dict = {
        "enabled": effective.enabled,
        "extra_marketplaces": effective.extra_marketplaces,
    }
    # Pass path_prefix for container-only mode (absolute paths in container HOME)
    rendered = render_settings(effective_dict, materialized, path_prefix=container_path_prefix)

    # ── Step 5: Merge with existing settings (only if writing to workspace) ───
    # When write_to_workspace=False, we skip merging because settings go to
    # container HOME, not the workspace settings.local.json
    if write_to_workspace:
        merged = merge_settings(project_dir, rendered)
    else:
        # For container-only mode, use rendered settings directly
        # (no merging with workspace settings since we're not writing there)
        merged = rendered

    # ── Step 6: Prepare managed state ────────────────────────────────────────
    managed_state = ManagedState(
        managed_plugins=list(effective.enabled),
        managed_marketplaces=[m.get("relative_path", "") for m in materialized.values()],
        last_sync=datetime.now(timezone.utc),
        org_config_url=org_config_url,
        team_id=team_id,
    )

    # ── Step 7: Write files (unless dry_run or write_to_workspace=False) ─────
    settings_path = project_dir / ".claude" / "settings.local.json"

    if not dry_run and write_to_workspace:
        # Ensure .claude directory exists
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Write settings to workspace (host-visible)
        settings_path.write_text(json.dumps(merged, indent=2))

        # Save managed state
        save_managed_state(project_dir, managed_state)
    elif not dry_run and not write_to_workspace:
        # Container-only mode: ensure .claude dir exists for marketplaces
        # (marketplaces are still materialized to workspace for bind-mount access)
        claude_dir = project_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Save managed state (for future cleanup)
        save_managed_state(project_dir, managed_state)

    return SyncResult(
        success=True,
        plugins_enabled=list(effective.enabled),
        marketplaces_materialized=list(materialized.keys()),
        warnings=warnings,
        settings_path=settings_path if (not dry_run and write_to_workspace) else None,
        # Return rendered settings for container injection when not writing to workspace
        rendered_settings=merged if not write_to_workspace else None,
    )


def _load_existing_plugins(project_dir: Path) -> list[str]:
    """Load existing plugins from settings.local.json."""
    settings_path = project_dir / ".claude" / "settings.local.json"
    if not settings_path.exists():
        return []

    try:
        data: dict[str, Any] = json.loads(settings_path.read_text())
        plugins = data.get("enabledPlugins", [])
        if isinstance(plugins, list):
            return [str(p) for p in plugins]
        return []
    except (json.JSONDecodeError, OSError):
        return []


def _find_marketplace_source(
    org_config: OrganizationConfig, marketplace_name: str
) -> MarketplaceSource | None:
    """Find marketplace source configuration by name."""
    if org_config.marketplaces is None:
        return None

    for name, source in org_config.marketplaces.items():
        if name == marketplace_name:
            return source

    return None
