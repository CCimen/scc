"""
Tests for marketplace sync orchestration (TDD Red Phase).

This module tests the sync_marketplace_settings() function that orchestrates
the full pipeline for syncing marketplace settings to a project.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.application.sync_marketplace import SyncMarketplaceDependencies
from scc_cli.marketplace.materialize import MaterializedMarketplace, materialize_marketplace
from scc_cli.marketplace.resolve import resolve_effective_config
from scc_cli.ports.remote_fetcher import RemoteFetcher


def make_org_config_data(**overrides: dict) -> dict:
    config = {
        "schema_version": "1.0.0",
        "organization": {"name": "Test Org", "id": "test-org"},
    }
    config.update(overrides)
    return config


def _materialize_with_fetcher(
    name: str,
    source: Any,
    project_dir: Path,
    force_refresh: bool = False,
    fetcher: RemoteFetcher | None = None,
) -> MaterializedMarketplace:
    return materialize_marketplace(
        name=name,
        source=source,
        project_dir=project_dir,
        force_refresh=force_refresh,
    )


@pytest.fixture
def sync_dependencies() -> SyncMarketplaceDependencies:
    remote_fetcher = MagicMock(spec=RemoteFetcher)
    remote_fetcher.get.side_effect = AssertionError("Unexpected remote fetch")
    return SyncMarketplaceDependencies(
        filesystem=LocalFilesystem(),
        remote_fetcher=remote_fetcher,
        clock=SystemClock(),
        resolve_effective_config=resolve_effective_config,
        materialize_marketplace=_materialize_with_fetcher,
    )


class TestSyncError:
    """Tests for SyncError exception."""

    def test_create_with_message(self) -> None:
        """Should create error with message."""
        from scc_cli.application.sync_marketplace import SyncError

        error = SyncError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}

    def test_create_with_details(self) -> None:
        """Should create error with details dict."""
        from scc_cli.application.sync_marketplace import SyncError

        error = SyncError("Test error", details={"key": "value"})
        assert str(error) == "Test error"
        assert error.details == {"key": "value"}


class TestSyncResult:
    """Tests for SyncResult data structure."""

    def test_create_success_result(self) -> None:
        """Should create successful result with empty lists."""
        from scc_cli.application.sync_marketplace import SyncResult

        result = SyncResult(success=True)
        assert result.success is True
        assert result.plugins_enabled == []
        assert result.marketplaces_materialized == []
        assert result.warnings == []
        assert result.settings_path is None

    def test_create_with_plugins(self) -> None:
        """Should create result with enabled plugins."""
        from scc_cli.application.sync_marketplace import SyncResult

        result = SyncResult(
            success=True,
            plugins_enabled=["plugin-a@mp", "plugin-b@mp"],
        )
        assert result.plugins_enabled == ["plugin-a@mp", "plugin-b@mp"]

    def test_create_with_marketplaces(self) -> None:
        """Should create result with materialized marketplaces."""
        from scc_cli.application.sync_marketplace import SyncResult

        result = SyncResult(
            success=True,
            marketplaces_materialized=["internal", "security"],
        )
        assert result.marketplaces_materialized == ["internal", "security"]

    def test_create_with_warnings(self) -> None:
        """Should create result with warnings."""
        from scc_cli.application.sync_marketplace import SyncResult

        result = SyncResult(
            success=True,
            warnings=["Warning 1", "Warning 2"],
        )
        assert result.warnings == ["Warning 1", "Warning 2"]

    def test_create_with_settings_path(self, tmp_path: Path) -> None:
        """Should create result with settings path."""
        from scc_cli.application.sync_marketplace import SyncResult

        settings_path = tmp_path / ".claude" / "settings.local.json"
        result = SyncResult(
            success=True,
            settings_path=settings_path,
        )
        assert result.settings_path == settings_path


class TestSyncMarketplaceSettingsValidation:
    """Tests for sync_marketplace_settings input validation."""

    def test_invalid_org_config_raises_sync_error(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should raise SyncError for invalid org config."""
        from scc_cli.application.sync_marketplace import SyncError, sync_marketplace_settings

        with pytest.raises(SyncError, match="Invalid org config"):
            sync_marketplace_settings(
                project_dir=tmp_path,
                org_config_data={"invalid": "config"},
                team_id="test-team",
                dependencies=sync_dependencies,
            )

    def test_none_team_id_raises_sync_error(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should raise SyncError when team_id is None."""
        from scc_cli.application.sync_marketplace import SyncError, sync_marketplace_settings

        valid_config = make_org_config_data(
            profiles={"test-team": {}},
        )

        with pytest.raises(SyncError, match="team_id is required"):
            sync_marketplace_settings(
                project_dir=tmp_path,
                org_config_data=valid_config,
                team_id=None,
                dependencies=sync_dependencies,
            )


class TestSyncMarketplaceSettingsOrchestration:
    """Tests for sync_marketplace_settings pipeline orchestration."""

    @pytest.fixture
    def minimal_org_config(self) -> dict:
        """Minimal valid org config."""
        return make_org_config_data(
            defaults={
                "enabled_plugins": ["plugin-a@claude-plugins-official"],
            },
            profiles={
                "test-team": {},
            },
        )

    @pytest.fixture
    def org_config_with_marketplace(self) -> dict:
        """Org config with custom marketplace."""
        return make_org_config_data(
            marketplaces={
                "internal": {
                    "source": "directory",
                    "path": "/path/to/plugins",
                },
            },
            defaults={
                "enabled_plugins": ["my-plugin@internal"],
            },
            profiles={
                "test-team": {},
            },
        )

    def test_computes_effective_plugins(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should compute effective plugins for team."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        assert result.success is True
        assert "plugin-a@claude-plugins-official" in result.plugins_enabled

    def test_skips_implicit_marketplaces(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should not materialize claude-plugins-official."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        # claude-plugins-official should not be materialized
        assert "claude-plugins-official" not in result.marketplaces_materialized

    def test_warns_on_missing_marketplace_source(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should warn when marketplace source is not found."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        config = make_org_config_data(
            defaults={
                "enabled_plugins": ["plugin@missing-marketplace"],
            },
            profiles={
                "test-team": {},
            },
        )

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        assert any("missing-marketplace" in w for w in result.warnings)

    def test_materializes_custom_marketplaces(
        self,
        tmp_path: Path,
        org_config_with_marketplace: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should materialize custom marketplaces."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        mock_materialize = MagicMock()
        mock_materialize.return_value = MaterializedMarketplace(
            name="internal",
            canonical_name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="directory",
            source_url="/path/to/plugins",
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha=None,
            etag=None,
            plugins_available=["my-plugin"],
        )

        dependencies = replace(sync_dependencies, materialize_marketplace=mock_materialize)
        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=org_config_with_marketplace,
            team_id="test-team",
            dependencies=dependencies,
        )

        assert "internal" in result.marketplaces_materialized

    def test_warns_on_materialization_error(
        self,
        tmp_path: Path,
        org_config_with_marketplace: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should warn when materialization fails."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings
        from scc_cli.marketplace.materialize import MaterializationError

        mock_materialize = MagicMock()
        mock_materialize.side_effect = MaterializationError("Failed to clone", "internal")

        dependencies = replace(sync_dependencies, materialize_marketplace=mock_materialize)
        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=org_config_with_marketplace,
            team_id="test-team",
            dependencies=dependencies,
        )

        assert any("Failed to materialize" in w for w in result.warnings)

    def test_writes_settings_file(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should write settings.local.json."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        settings_path = tmp_path / ".claude" / "settings.local.json"
        assert settings_path.exists()
        assert result.settings_path == settings_path

        data = json.loads(settings_path.read_text())
        assert "enabledPlugins" in data

    def test_creates_claude_directory(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should create .claude directory if missing."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        # Ensure .claude doesn't exist
        claude_dir = tmp_path / ".claude"
        assert not claude_dir.exists()

        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        assert claude_dir.exists()
        assert claude_dir.is_dir()

    def test_saves_managed_state(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should save managed state tracking file."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            org_config_url="https://example.com/config.json",
            dependencies=sync_dependencies,
        )

        managed_path = tmp_path / ".claude" / ".scc-managed.json"
        assert managed_path.exists()

        data = json.loads(managed_path.read_text())
        assert "managed_plugins" in data
        assert data["org_config_url"] == "https://example.com/config.json"
        assert data["team_id"] == "test-team"

    def test_dry_run_does_not_write_files(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should not write files when dry_run=True."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dry_run=True,
            dependencies=sync_dependencies,
        )

        assert result.success is True
        assert result.settings_path is None

        settings_path = tmp_path / ".claude" / "settings.local.json"
        assert not settings_path.exists()

    def test_preserves_user_customizations(
        self,
        tmp_path: Path,
        minimal_org_config: dict,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should preserve user-added plugins in settings."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        # Create existing settings with user plugin
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        existing_settings = {
            "enabledPlugins": ["user-plugin@custom-marketplace"],
        }
        (claude_dir / "settings.local.json").write_text(json.dumps(existing_settings))

        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        settings_path = claude_dir / "settings.local.json"
        data = json.loads(settings_path.read_text())

        # Both user plugin and org plugins should be present
        assert "user-plugin@custom-marketplace" in data["enabledPlugins"]
        assert "plugin-a@claude-plugins-official" in data["enabledPlugins"]


class TestBlockedPluginWarnings:
    """Tests for blocked plugin conflict detection."""

    def test_warns_on_blocked_plugin_conflict(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should warn when user has blocked plugin installed."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        # Create settings with a plugin that will be blocked
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"enabledPlugins": ["bad-plugin@marketplace"]})
        )

        config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "security": {
                "blocked_plugins": ["bad-plugin@*"],
            },
            "delegation": {"teams": {"allow_additional_plugins": ["*"]}},
            "profiles": {
                "test-team": {},
            },
        }

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=config,
            team_id="test-team",
            dependencies=sync_dependencies,
        )

        # Should have a warning about the blocked plugin
        assert any("bad-plugin" in w.lower() for w in result.warnings)


class TestLoadExistingPlugins:
    """Tests for _load_existing_plugins helper."""

    def test_returns_empty_when_no_file(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should return empty list when settings file doesn't exist."""
        from scc_cli.application.sync_marketplace import _load_existing_plugins

        result = _load_existing_plugins(tmp_path, sync_dependencies.filesystem)
        assert result == []

    def test_returns_empty_on_invalid_json(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should return empty list on corrupted JSON."""
        from scc_cli.application.sync_marketplace import _load_existing_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text("not valid json")

        result = _load_existing_plugins(tmp_path, sync_dependencies.filesystem)
        assert result == []

    def test_returns_plugins_list(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should return plugins from settings file."""
        from scc_cli.application.sync_marketplace import _load_existing_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"enabledPlugins": ["p1@m1", "p2@m2"]})
        )

        result = _load_existing_plugins(tmp_path, sync_dependencies.filesystem)
        assert result == ["p1@m1", "p2@m2"]

    def test_returns_empty_on_missing_key(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should return empty list when enabledPlugins key missing."""
        from scc_cli.application.sync_marketplace import _load_existing_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(json.dumps({}))

        result = _load_existing_plugins(tmp_path, sync_dependencies.filesystem)
        assert result == []


class TestForceRefreshBehavior:
    """Tests for force_refresh parameter handling."""

    def test_passes_force_refresh_to_materialize(
        self,
        tmp_path: Path,
        sync_dependencies: SyncMarketplaceDependencies,
    ) -> None:
        """Should pass force_refresh to materialize_marketplace."""
        from scc_cli.application.sync_marketplace import sync_marketplace_settings

        mock_materialize = MagicMock()
        mock_materialize.return_value = MaterializedMarketplace(
            name="internal",
            canonical_name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="directory",
            source_url="/path",
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha=None,
            etag=None,
            plugins_available=["plugin"],
        )

        config = make_org_config_data(
            marketplaces={
                "internal": {"source": "directory", "path": "/path"},
            },
            defaults={
                "enabled_plugins": ["plugin@internal"],
            },
            profiles={
                "test-team": {},
            },
        )

        dependencies = replace(sync_dependencies, materialize_marketplace=mock_materialize)
        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=config,
            team_id="test-team",
            force_refresh=True,
            dependencies=dependencies,
        )

        mock_materialize.assert_called_once()
        call_kwargs = mock_materialize.call_args.kwargs
        assert call_kwargs.get("force_refresh") is True
