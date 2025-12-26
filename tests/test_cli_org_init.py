"""
Tests for scc org init command.

TDD: Tests written before implementation.
Tests cover: template listing, generation, --stdout mode, output file writing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

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


# ═══════════════════════════════════════════════════════════════════════════════
# Template Listing Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgInitListTemplates:
    """Test the CLI command: scc org init --list-templates."""

    def test_list_templates_shows_available(self, cli_runner: CliRunner) -> None:
        """--list-templates should show all available templates."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--list-templates"])

        assert result.exit_code == 0
        assert "minimal" in result.stdout
        assert "teams" in result.stdout
        assert "strict" in result.stdout
        assert "reference" in result.stdout

    def test_list_templates_shows_descriptions(self, cli_runner: CliRunner) -> None:
        """--list-templates should show template descriptions."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--list-templates"])

        assert result.exit_code == 0
        # Should include some description text
        output_lower = result.stdout.lower()
        assert "quickstart" in output_lower or "beginner" in output_lower

    def test_list_templates_json_output(self, cli_runner: CliRunner) -> None:
        """--list-templates --json should return structured data."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--list-templates", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert "templates" in data["data"]
        # Should list at least 4 templates
        assert len(data["data"]["templates"]) >= 4


# ═══════════════════════════════════════════════════════════════════════════════
# Stdout Generation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgInitStdout:
    """Test the CLI command: scc org init --stdout."""

    def test_stdout_outputs_json_config(self, cli_runner: CliRunner) -> None:
        """--stdout should print valid JSON config to stdout."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--stdout", "--template", "minimal"])

        assert result.exit_code == 0
        # Should be valid JSON
        config = json.loads(result.stdout)
        assert "schema_version" in config
        assert "organization" in config

    def test_stdout_with_org_name(self, cli_runner: CliRunner) -> None:
        """--stdout with --org-name should substitute organization name."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(
            org_app,
            ["init", "--stdout", "--template", "minimal", "--org-name", "acme-corp"],
        )

        assert result.exit_code == 0
        config = json.loads(result.stdout)
        assert config["organization"]["name"] == "acme-corp"
        assert config["organization"]["id"] == "acme-corp"

    def test_stdout_with_org_domain(self, cli_runner: CliRunner) -> None:
        """--stdout with --org-domain should substitute contact email."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(
            org_app,
            ["init", "--stdout", "--template", "minimal", "--org-domain", "acme.com"],
        )

        assert result.exit_code == 0
        config = json.loads(result.stdout)
        assert "acme.com" in config["organization"]["contact"]

    def test_stdout_minimal_template(self, cli_runner: CliRunner) -> None:
        """--stdout with minimal template produces valid minimal config."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--stdout", "--template", "minimal"])

        assert result.exit_code == 0
        config = json.loads(result.stdout)
        assert "profiles" in config
        assert "defaults" in config

    def test_stdout_teams_template_has_multiple_profiles(self, cli_runner: CliRunner) -> None:
        """Teams template should have multiple profiles defined."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--stdout", "--template", "teams"])

        assert result.exit_code == 0
        config = json.loads(result.stdout)
        assert len(config.get("profiles", {})) >= 2

    def test_stdout_unknown_template_shows_error(self, cli_runner: CliRunner) -> None:
        """Unknown template should show error with available templates."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--stdout", "--template", "nonexistent"])

        assert result.exit_code != 0
        output_lower = result.stdout.lower()
        assert "unknown" in output_lower or "not found" in output_lower
        # Should suggest available templates
        assert "minimal" in result.stdout


# ═══════════════════════════════════════════════════════════════════════════════
# File Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgInitFileOutput:
    """Test the CLI command: scc org init --output <file>."""

    def test_output_writes_to_file(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """--output should write config to specified file."""
        from scc_cli.cli_org import org_app

        output_file = tmp_path / "org-config.json"

        result = cli_runner.invoke(
            org_app,
            [
                "init",
                "--template",
                "minimal",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        # File should contain valid JSON
        config = json.loads(output_file.read_text())
        assert "schema_version" in config

    def test_output_with_org_name(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """--output with --org-name should write config with correct name."""
        from scc_cli.cli_org import org_app

        output_file = tmp_path / "org-config.json"

        result = cli_runner.invoke(
            org_app,
            [
                "init",
                "--template",
                "minimal",
                "--org-name",
                "test-org",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        config = json.loads(output_file.read_text())
        assert config["organization"]["name"] == "test-org"

    def test_output_refuses_overwrite_without_force(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """--output should refuse to overwrite existing file without --force."""
        from scc_cli.cli_org import org_app

        output_file = tmp_path / "org-config.json"
        output_file.write_text('{"existing": true}')

        result = cli_runner.invoke(
            org_app,
            [
                "init",
                "--template",
                "minimal",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code != 0
        output_lower = result.stdout.lower()
        assert "exists" in output_lower or "overwrite" in output_lower

    def test_output_overwrites_with_force(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """--output --force should overwrite existing file."""
        from scc_cli.cli_org import org_app

        output_file = tmp_path / "org-config.json"
        output_file.write_text('{"existing": true}')

        result = cli_runner.invoke(
            org_app,
            [
                "init",
                "--template",
                "minimal",
                "--output",
                str(output_file),
                "--force",
            ],
        )

        assert result.exit_code == 0
        config = json.loads(output_file.read_text())
        assert "schema_version" in config
        assert "existing" not in config


# ═══════════════════════════════════════════════════════════════════════════════
# Default Behavior Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgInitDefaults:
    """Test default behavior of scc org init."""

    def test_default_template_is_minimal(self, cli_runner: CliRunner) -> None:
        """Without --template, should use 'minimal' template."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--stdout"])

        assert result.exit_code == 0
        config = json.loads(result.stdout)
        # Minimal template should be relatively simple
        assert "schema_version" in config
        assert "organization" in config

    def test_init_without_output_or_stdout_shows_help(self, cli_runner: CliRunner) -> None:
        """Without --stdout or --output, should show usage help."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--template", "minimal"])

        # Should indicate need for --stdout or --output
        output_lower = result.stdout.lower()
        assert "--stdout" in output_lower or "--output" in output_lower or "specify" in output_lower


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrgInitJsonEnvelope:
    """Test JSON envelope output for scc org init."""

    def test_output_json_envelope(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """--output --json should return envelope with file path."""
        from scc_cli.cli_org import org_app

        output_file = tmp_path / "org-config.json"

        result = cli_runner.invoke(
            org_app,
            [
                "init",
                "--template",
                "minimal",
                "--output",
                str(output_file),
                "--json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert "data" in data
        assert data["data"]["file"] == str(output_file)

    def test_list_templates_json_envelope_kind(self, cli_runner: CliRunner) -> None:
        """--list-templates --json should use proper envelope kind."""
        from scc_cli.cli_org import org_app

        result = cli_runner.invoke(org_app, ["init", "--list-templates", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "kind" in data
