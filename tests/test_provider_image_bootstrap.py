"""Tests for automatic provider image preparation in launch flows."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scc_cli.commands.launch.provider_image import (
    _build_provider_image,
    ensure_provider_image,
    get_provider_build_command,
)
from scc_cli.core.errors import ProviderImageBuildError, ProviderImageMissingError


def test_get_provider_build_command_uses_registry_image_and_context() -> None:
    command = get_provider_build_command("claude")

    assert command[:4] == ["docker", "build", "-t", "scc-agent-claude:latest"]
    assert command[-1].endswith("images/scc-agent-claude")


@patch("scc_cli.commands.launch.provider_image._provider_image_exists", return_value=True)
@patch("scc_cli.commands.launch.provider_image._build_provider_image")
def test_ensure_provider_image_skips_when_present(
    mock_build: MagicMock,
    _mock_exists: MagicMock,
) -> None:
    show_notice = MagicMock()

    ensure_provider_image(
        "claude",
        console=MagicMock(),
        non_interactive=False,
        show_notice=show_notice,
    )

    show_notice.assert_not_called()
    mock_build.assert_not_called()


@patch("scc_cli.commands.launch.provider_image._provider_image_exists", return_value=False)
@patch("scc_cli.commands.launch.provider_image._build_provider_image")
def test_ensure_provider_image_auto_builds_interactively(
    mock_build: MagicMock,
    _mock_exists: MagicMock,
) -> None:
    show_notice = MagicMock()

    ensure_provider_image(
        "claude",
        console=MagicMock(),
        non_interactive=False,
        show_notice=show_notice,
    )

    show_notice.assert_called_once()
    mock_build.assert_called_once()


@patch("scc_cli.commands.launch.provider_image._provider_image_exists", return_value=False)
def test_ensure_provider_image_fails_closed_non_interactive(
    _mock_exists: MagicMock,
) -> None:
    with pytest.raises(ProviderImageMissingError) as exc_info:
        ensure_provider_image(
            "codex",
            console=MagicMock(),
            non_interactive=True,
            show_notice=MagicMock(),
        )

    assert "docker build -t scc-agent-codex:latest" in exc_info.value.suggested_action


@patch("scc_cli.commands.launch.provider_image.Status")
@patch("scc_cli.commands.launch.provider_image.subprocess.run")
def test_build_provider_image_raises_typed_error_on_failure(
    mock_run: MagicMock,
    _mock_status: MagicMock,
) -> None:
    mock_run.return_value = MagicMock(returncode=1, stderr="boom")

    with pytest.raises(ProviderImageBuildError) as exc_info:
        _build_provider_image("codex", console=MagicMock())

    assert "codex" in exc_info.value.user_message
    assert "docker build -t scc-agent-codex:latest" in exc_info.value.suggested_action
