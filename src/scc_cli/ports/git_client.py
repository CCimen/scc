"""Git client port definition."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from scc_cli.services.git.worktree import WorktreeInfo


class GitClient(Protocol):
    """Abstract git operations used by application logic."""

    def check_available(self) -> None:
        """Ensure git is installed and available."""
        ...

    def check_installed(self) -> bool:
        """Return True if git is available."""
        ...

    def get_version(self) -> str | None:
        """Return the git version string."""
        ...

    def is_git_repo(self, path: Path) -> bool:
        """Return True if the path is within a git repository."""
        ...

    def init_repo(self, path: Path) -> bool:
        """Initialize a git repository."""
        ...

    def create_empty_initial_commit(self, path: Path) -> tuple[bool, str | None]:
        """Create an empty initial commit if needed."""
        ...

    def detect_workspace_root(self, start_dir: Path) -> tuple[Path | None, Path]:
        """Detect the git workspace root from a starting directory."""
        ...

    def get_current_branch(self, path: Path) -> str | None:
        """Return the current branch name."""
        ...

    def has_commits(self, path: Path) -> bool:
        """Return True if the repository has at least one commit."""
        ...

    def has_remote(self, path: Path) -> bool:
        """Return True if the repository has a remote origin."""
        ...

    def get_default_branch(self, path: Path) -> str:
        """Return the default branch name for a repository."""
        ...

    def list_worktrees(self, path: Path) -> list[WorktreeInfo]:
        """Return the worktrees configured for the repository."""
        ...

    def get_worktree_status(self, path: Path) -> tuple[int, int, int, bool]:
        """Return (staged, modified, untracked, timed_out) for a worktree."""
        ...

    def find_worktree_by_query(
        self,
        path: Path,
        query: str,
    ) -> tuple[WorktreeInfo | None, list[WorktreeInfo]]:
        """Find a worktree by name, branch, or path using fuzzy matching."""
        ...

    def find_main_worktree(self, path: Path) -> WorktreeInfo | None:
        """Return the worktree for the default/main branch if present."""
        ...

    def list_branches_without_worktrees(self, path: Path) -> list[str]:
        """Return remote branches that do not have worktrees."""
        ...

    def fetch_branch(self, path: Path, branch: str) -> None:
        """Fetch a branch from the remote origin if available."""
        ...

    def add_worktree(
        self,
        repo_path: Path,
        worktree_path: Path,
        branch_name: str,
        base_branch: str,
    ) -> None:
        """Create a worktree directory for the given branch."""
        ...

    def remove_worktree(self, repo_path: Path, worktree_path: Path, *, force: bool) -> None:
        """Remove a worktree from the repository."""
        ...

    def prune_worktrees(self, repo_path: Path) -> None:
        """Prune stale worktree metadata from the repository."""
        ...
