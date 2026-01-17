"""Tests for handle_errors JSON behavior."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest
import typer

from scc_cli.cli_common import handle_errors
from scc_cli.core.errors import ConfigError
from scc_cli.core.exit_codes import EXIT_CANCELLED, EXIT_CONFIG
from scc_cli.output_mode import json_command_mode


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


@handle_errors
def _raise_config_error() -> None:
    raise ConfigError(user_message="Config boom")


@handle_errors
def _raise_keyboard_interrupt() -> None:
    raise KeyboardInterrupt


def test_handle_errors_config_error_json(capsys: pytest.CaptureFixture[str]) -> None:
    with json_command_mode():
        with pytest.raises(typer.Exit) as exc_info:
            _raise_config_error()

    assert exc_info.value.exit_code == EXIT_CONFIG
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "Error"
    assert payload["status"]["errors"] == ["Config boom"]


def test_handle_errors_keyboard_interrupt_json(capsys: pytest.CaptureFixture[str]) -> None:
    with json_command_mode():
        with pytest.raises(typer.Exit) as exc_info:
            _raise_keyboard_interrupt()

    assert exc_info.value.exit_code == EXIT_CANCELLED
    payload = json.loads(capsys.readouterr().out)

    assert payload["kind"] == "Error"
    assert payload["status"]["errors"] == ["Operation cancelled by user"]
