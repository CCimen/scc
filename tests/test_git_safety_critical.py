"""Safety-critical tests for git.py - Expert-recommended high-risk function coverage.

Based on expert consultation with GPT-5.2 and Gemini-3-Pro-Preview, these tests focus on:

1. cleanup_worktree: The rmtree fallback path (lines 972-979)
   - RISK: shutil.rmtree can delete data if git worktree remove fails
   - REQUIRED: 100% branch coverage on destructive operation

2. get_workspace_mount_path: Docker mount security boundary
   - RISK: Mounting too broad a path exposes sensitive system files to Docker
   - REQUIRED: Parameterized tests for all blocked_roots entries

3. install_pre_push_hook: User hook overwrite prevention
   - RISK: Overwriting user's custom hooks causes data loss
   - REQUIRED: Test matrix for existing hook scenarios

Test philosophy (per expert consensus):
- Use real git repos with tmp_path, not mocks (catches integration bugs)
- Assert OUTCOMES (state changed), not mock call counts
- Test failure paths, not just happy paths
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli import git

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures for Real Git Operations
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def real_git_repo(tmp_path):
    """Create a REAL git repo for integration testing.

    Expert recommendation: Real git catches bugs that mocks miss.
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
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.fixture
def worktree_setup(real_git_repo):
    """Create a worktree for cleanup testing."""
    worktree_base = real_git_repo.parent / f"{real_git_repo.name}-worktrees"
    worktree_base.mkdir(exist_ok=True)
    worktree_path = worktree_base / "test-feature"

    subprocess.run(
        ["git", "worktree", "add", "-b", "claude/test-feature", str(worktree_path)],
        cwd=real_git_repo,
        check=True,
        capture_output=True,
    )

    return {
        "repo": real_git_repo,
        "worktree_base": worktree_base,
        "worktree_path": worktree_path,
        "worktree_name": "test-feature",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: cleanup_worktree rmtree Fallback Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCleanupWorktreeRmtreeFallback:
    """Tests for the dangerous rmtree fallback path in cleanup_worktree.

    Lines 972-979 contain:
        except subprocess.CalledProcessError:
            # Fallback: manual removal
            shutil.rmtree(worktree_path, ignore_errors=True)
            subprocess.run(["git", "worktree", "prune"], ...)

    This path is triggered when `git worktree remove` fails but we want
    to continue anyway. The rmtree is DESTRUCTIVE and must be tested.
    """

    def test_rmtree_fallback_triggered_when_git_worktree_remove_fails(self, worktree_setup):
        """When git worktree remove fails, rmtree fallback should execute.

        SAFETY TEST: Verify fallback actually removes the worktree directory.
        """
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock()

        worktree_path = worktree_setup["worktree_path"]
        repo = worktree_setup["repo"]

        # Verify worktree exists before cleanup
        assert worktree_path.exists()

        # Force the fallback by making git worktree remove fail
        # We do this by corrupting the worktree's .git file
        git_file = worktree_path / ".git"
        git_file.write_text("corrupted")  # Invalid gitdir pointer

        # Run cleanup with force=True (skips uncommitted change check)
        with patch("scc_cli.git.Confirm.ask", return_value=False):  # Don't delete branch
            result = git.cleanup_worktree(
                repo,
                worktree_setup["worktree_name"],
                force=True,
                console=console,
            )

        # OUTCOME ASSERTION: worktree directory should be removed by rmtree
        assert result is True
        assert not worktree_path.exists(), "rmtree fallback should have removed worktree"

    def test_rmtree_fallback_does_not_affect_main_repo(self, worktree_setup):
        """rmtree fallback must NOT touch the main repository.

        SAFETY TEST: Main repo integrity after worktree cleanup.
        """
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock()

        repo = worktree_setup["repo"]
        worktree_path = worktree_setup["worktree_path"]

        # Add a file to main repo to verify it's not touched
        test_file = repo / "important.txt"
        test_file.write_text("important data")

        # Corrupt worktree to trigger rmtree fallback
        (worktree_path / ".git").write_text("corrupted")

        with patch("scc_cli.git.Confirm.ask", return_value=False):
            git.cleanup_worktree(
                repo,
                worktree_setup["worktree_name"],
                force=True,
                console=console,
            )

        # OUTCOME ASSERTION: Main repo and its files must be intact
        assert repo.exists()
        assert (repo / ".git").exists()
        assert test_file.exists()
        assert test_file.read_text() == "important data"

    def test_rmtree_handles_worktree_with_uncommitted_changes_when_forced(self, worktree_setup):
        """Force flag should allow rmtree to delete worktree with uncommitted changes.

        SAFETY TEST: Verify data loss warning path works correctly.
        """
        console = MagicMock()
        console.status.return_value.__enter__ = MagicMock()
        console.status.return_value.__exit__ = MagicMock()

        worktree_path = worktree_setup["worktree_path"]

        # Add uncommitted data that WILL be lost
        uncommitted_file = worktree_path / "uncommitted.txt"
        uncommitted_file.write_text("data that will be lost")

        # Force cleanup (skips confirmation)
        with patch("scc_cli.git.Confirm.ask", return_value=False):
            result = git.cleanup_worktree(
                worktree_setup["repo"],
                worktree_setup["worktree_name"],
                force=True,
                console=console,
            )

        # OUTCOME ASSERTION: File should be deleted
        assert result is True
        assert not uncommitted_file.exists()
        assert not worktree_path.exists()

    def test_cleanup_nonexistent_worktree_returns_false(self, real_git_repo):
        """Attempting to clean up non-existent worktree should fail gracefully."""
        console = MagicMock()

        result = git.cleanup_worktree(
            real_git_repo,
            "nonexistent-worktree",
            force=False,
            console=console,
        )

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: get_workspace_mount_path Security Boundary Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetWorkspaceMountPathSecurity:
    """Parameterized tests for Docker mount security boundary.

    The blocked_roots blocklist (lines 345-377) prevents mounting sensitive
    system directories into Docker. Each entry MUST be tested.

    Expert recommendation: "100% branch coverage for security-critical functions"
    """

    @pytest.mark.parametrize(
        "blocked_path",
        [
            "/",
            "/home",
            "/Users",
            "/bin",
            "/boot",
            "/dev",
            "/etc",
            "/lib",
            "/lib64",
            "/opt",
            "/proc",
            "/root",
            "/run",
            "/sbin",
            "/srv",
            "/sys",
            "/usr",
            "/tmp",
            "/var",
            "/System",
            "/Library",
            "/Applications",
            "/Volumes",
            "/private",
            "/mnt",
        ],
    )
    def test_rejects_blocked_root_as_mount_point(self, blocked_path):
        """Each blocked root should be rejected as a mount point.

        SECURITY TEST: Prevents Docker from accessing system directories.
        """
        # Simulate a worktree whose common parent would be a blocked root
        fake_worktree = Path(blocked_path) / "worktree"
        fake_main_repo = Path(blocked_path) / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        # SECURITY ASSERTION: Must fall back to original path, not blocked root
        assert mount_path == fake_worktree
        assert is_expanded is False

    def test_allows_safe_user_workspace_path(self):
        """Valid user workspace paths should be allowed.

        Example: /Users/dev/projects or /home/user/projects
        """
        # /Users/dev/projects is depth 4, which is safe
        fake_base = Path("/Users/dev/projects")
        fake_worktree = fake_base / "repo-worktrees" / "feature"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        # OUTCOME: Should expand to common parent
        assert mount_path == fake_base
        assert is_expanded is True

    def test_rejects_shallow_home_path(self):
        """Paths like /home/user (depth 3) should be rejected.

        SECURITY TEST: Prevents mounting user's entire home directory.
        """
        # /home/user is depth 3 - too shallow, would expose entire home
        fake_base = Path("/home/user")
        fake_worktree = fake_base / "worktree"
        fake_main_repo = fake_base / "repo"

        # Mock resolve to prevent macOS firmlink resolution issues
        def mock_resolve(self):
            return self

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
            patch.object(Path, "resolve", mock_resolve),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        # SECURITY ASSERTION: Should NOT expand to /home/user
        assert mount_path == fake_worktree
        assert is_expanded is False

    @pytest.mark.parametrize(
        "wsl_invalid_mount",
        [
            "/mnt/nfs/shared",  # Not a Windows drive mount
            "/mnt/wsl/distro",  # WSL internal path
            "/mnt/wslg/something",  # WSL graphics path
            "/mnt/usb/device",  # USB mount
        ],
    )
    def test_rejects_non_windows_mnt_paths(self, wsl_invalid_mount):
        """Non-Windows /mnt paths should be rejected.

        SECURITY TEST: Only single-letter WSL2 drives (c, d, etc.) are allowed.
        """
        fake_base = Path(wsl_invalid_mount)
        fake_worktree = fake_base / "worktree"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        assert mount_path == fake_worktree
        assert is_expanded is False

    def test_allows_valid_wsl2_drive_mount(self):
        """Valid WSL2 paths like /mnt/c/Users/dev/projects should work.

        Requirements: single-letter drive AND depth >= 5
        """
        # /mnt/c/Users/dev/projects = depth 6, drive = 'c' (valid)
        fake_base = Path("/mnt/c/Users/dev/projects")
        fake_worktree = fake_base / "repo-worktrees" / "feature"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        assert mount_path == fake_base
        assert is_expanded is True

    def test_rejects_shallow_wsl2_path(self):
        """Shallow WSL2 paths like /mnt/c or /mnt/c/dev should be rejected.

        SECURITY TEST: Prevents mounting entire Windows drive.
        """
        # /mnt/c/dev = depth 4, requires >= 5
        fake_base = Path("/mnt/c/dev")
        fake_worktree = fake_base / "worktree"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        assert mount_path == fake_worktree
        assert is_expanded is False

    def test_non_worktree_returns_original_path(self, tmp_path):
        """Regular repos (not worktrees) should return unchanged path."""
        # Create a regular repo (not a worktree)
        repo = tmp_path / "regular-repo"
        repo.mkdir()
        (repo / ".git").mkdir()  # .git as directory = regular repo

        mount_path, is_expanded = git.get_workspace_mount_path(repo)

        assert mount_path == repo
        assert is_expanded is False

    def test_handles_no_common_ancestor_gracefully(self):
        """When worktree and main repo share no common path, fall back safely."""
        # Simulate completely different locations
        fake_worktree = Path("/home/userA/project")
        fake_main_repo = Path("/var/repos/project")

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = git.get_workspace_mount_path(fake_worktree)

        # Should fall back to original (common ancestor would be /)
        assert mount_path == fake_worktree
        assert is_expanded is False


# ═══════════════════════════════════════════════════════════════════════════════
# CRITICAL: install_pre_push_hook Overwrite Prevention Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestInstallPrePushHookOverwritePrevention:
    """Test matrix for hook overwrite prevention.

    SAFETY REQUIREMENT: Never overwrite user's existing hooks without SCC marker.

    Matrix:
    | Hook Exists | Has SCC Marker | Action          |
    |-------------|----------------|-----------------|
    | No          | N/A            | Create new      |
    | Yes         | Yes            | Update existing |
    | Yes         | No             | REFUSE (safety) |
    """

    def test_creates_hook_when_none_exists(self, tmp_path):
        """Should create hook when no pre-push hook exists."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is True
        hook_path = repo / ".git" / "hooks" / "pre-push"
        assert hook_path.exists()
        assert git.SCC_HOOK_MARKER in hook_path.read_text()

    def test_updates_existing_scc_managed_hook(self, tmp_path):
        """Should update hook that has SCC marker."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        hook_path = repo / ".git" / "hooks" / "pre-push"
        old_content = f"#!/bin/bash\n{git.SCC_HOOK_MARKER}\nold-scc-content"
        hook_path.write_text(old_content)

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is True
        assert "updated" in message.lower()
        # Content should be different (updated)
        new_content = hook_path.read_text()
        assert git.SCC_HOOK_MARKER in new_content
        assert new_content != old_content

    def test_refuses_to_overwrite_user_hook(self, tmp_path):
        """CRITICAL: Must NOT overwrite user's custom hook (no SCC marker).

        SAFETY TEST: User's hook content must be preserved exactly.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        hook_path = repo / ".git" / "hooks" / "pre-push"
        user_content = "#!/bin/bash\n# My custom hook\nrun-my-checks.sh"
        hook_path.write_text(user_content)

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(repo)

        # SAFETY ASSERTIONS
        assert success is False
        assert "will not overwrite" in message.lower()
        # User's content must be EXACTLY preserved
        assert hook_path.read_text() == user_content

    def test_respects_hooks_disabled_config(self, tmp_path):
        """Should not install when hooks.enabled is False."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": False}}):
            success, message = git.install_pre_push_hook(repo)

        assert success is False
        assert "not enabled" in message.lower()
        # Hook should NOT be created
        hook_path = repo / ".git" / "hooks" / "pre-push"
        assert not hook_path.exists()

    def test_fails_gracefully_for_non_git_repo(self, tmp_path):
        """Should return False for non-git directories."""
        not_repo = tmp_path / "not-a-repo"
        not_repo.mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            success, message = git.install_pre_push_hook(not_repo)

        assert success is False
        assert "not a git repository" in message.lower()

    def test_hook_is_executable_after_creation(self, tmp_path):
        """Created hook must have executable permission."""
        import os

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            git.install_pre_push_hook(repo)

        hook_path = repo / ".git" / "hooks" / "pre-push"
        assert os.access(hook_path, os.X_OK)

    def test_hook_contains_protected_branch_checks(self, tmp_path):
        """Created hook must check for protected branches."""
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        (repo / ".git" / "hooks").mkdir()

        with patch("scc_cli.config.load_user_config", return_value={"hooks": {"enabled": True}}):
            git.install_pre_push_hook(repo)

        hook_path = repo / ".git" / "hooks" / "pre-push"
        content = hook_path.read_text()

        # Verify essential protected branches are checked
        assert "main" in content
        assert "master" in content
        assert "develop" in content
        # Verify it can block pushes
        assert "exit 1" in content


# ═══════════════════════════════════════════════════════════════════════════════
# Additional Safety Tests: Branch Protection
# ═══════════════════════════════════════════════════════════════════════════════


class TestProtectedBranchSafety:
    """Ensure protected branch detection is comprehensive."""

    @pytest.mark.parametrize(
        "protected",
        ["main", "master", "develop", "production", "staging"],
    )
    def test_all_protected_branches_detected(self, protected):
        """Each standard protected branch MUST be detected."""
        assert git.is_protected_branch(protected) is True

    @pytest.mark.parametrize(
        "allowed",
        [
            "claude/feature-x",
            "feature/new-thing",
            "bugfix/fix-123",
            "hotfix/urgent",
            "release/v1.0",
            "user/experiment",
        ],
    )
    def test_work_branches_not_protected(self, allowed):
        """Work branches should NOT be protected."""
        assert git.is_protected_branch(allowed) is False
