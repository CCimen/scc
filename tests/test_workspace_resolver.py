"""Tests for workspace resolver."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scc_cli.core.workspace import ResolverResult
from scc_cli.services.workspace import resolve_launch_context


class TestResolveFromGitRepo:
    """Tests for git repo detection."""

    def test_git_repo_root_returns_result(self, tmp_path: Path) -> None:
        """Git repo root returns valid ResolverResult."""
        # Create git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Mock _detect_git_root to return tmp_path (simulating git rev-parse)
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == tmp_path
        assert result.entry_dir == tmp_path
        assert result.is_auto_detected is True

    def test_git_subdir_returns_repo_root(self, tmp_path: Path) -> None:
        """Running from subdir detects repo root."""
        # Create git repo with subdir
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        subdir = tmp_path / "src" / "components"
        subdir.mkdir(parents=True)

        # Mock _detect_git_root to return tmp_path (the repo root)
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(subdir, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == tmp_path
        assert result.entry_dir == subdir
        # CW should mirror ED when within MR
        assert result.container_workdir == str(subdir)

    def test_git_detection_reason_message(self, tmp_path: Path) -> None:
        """Reason field contains git detection message."""
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert "Git repository detected" in result.reason


class TestResolveFromSccYaml:
    """Tests for .scc.yaml detection."""

    def test_scc_yaml_detected(self, tmp_path: Path) -> None:
        """Directory with .scc.yaml is detected."""
        # Create .scc.yaml without git
        (tmp_path / ".scc.yaml").write_text("team: test\n")

        # Mock git to return None (no git repo)
        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == tmp_path
        assert result.is_auto_detected is True

    def test_scc_yaml_upward_search(self, tmp_path: Path) -> None:
        """Finds .scc.yaml by searching upward."""
        # Create .scc.yaml in parent
        (tmp_path / ".scc.yaml").write_text("team: test\n")
        subdir = tmp_path / "packages" / "core"
        subdir.mkdir(parents=True)

        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
            result = resolve_launch_context(subdir, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == tmp_path
        assert result.entry_dir == subdir

    def test_scc_yaml_reason_message(self, tmp_path: Path) -> None:
        """Reason field contains .scc.yaml detection message."""
        (tmp_path / ".scc.yaml").write_text("team: test\n")

        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert ".scc.yaml found" in result.reason

    def test_git_takes_precedence_over_scc_yaml(self, tmp_path: Path) -> None:
        """Git detection takes precedence over .scc.yaml."""
        # Create both .scc.yaml and mock git repo
        (tmp_path / ".scc.yaml").write_text("team: test\n")

        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert "Git repository detected" in result.reason


class TestNoAutoDetect:
    """Tests when no workspace can be auto-detected."""

    def test_no_git_no_scc_returns_none(self, tmp_path: Path) -> None:
        """Returns None when no git and no .scc.yaml."""
        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is None

    def test_weak_markers_not_detected(self, tmp_path: Path) -> None:
        """Weak markers (package.json) do NOT cause auto-detect."""
        (tmp_path / "package.json").write_text("{}")

        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=None):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is None


class TestExplicitWorkspace:
    """Tests for explicit workspace argument."""

    def test_explicit_workspace_used(self, tmp_path: Path) -> None:
        """Explicit workspace path is used."""
        explicit = tmp_path / "explicit_project"
        explicit.mkdir()

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(explicit),
        )

        assert result is not None
        assert result.workspace_root.resolve() == explicit.resolve()
        assert result.is_auto_detected is False

    def test_explicit_workspace_is_not_auto_detected(self, tmp_path: Path) -> None:
        """Explicit workspace sets is_auto_detected=False."""
        explicit = tmp_path / "explicit_project"
        explicit.mkdir()

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(explicit),
        )

        assert result is not None
        assert result.is_auto_detected is False

    def test_explicit_workspace_reason_message(self, tmp_path: Path) -> None:
        """Reason field contains explicit workspace message."""
        explicit = tmp_path / "explicit_project"
        explicit.mkdir()

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(explicit),
        )

        assert result is not None
        assert "Explicit --workspace" in result.reason

    def test_explicit_nonexistent_path_returns_none(self, tmp_path: Path) -> None:
        """Explicit workspace that doesn't exist returns None."""
        nonexistent = tmp_path / "does_not_exist"

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(nonexistent),
        )

        assert result is None

    def test_explicit_relative_path_resolved(self, tmp_path: Path) -> None:
        """Relative explicit workspace path is resolved."""
        subdir = tmp_path / "my_project"
        subdir.mkdir()

        # Use relative path from tmp_path
        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg="my_project",
        )

        assert result is not None
        assert result.workspace_root.resolve() == subdir.resolve()

    def test_explicit_tilde_path_expanded(self, tmp_path: Path) -> None:
        """Tilde (~) in explicit path is expanded."""
        # Create a real directory for this test
        home = Path.home()
        test_dir = home / ".scc_test_workspace_resolver"

        try:
            test_dir.mkdir(exist_ok=True)

            result = resolve_launch_context(
                cwd=tmp_path,
                workspace_arg="~/.scc_test_workspace_resolver",
            )

            assert result is not None
            assert result.workspace_root.resolve() == test_dir.resolve()
        finally:
            # Cleanup
            if test_dir.exists():
                test_dir.rmdir()


