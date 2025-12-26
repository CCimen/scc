"""
Tests for scc org import command.

TDD: Tests written before implementation.
Tests cover: URL import, shorthand resolution, --preview mode, validation.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

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
def valid_org_config() -> dict:
    """Valid organization config that passes validation."""
    return {
        "schema_version": "1.0.0",
        "min_cli_version": "1.0.0",
        "organization": {
            "name": "acme-corp",
            "id": "acme-corp",
            "contact": "admin@acme.com",
        },
        "defaults": {
            "allowed_plugins": ["code-review", "linter"],
            "network_policy": "unrestricted",
        },
        "profiles": {
            "base": {"description": "Default profile"},
            "platform": {"description": "Platform team"},
        },
    }


@pytest.fixture
def invalid_org_config() -> dict:
    """Invalid organization config missing required fields."""
    return {
        "schema_version": "1.0.0",
        # Missing organization field
        "profiles": {},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Pure Function Tests - build_import_preview_data
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildImportPreviewData:
    """Test the pure function that builds import preview data."""

    def test_builds_preview_with_org_info(self, valid_org_config: dict) -> None:
        """Preview should include organization information."""
        from scc_cli.cli_org import build_import_preview_data

        result = build_import_preview_data(
            source="https://example.com/org.json",
            resolved_url="https://example.com/org.json",
            config=valid_org_config,
            validation_errors=[],
        )

        assert result["source"] == "https://example.com/org.json"
        assert result["organization"]["name"] == "acme-corp"
        assert result["valid"] is True

    def test_preview_with_shorthand_shows_resolved_url(self, valid_org_config: dict) -> None:
        """When using shorthand, should show both original and resolved URL."""
        from scc_cli.cli_org import build_import_preview_data

        result = build_import_preview_data(
            source="github:acme/configs",
            resolved_url="https://raw.githubusercontent.com/acme/configs/main/org-config.json",
            config=valid_org_config,
            validation_errors=[],
        )

        assert result["source"] == "github:acme/configs"
        assert "raw.githubusercontent.com" in result["resolved_url"]

    def test_preview_includes_validation_status(self, valid_org_config: dict) -> None:
        """Preview should indicate validation status."""
        from scc_cli.cli_org import build_import_preview_data

        result = build_import_preview_data(
            source="https://example.com/org.json",
            resolved_url="https://example.com/org.json",
            config=valid_org_config,
            validation_errors=[],
        )

        assert result["valid"] is True
        assert result["validation_errors"] == []

    def test_preview_with_validation_errors(self, invalid_org_config: dict) -> None:
        """Preview should show validation errors when config is invalid."""
        from scc_cli.cli_org import build_import_preview_data

        result = build_import_preview_data(
            source="https://example.com/org.json",
            resolved_url="https://example.com/org.json",
            config=invalid_org_config,
            validation_errors=["Missing required field: organization"],
        )

        assert result["valid"] is False
        assert "Missing required field" in result["validation_errors"][0]

    def test_preview_includes_available_profiles(self, valid_org_config: dict) -> None:
        """Preview should list available profiles."""
        from scc_cli.cli_org import build_import_preview_data

        result = build_import_preview_data(
            source="https://example.com/org.json",
            resolved_url="https://example.com/org.json",
            config=valid_org_config,
            validation_errors=[],
        )

        assert "base" in result["available_profiles"]
        assert "platform" in result["available_profiles"]

    def test_preview_includes_version_info(self, valid_org_config: dict) -> None:
        """Preview should include version compatibility info."""
        from scc_cli.cli_org import build_import_preview_data

        result = build_import_preview_data(
            source="https://example.com/org.json",
            resolved_url="https://example.com/org.json",
            config=valid_org_config,
            validation_errors=[],
        )

        assert result["schema_version"] == "1.0.0"
        assert result["min_cli_version"] == "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Command Tests - Preview Mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgImportPreview:
    """Test the CLI command: scc org import --preview."""

    def test_preview_shows_org_info_without_saving(
        self, cli_runner: CliRunner, valid_org_config: dict
    ) -> None:
        """--preview should show info but not save config."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_org_config
        mock_response.headers = {"ETag": '"abc123"'}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
            )
            with patch("requests.get", return_value=mock_response):
                with patch("scc_cli.cli_org.save_user_config") as mock_save:
                    result = cli_runner.invoke(
                        org_app, ["import", "https://example.com/org.json", "--preview"]
                    )

        assert result.exit_code == 0
        assert "acme-corp" in result.stdout
        # Should NOT save in preview mode
        mock_save.assert_not_called()

    def test_preview_json_output(self, cli_runner: CliRunner, valid_org_config: dict) -> None:
        """--preview --json should return structured data."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_org_config
        mock_response.headers = {"ETag": '"abc123"'}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
            )
            with patch("requests.get", return_value=mock_response):
                result = cli_runner.invoke(
                    org_app,
                    ["import", "https://example.com/org.json", "--preview", "--json"],
                )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["valid"] is True
        assert data["data"]["organization"]["name"] == "acme-corp"

    def test_preview_shows_validation_errors(
        self, cli_runner: CliRunner, invalid_org_config: dict
    ) -> None:
        """--preview should show validation errors for invalid config."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_org_config
        mock_response.headers = {}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
            )
            with patch("requests.get", return_value=mock_response):
                result = cli_runner.invoke(
                    org_app, ["import", "https://example.com/org.json", "--preview"]
                )

        # Preview should succeed even with invalid config (it's showing what would happen)
        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "invalid" in output_lower or "error" in output_lower


