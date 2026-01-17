"""Tests for json_command decorator behavior.

These tests lock current JSON envelope and exit code behavior before refactors.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator
from typing import Any

import pytest
import typer

from scc_cli.core.errors import ConfigError, PolicyViolationError
from scc_cli.core.exit_codes import EXIT_CANCELLED, EXIT_CONFIG, EXIT_GOVERNANCE, EXIT_SUCCESS
from scc_cli.json_command import json_command
from scc_cli.kinds import Kind

JsonCommand = Callable[..., dict[str, Any]]


@pytest.fixture(autouse=True)
def reset_output_mode_state() -> Generator[None, None, None]:
    """Reset JSON output state to avoid cross-test leakage."""
    from scc_cli.output_mode import _json_command_mode, _json_mode, _pretty_mode

    _pretty_mode.set(False)
    _json_mode.set(False)
    _json_command_mode.set(False)
    yield
    _pretty_mode.set(False)
    _json_mode.set(False)
    _json_command_mode.set(False)


def _build_success_command() -> JsonCommand:
    @json_command(Kind.TEAM_LIST)
    def command(json_output: bool = False, pretty: bool = False) -> dict[str, Any]:
        return {"teams": ["alpha", "beta"]}

    return command


def _build_config_error_command() -> JsonCommand:
    @json_command(Kind.TEAM_LIST)
    def command(json_output: bool = False, pretty: bool = False) -> dict[str, Any]:
        raise ConfigError()

    return command


def _build_policy_error_command() -> JsonCommand:
    @json_command(Kind.TEAM_LIST)
    def command(json_output: bool = False, pretty: bool = False) -> dict[str, Any]:
        raise PolicyViolationError(item="dangerous")

    return command


def _build_keyboard_interrupt_command() -> JsonCommand:
    @json_command(Kind.TEAM_LIST)
    def command(json_output: bool = False, pretty: bool = False) -> dict[str, Any]:
        raise KeyboardInterrupt

    return command


def test_json_command_success_envelope(capsys: pytest.CaptureFixture[str]) -> None:
    command = _build_success_command()

    with pytest.raises(typer.Exit) as exc_info:
        command(json_output=True, pretty=False)

    assert exc_info.value.exit_code == EXIT_SUCCESS
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == Kind.TEAM_LIST
    assert payload["status"]["ok"] is True
    assert payload["data"] == {"teams": ["alpha", "beta"]}


def test_json_command_non_json_mode_returns_value(
    capsys: pytest.CaptureFixture[str],
) -> None:
    command = _build_success_command()

    result = command(json_output=False, pretty=False)

    assert result == {"teams": ["alpha", "beta"]}
    assert capsys.readouterr().out == ""


def test_json_command_config_error_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    command = _build_config_error_command()

    with pytest.raises(typer.Exit) as exc_info:
        command(json_output=True, pretty=False)

    assert exc_info.value.exit_code == EXIT_CONFIG
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"]["ok"] is False
    assert payload["status"]["errors"] == ["Configuration error"]


def test_json_command_policy_violation_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    command = _build_policy_error_command()

    with pytest.raises(typer.Exit) as exc_info:
        command(json_output=True, pretty=False)

    assert exc_info.value.exit_code == EXIT_GOVERNANCE
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"]["ok"] is False
    assert "blocked" in payload["status"]["errors"][0]


def test_json_command_keyboard_interrupt_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    command = _build_keyboard_interrupt_command()

    with pytest.raises(typer.Exit) as exc_info:
        command(json_output=True, pretty=False)

    assert exc_info.value.exit_code == EXIT_CANCELLED
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"]["ok"] is False
    assert payload["status"]["errors"] == ["Cancelled"]
