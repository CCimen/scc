"""Hermetic end-to-end tests for core CLI journeys."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app

pytestmark = pytest.mark.e2e

runner = CliRunner()


def _json_output(output: str) -> dict[str, Any]:
    return json.loads(output)


def _subprocess_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parents[2] / "src"), env.get("PYTHONPATH", "")]
    )
    return env


def _run_scc_subprocess(
    args: list[str], *, home: Path, cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scc_cli.cli", *args],
        cwd=cwd,
        env=_subprocess_env(home),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def _enterprise_org_config() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "organization": {"name": "Example Municipality", "id": "example-muni"},
        "defaults": {
            "enabled_plugins": ["org-baseline@internal"],
            "allowed_plugins": ["org-*", "team-*", "project-*"],
            "network_policy": "web-egress-enforced",
            "session": {"timeout_hours": 8, "auto_resume": False},
        },
        "delegation": {
            "teams": {"allow_additional_plugins": ["*"]},
            "projects": {"inherit_team_delegation": True},
        },
        "security": {"blocked_plugins": ["blocked-*"]},
        "profiles": {
            "platform": {
                "description": "Platform engineering",
                "additional_plugins": ["team-platform@internal"],
                "delegation": {"allow_project_overrides": True},
                "session": {"timeout_hours": 6},
            },
            "analytics": {
                "description": "Analytics applications",
                "additional_plugins": ["team-insight@internal"],
                "delegation": {"allow_project_overrides": True},
                "network_policy": "locked-down-web",
                "session": {"timeout_hours": 5},
            },
        },
        "marketplaces": {
            "internal": {
                "source": "github",
                "owner": "example",
                "repo": "scc-artifacts",
            }
        },
    }


def test_standalone_setup_and_project_init(e2e_config_paths, tmp_path: Path) -> None:
    setup_result = runner.invoke(app, ["setup", "--standalone", "--non-interactive"])

    assert setup_result.exit_code == 0
    config_payload = json.loads(e2e_config_paths.config_file.read_text())
    assert config_payload["standalone"] is True
    assert config_payload["organization_source"] is None

    get_result = runner.invoke(app, ["config", "get", "standalone"])
    assert get_result.exit_code == 0
    assert get_result.output.strip() == "True"

    workspace = tmp_path / "standalone-project"
    workspace.mkdir()
    init_result = runner.invoke(app, ["init", str(workspace), "--json"])

    assert init_result.exit_code == 0
    init_payload = _json_output(init_result.output)
    assert init_payload["kind"] == "InitResult"
    assert init_payload["status"]["ok"] is True
    assert init_payload["data"]["created"] is True
    assert Path(init_payload["data"]["file_path"]) == workspace / ".scc.yaml"
    assert (workspace / ".scc.yaml").exists()


def test_subprocess_standalone_setup_and_init_use_isolated_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "subprocess-project"
    workspace.mkdir()

    setup_result = _run_scc_subprocess(
        ["setup", "--standalone", "--non-interactive"],
        home=home,
        cwd=tmp_path,
    )
    assert setup_result.returncode == 0, setup_result.stderr + setup_result.stdout

    config_file = home / ".config" / "scc" / "config.json"
    config_payload = json.loads(config_file.read_text())
    assert config_payload["standalone"] is True
    assert config_payload["organization_source"] is None

    get_result = _run_scc_subprocess(["config", "get", "standalone"], home=home, cwd=tmp_path)
    assert get_result.returncode == 0, get_result.stderr + get_result.stdout
    assert get_result.stdout.strip() == "True"

    init_result = _run_scc_subprocess(
        ["init", str(workspace), "--json"],
        home=home,
        cwd=tmp_path,
    )
    assert init_result.returncode == 0, init_result.stderr + init_result.stdout
    init_payload = _json_output(init_result.stdout)
    assert init_payload["kind"] == "InitResult"
    assert init_payload["status"]["ok"] is True
    assert Path(init_payload["data"]["file_path"]) == workspace / ".scc.yaml"


def test_subprocess_start_dry_run_outputs_launch_contract_without_docker(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "dry-run-project"
    workspace.mkdir()
    (workspace / ".git").mkdir()

    result = _run_scc_subprocess(
        [
            "start",
            str(workspace),
            "--standalone",
            "--dry-run",
            "--json",
            "--non-interactive",
            "--provider",
            "claude",
        ],
        home=home,
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    payload = _json_output(result.stdout)
    assert payload["kind"] == "StartDryRun"
    assert payload["status"]["ok"] is True
    assert payload["data"]["workspace_root"] == str(workspace.resolve())
    assert payload["data"]["provider_id"] == "claude"
    assert payload["data"]["ready_to_start"] is True
    assert not (home / ".config" / "scc" / "audit" / "launch-events.jsonl").exists()


def test_org_team_project_effective_config_journey(
    e2e_config_paths,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    org_config = _enterprise_org_config()

    monkeypatch.setattr(
        "scc_cli.setup.fetch_org_config",
        lambda url, auth, etag=None, auth_header=None: (org_config, '"e2e"', 200),
    )
    monkeypatch.setattr("scc_cli.setup._run_provider_onboarding", lambda console: (None, None))

    setup_result = runner.invoke(
        app,
        [
            "setup",
            "--org-url",
            "https://example.test/scc/org.json",
            "--team",
            "platform",
            "--non-interactive",
        ],
    )

    assert setup_result.exit_code == 0
    assert (e2e_config_paths.cache_dir / "org_config.json").exists()

    list_result = runner.invoke(app, ["team", "list", "--json"])
    assert list_result.exit_code == 0
    list_payload = _json_output(list_result.output)
    assert list_payload["kind"] == "TeamList"
    assert {team["name"] for team in list_payload["data"]["teams"]} == {
        "platform",
        "analytics",
    }
    assert list_payload["data"]["current"] == "platform"

    switch_result = runner.invoke(app, ["team", "switch", "analytics", "--json"])
    assert switch_result.exit_code == 0
    switch_payload = _json_output(switch_result.output)
    assert switch_payload["kind"] == "TeamSwitch"
    assert switch_payload["data"]["success"] is True
    assert switch_payload["data"]["previous"] == "platform"
    assert switch_payload["data"]["current"] == "analytics"

    workspace = tmp_path / "analytics-project"
    workspace.mkdir()
    (workspace / ".scc.yaml").write_text(
        "\n".join(
            [
                "additional_plugins:",
                '  - "project-runner@internal"',
                "network_policy: open",
                "session:",
                "  timeout_hours: 4",
                "",
            ]
        )
    )

    validate_result = runner.invoke(
        app,
        ["config", "validate", "--workspace", str(workspace), "--json"],
    )
    assert validate_result.exit_code == 0
    validate_payload = _json_output(validate_result.output)
    assert validate_payload["kind"] == "ConfigValidate"
    assert validate_payload["status"]["ok"] is True
    assert validate_payload["data"]["team"] == "analytics"
    assert validate_payload["data"]["project_config_found"] is True
    assert validate_payload["status"]["warnings"] == [
        "network_policy ignored: Project network_policy cannot be less restrictive than "
        "inherited policy (open -> locked-down-web)."
    ]

    explain_result = runner.invoke(
        app,
        ["config", "explain", "--workspace", str(workspace), "--json"],
    )
    assert explain_result.exit_code == 0
    explain_payload = _json_output(explain_result.output)
    assert explain_payload["kind"] == "ConfigExplain"
    assert explain_payload["data"]["team"] == "analytics"
    assert explain_payload["data"]["organization"]["name"] == "Example Municipality"
    assert explain_payload["data"]["effective"]["plugins"] == [
        "org-baseline@internal",
        "project-runner@internal",
        "team-insight@internal",
    ]
    assert explain_payload["data"]["effective"]["network_policy"] == "locked-down-web"
    assert explain_payload["data"]["effective"]["session"]["timeout_hours"] == 4
    assert explain_payload["data"]["ignored_policy_changes"] == [
        {
            "field": "network_policy",
            "requested_value": "open",
            "effective_value": "locked-down-web",
            "source": "project",
            "reason": "Project network_policy cannot be less restrictive than inherited policy",
        }
    ]
