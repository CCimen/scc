from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from typer.testing import CliRunner

from scc_cli import cli
from scc_cli.application.dev_environment_bridge import (
    CapturedStream,
    RunDevEnvironmentCommandResult,
)
from scc_cli.core.exit_codes import EXIT_TOOL
from tests.fakes import FakeAuditEventSink

runner = CliRunner()


def _result(tmp_path: Path, *, status: str = "succeeded") -> RunDevEnvironmentCommandResult:
    exit_code = 0 if status == "succeeded" else 2
    return RunDevEnvironmentCommandResult(
        command_name="test",
        argv=("uv", "run", "pytest", "-q"),
        cwd=tmp_path,
        status=status,
        exit_code=exit_code,
        timed_out=False,
        duration_ms=12,
        stdout=CapturedStream(tail="ok\n", total_bytes=3, truncated=False),
        stderr=CapturedStream(tail="", total_bytes=0, truncated=False),
        team_name="platform",
        team_source="selected_profile",
        provider_id="codex",
        provider_source="workspace",
    )


def test_dev_app_registers_run_command() -> None:
    command_names = [group.name for group in cli.app.registered_groups]
    assert "dev" in command_names


def test_dev_run_json_outputs_command_result(tmp_path: Path) -> None:
    with patch("scc_cli.commands.dev._run_dev_command", return_value=_result(tmp_path)) as run:
        result = runner.invoke(cli.app, ["dev", "run", "test", str(tmp_path), "--json"])

    assert result.exit_code == 0
    run.assert_called_once()
    payload = json.loads(result.output)
    assert payload["kind"] == "DevEnvironmentCommand"
    assert payload["status"]["ok"] is True
    assert payload["data"]["command_name"] == "test"
    assert payload["data"]["stdout"]["tail"] == "ok\n"
    assert payload["data"]["team"] == {"name": "platform", "source": "selected_profile"}
    assert payload["data"]["provider"] == {"id": "codex", "source": "workspace"}


def test_dev_run_nonzero_result_exits_tool_error(tmp_path: Path) -> None:
    with patch(
        "scc_cli.commands.dev._run_dev_command",
        return_value=_result(tmp_path, status="failed"),
    ):
        result = runner.invoke(cli.app, ["dev", "run", "test", str(tmp_path), "--json"])

    assert result.exit_code == EXIT_TOOL
    payload = json.loads(result.output)
    assert payload["status"]["ok"] is False
    assert payload["data"]["status"] == "failed"


def test_dev_run_json_resolves_config_and_audits_missing_executable(tmp_path: Path) -> None:
    sink = FakeAuditEventSink()
    user_config = {
        "selected_profile": "platform",
        "selected_provider": "codex",
        "workspace_team_map": {},
    }
    org_config = {
        "schema_version": "1.0.0",
        "organization": {"name": "Test Org", "id": "test"},
        "defaults": {
            "dev_environment": {
                "commands": {
                    "test": {
                        "argv": ["definitely-not-a-real-scc-test-command"],
                        "working_directory": ".",
                        "timeout_seconds": 5,
                    }
                }
            }
        },
        "profiles": {"platform": {"description": "Platform"}},
    }

    with (
        patch("scc_cli.commands.dev.config.load_user_config", return_value=user_config),
        patch("scc_cli.commands.dev.config.load_cached_org_config", return_value=org_config),
        patch(
            "scc_cli.commands.dev.get_default_adapters",
            return_value=SimpleNamespace(audit_event_sink=sink),
        ),
    ):
        result = runner.invoke(cli.app, ["dev", "run", "test", str(tmp_path), "--json"])

    assert result.exit_code == EXIT_TOOL
    payload = json.loads(result.output)
    assert payload["kind"] == "DevEnvironmentCommand"
    assert payload["data"]["status"] == "failed"
    assert "definitely-not-a-real-scc-test-command" in payload["data"]["stderr"]["tail"]
    assert [event.event_type for event in sink.events] == [
        "dev_environment.command.started",
        "dev_environment.command.failed",
    ]
