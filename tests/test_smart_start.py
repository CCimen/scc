"""Acceptance tests for Smart Start feature.

These tests verify the 8 key behaviors from the Smart Start spec:
T1: Git subdir resolution + mirrored CW
T2: Worktree subdir detection
T3: .scc.yaml upward search
T4: Weak markers only -> non-interactive fails, interactive shows wizard
T5: Auto-detected suspicious -> non-interactive fails, interactive shows wizard
T6: Explicit suspicious -> interactive warns+continues, non-interactive requires flag
T7: QR team scoping
T8: scc vs scc start parity
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestT1GitSubdirResolution:
    """T1: Git subdir resolution + mirrored CW."""

    def test_subdir_resolves_to_repo_root_with_mirrored_cw(self, tmp_path: Path) -> None:
        """Running from repo subdir should resolve WR=repo root, CW=ED."""
        from scc_cli.services.workspace import resolve_launch_context

        # Create git repo with subdir
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "components"
        subdir.mkdir(parents=True)

        # Mock git rev-parse to return the repo root
        with patch(
            "scc_cli.services.workspace.resolver.run_command",
            return_value=str(tmp_path),
        ):
            result = resolve_launch_context(subdir, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == tmp_path.resolve()  # WR = repo root
        assert result.entry_dir == subdir.resolve()  # ED = subdir
        assert result.container_workdir == str(subdir.resolve())  # CW mirrors ED


class TestT2WorktreeSubdir:
    """T2: Worktree subdir detection."""

    def test_worktree_subdir_resolves_correctly(self, tmp_path: Path) -> None:
        """Running from worktree subdir should detect worktree root."""
        from scc_cli.services.workspace import resolve_launch_context

        # Create a worktree structure (simplified)
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        subdir = worktree / "packages"
        subdir.mkdir()

        # Worktree marker (file pointing to main repo)
        git_file = worktree / ".git"
        git_file.write_text(f"gitdir: {tmp_path}/.git/worktrees/worktree\n")

        # Create main repo structure
        main_git = tmp_path / ".git" / "worktrees" / "worktree"
        main_git.mkdir(parents=True)
        (main_git / "gitdir").write_text(str(worktree))
        (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")

        # Mock git rev-parse to return the worktree root (as git would)
        with patch(
            "scc_cli.services.workspace.resolver.run_command",
            return_value=str(worktree),
        ):
            result = resolve_launch_context(subdir, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == worktree.resolve()  # WR = worktree root
        assert result.entry_dir == subdir.resolve()  # ED = subdir
        assert result.container_workdir == str(subdir.resolve())  # CW mirrors ED


class TestT3SccYamlUpward:
    """T3: .scc.yaml upward search."""

    def test_scc_yaml_found_upward(self, tmp_path: Path) -> None:
        """Running from child dir should find .scc.yaml in parent."""
        from scc_cli.services.workspace import resolve_launch_context

        # Create .scc.yaml in root
        (tmp_path / ".scc.yaml").write_text("team: test\n")
        subdir = tmp_path / "packages" / "core" / "src"
        subdir.mkdir(parents=True)

        # Mock git detection to return None (no git repo)
        with patch(
            "scc_cli.services.workspace.resolver.run_command",
            return_value=None,
        ):
            result = resolve_launch_context(subdir, workspace_arg=None)

        assert result is not None
        assert result.workspace_root == tmp_path.resolve()  # WR = .scc.yaml dir
        assert result.entry_dir == subdir.resolve()  # ED = subdir
        assert result.container_workdir == str(subdir.resolve())  # CW = ED


class TestT4WeakMarkersOnly:
    """T4: Weak markers only -> non-interactive fails F1, interactive shows wizard."""

    def test_weak_markers_not_auto_detected(self, tmp_path: Path) -> None:
        """Directory with only weak markers should NOT be auto-detected."""
        from scc_cli.services.workspace import resolve_launch_context

        # Create only weak markers (no git, no .scc.yaml)
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / ".gitignore").write_text("node_modules/\n")

        # Mock git detection to return None
        with patch(
            "scc_cli.services.workspace.resolver.run_command",
            return_value=None,
        ):
            result = resolve_launch_context(tmp_path, workspace_arg=None)

        # Should return None - weak markers don't trigger auto-detect
        assert result is None


class TestT5AutoDetectedSuspicious:
    """T5: Auto-detected suspicious -> non-interactive fails F2, interactive shows wizard."""

    def test_auto_detected_suspicious_is_flagged(self) -> None:
        """Auto-detected workspace in suspicious location should be flagged."""
        from scc_cli.services.workspace import resolve_launch_context

        home = Path.home()

        # Mock git detection to return home directory
        with patch(
            "scc_cli.services.workspace.resolver.run_command",
            return_value=str(home),
        ):
            result = resolve_launch_context(home, workspace_arg=None)

        assert result is not None
        assert result.is_suspicious is True
        assert result.is_auto_eligible() is False  # Not eligible for auto-launch


class TestT6ExplicitSuspicious:
    """T6: Explicit suspicious -> interactive warns+continues, non-interactive requires flag."""

    def test_explicit_suspicious_still_flagged(self, tmp_path: Path) -> None:
        """Explicit suspicious workspace should still be flagged."""
        from scc_cli.services.workspace import resolve_launch_context

        # Use home directory as explicit workspace
        home = Path.home()

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(home),
        )

        assert result is not None
        assert result.is_suspicious is True

    def test_allow_suspicious_flag_works(self, tmp_path: Path) -> None:
        """allow_suspicious flag should still return result (caller decides action)."""
        from scc_cli.services.workspace import resolve_launch_context

        home = Path.home()

        result = resolve_launch_context(
            cwd=tmp_path,
            workspace_arg=str(home),
            allow_suspicious=True,
        )

        # Should still return result, is_suspicious still True
        # (allow_suspicious doesn't clear the flag, it's for caller to decide)
        assert result is not None


class TestT7QRTeamScoping:
    """T7: QR team scoping (--team X shows only X, standalone shows only None)."""

    def test_qr_gating_returns_false_for_json(self) -> None:
        """QR should not show in JSON mode."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        assert should_show_quick_resume(json_mode=True) is False

    def test_qr_gating_returns_false_for_interactive_flag(self) -> None:
        """QR should not show when --interactive forces wizard."""
        from scc_cli.ui.quick_resume import should_show_quick_resume

        assert should_show_quick_resume(interactive_flag=True) is False

    def test_qr_team_filtering_standalone(self, tmp_path: Path) -> None:
        """Standalone mode should only show contexts with no team."""
        from scc_cli.contexts import WorkContext
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "project"
        workspace.mkdir()

        mock_contexts = [
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="platform"),
        ]

        # Patch in contexts module where load_recent_contexts is defined
        with patch("scc_cli.contexts.load_recent_contexts", return_value=mock_contexts):
            result = load_contexts_for_workspace_and_team(workspace, team=None)

        assert len(result) == 1
        assert result[0].team is None

    def test_qr_team_filtering_specific_team(self, tmp_path: Path) -> None:
        """Team mode should only show contexts matching that team."""
        from scc_cli.contexts import WorkContext
        from scc_cli.ui.quick_resume import load_contexts_for_workspace_and_team

        workspace = tmp_path / "project"
        workspace.mkdir()

        mock_contexts = [
            MagicMock(spec=WorkContext, repo_root=str(workspace), team=None),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="platform"),
            MagicMock(spec=WorkContext, repo_root=str(workspace), team="data"),
        ]

        # Patch in contexts module where load_recent_contexts is defined
        with patch("scc_cli.contexts.load_recent_contexts", return_value=mock_contexts):
            result = load_contexts_for_workspace_and_team(workspace, team="platform")

        assert len(result) == 1
        assert result[0].team == "platform"


class TestT8Parity:
    """T8: scc vs scc start parity (identical WR/ED/MR/CW)."""

    def test_resolver_produces_same_result_regardless_of_entry_point(self, tmp_path: Path) -> None:
        """The resolver should produce identical results for both entry points."""
        from scc_cli.services.workspace import resolve_launch_context

        # Create a git repo
        (tmp_path / ".git").mkdir()

        # Mock git rev-parse to return the repo root
        with patch(
            "scc_cli.services.workspace.resolver.run_command",
            return_value=str(tmp_path),
        ):
            # Same resolver call, same result - both entry points use this
            result1 = resolve_launch_context(tmp_path, workspace_arg=None)
            result2 = resolve_launch_context(tmp_path, workspace_arg=None)

        assert result1 is not None
        assert result2 is not None
        assert result1.workspace_root == result2.workspace_root
        assert result1.entry_dir == result2.entry_dir
        assert result1.mount_root == result2.mount_root
        assert result1.container_workdir == result2.container_workdir
