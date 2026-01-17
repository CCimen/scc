"""Local git adapter for GitClient port."""

from __future__ import annotations

from pathlib import Path

from scc_cli.ports.git_client import GitClient
from scc_cli.services.git import branch as git_branch
from scc_cli.services.git import core as git_core


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
