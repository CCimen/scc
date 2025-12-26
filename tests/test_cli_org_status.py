"""
Tests for scc org status command.

TDD: Tests written before implementation.
Tests cover: standalone mode, org-connected mode, cache status, version compatibility.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Typer CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def standalone_config() -> dict:
    """User config in standalone mode (no org)."""
    return {
        "config_version": "1.0.0",
        "organization_source": None,
        "selected_profile": None,
        "standalone": True,
    }


@pytest.fixture
def org_connected_config() -> dict:
    """User config connected to an organization."""
    return {
        "config_version": "1.0.0",
        "organization_source": {
            "url": "https://example.com/org-config.json",
            "auth": "env:GITHUB_TOKEN",
        },
        "selected_profile": "platform",
        "standalone": False,
    }


@pytest.fixture
def org_config_with_versions() -> dict:
    """Organization config with version info."""
    return {
        "schema_version": "1.0.0",
        "min_cli_version": "1.2.0",
        "organization": {
            "name": "acme-corp",
            "id": "acme-corp",
            "contact": "admin@acme.com",
        },
        "profiles": {
            "base": {"description": "Default profile"},
            "platform": {"description": "Platform team"},
        },
    }


@pytest.fixture
def cache_meta_valid() -> dict:
    """Valid cache metadata (not expired)."""
    now = datetime.now(timezone.utc)
    return {
        "org_config": {
            "source_url": "https://example.com/org-config.json",
            "fetched_at": (now - timedelta(hours=1)).isoformat(),
            "expires_at": (now + timedelta(hours=23)).isoformat(),
            "etag": '"abc123"',
            "fingerprint": "sha256:abc123",
        }
    }


@pytest.fixture
def cache_meta_expired() -> dict:
    """Expired cache metadata."""
    now = datetime.now(timezone.utc)
    return {
        "org_config": {
            "source_url": "https://example.com/org-config.json",
            "fetched_at": (now - timedelta(hours=48)).isoformat(),
            "expires_at": (now - timedelta(hours=24)).isoformat(),
            "etag": '"old456"',
            "fingerprint": "sha256:old456",
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Pure Function Tests - build_status_data
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildStatusData:
    """Test the pure function that builds status data."""

    def test_standalone_mode_returns_minimal_data(self) -> None:
        """Standalone mode should return minimal status info."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config={"standalone": True, "organization_source": None},
            org_config=None,
            cache_meta=None,
        )

        assert result["mode"] == "standalone"
        assert result["organization"] is None
        assert result["cache"] is None
        assert result["version_compatibility"] is None

    def test_org_connected_mode_includes_org_info(
        self, org_connected_config: dict, org_config_with_versions: dict
    ) -> None:
        """Org-connected mode should include organization details."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=None,
        )

        assert result["mode"] == "organization"
        assert result["organization"]["name"] == "acme-corp"
        assert result["organization"]["source_url"] == "https://example.com/org-config.json"

    def test_includes_cache_status_when_available(
        self,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_valid: dict,
    ) -> None:
        """Should include cache metadata when available."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=cache_meta_valid,
        )

        assert result["cache"] is not None
        assert result["cache"]["etag"] == '"abc123"'
        assert "fetched_at" in result["cache"]
        assert "expires_at" in result["cache"]

    def test_cache_valid_flag_when_not_expired(
        self,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_valid: dict,
    ) -> None:
        """Cache should be marked as valid when not expired."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=cache_meta_valid,
        )

        assert result["cache"]["valid"] is True

    def test_cache_invalid_flag_when_expired(
        self,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_expired: dict,
    ) -> None:
        """Cache should be marked as invalid when expired."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=cache_meta_expired,
        )

        assert result["cache"]["valid"] is False

    def test_includes_version_compatibility(
        self, org_connected_config: dict, org_config_with_versions: dict
    ) -> None:
        """Should include version compatibility information."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=None,
        )

        assert result["version_compatibility"] is not None
        assert "compatible" in result["version_compatibility"]
        assert "schema_version" in result["version_compatibility"]

    def test_includes_selected_profile(
        self, org_connected_config: dict, org_config_with_versions: dict
    ) -> None:
        """Should include the currently selected profile."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=None,
        )

        assert result["selected_profile"] == "platform"

    def test_no_profile_selected(self, org_config_with_versions: dict) -> None:
        """Should handle no profile selection gracefully."""
        from scc_cli.cli_org import build_status_data

        config = {
            "organization_source": {"url": "https://example.com/org.json"},
            "selected_profile": None,
            "standalone": False,
        }

        result = build_status_data(
            user_config=config,
            org_config=org_config_with_versions,
            cache_meta=None,
        )

        assert result["selected_profile"] is None

    def test_available_profiles_from_org_config(
        self, org_connected_config: dict, org_config_with_versions: dict
    ) -> None:
        """Should list available profiles from org config."""
        from scc_cli.cli_org import build_status_data

        result = build_status_data(
            user_config=org_connected_config,
            org_config=org_config_with_versions,
            cache_meta=None,
        )

        assert "available_profiles" in result
        assert "base" in result["available_profiles"]
        assert "platform" in result["available_profiles"]


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgStatusCommand:
    """Test the CLI command: scc org status."""

    def test_standalone_mode_shows_standalone_message(
        self, cli_runner: CliRunner, standalone_config: dict
    ) -> None:
        """In standalone mode, should show 'standalone' status."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=standalone_config):
            with patch("scc_cli.cli_org.load_from_cache", return_value=(None, None)):
                result = cli_runner.invoke(org_app, ["status"])

        assert result.exit_code == 0
        assert "standalone" in result.stdout.lower()

    def test_org_connected_shows_org_name(
        self,
        cli_runner: CliRunner,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_valid: dict,
    ) -> None:
        """When connected to org, should show organization name."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch(
                "scc_cli.cli_org.load_from_cache",
                return_value=(org_config_with_versions, cache_meta_valid),
            ):
                result = cli_runner.invoke(org_app, ["status"])

        assert result.exit_code == 0
        assert "acme-corp" in result.stdout

    def test_shows_selected_profile(
        self,
        cli_runner: CliRunner,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_valid: dict,
    ) -> None:
        """Should display the currently selected profile."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch(
                "scc_cli.cli_org.load_from_cache",
                return_value=(org_config_with_versions, cache_meta_valid),
            ):
                result = cli_runner.invoke(org_app, ["status"])

        assert result.exit_code == 0
        assert "platform" in result.stdout

    def test_shows_cache_status(
        self,
        cli_runner: CliRunner,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_valid: dict,
    ) -> None:
        """Should show cache freshness information."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch(
                "scc_cli.cli_org.load_from_cache",
                return_value=(org_config_with_versions, cache_meta_valid),
            ):
                result = cli_runner.invoke(org_app, ["status"])

        assert result.exit_code == 0
        # Should show some cache-related info (fresh, valid, etc.)
        output_lower = result.stdout.lower()
        assert "cache" in output_lower or "fresh" in output_lower or "valid" in output_lower


