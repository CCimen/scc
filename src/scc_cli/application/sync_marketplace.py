"""Marketplace sync use case for agent integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from scc_cli.marketplace.constants import IMPLICIT_MARKETPLACES
from scc_cli.marketplace.managed import ManagedState, save_managed_state
from scc_cli.marketplace.materialize import MaterializationError
from scc_cli.marketplace.normalize import matches_any_pattern
from scc_cli.marketplace.render import check_conflicts, merge_settings, render_settings
from scc_cli.marketplace.schema import OrganizationConfig, normalize_org_config_data
from scc_cli.ports.clock import Clock
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.remote_fetcher import RemoteFetcher

if TYPE_CHECKING:
    from scc_cli.marketplace.materialize import MaterializedMarketplace
    from scc_cli.marketplace.resolve import MarketplaceResolution
    from scc_cli.marketplace.schema import MarketplaceSource


class MarketplaceConfigResolver(Protocol):
    """Protocol for resolving effective marketplace config."""

    def __call__(self, config: OrganizationConfig, team_id: str) -> MarketplaceResolution:
        """Return marketplace resolution for the specified team."""


class MarketplaceMaterializer(Protocol):
    """Protocol for materializing marketplace sources."""

    def __call__(
        self,
        name: str,
        source: MarketplaceSource,
        project_dir: Path,
        force_refresh: bool = False,
        fetcher: RemoteFetcher | None = None,
    ) -> MaterializedMarketplace:
        """Materialize a marketplace source."""


@dataclass(frozen=True)
class SyncMarketplaceDependencies:
    """Dependencies for marketplace sync use case."""

    filesystem: Filesystem
    remote_fetcher: RemoteFetcher
    clock: Clock
    resolve_effective_config: MarketplaceConfigResolver
    materialize_marketplace: MarketplaceMaterializer


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


def _collect_policy_warnings(
    *,
    project_dir: Path,
    org_config: OrganizationConfig,
    effective_config: MarketplaceResolution,
    filesystem: Filesystem,
) -> list[str]:
    warnings: list[str] = []
    existing_plugins: list[str] | None = None

    if effective_config.blocked_plugins:
        existing_plugins = _load_existing_plugins(project_dir, filesystem)
        warnings.extend(
            check_conflicts(
                existing_plugins=existing_plugins,
                blocked_plugins=[
                    {
                        "plugin_id": blocked.plugin_id,
                        "reason": blocked.reason,
                        "pattern": blocked.pattern,
                    }
                    for blocked in effective_config.blocked_plugins
                ],
            )
        )

    security = org_config.security
    if security.blocked_plugins:
        if existing_plugins is None:
            existing_plugins = _load_existing_plugins(project_dir, filesystem)
        for plugin in existing_plugins:
            matched = matches_any_pattern(plugin, security.blocked_plugins)
            if matched:
                warnings.append(
                    f"⚠️ Plugin '{plugin}' is blocked by organization policy "
                    f"(matched pattern: {matched})"
                )

    return warnings


def _required_marketplaces(effective_config: MarketplaceResolution) -> set[str]:
    marketplaces_used: set[str] = set()
    for plugin_ref in effective_config.enabled_plugins:
        if "@" in plugin_ref:
            marketplaces_used.add(plugin_ref.split("@")[1])

    marketplaces_used.update(effective_config.extra_marketplaces)
    return marketplaces_used


def _materialize_required_marketplaces(
    *,
    project_dir: Path,
    effective_config: MarketplaceResolution,
    force_refresh: bool,
    dependencies: SyncMarketplaceDependencies,
) -> tuple[dict[str, Any], list[str]]:
    materialized: dict[str, Any] = {}
    warnings: list[str] = []

    for marketplace_name in _required_marketplaces(effective_config):
        if marketplace_name in IMPLICIT_MARKETPLACES:
            continue

        source = effective_config.marketplaces.get(marketplace_name)
        if source is None:
            warnings.append(f"Marketplace '{marketplace_name}' not defined in effective config")
            continue

        try:
            result = dependencies.materialize_marketplace(
                name=marketplace_name,
                source=source,
                project_dir=project_dir,
                force_refresh=force_refresh,
                fetcher=dependencies.remote_fetcher,
            )
            materialized[marketplace_name] = {
                "relative_path": result.relative_path,
                "source_type": result.source_type,
                "canonical_name": result.canonical_name,
            }
        except MaterializationError as exc:
            warnings.append(f"Failed to materialize '{marketplace_name}': {exc}")

    return materialized, warnings


def _ensure_unique_canonical_marketplace_names(materialized: dict[str, Any]) -> None:
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
                "Each marketplace must have a unique canonical name.",
                details={"canonical_name": canonical, "conflicting_aliases": aliases},
            )


def _settings_payload(
    *,
    project_dir: Path,
    rendered: dict[str, Any],
    write_to_workspace: bool,
    filesystem: Filesystem,
) -> dict[str, Any]:
    if write_to_workspace:
        return merge_settings(project_dir, rendered, filesystem=filesystem)
    return rendered


def _build_managed_state(
    *,
    effective_config: MarketplaceResolution,
    materialized: dict[str, Any],
    clock: Clock,
    org_config_url: str | None,
    team_id: str,
) -> ManagedState:
    return ManagedState(
        managed_plugins=list(effective_config.enabled_plugins),
        managed_marketplaces=[item.get("relative_path", "") for item in materialized.values()],
        last_sync=clock.now(),
        org_config_url=org_config_url,
        team_id=team_id,
    )


def _write_sync_artifacts(
    *,
    project_dir: Path,
    merged_settings: dict[str, Any],
    managed_state: ManagedState,
    dry_run: bool,
    write_to_workspace: bool,
    filesystem: Filesystem,
) -> None:
    if dry_run:
        return

    claude_dir = project_dir / ".claude"
    filesystem.mkdir(claude_dir, parents=True, exist_ok=True)
    if write_to_workspace:
        settings_path = claude_dir / "settings.local.json"
        filesystem.write_text(settings_path, json.dumps(merged_settings, indent=2))
    save_managed_state(project_dir, managed_state, filesystem=filesystem)


def sync_marketplace_settings(
    project_dir: Path,
    org_config_data: dict[str, Any],
    team_id: str | None = None,
    org_config_url: str | None = None,
    force_refresh: bool = False,
    dry_run: bool = False,
    write_to_workspace: bool = True,
    container_path_prefix: str = "",
    *,
    dependencies: SyncMarketplaceDependencies,
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
        dependencies: Injected dependencies for filesystem, time, and IO ports

    Returns:
        SyncResult with success status and details. When write_to_workspace=False,
        rendered_settings contains the computed settings for container injection.

    Raises:
        SyncError: On validation or processing errors
        TeamNotFoundError: If team_id not found in config
    """
    # ── Step 1: Parse org config ─────────────────────────────────────────────
    # Org config is already validated by JSON Schema before caching.
    try:
        org_config = OrganizationConfig.model_validate(normalize_org_config_data(org_config_data))
    except Exception as exc:
        raise SyncError(f"Invalid org config: {exc}") from exc

    # ── Step 2: Resolve effective config (federation-aware) ───────────────────
    if team_id is None:
        raise SyncError("team_id is required for marketplace sync")

    # Use resolve_effective_config for federation support
    # This handles both inline and federated teams uniformly
    effective_config = dependencies.resolve_effective_config(org_config, team_id=team_id)

    warnings = _collect_policy_warnings(
        project_dir=project_dir,
        org_config=org_config,
        effective_config=effective_config,
        filesystem=dependencies.filesystem,
    )

    # ── Step 3: Materialize required marketplaces ───────────────────────────
    materialized, materialization_warnings = _materialize_required_marketplaces(
        project_dir=project_dir,
        effective_config=effective_config,
        force_refresh=force_refresh,
        dependencies=dependencies,
    )
    warnings.extend(materialization_warnings)

    # ── Step 3b: Check for canonical name collisions ────────────────────────
    # Multiple aliases resolving to the same canonical name is a configuration error
    _ensure_unique_canonical_marketplace_names(materialized)

    # ── Step 4: Render settings ─────────────────────────────────────────────
    effective_dict = {
        "enabled": effective_config.enabled_plugins,
        "extra_marketplaces": effective_config.extra_marketplaces,
    }
    # Pass path_prefix for container-only mode (absolute paths in container HOME)
    rendered = render_settings(effective_dict, materialized, path_prefix=container_path_prefix)

    # ── Step 5: Merge with existing settings (only if writing to workspace) ──
    # When write_to_workspace=False, we skip merging because settings go to
    # container HOME, not the workspace settings.local.json
    merged = _settings_payload(
        project_dir=project_dir,
        rendered=rendered,
        write_to_workspace=write_to_workspace,
        filesystem=dependencies.filesystem,
    )

    # ── Step 6: Prepare managed state ───────────────────────────────────────
    managed_state = _build_managed_state(
        effective_config=effective_config,
        materialized=materialized,
        clock=dependencies.clock,
        org_config_url=org_config_url,
        team_id=team_id,
    )

    # ── Step 7: Write files (unless dry_run or write_to_workspace=False) ─────
    settings_path = project_dir / ".claude" / "settings.local.json"
    _write_sync_artifacts(
        project_dir=project_dir,
        merged_settings=merged,
        managed_state=managed_state,
        dry_run=dry_run,
        write_to_workspace=write_to_workspace,
        filesystem=dependencies.filesystem,
    )

    return SyncResult(
        success=True,
        plugins_enabled=list(effective_config.enabled_plugins),
        marketplaces_materialized=list(materialized.keys()),
        warnings=warnings,
        settings_path=settings_path if (not dry_run and write_to_workspace) else None,
        # Return rendered settings for container injection when not writing to workspace
        rendered_settings=merged if not write_to_workspace else None,
    )


def _load_existing_plugins(project_dir: Path, filesystem: Filesystem) -> list[str]:
    """Load existing plugins from settings.local.json."""
    settings_path = project_dir / ".claude" / "settings.local.json"
    if not filesystem.exists(settings_path):
        return []

    try:
        data: dict[str, Any] = json.loads(filesystem.read_text(settings_path))
        plugins = data.get("enabledPlugins", [])
        if isinstance(plugins, list):
            return [str(plugin) for plugin in plugins]
        return []
    except (json.JSONDecodeError, OSError):
        return []
