"""Marketplace sync adapter wrapper for Claude Code integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scc_cli.application.sync_marketplace import (
    SyncError,
    SyncMarketplaceDependencies,
    SyncResult,
)
from scc_cli.application.sync_marketplace import (
    sync_marketplace_settings as sync_marketplace_use_case,
)
from scc_cli.bootstrap import get_default_adapters
from scc_cli.marketplace.materialize import materialize_marketplace
from scc_cli.marketplace.resolve import resolve_effective_config


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

    This wrapper builds default dependencies and delegates to the application
    use case. See scc_cli.application.sync_marketplace for full behavior.
    """
    adapters = get_default_adapters()
    dependencies = SyncMarketplaceDependencies(
        filesystem=adapters.filesystem,
        remote_fetcher=adapters.remote_fetcher,
        clock=adapters.clock,
        resolve_effective_config=resolve_effective_config,
        materialize_marketplace=materialize_marketplace,
    )

    return sync_marketplace_use_case(
        project_dir=project_dir,
        org_config_data=org_config_data,
        team_id=team_id,
        org_config_url=org_config_url,
        force_refresh=force_refresh,
        dry_run=dry_run,
        write_to_workspace=write_to_workspace,
        container_path_prefix=container_path_prefix,
        dependencies=dependencies,
    )


__all__ = ["SyncError", "SyncResult", "sync_marketplace_settings"]
