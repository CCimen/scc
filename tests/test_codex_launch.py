"""Tests for Codex launch and browser-auth bootstrap helpers."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters.codex_auth import (
    AUTH_CALLBACK_PORT,
    AUTH_RELAY_PORT,
    build_codex_browser_auth_command,
    run_codex_browser_auth,
)
from scc_cli.adapters.codex_launch import build_codex_container_argv
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.provider_registry import get_runtime_spec


def test_build_codex_container_argv_is_plain_codex_launch() -> None:
    """The steady-state container argv is just the Codex TUI plus SCC bypass."""
    assert build_codex_container_argv() == (
        "codex",
        "--dangerously-bypass-approvals-and-sandbox",
    )


def test_build_codex_browser_auth_command_uses_published_callback_port() -> None:
    """Browser auth runs through a relay that exposes Codex's loopback callback."""
    spec = get_runtime_spec("codex")

    assert build_codex_browser_auth_command() == [
        "docker",
        "run",
        "--rm",
        "-it",
        "--entrypoint",
        "/bin/sh",
        "-p",
        f"127.0.0.1:{AUTH_CALLBACK_PORT}:{AUTH_RELAY_PORT}",
        "-v",
        f"{spec.data_volume}:/home/agent/{spec.config_dir}",
        "-w",
        "/home/agent",
        spec.image_ref,
        "-lc",
        (
            "socat TCP-LISTEN:1456,bind=0.0.0.0,reuseaddr,fork "
            "TCP:127.0.0.1:1455 & "
            "exec codex login -c cli_auth_credentials_store=file"
        ),
    ]


@patch("scc_cli.adapters.codex_auth.subprocess.run")
@patch("scc_cli.adapters.codex_auth._is_local_callback_port_available", return_value=True)
def test_run_codex_browser_auth_executes_docker_login(
    mock_port_available: MagicMock,
    mock_run: MagicMock,
) -> None:
    """Successful browser bootstrap executes the temporary Docker login flow."""
    mock_run.return_value = subprocess.CompletedProcess(["docker"], 0)

    return_code = run_codex_browser_auth()

    mock_port_available.assert_called_once_with(AUTH_CALLBACK_PORT)
    assert mock_run.call_args.args[0] == build_codex_browser_auth_command()
    assert return_code == 0


@patch("scc_cli.adapters.codex_auth.subprocess.run")
@patch("scc_cli.adapters.codex_auth._is_local_callback_port_available", return_value=False)
def test_run_codex_browser_auth_fails_cleanly_when_callback_port_busy(
    mock_port_available: MagicMock,
    mock_run: MagicMock,
) -> None:
    """Port 1455 conflicts fail with actionable SCC guidance before Docker runs."""
    with pytest.raises(ProviderNotReadyError) as exc_info:
        run_codex_browser_auth()

    mock_port_available.assert_called_once_with(AUTH_CALLBACK_PORT)
    mock_run.assert_not_called()
    assert "localhost:1455" in str(exc_info.value)
    assert "device-code" in exc_info.value.suggested_action.lower()


@patch("scc_cli.adapters.codex_auth.subprocess.run")
@patch("scc_cli.adapters.codex_auth._is_local_callback_port_available", return_value=True)
def test_run_codex_browser_auth_surfaces_login_failure(
    mock_port_available: MagicMock,
    mock_run: MagicMock,
) -> None:
    """Non-zero login exits are returned for provider-owned confirmation."""
    mock_run.return_value = subprocess.CompletedProcess(["docker"], 1)

    return_code = run_codex_browser_auth()
    mock_port_available.assert_called_once_with(AUTH_CALLBACK_PORT)
    mock_run.assert_called_once()
    assert return_code == 1
