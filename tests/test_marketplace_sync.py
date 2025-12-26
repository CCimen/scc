"""
Tests for marketplace sync orchestration (TDD Red Phase).

This module tests the sync_marketplace_settings() function that orchestrates
the full pipeline for syncing marketplace settings to a project.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


class TestSyncError:
    """Tests for SyncError exception."""

    def test_create_with_message(self) -> None:
        """Should create error with message."""
        from scc_cli.marketplace.sync import SyncError

        error = SyncError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}

    def test_create_with_details(self) -> None:
        """Should create error with details dict."""
        from scc_cli.marketplace.sync import SyncError

        error = SyncError("Test error", details={"key": "value"})
        assert str(error) == "Test error"
        assert error.details == {"key": "value"}


class TestSyncResult:
    """Tests for SyncResult data structure."""

    def test_create_success_result(self) -> None:
        """Should create successful result with empty lists."""
        from scc_cli.marketplace.sync import SyncResult

        result = SyncResult(success=True)
        assert result.success is True
        assert result.plugins_enabled == []
        assert result.marketplaces_materialized == []
        assert result.warnings == []
        assert result.settings_path is None

    def test_create_with_plugins(self) -> None:
        """Should create result with enabled plugins."""
        from scc_cli.marketplace.sync import SyncResult

        result = SyncResult(
            success=True,
            plugins_enabled=["plugin-a@mp", "plugin-b@mp"],
        )
        assert result.plugins_enabled == ["plugin-a@mp", "plugin-b@mp"]

    def test_create_with_marketplaces(self) -> None:
        """Should create result with materialized marketplaces."""
        from scc_cli.marketplace.sync import SyncResult

        result = SyncResult(
            success=True,
            marketplaces_materialized=["internal", "security"],
        )
        assert result.marketplaces_materialized == ["internal", "security"]

    def test_create_with_warnings(self) -> None:
        """Should create result with warnings."""
        from scc_cli.marketplace.sync import SyncResult

        result = SyncResult(
            success=True,
            warnings=["Warning 1", "Warning 2"],
        )
        assert result.warnings == ["Warning 1", "Warning 2"]

    def test_create_with_settings_path(self, tmp_path: Path) -> None:
        """Should create result with settings path."""
        from scc_cli.marketplace.sync import SyncResult

        settings_path = tmp_path / ".claude" / "settings.local.json"
        result = SyncResult(
            success=True,
            settings_path=settings_path,
        )
        assert result.settings_path == settings_path


class TestSyncMarketplaceSettingsValidation:
    """Tests for sync_marketplace_settings input validation."""

    def test_invalid_org_config_raises_sync_error(self, tmp_path: Path) -> None:
        """Should raise SyncError for invalid org config."""
        from scc_cli.marketplace.sync import SyncError, sync_marketplace_settings

        with pytest.raises(SyncError, match="Invalid org config"):
            sync_marketplace_settings(
                project_dir=tmp_path,
                org_config_data={"invalid": "config"},
                team_id="test-team",
            )

    def test_none_team_id_raises_sync_error(self, tmp_path: Path) -> None:
        """Should raise SyncError when team_id is None."""
        from scc_cli.marketplace.sync import SyncError, sync_marketplace_settings

        valid_config = {
            "schema_version": 1,
            "name": "Test Org",
        }

        with pytest.raises(SyncError, match="team_id is required"):
            sync_marketplace_settings(
                project_dir=tmp_path,
                org_config_data=valid_config,
                team_id=None,
            )


class TestSyncMarketplaceSettingsOrchestration:
    """Tests for sync_marketplace_settings pipeline orchestration."""

    @pytest.fixture
    def minimal_org_config(self) -> dict:
        """Minimal valid org config."""
        return {
            "schema_version": 1,
            "name": "Test Org",
            "defaults": {
                "enabled_plugins": ["plugin-a@claude-plugins-official"],
            },
            "profiles": {
                "test-team": {
                    "name": "Test Team",
                },
            },
        }

    @pytest.fixture
    def org_config_with_marketplace(self) -> dict:
        """Org config with custom marketplace."""
        return {
            "schema_version": 1,
            "name": "Test Org",
            "marketplaces": {
                "internal": {
                    "source": "directory",
                    "path": "/path/to/plugins",
                },
            },
            "defaults": {
                "enabled_plugins": ["my-plugin@internal"],
            },
            "profiles": {
                "test-team": {
                    "name": "Test Team",
                },
            },
        }

    def test_computes_effective_plugins(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should compute effective plugins for team."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
        )

        assert result.success is True
        assert "plugin-a@claude-plugins-official" in result.plugins_enabled

    def test_skips_implicit_marketplaces(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should not materialize claude-plugins-official."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
        )

        # claude-plugins-official should not be materialized
        assert "claude-plugins-official" not in result.marketplaces_materialized

    def test_warns_on_missing_marketplace_source(self, tmp_path: Path) -> None:
        """Should warn when marketplace source is not found."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        config = {
            "schema_version": 1,
            "name": "Test Org",
            "defaults": {
                "enabled_plugins": ["plugin@missing-marketplace"],
            },
            "profiles": {
                "test-team": {"name": "Test"},
            },
        }

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=config,
            team_id="test-team",
        )

        assert any("missing-marketplace" in w for w in result.warnings)

    @patch("scc_cli.marketplace.sync.materialize_marketplace")
    def test_materializes_custom_marketplaces(
        self,
        mock_materialize: MagicMock,
        tmp_path: Path,
        org_config_with_marketplace: dict,
    ) -> None:
        """Should materialize custom marketplaces."""
        from scc_cli.marketplace.materialize import MaterializedMarketplace
        from scc_cli.marketplace.sync import sync_marketplace_settings

        mock_materialize.return_value = MaterializedMarketplace(
            name="internal",
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

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=org_config_with_marketplace,
            team_id="test-team",
        )

        assert "internal" in result.marketplaces_materialized

    @patch("scc_cli.marketplace.sync.materialize_marketplace")
    def test_warns_on_materialization_error(
        self,
        mock_materialize: MagicMock,
        tmp_path: Path,
        org_config_with_marketplace: dict,
    ) -> None:
        """Should warn when materialization fails."""
        from scc_cli.marketplace.materialize import MaterializationError
        from scc_cli.marketplace.sync import sync_marketplace_settings

        mock_materialize.side_effect = MaterializationError("Failed to clone", "internal")

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=org_config_with_marketplace,
            team_id="test-team",
        )

        assert any("Failed to materialize" in w for w in result.warnings)

    def test_writes_settings_file(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should write settings.local.json."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
        )

        settings_path = tmp_path / ".claude" / "settings.local.json"
        assert settings_path.exists()
        assert result.settings_path == settings_path

        data = json.loads(settings_path.read_text())
        assert "enabledPlugins" in data

    def test_creates_claude_directory(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should create .claude directory if missing."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        # Ensure .claude doesn't exist
        claude_dir = tmp_path / ".claude"
        assert not claude_dir.exists()

        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
        )

        assert claude_dir.exists()
        assert claude_dir.is_dir()

    def test_saves_managed_state(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should save managed state tracking file."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            org_config_url="https://example.com/config.json",
        )

        managed_path = tmp_path / ".claude" / ".scc-managed.json"
        assert managed_path.exists()

        data = json.loads(managed_path.read_text())
        assert "managed_plugins" in data
        assert data["org_config_url"] == "https://example.com/config.json"
        assert data["team_id"] == "test-team"

    def test_dry_run_does_not_write_files(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should not write files when dry_run=True."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=minimal_org_config,
            team_id="test-team",
            dry_run=True,
        )

        assert result.success is True
        assert result.settings_path is None

        settings_path = tmp_path / ".claude" / "settings.local.json"
        assert not settings_path.exists()

    def test_preserves_user_customizations(self, tmp_path: Path, minimal_org_config: dict) -> None:
        """Should preserve user-added plugins in settings."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

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
        )

        settings_path = claude_dir / "settings.local.json"
        data = json.loads(settings_path.read_text())

        # Both user plugin and org plugins should be present
        assert "user-plugin@custom-marketplace" in data["enabledPlugins"]
        assert "plugin-a@claude-plugins-official" in data["enabledPlugins"]


class TestBlockedPluginWarnings:
    """Tests for blocked plugin conflict detection."""

    def test_warns_on_blocked_plugin_conflict(self, tmp_path: Path) -> None:
        """Should warn when user has blocked plugin installed."""
        from scc_cli.marketplace.sync import sync_marketplace_settings

        # Create settings with a plugin that will be blocked
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"enabledPlugins": ["bad-plugin@marketplace"]})
        )

        config = {
            "schema_version": 1,
            "name": "Test Org",
            "security": {
                "blocked_plugins": ["bad-plugin@*"],
                "blocked_reason": "Security risk",
            },
            "profiles": {
                "test-team": {"name": "Test"},
            },
        }

        result = sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=config,
            team_id="test-team",
        )

        # Should have a warning about the blocked plugin
        assert any("bad-plugin" in w.lower() for w in result.warnings)


class TestLoadExistingPlugins:
    """Tests for _load_existing_plugins helper."""

    def test_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        """Should return empty list when settings file doesn't exist."""
        from scc_cli.marketplace.sync import _load_existing_plugins

        result = _load_existing_plugins(tmp_path)
        assert result == []

    def test_returns_empty_on_invalid_json(self, tmp_path: Path) -> None:
        """Should return empty list on corrupted JSON."""
        from scc_cli.marketplace.sync import _load_existing_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text("not valid json")

        result = _load_existing_plugins(tmp_path)
        assert result == []

    def test_returns_plugins_list(self, tmp_path: Path) -> None:
        """Should return plugins from settings file."""
        from scc_cli.marketplace.sync import _load_existing_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"enabledPlugins": ["p1@m1", "p2@m2"]})
        )

        result = _load_existing_plugins(tmp_path)
        assert result == ["p1@m1", "p2@m2"]

    def test_returns_empty_on_missing_key(self, tmp_path: Path) -> None:
        """Should return empty list when enabledPlugins key missing."""
        from scc_cli.marketplace.sync import _load_existing_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.local.json").write_text(json.dumps({}))

        result = _load_existing_plugins(tmp_path)
        assert result == []


