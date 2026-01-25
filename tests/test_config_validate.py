"""Tests for scc config validate command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from scc_cli import cli

runner = CliRunner()


def _org_config(*, allowed_plugins: list[str] | None = None) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {"allowed_plugins": allowed_plugins},
        "delegation": {"projects": {"inherit_team_delegation": True}},
        "profiles": {"backend": {"delegation": {"allow_project_overrides": True}}},
    }


def test_config_validate_success(tmp_path, monkeypatch):
    scc_yaml = tmp_path / ".scc.yaml"
    scc_yaml.write_text(
        """
additional_plugins:
  - "project-tool@internal"
session:
  timeout_hours: 4
"""
    )

    org_config = _org_config(allowed_plugins=["project-*"])

    monkeypatch.setattr(
        "scc_cli.commands.config.config.load_cached_org_config",
        lambda: org_config,
    )

    result = runner.invoke(
        cli.app,
        ["config", "validate", "--workspace", str(tmp_path), "--team", "backend"],
    )

    assert result.exit_code == 0
    assert "Project Config Valid" in result.output


def test_config_validate_denied_plugin_returns_governance_exit(tmp_path, monkeypatch):
    scc_yaml = tmp_path / ".scc.yaml"
    scc_yaml.write_text(
        """
additional_plugins:
  - "blocked-tool@internal"
"""
    )

    org_config = _org_config(allowed_plugins=["safe-*"])

    monkeypatch.setattr(
        "scc_cli.commands.config.config.load_cached_org_config",
        lambda: org_config,
    )

    result = runner.invoke(
        cli.app,
        [
            "config",
            "validate",
            "--workspace",
            str(tmp_path),
            "--team",
            "backend",
            "--json",
        ],
    )

    assert result.exit_code == 6
    payload = json.loads(result.output)
    assert payload["kind"] == "ConfigValidate"
    assert payload["status"]["ok"] is False
    assert payload["status"]["errors"]


def test_config_validate_missing_config(tmp_path, monkeypatch):
    org_config = _org_config(allowed_plugins=["*"])
    monkeypatch.setattr(
        "scc_cli.commands.config.config.load_cached_org_config",
        lambda: org_config,
    )

    result = runner.invoke(
        cli.app,
        ["config", "validate", "--workspace", str(tmp_path), "--team", "backend"],
    )

    assert result.exit_code == 3
    assert "Project Config Invalid" in result.output