class TestContainerWorkdir:
    """Tests for CW (container_workdir) calculation."""

    def test_cw_mirrors_ed_when_within_mr(self, tmp_path: Path) -> None:
        """CW equals ED when ED is within MR."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        subdir = tmp_path / "src"
        subdir.mkdir()

        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(subdir, workspace_arg=None)

        assert result is not None
        assert result.container_workdir == str(subdir)

    def test_cw_defaults_to_wr_when_ed_outside_mr(self, tmp_path: Path) -> None:
        """CW defaults to WR when ED is not within MR."""
        # This is a tricky case - normally ED should be within MR
        # Test with explicit workspace where cwd might differ
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".git").mkdir()

        result = resolve_launch_context(
            cwd=tmp_path,  # CWD is parent, not within workspace
            workspace_arg=str(workspace),
        )

        assert result is not None
        # CW should be workspace since cwd isn't within it
        assert Path(result.container_workdir).resolve() == workspace.resolve()

    def test_cw_equals_entry_dir_at_repo_root(self, tmp_path: Path) -> None:
        """CW equals entry_dir when at repo root."""
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.container_workdir == str(tmp_path)
        assert result.entry_dir == tmp_path


class TestSuspiciousWorkspace:
    """Tests for suspicious workspace detection."""

    def test_home_directory_is_suspicious(self) -> None:
        """Home directory is flagged as suspicious."""
        home = Path.home()

        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=home):
            result = resolve_launch_context(home, workspace_arg=None)

        if result is not None:
            assert result.is_suspicious is True
            assert result.is_auto_eligible() is False

    def test_tmp_directory_is_suspicious(self) -> None:
        """System temp directory is flagged as suspicious."""
        tmp = Path("/tmp")

        with patch("scc_cli.services.workspace.resolver._detect_git_root", return_value=tmp):
            result = resolve_launch_context(tmp, workspace_arg=None)

        if result is not None:
            assert result.is_suspicious is True

    def test_normal_project_not_suspicious(self, tmp_path: Path) -> None:
        """Normal project directory is not suspicious."""
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.is_suspicious is False
        assert result.is_auto_eligible() is True

    def test_explicit_suspicious_still_flagged(self) -> None:
        """Explicit workspace in suspicious location is still flagged."""
        home = Path.home()

        result = resolve_launch_context(
            cwd=home,
            workspace_arg=str(home),
            allow_suspicious=False,
        )

        if result is not None:
            assert result.is_suspicious is True


class TestAllowSuspicious:
    """Tests for allow_suspicious parameter."""

    def test_allow_suspicious_does_not_clear_flag(self) -> None:
        """allow_suspicious=True does not clear is_suspicious flag."""
        home = Path.home()

        result = resolve_launch_context(
            cwd=home,
            workspace_arg=str(home),
            allow_suspicious=True,
        )

        if result is not None:
            # Flag is still set (for caller awareness)
            assert result.is_suspicious is True


class TestResolverResult:
    """Tests for ResolverResult dataclass."""

    def test_is_auto_eligible_true_when_auto_and_not_suspicious(self, tmp_path: Path) -> None:
        """is_auto_eligible returns True when auto-detected and not suspicious."""
        result = ResolverResult(
            workspace_root=tmp_path,
            entry_dir=tmp_path,
            mount_root=tmp_path,
            container_workdir=str(tmp_path),
            is_auto_detected=True,
            is_suspicious=False,
        )
        assert result.is_auto_eligible() is True

    def test_is_auto_eligible_false_when_suspicious(self, tmp_path: Path) -> None:
        """is_auto_eligible returns False when suspicious."""
        result = ResolverResult(
            workspace_root=tmp_path,
            entry_dir=tmp_path,
            mount_root=tmp_path,
            container_workdir=str(tmp_path),
            is_auto_detected=True,
            is_suspicious=True,
        )
        assert result.is_auto_eligible() is False

    def test_is_auto_eligible_false_when_not_auto(self, tmp_path: Path) -> None:
        """is_auto_eligible returns False when not auto-detected."""
        result = ResolverResult(
            workspace_root=tmp_path,
            entry_dir=tmp_path,
            mount_root=tmp_path,
            container_workdir=str(tmp_path),
            is_auto_detected=False,
            is_suspicious=False,
        )
        assert result.is_auto_eligible() is False

    def test_resolver_result_is_frozen(self, tmp_path: Path) -> None:
        """ResolverResult is immutable (frozen dataclass)."""
        result = ResolverResult(
            workspace_root=tmp_path,
            entry_dir=tmp_path,
            mount_root=tmp_path,
            container_workdir=str(tmp_path),
            is_auto_detected=True,
            is_suspicious=False,
        )
        with pytest.raises(AttributeError):
            result.workspace_root = tmp_path / "other"  # type: ignore[misc]

    def test_resolver_result_has_optional_fields(self, tmp_path: Path) -> None:
        """ResolverResult has default values for optional fields."""
        result = ResolverResult(
            workspace_root=tmp_path,
            entry_dir=tmp_path,
            mount_root=tmp_path,
            container_workdir=str(tmp_path),
            is_auto_detected=True,
            is_suspicious=False,
        )
        assert result.is_mount_expanded is False
        assert result.reason == ""


class TestPathResolution:
    """Tests for path canonicalization."""

    def test_entry_dir_is_resolved(self, tmp_path: Path) -> None:
        """Entry dir is resolved to absolute path."""
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.entry_dir.is_absolute()
        assert result.entry_dir == tmp_path.resolve()

    def test_workspace_root_is_resolved(self, tmp_path: Path) -> None:
        """Workspace root is resolved to absolute path."""
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.workspace_root.is_absolute()
        assert result.workspace_root == tmp_path.resolve()

    def test_mount_root_is_resolved(self, tmp_path: Path) -> None:
        """Mount root is resolved to absolute path."""
        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.mount_root.is_absolute()


class TestMountExpansion:
    """Tests for worktree mount expansion."""

    def test_non_worktree_not_expanded(self, tmp_path: Path) -> None:
        """Regular repo (not worktree) is not expanded."""
        # Create .git as directory (regular repo)
        (tmp_path / ".git").mkdir()

        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=tmp_path,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result is not None
        assert result.is_mount_expanded is False
        assert result.mount_root == tmp_path

    def test_worktree_mount_expanded_flag_propagated(self, tmp_path: Path) -> None:
        """Worktree mount expansion flag is propagated from get_workspace_mount_path."""
        # Mock get_workspace_mount_path to return expanded mount
        # This tests that the resolver correctly propagates the is_mount_expanded flag
        # The actual mount expansion logic is tested in test_git_worktree.py
        parent = tmp_path / "parent"
        parent.mkdir()

        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with (
            patch(
                "scc_cli.services.workspace.resolver._detect_git_root",
                return_value=worktree,
            ),
            patch(
                "scc_cli.services.workspace.resolver.get_workspace_mount_path",
                return_value=(parent, True),  # Simulate expanded mount
            ),
        ):
            result = resolve_launch_context(worktree, workspace_arg=None)

        assert result is not None
        assert result.is_mount_expanded is True
        assert result.mount_root == parent

    def test_worktree_mount_not_expanded_when_blocked(self, tmp_path: Path) -> None:
        """Worktree mount is not expanded when common parent is blocked."""
        # Mock get_workspace_mount_path to return non-expanded (blocked case)
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        with (
            patch(
                "scc_cli.services.workspace.resolver._detect_git_root",
                return_value=worktree,
            ),
            patch(
                "scc_cli.services.workspace.resolver.get_workspace_mount_path",
                return_value=(worktree, False),  # Not expanded (blocked)
            ),
        ):
            result = resolve_launch_context(worktree, workspace_arg=None)

        assert result is not None
        assert result.is_mount_expanded is False
        assert result.mount_root == worktree


class TestSymlinkCanonicalization:
    """Tests for symlink and path canonicalization edge cases.

    These tests verify that the resolver correctly handles symlinks and
    relative paths (e.g., ".." in paths) to avoid false "within" checks.

    Note: Symlink tests are skipped on Windows native (not WSL) because
    symlink creation requires elevated privileges.
    """

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Symlink creation requires elevated privileges on Windows",
    )
    def test_symlink_to_repo_resolves_correctly(self, tmp_path: Path) -> None:
        """Symlink to git repo resolves to real repo root."""
        # Create real repo
        real_repo = tmp_path / "real_repo"
        real_repo.mkdir()
        (real_repo / ".git").mkdir()

        # Create symlink to repo
        link = tmp_path / "link_to_repo"
        link.symlink_to(real_repo)

        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=real_repo,  # Git returns the real path
        ):
            result = resolve_launch_context(link, workspace_arg=None)

        assert result is not None
        # ED should be resolved (real path)
        assert result.entry_dir.resolve() == real_repo.resolve()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Symlink creation requires elevated privileges on Windows",
    )
    def test_symlink_subdir_within_repo(self, tmp_path: Path) -> None:
        """Symlink to subdir within repo has correct CW."""
        # Create real repo with subdir
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        subdir = repo / "src"
        subdir.mkdir()

        # Create symlink to subdir
        link_to_src = tmp_path / "link_to_src"
        link_to_src.symlink_to(subdir)

        with patch(
            "scc_cli.services.workspace.resolver._detect_git_root",
            return_value=repo,
        ):
            result = resolve_launch_context(link_to_src, workspace_arg=None)

        assert result is not None
        # CW should be the resolved subdir path
        assert Path(result.container_workdir).resolve() == subdir.resolve()

    def test_relative_path_with_dotdot_resolves(self, tmp_path: Path) -> None:
        """Paths with .. are correctly resolved."""
        # Create repo
        repo = tmp_path / "projects" / "myrepo"
        repo.mkdir(parents=True)
        (repo / ".git").mkdir()

        # Use path with .. (going up and back down)
        weird_path = repo / "src" / ".." / "."
        weird_path.mkdir(parents=True, exist_ok=True)

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(weird_path),
        )

        assert result is not None
        # Should resolve to the repo itself
        assert result.workspace_root.resolve() == repo.resolve()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Symlink creation requires elevated privileges on Windows",
    )
    def test_explicit_workspace_with_symlink(self, tmp_path: Path) -> None:
        """Explicit workspace via symlink is resolved correctly."""
        # Create real project
        real_project = tmp_path / "real_project"
        real_project.mkdir()

        # Create symlink
        symlink_project = tmp_path / "symlink_project"
        symlink_project.symlink_to(real_project)

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(symlink_project),
        )

        assert result is not None
        # workspace_root should be resolved
        assert result.workspace_root.resolve() == real_project.resolve()
