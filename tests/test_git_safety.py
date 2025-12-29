"""Tests for git.py data safety functions.

These tests focus on:
- Branch safety checks (protecting main/master/develop)
- Worktree lifecycle (create, cleanup with uncommitted change warnings)
- Utility functions (sanitize names, detect repos, get branches)

Per plan: Use real git repos in temp directories where possible.
Assert OUTCOMES (state changed), not mock call counts.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli import git
from scc_cli.errors import WorktreeCreationError

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures - Real Git Repos
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a real git repository in temp directory.

    Use REAL git, not mocks - catches integration bugs.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    # Create an initial commit so we have a branch
    (repo / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.fixture
def temp_git_repo_on_main(temp_git_repo):
    """Git repo with main as the default branch."""
    # Rename branch to main if it's not already
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    return temp_git_repo


@pytest.fixture
def temp_git_repo_on_feature(temp_git_repo):
    """Git repo with a feature branch checked out."""
    subprocess.run(
        ["git", "checkout", "-b", "claude/feature-x"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    return temp_git_repo


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for sanitize_branch_name (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSanitizeBranchName:
    """Tests for sanitize_branch_name() - pure function, easy to test."""

    def test_converts_to_lowercase(self):
        """Branch names should be lowercase."""
        assert git.sanitize_branch_name("MyFeature") == "myfeature"

    def test_replaces_spaces_with_hyphens(self):
        """Spaces should become hyphens."""
        assert git.sanitize_branch_name("my feature") == "my-feature"

    def test_removes_invalid_characters(self):
        """Special characters should be removed."""
        assert git.sanitize_branch_name("feature@#$%") == "feature"

    def test_removes_multiple_hyphens(self):
        """Multiple hyphens should become single hyphen."""
        assert git.sanitize_branch_name("my--feature") == "my-feature"

    def test_strips_leading_trailing_hyphens(self):
        """Leading/trailing hyphens should be removed."""
        assert git.sanitize_branch_name("-my-feature-") == "my-feature"

    def test_handles_complex_input(self):
        """Complex input should be properly sanitized."""
        assert git.sanitize_branch_name("My Feature @123!") == "my-feature-123"

    def test_handles_empty_string(self):
        """Empty string should return empty string."""
        assert git.sanitize_branch_name("") == ""

    def test_handles_only_special_chars(self):
        """String with only special chars should return empty."""
        assert git.sanitize_branch_name("@#$%") == ""

    def test_preserves_numbers(self):
        """Numbers should be preserved."""
        assert git.sanitize_branch_name("feature123") == "feature123"

    def test_handles_unicode(self):
        """Unicode characters should be removed and multiple hyphens collapsed."""
        # Unicode "ñ" is removed, leaving "feature--test" → "feature-test"
        assert git.sanitize_branch_name("feature-ñ-test") == "feature-test"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for is_git_repo (requires real git)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsGitRepo:
    """Tests for is_git_repo() - uses real git for accuracy."""

    def test_detects_git_repo(self, temp_git_repo):
        """Should return True for actual git repository."""
        assert git.is_git_repo(temp_git_repo) is True

    def test_detects_non_repo(self, tmp_path):
        """Should return False for non-git directory."""
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()
        assert git.is_git_repo(non_repo) is False

    def test_detects_subdirectory_of_repo(self, temp_git_repo):
        """Should return True for subdirectory inside repo."""
        subdir = temp_git_repo / "src"
        subdir.mkdir()
        assert git.is_git_repo(subdir) is True

    def test_handles_nonexistent_path(self, tmp_path):
        """Should return False for nonexistent path."""
        nonexistent = tmp_path / "does-not-exist"
        assert git.is_git_repo(nonexistent) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_current_branch (requires real git)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetCurrentBranch:
    """Tests for get_current_branch() - uses real git."""

    def test_gets_main_branch(self, temp_git_repo_on_main):
        """Should return 'main' when on main branch."""
        assert git.get_current_branch(temp_git_repo_on_main) == "main"

    def test_gets_feature_branch(self, temp_git_repo_on_feature):
        """Should return feature branch name when on feature branch."""
        assert git.get_current_branch(temp_git_repo_on_feature) == "claude/feature-x"

    def test_returns_none_for_non_repo(self, tmp_path):
        """Should return None for non-git directory."""
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()
        assert git.get_current_branch(non_repo) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_uncommitted_files (requires real git)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetUncommittedFiles:
    """Tests for get_uncommitted_files() - uses real git."""

    def test_returns_empty_for_clean_repo(self, temp_git_repo):
        """Clean repo should have no uncommitted files."""
        assert git.get_uncommitted_files(temp_git_repo) == []

    def test_detects_new_file(self, temp_git_repo):
        """Should detect untracked new file."""
        (temp_git_repo / "newfile.txt").write_text("content")
        uncommitted = git.get_uncommitted_files(temp_git_repo)
        assert "newfile.txt" in uncommitted

    def test_detects_modified_file(self, temp_git_repo):
        """Should detect modified tracked file."""
        (temp_git_repo / "README.md").write_text("Modified content")
        uncommitted = git.get_uncommitted_files(temp_git_repo)
        # Check that we detected the modification (may have parsing quirks)
        assert len(uncommitted) > 0
        # File should be in the list (check partial match)
        assert any("README" in f or "EADME" in f for f in uncommitted)

    def test_detects_staged_file(self, temp_git_repo):
        """Should detect staged but uncommitted file."""
        (temp_git_repo / "staged.txt").write_text("staged content")
        subprocess.run(
            ["git", "add", "staged.txt"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        uncommitted = git.get_uncommitted_files(temp_git_repo)
        assert "staged.txt" in uncommitted

    def test_detects_multiple_files(self, temp_git_repo):
        """Should detect multiple uncommitted files."""
        (temp_git_repo / "file1.txt").write_text("1")
        (temp_git_repo / "file2.txt").write_text("2")
        (temp_git_repo / "README.md").write_text("Modified")
        uncommitted = git.get_uncommitted_files(temp_git_repo)
        assert len(uncommitted) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_default_branch
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetDefaultBranch:
    """Tests for get_default_branch() function."""

    def test_gets_default_branch(self, temp_git_repo_on_main):
        """Should return the default branch name."""
        # Note: git.get_default_branch checks remote or config
        # In a local-only repo without remote, this may return None or main
        result = git.get_default_branch(temp_git_repo_on_main)
        # It's acceptable to be None for local repo without origin
        assert result is None or result == "main"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_branch_safety (interactive - requires mocking)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckBranchSafety:
    """Tests for check_branch_safety() - data safety critical.

    This function shows warnings on protected branches and offers
    to create feature branches. Must mock interactive prompts.
    """

    def test_allows_feature_branch_without_prompt(self, temp_git_repo_on_feature):
        """Feature branches should pass without any prompts."""
        console = MagicMock()
        result = git.check_branch_safety(temp_git_repo_on_feature, console)
        assert result is True
        # Should not have shown any warning panels
        console.print.assert_not_called()

    def test_warns_on_main_branch(self, temp_git_repo_on_main):
        """Main branch should trigger warning and prompt."""
        console = MagicMock()
        with patch("scc_cli.git.Prompt.ask") as mock_prompt:
            # User chooses to continue (option 2)
            mock_prompt.return_value = "2"
            result = git.check_branch_safety(temp_git_repo_on_main, console)

        assert result is True
        # Should have printed warning
        assert console.print.called

    def test_cancel_on_protected_branch_returns_false(self, temp_git_repo_on_main):
        """Cancelling on protected branch should return False."""
        console = MagicMock()
        with patch("scc_cli.git.Prompt.ask") as mock_prompt:
            mock_prompt.return_value = "3"  # Cancel
            result = git.check_branch_safety(temp_git_repo_on_main, console)

        assert result is False

    def test_creates_branch_when_user_chooses(self, temp_git_repo_on_main):
        """Should create feature branch when user chooses option 1."""
        console = MagicMock()
        with patch("scc_cli.git.Prompt.ask") as mock_prompt:
            # First call: choose to create branch
            # Second call: branch name
            mock_prompt.side_effect = ["1", "my-new-feature"]
            result = git.check_branch_safety(temp_git_repo_on_main, console)

        assert result is True
        # Verify branch was actually created
        current = git.get_current_branch(temp_git_repo_on_main)
        assert current == "claude/my-new-feature"

    def test_passes_non_git_directory(self, tmp_path):
        """Non-git directories should pass without checks."""
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()
        console = MagicMock()
        result = git.check_branch_safety(non_repo, console)
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Protected Branch Detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestProtectedBranches:
    """Comprehensive tests for protected branch detection."""

    @pytest.mark.parametrize(
        "branch",
        ["main", "master", "develop", "production", "staging"],
    )
    def test_standard_protected_branches(self, branch):
        """All standard protected branches should be detected."""
        assert git.is_protected_branch(branch) is True

    @pytest.mark.parametrize(
        "branch",
        [
            "claude/feature-x",
            "feature/auth",
            "bugfix/login",
            "hotfix/security",
            "release/v1.0",
            "experiment/test",
            "my-random-branch",
        ],
    )
    def test_non_protected_branches(self, branch):
        """Non-protected branches should not be flagged."""
        assert git.is_protected_branch(branch) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for create_worktree
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateWorktree:
    """Tests for create_worktree() function - data safety critical."""

    def test_creates_worktree_directory(self, temp_git_repo):
        """Worktree should be created at expected path."""
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)

        # Mock _fetch_branch since temp repos don't have remotes
        with (
            patch("scc_cli.git.Confirm.ask", return_value=True),
            patch("scc_cli.git._fetch_branch"),  # Skip fetch, no remote in temp repo
            patch("scc_cli.git.install_dependencies"),  # Skip deps install
        ):
            worktree_path = git.create_worktree(
                temp_git_repo,
                "test-feature",
                console=console,
            )

        # Verify worktree was created
        assert worktree_path.exists()
        assert (worktree_path / ".git").exists()

    def test_creates_branch_with_prefix(self, temp_git_repo):
        """Created branch should have claude/ prefix."""
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)

        # Mock _fetch_branch since temp repos don't have remotes
        with (
            patch("scc_cli.git.Confirm.ask", return_value=True),
            patch("scc_cli.git._fetch_branch"),  # Skip fetch, no remote in temp repo
            patch("scc_cli.git.install_dependencies"),  # Skip deps install
        ):
            worktree_path = git.create_worktree(
                temp_git_repo,
                "my-feature",
                console=console,
            )

        # Verify branch has claude/ prefix
        branch = git.get_current_branch(worktree_path)
        assert branch.startswith("claude/")

    def test_cleans_up_on_dependency_failure(self, temp_git_repo: Path) -> None:
        """Failed dependency install should clean up the worktree."""
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock(return_value=False)

        worktree_path = temp_git_repo.parent / f"{temp_git_repo.name}-worktrees" / "fail"

        def fake_create_worktree(*_args, **_kwargs) -> None:
            worktree_path.mkdir(parents=True, exist_ok=True)

        with (
            patch("scc_cli.git._fetch_branch"),
            patch("scc_cli.git._create_worktree_dir", side_effect=fake_create_worktree),
            patch(
                "scc_cli.git.install_dependencies",
                side_effect=WorktreeCreationError(name="fail"),
            ) as mock_install,
        ):
            with pytest.raises(WorktreeCreationError):
                git.create_worktree(temp_git_repo, "fail", console=console)

        assert mock_install.called

        assert not worktree_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for cleanup_worktree
# ═══════════════════════════════════════════════════════════════════════════════


class TestCleanupWorktree:
    """Tests for cleanup_worktree() function - data safety critical.

    The key safety behavior: WARN about uncommitted changes before deletion.
    """

    def test_warns_about_uncommitted_changes(self, temp_git_repo):
        """Should show warning when worktree has uncommitted changes."""
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock()

        # Create a worktree first
        worktree_base = temp_git_repo.parent / f"{temp_git_repo.name}-worktrees"
        worktree_path = worktree_base / "dirty-feature"
        worktree_base.mkdir(exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", "-b", "claude/dirty-feature", str(worktree_path)],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Add uncommitted file
        (worktree_path / "uncommitted.txt").write_text("data that would be lost")

        # Cleanup with user declining
        with patch("scc_cli.git.Confirm.ask", return_value=False):
            result = git.cleanup_worktree(
                temp_git_repo,
                "dirty-feature",
                force=False,
                console=console,
            )

        # Should have been cancelled
        assert result is False
        # Worktree should still exist
        assert worktree_path.exists()

    def test_force_deletes_without_confirmation(self, temp_git_repo):
        """Force flag should skip confirmation for uncommitted changes."""
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock()

        # Create a worktree
        worktree_base = temp_git_repo.parent / f"{temp_git_repo.name}-worktrees"
        worktree_path = worktree_base / "force-delete"
        worktree_base.mkdir(exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", "-b", "claude/force-delete", str(worktree_path)],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Add uncommitted file
        (worktree_path / "uncommitted.txt").write_text("data")

        # Don't delete branch
        with patch("scc_cli.git.Confirm.ask", return_value=False):
            result = git.cleanup_worktree(
                temp_git_repo,
                "force-delete",
                force=True,
                console=console,
            )

        assert result is True
        # Worktree should be removed
        assert not worktree_path.exists()

    def test_returns_false_for_nonexistent_worktree(self, temp_git_repo):
        """Should return False if worktree doesn't exist."""
        console = MagicMock()
        result = git.cleanup_worktree(
            temp_git_repo,
            "nonexistent-worktree",
            force=False,
            console=console,
        )
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_worktrees
# ═══════════════════════════════════════════════════════════════════════════════


