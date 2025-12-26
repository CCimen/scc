"""
Tests for settings rendering and non-destructive merge.

TDD: Tests written before implementation.
Tests cover: render_settings(), merge_settings(), path resolution for Docker sandbox.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a project directory with .claude/ subdirectory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path


@pytest.fixture
def marketplace_cache_dir(project_dir: Path) -> Path:
    """Create the .scc-marketplaces cache directory with a marketplace."""
    cache_dir = project_dir / ".claude" / ".scc-marketplaces"
    cache_dir.mkdir()

    # Create a materialized marketplace
    internal_dir = cache_dir / "internal"
    internal_dir.mkdir()
    plugin_dir = internal_dir / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "marketplace.json").write_text(json.dumps({"name": "internal", "plugins": []}))

    return cache_dir


@pytest.fixture
def existing_settings(project_dir: Path) -> Path:
    """Create existing settings.local.json with user-added plugins."""
    settings_path = project_dir / ".claude" / "settings.local.json"
    settings_data = {
        "extraKnownMarketplaces": [
            {
                "type": "directory",
                "path": "./user-custom-marketplace",
            }
        ],
        "enabledPlugins": [
            "user-custom-plugin@user-marketplace",
            "some-other-plugin@external",
        ],
        "enabledMcpServers": ["context7", "playwright"],
    }
    settings_path.write_text(json.dumps(settings_data, indent=2))
    return settings_path


@pytest.fixture
def managed_state(project_dir: Path) -> Path:
    """Create existing .scc-managed.json tracking SCC-managed entries."""
    managed_path = project_dir / ".claude" / ".scc-managed.json"
    managed_data = {
        "version": 1,
        "team": "backend",
        "last_updated": "2025-01-01T00:00:00+00:00",
        "managed_marketplaces": [".claude/.scc-marketplaces/internal"],
        "managed_plugins": ["code-review@internal", "linter@internal"],
    }
    managed_path.write_text(json.dumps(managed_data, indent=2))
    return managed_path


@pytest.fixture
def effective_plugins() -> dict:
    """Effective plugins result from compute_effective_plugins()."""
    return {
        "enabled": {"code-review@internal", "linter@internal", "api-tool@internal"},
        "blocked": [],
        "not_allowed": [],
        "disabled": [],
        "extra_marketplaces": ["internal"],
    }


@pytest.fixture
def materialized_marketplaces() -> dict:
    """Materialized marketplace entries."""
    return {
        "internal": {
            "name": "internal",
            "relative_path": ".claude/.scc-marketplaces/internal",
            "source_type": "github",
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# render_settings() Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderSettings:
    """Test render_settings() function."""

    def test_builds_extra_known_marketplaces(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """Should build extraKnownMarketplaces array from materialized marketplaces."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        assert "extraKnownMarketplaces" in settings
        marketplaces = settings["extraKnownMarketplaces"]
        assert len(marketplaces) == 1
        assert marketplaces[0]["type"] == "directory"

    def test_builds_enabled_plugins_list(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """Should build enabledPlugins array from effective plugins."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        assert "enabledPlugins" in settings
        plugins = settings["enabledPlugins"]
        assert "code-review@internal" in plugins
        assert "linter@internal" in plugins
        assert "api-tool@internal" in plugins

    def test_uses_relative_paths_only(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """All paths in settings should be relative (RQ-11 Docker constraint)."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        for marketplace in settings.get("extraKnownMarketplaces", []):
            path = marketplace.get("path", "")
            assert not path.startswith("/"), f"Absolute path found: {path}"
            assert path.startswith("."), f"Path should be relative: {path}"

    def test_includes_directory_type_for_local_marketplaces(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """Local materialized marketplaces should use type: directory."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        marketplaces = settings.get("extraKnownMarketplaces", [])
        assert all(m["type"] == "directory" for m in marketplaces)

    def test_handles_empty_effective_plugins(self, materialized_marketplaces: dict) -> None:
        """Should handle case with no enabled plugins."""
        from scc_cli.marketplace.render import render_settings

        empty_effective = {
            "enabled": set(),
            "blocked": [],
            "not_allowed": [],
            "disabled": [],
            "extra_marketplaces": [],
        }

        settings = render_settings(
            effective_plugins=empty_effective,
            materialized_marketplaces=materialized_marketplaces,
        )

        assert settings["enabledPlugins"] == []

    def test_handles_empty_marketplaces(self, effective_plugins: dict) -> None:
        """Should handle case with no extra marketplaces."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces={},
        )

        assert settings.get("extraKnownMarketplaces", []) == []


# ═══════════════════════════════════════════════════════════════════════════════
# merge_settings() Tests (Non-Destructive Merge)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMergeSettings:
    """Test merge_settings() for non-destructive merge."""

    def test_preserves_user_added_plugins(
        self,
        project_dir: Path,
        existing_settings: Path,
        managed_state: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Should preserve plugins not managed by SCC."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        new_settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # User-added plugin should be preserved
        assert "user-custom-plugin@user-marketplace" in merged["enabledPlugins"]
        assert "some-other-plugin@external" in merged["enabledPlugins"]

    def test_preserves_user_added_marketplaces(
        self,
        project_dir: Path,
        existing_settings: Path,
        managed_state: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Should preserve marketplaces not managed by SCC."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        new_settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # User-added marketplace should be preserved
        marketplace_paths = [m["path"] for m in merged["extraKnownMarketplaces"]]
        assert "./user-custom-marketplace" in marketplace_paths

    def test_removes_old_scc_managed_entries(
        self,
        project_dir: Path,
        existing_settings: Path,
        managed_state: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Should remove old SCC-managed entries before adding new ones."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        # Simulate team change - different plugins now
        new_effective = {
            "enabled": {"new-tool@internal"},  # Different from managed_state
            "blocked": [],
            "not_allowed": [],
            "disabled": [],
            "extra_marketplaces": ["internal"],
        }

        new_settings = render_settings(
            effective_plugins=new_effective,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # Old managed plugins should be removed
        assert "code-review@internal" not in merged["enabledPlugins"]
        assert "linter@internal" not in merged["enabledPlugins"]
        # New managed plugin should be present
        assert "new-tool@internal" in merged["enabledPlugins"]

    def test_preserves_non_plugin_settings(
        self,
        project_dir: Path,
        existing_settings: Path,
        managed_state: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Should preserve other settings like enabledMcpServers."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        new_settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # MCP servers should be untouched
        assert "context7" in merged.get("enabledMcpServers", [])
        assert "playwright" in merged.get("enabledMcpServers", [])

    def test_creates_settings_when_none_exist(
        self,
        project_dir: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Should create settings.local.json when it doesn't exist."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        new_settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # Should have all new entries
        assert "code-review@internal" in merged["enabledPlugins"]
        assert len(merged["extraKnownMarketplaces"]) > 0

    def test_handles_empty_managed_state(
        self,
        project_dir: Path,
        existing_settings: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Should work when .scc-managed.json doesn't exist."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        # No managed_state fixture - file doesn't exist

        new_settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # All existing user plugins should be preserved (nothing was managed)
        assert "user-custom-plugin@user-marketplace" in merged["enabledPlugins"]
        # New plugins should be added
        assert "code-review@internal" in merged["enabledPlugins"]


# ═══════════════════════════════════════════════════════════════════════════════
# Path Resolution Tests (Docker Sandbox - RQ-11)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathResolution:
    """Test path resolution for Docker sandbox compatibility."""

    def test_relative_path_from_project_root(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """Paths should be relative to project root (where scc start is run)."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        for marketplace in settings.get("extraKnownMarketplaces", []):
            path = marketplace.get("path", "")
            # Path should start with ./ or .claude/
            assert path.startswith("."), f"Path should be relative: {path}"

    def test_no_host_specific_paths(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """Paths should never contain host-specific elements."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        for marketplace in settings.get("extraKnownMarketplaces", []):
            path = marketplace.get("path", "")
            # No home directory paths
            assert "~" not in path
            assert "/Users/" not in path
            assert "/home/" not in path
            # No /tmp paths
            assert "/tmp" not in path

    def test_consistent_path_format(
        self, effective_plugins: dict, materialized_marketplaces: dict
    ) -> None:
        """All marketplace paths should use consistent format."""
        from scc_cli.marketplace.render import render_settings

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        for marketplace in settings.get("extraKnownMarketplaces", []):
            path = marketplace.get("path", "")
            # Should use forward slashes
            assert "\\" not in path
            # Should start with .claude/.scc-marketplaces/
            if path.startswith(".claude"):
                assert ".scc-marketplaces" in path

    def test_paths_work_inside_docker_container(self, effective_plugins: dict) -> None:
        """Paths should resolve correctly from /workspace in Docker."""
        from scc_cli.marketplace.render import render_settings

        # Simulate marketplace materialized at project-local path
        docker_compatible_marketplaces = {
            "internal": {
                "name": "internal",
                "relative_path": ".claude/.scc-marketplaces/internal",
                "source_type": "github",
            }
        }

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=docker_compatible_marketplaces,
        )

        marketplace = settings["extraKnownMarketplaces"][0]
        # Path should be relative so it works from /workspace/<project>/ in Docker
        assert marketplace["path"] == ".claude/.scc-marketplaces/internal"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderEdgeCases:
    """Test edge cases in settings rendering."""

    def test_handles_duplicate_plugins(self, materialized_marketplaces: dict) -> None:
        """Should deduplicate plugins if present in both user and team sets."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        effective = {
            "enabled": {"shared-plugin@internal"},
            "blocked": [],
            "not_allowed": [],
            "disabled": [],
            "extra_marketplaces": ["internal"],
        }

        new_settings = render_settings(
            effective_plugins=effective,
            materialized_marketplaces=materialized_marketplaces,
        )

        # Simulating existing settings with same plugin
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            claude_dir = project_dir / ".claude"
            claude_dir.mkdir()

            existing = {
                "enabledPlugins": ["shared-plugin@internal", "other-plugin"],
                "extraKnownMarketplaces": [],
            }
            (claude_dir / "settings.local.json").write_text(json.dumps(existing))

            merged = merge_settings(
                project_dir=project_dir,
                new_settings=new_settings,
            )

            # Should not have duplicate
            plugin_count = merged["enabledPlugins"].count("shared-plugin@internal")
            assert plugin_count == 1

    def test_handles_special_characters_in_marketplace_names(self, effective_plugins: dict) -> None:
        """Should handle marketplace names with special characters."""
        from scc_cli.marketplace.render import render_settings

        special_marketplaces = {
            "sundsvall-ai-2024": {
                "name": "sundsvall-ai-2024",
                "relative_path": ".claude/.scc-marketplaces/sundsvall-ai-2024",
                "source_type": "github",
            }
        }

        settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=special_marketplaces,
        )

        assert len(settings["extraKnownMarketplaces"]) == 1
        assert "sundsvall-ai-2024" in settings["extraKnownMarketplaces"][0]["path"]

    def test_preserves_json_structure_integrity(
        self,
        project_dir: Path,
        existing_settings: Path,
        effective_plugins: dict,
        materialized_marketplaces: dict,
    ) -> None:
        """Merged settings should be valid JSON structure."""
        from scc_cli.marketplace.render import merge_settings, render_settings

        new_settings = render_settings(
            effective_plugins=effective_plugins,
            materialized_marketplaces=materialized_marketplaces,
        )

        merged = merge_settings(
            project_dir=project_dir,
            new_settings=new_settings,
        )

        # Should be serializable to JSON
        json_str = json.dumps(merged)
        parsed = json.loads(json_str)
        assert parsed == merged


# ═══════════════════════════════════════════════════════════════════════════════
# Conflict Warning Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConflictWarnings:
    """Test warnings for plugin conflicts."""

    def test_warns_on_user_plugin_blocked_by_policy(
        self,
        project_dir: Path,
        existing_settings: Path,
    ) -> None:
        """Should generate warning when user plugin conflicts with team policy."""
        from scc_cli.marketplace.render import check_conflicts

        # User has a plugin that would be blocked
        blocked_plugins = [
            {
                "plugin_id": "user-custom-plugin@user-marketplace",
                "reason": "Blocked by security policy",
                "pattern": "*@user-marketplace",
            }
        ]

        existing = json.loads(existing_settings.read_text())
        warnings = check_conflicts(
            existing_plugins=existing.get("enabledPlugins", []),
            blocked_plugins=blocked_plugins,
        )

        assert len(warnings) > 0
        assert "user-custom-plugin" in warnings[0]

    def test_no_warning_when_no_conflicts(
        self,
        project_dir: Path,
        existing_settings: Path,
    ) -> None:
        """Should not generate warnings when there are no conflicts."""
        from scc_cli.marketplace.render import check_conflicts

        # No blocked plugins
        blocked_plugins: list = []

        existing = json.loads(existing_settings.read_text())
        warnings = check_conflicts(
            existing_plugins=existing.get("enabledPlugins", []),
            blocked_plugins=blocked_plugins,
        )

        assert len(warnings) == 0
