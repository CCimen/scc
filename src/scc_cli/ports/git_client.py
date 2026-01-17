"""Git client port definition."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GitClient(Protocol):
    """Abstract git operations used by application logic."""

    def check_available(self) -> None:
        """Ensure git is installed and available."""

    def check_installed(self) -> bool:
        """Return True if git is available."""

    def get_version(self) -> str | None:
        """Return the git version string."""

    def is_git_repo(self, path: Path) -> bool:
        """Return True if the path is within a git repository."""

    def init_repo(self, path: Path) -> bool:
        """Initialize a git repository."""

    def create_empty_initial_commit(self, path: Path) -> tuple[bool, str | None]:
        """Create an empty initial commit if needed."""

    def detect_workspace_root(self, start_dir: Path) -> tuple[Path | None, Path]:
        """Detect the git workspace root from a starting directory."""

    def get_current_branch(self, path: Path) -> str | None:
        """Return the current branch name."""
