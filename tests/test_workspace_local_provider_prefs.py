"""Tests for workspace-local provider preferences."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scc_cli.workspace_local_config import (
    WORKSPACE_CONFIG_DIRNAME,
    WORKSPACE_CONFIG_FILENAME,
    get_workspace_last_used_provider,
    get_workspace_local_config_path,
    set_workspace_last_used_provider,
)


def test_workspace_config_path_points_to_local_scc_file(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()

    assert get_workspace_local_config_path(workspace) == (
        workspace / WORKSPACE_CONFIG_DIRNAME / WORKSPACE_CONFIG_FILENAME
    )


def test_workspace_last_used_provider_defaults_to_none(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()

    assert get_workspace_last_used_provider(workspace) is None


def test_set_workspace_last_used_provider_persists_local_state(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()

    set_workspace_last_used_provider(workspace, "codex")

    path = get_workspace_local_config_path(workspace)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["last_used_provider"] == "codex"
    assert get_workspace_last_used_provider(workspace) == "codex"


def test_set_workspace_last_used_provider_preserves_other_local_keys(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    path = workspace / WORKSPACE_CONFIG_DIRNAME / WORKSPACE_CONFIG_FILENAME
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"last_used_provider": "claude", "other_local_setting": True}),
        encoding="utf-8",
    )

    set_workspace_last_used_provider(workspace, "codex")

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["last_used_provider"] == "codex"
    assert on_disk["other_local_setting"] is True


@patch("scc_cli.workspace_local_config.subprocess.run")
def test_setting_workspace_provider_best_effort_updates_git_exclude(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    exclude_path = workspace / ".git" / "info" / "exclude"

    def _side_effect(cmd: list[str], **_kwargs: object) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        if "rev-parse" in cmd:
            result.stdout = f"{exclude_path}\n"
        else:
            result.stdout = ""
        return result

    mock_run.side_effect = _side_effect

    set_workspace_last_used_provider(workspace, "codex")

    assert mock_run.call_count == 1
    assert exclude_path.read_text(encoding="utf-8").splitlines() == [".scc/"]


@patch("scc_cli.workspace_local_config.subprocess.run")
def test_setting_workspace_provider_ignores_git_exclude_failures(
    mock_run: MagicMock, tmp_path: Path
) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()

    mock_run.side_effect = OSError("git unavailable")

    set_workspace_last_used_provider(workspace, "claude")

    assert get_workspace_last_used_provider(workspace) == "claude"
