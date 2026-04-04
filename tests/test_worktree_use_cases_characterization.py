"""Characterization tests for application/worktree/use_cases.py.

Lock the current behavior of pure domain logic — selection item building,
shell command resolution, summary construction, and request-to-outcome
routing — before S02 surgery begins.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from scc_cli.application.worktree.use_cases import (
    WorktreeConfirmAction,
    WorktreeConfirmation,
    WorktreeDependencies,
    WorktreeEnterRequest,
    WorktreeListRequest,
    WorktreeResolution,
    WorktreeSelectionItem,
    WorktreeSelectionPrompt,
    WorktreeSelectRequest,
    WorktreeShellResult,
    WorktreeSummary,
    WorktreeWarningOutcome,
    _build_selection_items,
    _build_shell_result,
    list_worktrees,
    select_worktree,
)
from scc_cli.core.exit_codes import EXIT_CANCELLED
from scc_cli.services.git.worktree import WorktreeInfo

# ═══════════════════════════════════════════════════════════════════════════════
# WorktreeSummary.from_info
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeSummaryFromInfo:
    """WorktreeSummary.from_info factory method."""

    def test_basic_construction(self) -> None:
        info = WorktreeInfo(
            path="/tmp/test-wt",
            branch="feature/foo",
            status="clean",
            is_current=False,
            has_changes=False,
            staged_count=0,
            modified_count=0,
            untracked_count=0,
            status_timed_out=False,
        )
        summary = WorktreeSummary.from_info(
            info,
            path=Path("/tmp/test-wt"),
            is_current=True,
            staged_count=2,
            modified_count=1,
            untracked_count=3,
            status_timed_out=False,
            has_changes=True,
        )
        assert summary.path == Path("/tmp/test-wt")
        assert summary.branch == "feature/foo"
        assert summary.is_current is True
        assert summary.staged_count == 2
        assert summary.modified_count == 1
        assert summary.untracked_count == 3
        assert summary.has_changes is True


# ═══════════════════════════════════════════════════════════════════════════════
# _build_selection_items
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildSelectionItems:
    """Selection item assembly from worktrees and branches."""

    def _make_summary(self, path: str, branch: str) -> WorktreeSummary:
        return WorktreeSummary(
            path=Path(path),
            branch=branch,
            status="clean",
            is_current=False,
            has_changes=False,
            staged_count=0,
            modified_count=0,
            untracked_count=0,
            status_timed_out=False,
        )

    def test_worktrees_only(self) -> None:
        summaries = [self._make_summary("/tmp/wt1", "main")]
        items = _build_selection_items(summaries, [])
        assert len(items) == 1
        assert items[0].is_branch_only is False
        assert items[0].item_id == "worktree:/tmp/wt1"

    def test_branches_only(self) -> None:
        items = _build_selection_items([], ["feature/x", "feature/y"])
        assert len(items) == 2
        assert all(i.is_branch_only for i in items)
        assert items[0].item_id == "branch:feature/x"

    def test_mixed_worktrees_and_branches(self) -> None:
        summaries = [self._make_summary("/tmp/wt1", "main")]
        items = _build_selection_items(summaries, ["feature/x"])
        assert len(items) == 2
        assert items[0].is_branch_only is False
        assert items[1].is_branch_only is True

    def test_empty_inputs(self) -> None:
        items = _build_selection_items([], [])
        assert items == []


# ═══════════════════════════════════════════════════════════════════════════════
# _build_shell_result
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildShellResult:
    """Shell resolution for worktree entry."""

    def _make_selection(self, path: str, branch: str) -> WorktreeSelectionItem:
        return WorktreeSelectionItem(
            item_id=f"worktree:{path}",
            branch=branch,
            worktree=WorktreeSummary(
                path=Path(path),
                branch=branch,
                status="clean",
                is_current=False,
                has_changes=False,
                staged_count=0,
                modified_count=0,
                untracked_count=0,
                status_timed_out=False,
            ),
            is_branch_only=False,
        )

    def test_linux_shell_resolution(self, tmp_path: Path) -> None:
        wt_path = tmp_path / "my-wt"
        wt_path.mkdir()
        selection = self._make_selection(str(wt_path), "feature/x")
        request = WorktreeEnterRequest(
            workspace_path=tmp_path,
            target=None,
            oldpwd=None,
            interactive_allowed=True,
            current_dir=tmp_path,
            env={"SHELL": "/bin/zsh"},
            platform_system="Linux",
        )
        result = _build_shell_result(request, selection)
        assert isinstance(result, WorktreeShellResult)
        assert result.shell_command.argv == ["/bin/zsh"]
        assert result.shell_command.workdir == wt_path
        assert result.shell_command.env["SCC_WORKTREE"] == "feature/x"

    def test_windows_shell_resolution(self, tmp_path: Path) -> None:
        wt_path = tmp_path / "my-wt"
        wt_path.mkdir()
        selection = self._make_selection(str(wt_path), "feature/x")
        request = WorktreeEnterRequest(
            workspace_path=tmp_path,
            target=None,
            oldpwd=None,
            interactive_allowed=True,
            current_dir=tmp_path,
            env={"COMSPEC": "C:\\Windows\\cmd.exe"},
            platform_system="Windows",
        )
        result = _build_shell_result(request, selection)
        assert isinstance(result, WorktreeShellResult)
        assert result.shell_command.argv == ["C:\\Windows\\cmd.exe"]

    def test_missing_worktree_path(self, tmp_path: Path) -> None:
        # Path that doesn't exist
        missing_path = str(tmp_path / "nonexistent")
        selection = self._make_selection(missing_path, "feature/gone")
        request = WorktreeEnterRequest(
            workspace_path=tmp_path,
            target=None,
            oldpwd=None,
            interactive_allowed=True,
            current_dir=tmp_path,
            env={},
            platform_system="Linux",
        )
        result = _build_shell_result(request, selection)
        assert isinstance(result, WorktreeWarningOutcome)
        assert "missing" in result.warning.title.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# list_worktrees
# ═══════════════════════════════════════════════════════════════════════════════


class TestListWorktrees:
    """Worktree listing via git client."""

    def _make_git_client(self, worktrees: list[WorktreeInfo]) -> MagicMock:
        client = MagicMock()
        client.list_worktrees.return_value = worktrees
        client.get_worktree_status.return_value = (0, 0, 0, False)
        return client

    def test_empty_repo(self, tmp_path: Path) -> None:
        client = self._make_git_client([])
        request = WorktreeListRequest(workspace_path=tmp_path, verbose=False, current_dir=tmp_path)
        result = list_worktrees(request, git_client=client)
        assert result.worktrees == ()

    def test_single_worktree(self, tmp_path: Path) -> None:
        info = WorktreeInfo(
            path=str(tmp_path),
            branch="main",
            status="clean",
            is_current=True,
            has_changes=False,
            staged_count=0,
            modified_count=0,
            untracked_count=0,
            status_timed_out=False,
        )
        client = self._make_git_client([info])
        request = WorktreeListRequest(workspace_path=tmp_path, verbose=False, current_dir=tmp_path)
        result = list_worktrees(request, git_client=client)
        assert len(result.worktrees) == 1
        assert result.worktrees[0].branch == "main"

    def test_verbose_queries_status(self, tmp_path: Path) -> None:
        info = WorktreeInfo(
            path=str(tmp_path),
            branch="main",
            status="clean",
            is_current=True,
            has_changes=False,
            staged_count=0,
            modified_count=0,
            untracked_count=0,
            status_timed_out=False,
        )
        client = self._make_git_client([info])
        client.get_worktree_status.return_value = (3, 2, 1, False)
        request = WorktreeListRequest(workspace_path=tmp_path, verbose=True, current_dir=tmp_path)
        result = list_worktrees(request, git_client=client)
        wt = result.worktrees[0]
        assert wt.staged_count == 3
        assert wt.modified_count == 2
        assert wt.untracked_count == 1
        assert wt.has_changes is True


# ═══════════════════════════════════════════════════════════════════════════════
# select_worktree — resolution paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectWorktreeResolution:
    """Selection resolution outcomes: resolve, confirm, cancel."""

    def _make_deps(self) -> WorktreeDependencies:
        git = MagicMock()
        git.is_git_repo.return_value = True
        git.list_worktrees.return_value = []
        git.list_branches_without_worktrees.return_value = []
        installer = MagicMock()
        return WorktreeDependencies(git_client=git, dependency_installer=installer)

    def test_worktree_selection_resolves_directly(self, tmp_path: Path) -> None:
        deps = self._make_deps()
        selection = WorktreeSelectionItem(
            item_id="worktree:/tmp/wt",
            branch="main",
            worktree=WorktreeSummary(
                path=tmp_path,
                branch="main",
                status="clean",
                is_current=False,
                has_changes=False,
                staged_count=0,
                modified_count=0,
                untracked_count=0,
                status_timed_out=False,
            ),
            is_branch_only=False,
        )
        request = WorktreeSelectRequest(
            workspace_path=tmp_path,
            include_branches=False,
            current_dir=tmp_path,
            selection=selection,
        )
        result = select_worktree(request, dependencies=deps)
        assert isinstance(result, WorktreeResolution)
        assert result.worktree_path == tmp_path

    def test_branch_selection_prompts_confirmation(self, tmp_path: Path) -> None:
        deps = self._make_deps()
        selection = WorktreeSelectionItem(
            item_id="branch:feature/x",
            branch="feature/x",
            worktree=None,
            is_branch_only=True,
        )
        request = WorktreeSelectRequest(
            workspace_path=tmp_path,
            include_branches=True,
            current_dir=tmp_path,
            selection=selection,
            confirm_create=None,  # No confirmation yet
        )
        result = select_worktree(request, dependencies=deps)
        assert isinstance(result, WorktreeConfirmation)
        assert result.action == WorktreeConfirmAction.CREATE_WORKTREE
        assert result.branch_name == "feature/x"

    def test_branch_selection_cancelled(self, tmp_path: Path) -> None:
        deps = self._make_deps()
        selection = WorktreeSelectionItem(
            item_id="branch:feature/x",
            branch="feature/x",
            worktree=None,
            is_branch_only=True,
        )
        request = WorktreeSelectRequest(
            workspace_path=tmp_path,
            include_branches=True,
            current_dir=tmp_path,
            selection=selection,
            confirm_create=False,
        )
        result = select_worktree(request, dependencies=deps)
        assert isinstance(result, WorktreeWarningOutcome)
        assert result.exit_code == EXIT_CANCELLED

    def test_no_selection_shows_prompt(self, tmp_path: Path) -> None:
        deps = self._make_deps()
        deps.git_client.list_worktrees.return_value = [
            WorktreeInfo(
                path=str(tmp_path),
                branch="main",
                status="clean",
                is_current=True,
                has_changes=False,
                staged_count=0,
                modified_count=0,
                untracked_count=0,
                status_timed_out=False,
            )
        ]
        request = WorktreeSelectRequest(
            workspace_path=tmp_path,
            include_branches=False,
            current_dir=tmp_path,
        )
        result = select_worktree(request, dependencies=deps)
        assert isinstance(result, WorktreeSelectionPrompt)

    def test_empty_repo_warning(self, tmp_path: Path) -> None:
        deps = self._make_deps()
        request = WorktreeSelectRequest(
            workspace_path=tmp_path,
            include_branches=True,
            current_dir=tmp_path,
        )
        result = select_worktree(request, dependencies=deps)
        assert isinstance(result, WorktreeWarningOutcome)
        assert "no worktrees" in result.warning.title.lower()
