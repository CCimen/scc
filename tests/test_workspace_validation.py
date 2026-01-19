from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scc_cli.application.workspace import validate_workspace
from scc_cli.core.errors import UsageError
from scc_cli.ports.platform_probe import PlatformProbe


class FakePlatformProbe(PlatformProbe):
    def __init__(self, is_wsl2: bool, is_optimal: bool) -> None:
        self._is_wsl2 = is_wsl2
        self._is_optimal = is_optimal

    def is_wsl2(self) -> bool:
        return self._is_wsl2

    def check_path_performance(self, path: Path) -> tuple[bool, str | None]:
        if self._is_optimal:
            return True, None
        return False, "warning"


def test_validate_workspace_returns_none_when_unset() -> None:
    result = validate_workspace(
        None,
        allow_suspicious=False,
        interactive_allowed=False,
        platform_probe=FakePlatformProbe(is_wsl2=False, is_optimal=True),
    )

    assert result is None


def test_validate_workspace_suspicious_interactive(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    with (
        patch("scc_cli.application.workspace.use_cases.is_suspicious_directory", return_value=True),
        patch(
            "scc_cli.application.workspace.use_cases.get_suspicious_reason", return_value="Reason"
        ),
    ):
        result = validate_workspace(
            str(workspace),
            allow_suspicious=False,
            interactive_allowed=True,
            platform_probe=FakePlatformProbe(is_wsl2=False, is_optimal=True),
        )

    assert result is not None
    assert result.workspace_path == workspace.resolve()
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.warning.title == "Suspicious Workspace"
    assert step.warning.message == "Reason"
    assert step.warning.emit_stderr is False
    assert step.confirm_request is not None
    assert step.confirm_request.prompt == "Continue anyway?"


def test_validate_workspace_suspicious_allow_flag(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    with (
        patch("scc_cli.application.workspace.use_cases.is_suspicious_directory", return_value=True),
        patch(
            "scc_cli.application.workspace.use_cases.get_suspicious_reason", return_value="Reason"
        ),
    ):
        result = validate_workspace(
            str(workspace),
            allow_suspicious=True,
            interactive_allowed=True,
            platform_probe=FakePlatformProbe(is_wsl2=False, is_optimal=True),
        )

    assert result is not None
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.warning.emit_stderr is True
    assert step.confirm_request is None


def test_validate_workspace_suspicious_non_interactive_raises(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    with (
        patch("scc_cli.application.workspace.use_cases.is_suspicious_directory", return_value=True),
        patch(
            "scc_cli.application.workspace.use_cases.get_suspicious_reason", return_value="Reason"
        ),
    ):
        with pytest.raises(UsageError) as excinfo:
            validate_workspace(
                str(workspace),
                allow_suspicious=False,
                interactive_allowed=False,
                platform_probe=FakePlatformProbe(is_wsl2=False, is_optimal=True),
            )

    assert "Refusing to start in suspicious directory" in str(excinfo.value)


def test_validate_workspace_wsl_warning_interactive(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    result = validate_workspace(
        str(workspace),
        allow_suspicious=False,
        interactive_allowed=True,
        platform_probe=FakePlatformProbe(is_wsl2=True, is_optimal=False),
    )

    assert result is not None
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.warning.title == "Performance Warning"
    assert step.warning.emit_stderr is True
    assert step.confirm_request is not None
