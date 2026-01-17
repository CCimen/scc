"""Contract tests for GitClient implementations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scc_cli.adapters.local_git_client import LocalGitClient


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_git_client_detects_repo_and_branch(tmp_path: Path) -> None:
    client = LocalGitClient()
    repo = tmp_path / "repo"
    repo.mkdir()

    assert client.is_git_repo(repo) is False
    assert client.init_repo(repo) is True
    assert client.is_git_repo(repo) is True

    subdir = repo / "subdir"
    subdir.mkdir()

    root, start = client.detect_workspace_root(subdir)
    assert root == repo.resolve()
    assert start == subdir.resolve()

    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )

    branch = client.get_current_branch(repo)
    assert branch