class TestFindMarketplaceSource:
    """Tests for _find_marketplace_source helper."""

    def test_returns_none_when_no_marketplaces(self) -> None:
        """Should return None when org config has no marketplaces."""
        from scc_cli.marketplace.schema import OrganizationConfig
        from scc_cli.marketplace.sync import _find_marketplace_source

        config = OrganizationConfig.model_validate(
            {
                "schema_version": 1,
                "name": "Test Org",
            }
        )

        result = _find_marketplace_source(config, "any-marketplace")
        assert result is None

    def test_returns_none_when_not_found(self) -> None:
        """Should return None when marketplace not found."""
        from scc_cli.marketplace.schema import OrganizationConfig
        from scc_cli.marketplace.sync import _find_marketplace_source

        config = OrganizationConfig.model_validate(
            {
                "schema_version": 1,
                "name": "Test Org",
                "marketplaces": {
                    "existing": {"source": "directory", "path": "/path"},
                },
            }
        )

        result = _find_marketplace_source(config, "missing")
        assert result is None

    def test_returns_source_when_found(self) -> None:
        """Should return source when marketplace found."""
        from scc_cli.marketplace.schema import (
            MarketplaceSourceDirectory,
            OrganizationConfig,
        )
        from scc_cli.marketplace.sync import _find_marketplace_source

        config = OrganizationConfig.model_validate(
            {
                "schema_version": 1,
                "name": "Test Org",
                "marketplaces": {
                    "internal": {"source": "directory", "path": "/path/to/plugins"},
                },
            }
        )

        result = _find_marketplace_source(config, "internal")
        assert result is not None
        assert isinstance(result, MarketplaceSourceDirectory)
        assert result.path == "/path/to/plugins"


class TestForceRefreshBehavior:
    """Tests for force_refresh parameter handling."""

    @patch("scc_cli.marketplace.sync.materialize_marketplace")
    def test_passes_force_refresh_to_materialize(
        self, mock_materialize: MagicMock, tmp_path: Path
    ) -> None:
        """Should pass force_refresh to materialize_marketplace."""
        from scc_cli.marketplace.materialize import MaterializedMarketplace
        from scc_cli.marketplace.sync import sync_marketplace_settings

        mock_materialize.return_value = MaterializedMarketplace(
            name="internal",
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

        config = {
            "schema_version": 1,
            "name": "Test Org",
            "marketplaces": {
                "internal": {"source": "directory", "path": "/path"},
            },
            "defaults": {
                "enabled_plugins": ["plugin@internal"],
            },
            "profiles": {
                "test-team": {"name": "Test"},
            },
        }

        sync_marketplace_settings(
            project_dir=tmp_path,
            org_config_data=config,
            team_id="test-team",
            force_refresh=True,
        )

        mock_materialize.assert_called_once()
        call_kwargs = mock_materialize.call_args.kwargs
        assert call_kwargs.get("force_refresh") is True
