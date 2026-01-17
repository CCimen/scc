"""Tests for worktree application use cases."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from scc_cli.application.worktree import (
    WorktreeConfirmation,
    WorktreeCreateResult,
    WorktreeDependencies,
    WorktreeEnterRequest,
    WorktreeResolution,
    WorktreeSelectionItem,
    WorktreeSelectRequest,
    WorktreeShellResult,
    WorktreeSwitchRequest,
    WorktreeWarningOutcome,
    enter_worktree_shell,
    select_worktree,
    switch_worktree,
)
from scc_cli.core.exit_codes import EXIT_CANCELLED
from scc_cli.ports.dependency_installer import DependencyInstallResult
from scc_cli.ports.git_client import GitClient
from scc_cli.services.git.worktree import WorktreeInfo


def _make_dependencies() -> WorktreeDependencies:
    git_client = MagicMock(spec=GitClient)
    git_client.is_git_repo.return_value = True
    dependency_installer = MagicMock()
    dependency_installer.install.return_value = DependencyInstallResult(
        attempted=False,
        success=False,
    )
    return WorktreeDependencies(
        git_client=git_client,
        dependency_installer=dependency_installer,
    )


def test_switch_dash_returns_oldpwd(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    outcome = switch_worktree(
        WorktreeSwitchRequest(
            workspace_path=tmp_path,
            target="-",
            oldpwd=str(tmp_path / "previous"),
            interactive_allowed=True,
            current_dir=tmp_path,
        ),
        dependencies=dependencies,
    )
    assert isinstance(outcome, WorktreeResolution)
    assert outcome.worktree_path == tmp_path / "previous"


def test_switch_caret_without_main_warns(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    dependencies.git_client.find_main_worktree.return_value = None
    dependencies.git_client.get_default_branch.return_value = "main"

    outcome = switch_worktree(
        WorktreeSwitchRequest(
            workspace_path=tmp_path,
            target="^",
            oldpwd=None,
            interactive_allowed=True,
            current_dir=tmp_path,
        ),
        dependencies=dependencies,
    )

    assert isinstance(outcome, WorktreeWarningOutcome)
    assert outcome.warning.title == "No Main Worktree"


def test_switch_branch_without_worktree_prompts_and_creates(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    dependencies.git_client.find_worktree_by_query.return_value = (None, [])
    dependencies.git_client.list_branches_without_worktrees.return_value = ["feature-x"]
    dependencies.git_client.has_remote.return_value = False

    repo = tmp_path / "repo"
    repo.mkdir()

    first = switch_worktree(
        WorktreeSwitchRequest(
            workspace_path=repo,
            target="feature-x",
            oldpwd=None,
            interactive_allowed=True,
            current_dir=repo,
        ),
        dependencies=dependencies,
    )
    assert isinstance(first, WorktreeConfirmation)

    dependencies.git_client.add_worktree.return_value = None

    second = switch_worktree(
        WorktreeSwitchRequest(
            workspace_path=repo,
            target="feature-x",
            oldpwd=None,
            interactive_allowed=True,
            current_dir=repo,
            confirm_create=True,
        ),
        dependencies=dependencies,
    )
    assert isinstance(second, WorktreeCreateResult)
    assert second.branch_name.endswith("feature-x")


def test_switch_ambiguous_matches_noninteractive(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    matches = [
        WorktreeInfo(path=str(tmp_path / "feature"), branch="feature/auth", status=""),
        WorktreeInfo(path=str(tmp_path / "feature2"), branch="feature/login", status=""),
    ]
    dependencies.git_client.find_worktree_by_query.return_value = (None, matches)
    dependencies.git_client.list_branches_without_worktrees.return_value = []

    outcome = switch_worktree(
        WorktreeSwitchRequest(
            workspace_path=tmp_path,
            target="feature",
            oldpwd=None,
            interactive_allowed=False,
            current_dir=tmp_path,
        ),
        dependencies=dependencies,
    )

    assert isinstance(outcome, WorktreeWarningOutcome)
    assert outcome.warning.title == "Ambiguous Match"
    assert "best match" in (outcome.warning.suggestion or "")


def test_select_branch_requires_confirmation(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    selection = WorktreeSelectionItem(
        item_id="branch:feature-x",
        branch="feature-x",
        worktree=None,
        is_branch_only=True,
    )

    outcome = select_worktree(
        WorktreeSelectRequest(
            workspace_path=tmp_path,
            include_branches=True,
            current_dir=tmp_path,
            selection=selection,
        ),
        dependencies=dependencies,
    )

    assert isinstance(outcome, WorktreeConfirmation)
    assert outcome.request.prompt.startswith("Create worktree")


def test_enter_dash_builds_shell_command(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    previous = tmp_path / "previous"
    previous.mkdir()

    outcome = enter_worktree_shell(
        WorktreeEnterRequest(
            workspace_path=tmp_path,
            target="-",
            oldpwd=str(previous),
            interactive_allowed=True,
            current_dir=tmp_path,
            env={"SHELL": "/bin/bash"},
            platform_system="Linux",
        ),
        dependencies=dependencies,
    )

    assert isinstance(outcome, WorktreeShellResult)
    assert outcome.worktree_path == previous
    assert outcome.shell_command.workdir == previous
    assert outcome.shell_command.env["SCC_WORKTREE"] == "previous"


def test_switch_branch_cancel_returns_exit_cancelled(tmp_path: Path) -> None:
    dependencies = _make_dependencies()
    dependencies.git_client.find_worktree_by_query.return_value = (None, [])
    dependencies.git_client.list_branches_without_worktrees.return_value = ["feature-x"]

    outcome = switch_worktree(
        WorktreeSwitchRequest(
            workspace_path=tmp_path,
            target="feature-x",
            oldpwd=None,
            interactive_allowed=True,
            current_dir=tmp_path,
            confirm_create=False,
        ),
        dependencies=dependencies,
    )

    assert isinstance(outcome, WorktreeWarningOutcome)
    assert outcome.exit_code == EXIT_CANCELLED
