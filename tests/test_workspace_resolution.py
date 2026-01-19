from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scc_cli.application.workspace import ResolveWorkspaceRequest, resolve_workspace


def test_resolve_explicit_workspace_arg(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()

    result = resolve_workspace(ResolveWorkspaceRequest(cwd=tmp_path, workspace_arg="project"))

    assert result is not None
    assert result.workspace_root == workspace.resolve()
    assert result.entry_dir == tmp_path.resolve()
    assert result.is_auto_detected is False
    assert result.reason.startswith("Explicit --workspace")


def test_resolve_prefers_git_over_scc_yaml(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".scc.yaml").write_text("# config")

    with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=project):
        result = resolve_workspace(ResolveWorkspaceRequest(cwd=project, workspace_arg=None))

    assert result is not None
    assert result.workspace_root == project
    assert result.reason.startswith("Git repository detected")


def test_resolve_uses_scc_yaml_when_no_git(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".scc.yaml").write_text("# config")

    with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
        result = resolve_workspace(ResolveWorkspaceRequest(cwd=project, workspace_arg=None))

    assert result is not None
    assert result.workspace_root == project
    assert result.reason.startswith(".scc.yaml found")


def test_resolve_returns_none_without_workspace(tmp_path: Path) -> None:
    with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
        result = resolve_workspace(ResolveWorkspaceRequest(cwd=tmp_path, workspace_arg=None))

    assert result is None