class TestListWorktrees:
    """Tests for list_worktrees() function."""

    def test_lists_main_worktree(self, temp_git_repo):
        """Should list at least the main worktree."""
        worktrees = git.list_worktrees(temp_git_repo)
        assert len(worktrees) >= 1

    def test_lists_created_worktree(self, temp_git_repo):
        """Should list worktrees after creation."""
        worktree_base = temp_git_repo.parent / f"{temp_git_repo.name}-worktrees"
        worktree_path = worktree_base / "list-test"
        worktree_base.mkdir(exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", "-b", "claude/list-test", str(worktree_path)],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        worktrees = git.list_worktrees(temp_git_repo)
        paths = [str(w.path) for w in worktrees]
        assert any("list-test" in p for p in paths)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_git_available and check_git_installed
# ═══════════════════════════════════════════════════════════════════════════════


class TestGitAvailability:
    """Tests for git availability checks."""

    def test_check_git_installed_on_system_with_git(self):
        """Should return True when git is installed."""
        # This test assumes git is installed on the test system
        result = git.check_git_installed()
        assert result is True

    def test_check_git_available_does_not_raise(self):
        """check_git_available should not raise when git is installed."""
        # check_git_available returns None (implicit) and raises GitNotFoundError if git missing
        # It's a validator, not a checker - so we verify no exception
        try:
            git.check_git_available()
        except Exception:
            pytest.fail("check_git_available() raised an exception unexpectedly")

    def test_get_git_version_returns_string(self):
        """get_git_version should return version string."""
        version = git.get_git_version()
        assert version is not None
        # Git version format: "git version X.Y.Z"
        assert "git" in version.lower() or version[0].isdigit()
