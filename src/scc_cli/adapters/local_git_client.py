"""Local git adapter for GitClient port."""

from __future__ import annotations

from pathlib import Path

from scc_cli.ports.git_client import GitClient
from scc_cli.services.git import branch as git_branch
from scc_cli.services.git import core as git_core
from scc_cli.services.git import worktree as git_worktree


class LocalGitClient(GitClient):
    """Git client adapter backed by local git CLI."""

    def check_available(self) -> None:
        git_core.check_git_available()

    def check_installed(self) -> bool:
        return git_core.check_git_installed()

    def get_version(self) -> str | None:
        return git_core.get_git_version()

    def is_git_repo(self, path: Path) -> bool:
        return git_core.is_git_repo(path)

    def init_repo(self, path: Path) -> bool:
        return git_core.init_repo(path)

    def create_empty_initial_commit(self, path: Path) -> tuple[bool, str | None]:
        return git_core.create_empty_initial_commit(path)

    def detect_workspace_root(self, start_dir: Path) -> tuple[Path | None, Path]:
        return git_core.detect_workspace_root(start_dir)

    def get_current_branch(self, path: Path) -> str | None:
        return git_branch.get_current_branch(path)

    def has_commits(self, path: Path) -> bool:
        return git_core.has_commits(path)

    def has_remote(self, path: Path) -> bool:
        return git_core.has_remote(path)

    def get_default_branch(self, path: Path) -> str:
        return git_branch.get_default_branch(path)

    def list_worktrees(self, path: Path) -> list[git_worktree.WorktreeInfo]:
        return git_worktree.get_worktrees_data(path)

    def get_worktree_status(self, path: Path) -> tuple[int, int, int, bool]:
        return git_worktree.get_worktree_status(str(path))

    def find_worktree_by_query(
        self,
        path: Path,
        query: str,
    ) -> tuple[git_worktree.WorktreeInfo | None, list[git_worktree.WorktreeInfo]]:
        return git_worktree.find_worktree_by_query(path, query)

    def find_main_worktree(self, path: Path) -> git_worktree.WorktreeInfo | None:
        return git_worktree.find_main_worktree(path)

    def list_branches_without_worktrees(self, path: Path) -> list[str]:
        return git_branch.list_branches_without_worktrees(path)

    def fetch_branch(self, path: Path, branch: str) -> None:
        git_worktree.fetch_branch(path, branch)

    def add_worktree(
        self,
        repo_path: Path,
        worktree_path: Path,
        branch_name: str,
        base_branch: str,
    ) -> None:
        git_worktree.add_worktree(repo_path, worktree_path, branch_name, base_branch)

    def remove_worktree(self, repo_path: Path, worktree_path: Path, *, force: bool) -> None:
        git_worktree.remove_worktree(repo_path, worktree_path, force=force)

    def prune_worktrees(self, repo_path: Path) -> None:
        git_worktree.prune_worktrees(repo_path)