class TestOrgImportShorthand:
    """Test shorthand resolution for scc org import."""

    def test_github_shorthand_resolves(self, cli_runner: CliRunner, valid_org_config: dict) -> None:
        """github:org/repo should resolve to raw.githubusercontent.com URL."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_org_config
        mock_response.headers = {}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://raw.githubusercontent.com/acme/configs/main/org-config.json",
                provider="github",
            )
            with patch("requests.get", return_value=mock_response):
                result = cli_runner.invoke(org_app, ["import", "github:acme/configs", "--preview"])

        assert result.exit_code == 0
        # Should resolve the shorthand
        mock_resolve.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Command Tests - Import Mode (without --preview)
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgImportSave:
    """Test the CLI command: scc org import (without --preview)."""

    def test_import_saves_config(self, cli_runner: CliRunner, valid_org_config: dict) -> None:
        """Import without --preview should save to user config."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_org_config
        mock_response.headers = {"ETag": '"abc123"'}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
                auth_spec=None,
            )
            with patch("requests.get", return_value=mock_response):
                with patch("scc_cli.cli_org.load_user_config", return_value={}):
                    with patch("scc_cli.cli_org.save_user_config") as mock_save:
                        with patch("scc_cli.cli_org.save_to_cache"):
                            result = cli_runner.invoke(
                                org_app, ["import", "https://example.com/org.json"]
                            )

        assert result.exit_code == 0
        # Should save config
        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][0]
        assert saved_config["organization_source"]["url"] == "https://example.com/org.json"

    def test_import_rejects_invalid_config(
        self, cli_runner: CliRunner, invalid_org_config: dict
    ) -> None:
        """Import should fail for invalid configs (validation gate)."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_org_config
        mock_response.headers = {}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
            )
            with patch("requests.get", return_value=mock_response):
                with patch("scc_cli.cli_org.save_user_config") as mock_save:
                    result = cli_runner.invoke(org_app, ["import", "https://example.com/org.json"])

        # Should fail with non-zero exit code
        assert result.exit_code != 0
        # Should NOT save invalid config
        mock_save.assert_not_called()

    def test_import_caches_config(self, cli_runner: CliRunner, valid_org_config: dict) -> None:
        """Import should cache the fetched config."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_org_config
        mock_response.headers = {"ETag": '"abc123"'}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
                auth_spec=None,
            )
            with patch("requests.get", return_value=mock_response):
                with patch("scc_cli.cli_org.load_user_config", return_value={}):
                    with patch("scc_cli.cli_org.save_user_config"):
                        with patch("scc_cli.cli_org.save_to_cache") as mock_cache:
                            result = cli_runner.invoke(
                                org_app, ["import", "https://example.com/org.json"]
                            )

        assert result.exit_code == 0
        mock_cache.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgImportErrors:
    """Test error handling for scc org import."""

    def test_network_error_shows_message(self, cli_runner: CliRunner) -> None:
        """Network errors should show helpful message."""
        import requests

        from scc_cli.cli_org import org_app

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
            )
            with patch("requests.get", side_effect=requests.RequestException("Connection failed")):
                result = cli_runner.invoke(
                    org_app, ["import", "https://example.com/org.json", "--preview"]
                )

        assert result.exit_code != 0
        output_lower = result.stdout.lower()
        assert "error" in output_lower or "failed" in output_lower

    def test_404_shows_not_found(self, cli_runner: CliRunner) -> None:
        """404 response should show not found message."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
            )
            with patch("requests.get", return_value=mock_response):
                result = cli_runner.invoke(
                    org_app, ["import", "https://example.com/org.json", "--preview"]
                )

        assert result.exit_code != 0
        output_lower = result.stdout.lower()
        assert "not found" in output_lower or "404" in output_lower

    def test_invalid_url_shows_error(self, cli_runner: CliRunner) -> None:
        """Invalid URL format should show error."""
        from scc_cli.cli_org import org_app
        from scc_cli.source_resolver import ResolveError

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = ResolveError(
                message="Invalid source format",
                source="not-a-valid-source",
                suggestion="Use: github:owner/repo@ref:path",
            )
            result = cli_runner.invoke(org_app, ["import", "not-a-valid-source", "--preview"])

        assert result.exit_code != 0
        output_lower = result.stdout.lower()
        assert "invalid" in output_lower or "error" in output_lower


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgImportJsonOutput:
    """Test JSON output format for scc org import."""

    def test_json_envelope_on_success(self, cli_runner: CliRunner, valid_org_config: dict) -> None:
        """Successful import should return proper JSON envelope."""
        from scc_cli.cli_org import org_app

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = valid_org_config
        mock_response.headers = {"ETag": '"abc123"'}

        with patch("scc_cli.cli_org.resolve_source") as mock_resolve:
            mock_resolve.return_value = MagicMock(
                resolved_url="https://example.com/org.json",
                provider="https",
                auth_spec=None,
            )
            with patch("requests.get", return_value=mock_response):
                with patch("scc_cli.cli_org.load_user_config", return_value={}):
                    with patch("scc_cli.cli_org.save_user_config"):
                        with patch("scc_cli.cli_org.save_to_cache"):
                            result = cli_runner.invoke(
                                org_app, ["import", "https://example.com/org.json", "--json"]
                            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert "data" in data