class TestOrgStatusJsonOutput:
    """Test JSON output format for scc org status."""

    def test_json_output_standalone(self, cli_runner: CliRunner, standalone_config: dict) -> None:
        """JSON output should include mode=standalone."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=standalone_config):
            with patch("scc_cli.cli_org.load_from_cache", return_value=(None, None)):
                result = cli_runner.invoke(org_app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["mode"] == "standalone"

    def test_json_output_org_connected(
        self,
        cli_runner: CliRunner,
        org_connected_config: dict,
        org_config_with_versions: dict,
        cache_meta_valid: dict,
    ) -> None:
        """JSON output should include full org status."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch(
                "scc_cli.cli_org.load_from_cache",
                return_value=(org_config_with_versions, cache_meta_valid),
            ):
                result = cli_runner.invoke(org_app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["mode"] == "organization"
        assert data["data"]["organization"]["name"] == "acme-corp"

    def test_json_envelope_structure(self, cli_runner: CliRunner, standalone_config: dict) -> None:
        """JSON output should follow envelope structure."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=standalone_config):
            with patch("scc_cli.cli_org.load_from_cache", return_value=(None, None)):
                result = cli_runner.invoke(org_app, ["status", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "kind" in data
        assert "status" in data  # ok is nested under status
        assert data["status"]["ok"] is True
        assert "data" in data

    def test_pretty_json_output(self, cli_runner: CliRunner, standalone_config: dict) -> None:
        """--pretty flag should format JSON with indentation."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=standalone_config):
            with patch("scc_cli.cli_org.load_from_cache", return_value=(None, None)):
                result = cli_runner.invoke(org_app, ["status", "--pretty"])

        assert result.exit_code == 0
        # Pretty JSON has newlines and indentation
        assert "\n" in result.stdout
        # Should still be valid JSON
        data = json.loads(result.stdout)
        assert data["data"]["mode"] == "standalone"


class TestOrgStatusVersionCompatibility:
    """Test version compatibility display in status."""

    def test_compatible_version_shows_success(
        self,
        cli_runner: CliRunner,
        org_connected_config: dict,
        cache_meta_valid: dict,
    ) -> None:
        """Compatible versions should show success indicator."""
        from scc_cli.cli_org import org_app

        org_config = {
            "schema_version": "1.0.0",
            "min_cli_version": "1.0.0",  # Lower than current
            "organization": {"name": "test-org"},
            "profiles": {},
        }

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch(
                "scc_cli.cli_org.load_from_cache",
                return_value=(org_config, cache_meta_valid),
            ):
                with patch("scc_cli.cli_org.CLI_VERSION", "1.2.4"):
                    result = cli_runner.invoke(org_app, ["status"])

        assert result.exit_code == 0
        # Should indicate compatibility (checkmark, "compatible", "ok", etc.)
        output_lower = result.stdout.lower()
        assert any(word in output_lower for word in ["compatible", "✓", "✔", "ok", "pass"])

    def test_incompatible_version_shows_warning(
        self,
        cli_runner: CliRunner,
        org_connected_config: dict,
        cache_meta_valid: dict,
    ) -> None:
        """Incompatible versions should show warning."""
        from scc_cli.cli_org import org_app

        org_config = {
            "schema_version": "1.0.0",
            "min_cli_version": "99.0.0",  # Higher than any current version
            "organization": {"name": "test-org"},
            "profiles": {},
        }

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch(
                "scc_cli.cli_org.load_from_cache",
                return_value=(org_config, cache_meta_valid),
            ):
                with patch("scc_cli.cli_org.CLI_VERSION", "1.2.4"):
                    result = cli_runner.invoke(org_app, ["status"])

        # Should still exit 0 (status command shows info, not validation)
        assert result.exit_code == 0
        # Should indicate incompatibility
        output_lower = result.stdout.lower()
        assert any(
            word in output_lower for word in ["incompatible", "warning", "upgrade", "⚠", "✗"]
        )


class TestOrgStatusNoCache:
    """Test status when no cache is available."""

    def test_no_cache_shows_not_fetched(
        self, cli_runner: CliRunner, org_connected_config: dict
    ) -> None:
        """When no cache exists, should indicate config not yet fetched."""
        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.load_user_config", return_value=org_connected_config):
            with patch("scc_cli.cli_org.load_from_cache", return_value=(None, None)):
                result = cli_runner.invoke(org_app, ["status"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        # Should indicate no cache or need to fetch
        assert any(word in output_lower for word in ["not fetched", "no cache", "run scc", "fetch"])
