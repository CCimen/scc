"""
Tests for org admin CLI commands (Phase 6).

TDD approach: Tests written before implementation.
These tests define the contract for:
- scc org validate <source>
- scc org schema
- JSON output support
- Semantic validation checks
"""

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Org App Structure
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgAppStructure:
    """Test org app Typer structure."""

    def test_org_app_exists(self) -> None:
        """org_app Typer should exist."""
        from scc_cli.cli_org import org_app

        assert org_app is not None

    def test_org_app_has_validate_command(self) -> None:
        """org_app should have 'validate' subcommand."""
        from scc_cli.cli_org import org_app

        command_names = [cmd.name for cmd in org_app.registered_commands]
        assert "validate" in command_names

    def test_org_app_has_schema_command(self) -> None:
        """org_app should have 'schema' subcommand."""
        from scc_cli.cli_org import org_app

        command_names = [cmd.name for cmd in org_app.registered_commands]
        assert "schema" in command_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Org Validate Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgValidate:
    """Test scc org validate command."""

    def test_validate_file_valid_config(self, tmp_path: Path) -> None:
        """validate should succeed for valid config file."""
        from scc_cli.cli_org import org_validate_cmd

        # Create a minimal valid config (matches v1 schema requirements)
        config_file = tmp_path / "org.json"
        config_file.write_text(
            json.dumps(
                {"schema_version": "1.0.0", "organization": {"name": "Test Org", "id": "test-org"}}
            )
        )

        with patch("scc_cli.cli_org.console"):
            try:
                org_validate_cmd(
                    source=str(config_file),
                    schema_version="v1",
                    json_output=False,
                    pretty=False,
                )
            except click.exceptions.Exit as e:
                assert e.exit_code == 0

    def test_validate_file_invalid_config(self, tmp_path: Path) -> None:
        """validate should fail for invalid config file."""
        from scc_cli.cli_org import org_validate_cmd

        # Create an invalid config (missing required fields)
        config_file = tmp_path / "org.json"
        config_file.write_text(
            json.dumps(
                {
                    "schema_version": "v1"
                    # Missing organization field
                }
            )
        )

        with patch("scc_cli.cli_org.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                org_validate_cmd(
                    source=str(config_file),
                    schema_version="v1",
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code == 4  # EXIT_VALIDATION

    def test_validate_json_output_valid(self, tmp_path: Path, capsys) -> None:
        """validate --json should output JSON envelope for valid config."""
        from scc_cli.cli_org import org_validate_cmd

        config_file = tmp_path / "org.json"
        config_file.write_text(
            json.dumps(
                {"schema_version": "1.0.0", "organization": {"name": "Test Org", "id": "test-org"}}
            )
        )

        try:
            org_validate_cmd(
                source=str(config_file),
                schema_version="v1",
                json_output=True,
                pretty=False,
            )
        except click.exceptions.Exit:
            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "OrgValidation"
        assert output["apiVersion"] == "scc.cli/v1"
        assert output["status"]["ok"] is True

    def test_validate_json_output_invalid(self, tmp_path: Path, capsys) -> None:
        """validate --json should output errors for invalid config."""
        from scc_cli.cli_org import org_validate_cmd

        config_file = tmp_path / "org.json"
        config_file.write_text(
            json.dumps(
                {
                    "schema_version": "v1"
                    # Missing organization
                }
            )
        )

        try:
            org_validate_cmd(
                source=str(config_file),
                schema_version="v1",
                json_output=True,
                pretty=False,
            )
        except click.exceptions.Exit:
            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "OrgValidation"
        assert output["status"]["ok"] is False
        assert len(output["status"]["errors"]) > 0

    def test_validate_nonexistent_file(self) -> None:
        """validate should fail for nonexistent file."""
        from scc_cli.cli_org import org_validate_cmd

        with patch("scc_cli.cli_org.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                org_validate_cmd(
                    source="/nonexistent/path/config.json",
                    schema_version="v1",
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code == 3  # EXIT_CONFIG

    def test_validate_malformed_json(self, tmp_path: Path) -> None:
        """validate should fail for malformed JSON."""
        from scc_cli.cli_org import org_validate_cmd

        config_file = tmp_path / "org.json"
        config_file.write_text("{ invalid json }")

        with patch("scc_cli.cli_org.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                org_validate_cmd(
                    source=str(config_file),
                    schema_version="v1",
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code == 3  # EXIT_CONFIG


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Org Schema Command
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgSchema:
    """Test scc org schema command."""

    def test_schema_prints_bundled_schema(self, capsys) -> None:
        """schema should print the bundled JSON schema."""
        from scc_cli.cli_org import org_schema_cmd

        try:
            org_schema_cmd(
                schema_version="v1",
                json_output=False,
                pretty=False,
            )
        except click.exceptions.Exit:
            pass

        captured = capsys.readouterr()
        # Should be valid JSON
        schema = json.loads(captured.out)
        assert "$schema" in schema or "type" in schema

    def test_schema_json_output(self, capsys) -> None:
        """schema --json should output envelope with schema."""
        from scc_cli.cli_org import org_schema_cmd

        try:
            org_schema_cmd(
                schema_version="v1",
                json_output=True,
                pretty=False,
            )
        except click.exceptions.Exit:
            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "OrgSchema"
        assert output["apiVersion"] == "scc.cli/v1"
        assert "schema" in output["data"]

    def test_schema_invalid_version(self) -> None:
        """schema with invalid version should fail."""
        from scc_cli.cli_org import org_schema_cmd

        with patch("scc_cli.cli_org.console"):
            with pytest.raises(click.exceptions.Exit) as exc_info:
                org_schema_cmd(
                    schema_version="v99",
                    json_output=False,
                    pretty=False,
                )
            assert exc_info.value.exit_code == 3  # EXIT_CONFIG


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Semantic Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSemanticValidation:
    """Test semantic validation checks beyond JSON schema."""

    def test_detect_duplicate_profile_names(self) -> None:
        """Should detect duplicate profile names."""
        from scc_cli.cli_org import check_semantic_errors

        config = {
            "organization": {
                "name": "Test",
                "profiles": [
                    {"name": "backend", "plugins": []},
                    {"name": "backend", "plugins": []},  # Duplicate
                ],
            }
        }

        errors = check_semantic_errors(config)
        assert any("duplicate" in e.lower() for e in errors)

    def test_detect_missing_default_profile(self) -> None:
        """Should warn if default_profile references non-existent profile."""
        from scc_cli.cli_org import check_semantic_errors

        config = {
            "organization": {
                "name": "Test",
                "default_profile": "nonexistent",
                "profiles": [
                    {"name": "backend", "plugins": []},
                ],
            }
        }

        errors = check_semantic_errors(config)
        assert any("default_profile" in e.lower() for e in errors)

    def test_valid_config_no_semantic_errors(self) -> None:
        """Valid config should have no semantic errors."""
        from scc_cli.cli_org import check_semantic_errors

        config = {
            "organization": {
                "name": "Test",
                "default_profile": "backend",
                "profiles": [
                    {"name": "backend", "plugins": []},
                    {"name": "frontend", "plugins": []},
                ],
            }
        }

        errors = check_semantic_errors(config)
        assert len(errors) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for CLI Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgAppRegistration:
    """Test org app is registered in main CLI."""

    def test_org_app_registered_in_main_cli(self) -> None:
        """org_app should be registered as subcommand in main CLI."""
        from scc_cli.cli import app

        group_names = [group.name for group in app.registered_groups if group.name]
        assert "org" in group_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Pure Functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildValidationData:
    """Test build_validation_data pure function."""

    def test_builds_correct_structure_valid(self) -> None:
        """build_validation_data should return correct structure for valid config."""
        from scc_cli.cli_org import build_validation_data

        result = build_validation_data(
            source="/path/to/config.json",
            schema_errors=[],
            semantic_errors=[],
            schema_version="v1",
        )

        assert result["source"] == "/path/to/config.json"
        assert result["schema_version"] == "v1"
        assert result["valid"] is True
        assert result["schema_errors"] == []
        assert result["semantic_errors"] == []

    def test_builds_correct_structure_invalid(self) -> None:
        """build_validation_data should return correct structure for invalid config."""
        from scc_cli.cli_org import build_validation_data

        result = build_validation_data(
            source="/path/to/config.json",
            schema_errors=["Missing required field: organization"],
            semantic_errors=["Duplicate profile name: backend"],
            schema_version="v1",
        )

        assert result["valid"] is False
        assert len(result["schema_errors"]) == 1
        assert len(result["semantic_errors"]) == 1
