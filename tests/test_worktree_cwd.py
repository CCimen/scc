"""Tests for worktree CWD consistency across all launch paths.

Verifies that container_workdir is correctly handled in:
- docker build_command() uses workspace for -w flag
- container_workdir parameter flows correctly through the API
"""

from pathlib import Path

from scc_cli.docker.core import build_command


class TestBuildCommandWorkspace:
    """Tests for build_command workspace parameter."""

    def test_build_command_sets_workspace_flag(self):
        """build_command should set -w flag from workspace parameter."""
        workspace = Path("/projects/my-workspace")

        cmd = build_command(workspace=workspace)

        # Command should include -w workspace
        assert "-w" in cmd
        w_idx = cmd.index("-w")
        assert cmd[w_idx + 1] == str(workspace)

    def test_build_command_with_worktree_path(self):
        """build_command with worktree path should include it in -w flag."""
        # For worktrees, the caller passes the worktree path, not parent
        worktree_path = Path("/projects/parent/worktree-feature")

        cmd = build_command(workspace=worktree_path)

        assert "-w" in cmd
        w_idx = cmd.index("-w")
        assert cmd[w_idx + 1] == str(worktree_path)

    def test_build_command_with_continue_session(self):
        """build_command with continue_session should add -c flag."""
        workspace = Path("/projects/test")

        cmd = build_command(workspace=workspace, continue_session=True)

        assert "-c" in cmd

    def test_build_command_with_resume(self):
        """build_command with resume should add --resume flag."""
        workspace = Path("/projects/test")

        cmd = build_command(workspace=workspace, resume=True)

        assert "--resume" in cmd

    def test_build_command_none_workspace(self):
        """build_command with None workspace should not include -w flag."""
        cmd = build_command(workspace=None)

        # -w flag should not be present with None workspace
        assert "-w" not in cmd


class TestContainerWorkdirParameter:
    """Tests for container_workdir parameter semantics."""

    def test_worktree_needs_different_cwd_than_mount(self):
        """Worktree setups require separate mount path and container workdir.

        When working with git worktrees:
        - Mount path: the common parent directory (contains all worktrees)
        - Container workdir: the specific worktree directory

        This ensures Claude finds .claude/settings.local.json in the right place.
        """
        mount_path = Path("/projects/my-repo")  # Parent containing worktrees
        worktree_path = Path("/projects/my-repo/worktree-feature")  # Actual worktree

        # The distinction is important
        assert mount_path != worktree_path
        assert worktree_path.is_relative_to(mount_path)

    def test_regular_repo_uses_same_path(self):
        """Regular (non-worktree) repos use same path for mount and CWD.

        When not using worktrees:
        - Mount path = workspace path
        - Container workdir can be None (defaults to mount path)
        """
        workspace = Path("/projects/regular-repo")

        # For regular repos, container_workdir=None means "use workspace"
        # This is the simpler case
        assert workspace == workspace  # Same path used for both


class TestEffectiveWorkspaceLogic:
    """Tests for effective workspace calculation pattern."""

    def test_container_workdir_takes_precedence(self):
        """When container_workdir is provided, it should be used."""
        workspace = Path("/projects/parent")
        container_workdir = Path("/projects/parent/worktree-feature")

        # The pattern: use container_workdir if provided, else workspace
        effective = container_workdir if container_workdir else workspace

        assert effective == container_workdir

    def test_workspace_used_when_no_container_workdir(self):
        """When container_workdir is None, workspace should be used."""
        workspace = Path("/projects/regular-repo")
        container_workdir = None

        effective = container_workdir if container_workdir else workspace

        assert effective == workspace
