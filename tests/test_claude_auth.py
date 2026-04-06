"""Tests for host-side Claude auth bootstrap."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters import claude_auth
from scc_cli.core.errors import ProviderNotReadyError


def test_build_claude_browser_auth_command_uses_host_claude_cli() -> None:
    assert claude_auth.build_claude_browser_auth_command() == [
        "claude",
        "auth",
        "login",
        "--claudeai",
    ]


@patch("scc_cli.adapters.claude_auth._sync_host_claude_auth_to_volume")
@patch("scc_cli.adapters.claude_auth.subprocess.run")
def test_run_claude_browser_auth_syncs_after_success(
    mock_run: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_run.return_value = MagicMock(returncode=0)

    result = claude_auth.run_claude_browser_auth()

    assert result == 0
    mock_run.assert_called_once_with(["claude", "auth", "login", "--claudeai"], check=False)
    mock_sync.assert_called_once_with()


@patch("scc_cli.adapters.claude_auth._sync_host_claude_auth_to_volume")
@patch("scc_cli.adapters.claude_auth.subprocess.run")
def test_run_claude_browser_auth_skips_sync_after_failure(
    mock_run: MagicMock,
    mock_sync: MagicMock,
) -> None:
    mock_run.return_value = MagicMock(returncode=1)

    result = claude_auth.run_claude_browser_auth()

    assert result == 1
    mock_sync.assert_not_called()


@patch("scc_cli.adapters.claude_auth.subprocess.run", side_effect=FileNotFoundError("claude"))
def test_run_claude_browser_auth_raises_when_host_claude_missing(_mock_run: MagicMock) -> None:
    with pytest.raises(ProviderNotReadyError, match="host 'claude' CLI is not installed"):
        claude_auth.run_claude_browser_auth()


@patch("scc_cli.adapters.claude_auth.subprocess.run")
@patch("scc_cli.adapters.claude_auth.Path.home")
def test_sync_host_claude_auth_to_volume_writes_claude_json(
    mock_home: MagicMock,
    mock_run: MagicMock,
    tmp_path: Path,
) -> None:
    host_file = tmp_path / ".claude.json"
    host_file.write_text('{"oauthAccount":{"email":"user@example.com"}}')
    mock_home.return_value = tmp_path
    mock_run.return_value = MagicMock(returncode=0)

    claude_auth._sync_host_claude_auth_to_volume()

    assert mock_run.call_count == 1
    args = mock_run.call_args.args[0]
    assert args[:4] == ["docker", "run", "--rm", "-i"]
    assert "docker-claude-sandbox-data:/data" in args
    assert mock_run.call_args.kwargs["input"] == '{"oauthAccount":{"email":"user@example.com"}}'
