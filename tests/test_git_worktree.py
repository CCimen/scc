"""Tests for git worktree detection and mounting functions."""

from pathlib import Path
from unittest.mock import patch


class TestIsWorktree:
    """Tests for is_worktree() detection."""

    def test_regular_repo_not_worktree(self, tmp_path):
        """Regular repos have .git as directory, not file."""
        from scc_cli.git import is_worktree

        # Create a mock .git directory (regular repo)
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        assert is_worktree(tmp_path) is False

    def test_worktree_has_git_file(self, tmp_path):
        """Worktrees have .git as file containing gitdir pointer."""
        from scc_cli.git import is_worktree

        # Create a mock .git file (worktree)
        git_file = tmp_path / ".git"
        git_file.write_text("gitdir: /path/to/main/.git/worktrees/feature")

        assert is_worktree(tmp_path) is True

    def test_no_git_at_all(self, tmp_path):
        """Non-git directories are not worktrees."""
        from scc_cli.git import is_worktree

        # Empty directory
        assert is_worktree(tmp_path) is False


class TestGetWorktreeMainRepo:
    """Tests for get_worktree_main_repo() parsing."""

    def test_parses_absolute_gitdir(self, tmp_path):
        """Correctly parses absolute gitdir path."""
        from scc_cli.git import get_worktree_main_repo

        # Create worktree .git file
        git_file = tmp_path / ".git"
        main_repo = Path("/Users/dev/myproject")
        git_file.write_text(f"gitdir: {main_repo}/.git/worktrees/feature")

        result = get_worktree_main_repo(tmp_path)
        assert result == main_repo

    def test_returns_none_for_regular_repo(self, tmp_path):
        """Returns None when .git is a directory."""
        from scc_cli.git import get_worktree_main_repo

        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        assert get_worktree_main_repo(tmp_path) is None

    def test_returns_none_for_non_git(self, tmp_path):
        """Returns None when no .git exists."""
        from scc_cli.git import get_worktree_main_repo

        assert get_worktree_main_repo(tmp_path) is None

    def test_returns_none_for_malformed_git_file(self, tmp_path):
        """Returns None when .git file doesn't have gitdir."""
        from scc_cli.git import get_worktree_main_repo

        git_file = tmp_path / ".git"
        git_file.write_text("invalid content")

        assert get_worktree_main_repo(tmp_path) is None


class TestGetWorkspaceMountPath:
    """Tests for get_workspace_mount_path() mount path calculation."""

    def test_regular_repo_unchanged(self, tmp_path):
        """Regular repos return unchanged path."""
        from scc_cli.git import get_workspace_mount_path

        # Create regular repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mount_path, is_expanded = get_workspace_mount_path(tmp_path)
        assert mount_path == tmp_path
        assert is_expanded is False

    def test_worktree_returns_common_parent(self):
        """Worktrees return common parent of worktree and main repo.

        Uses mocking to simulate a realistic user workspace structure
        since pytest temp dirs are in system paths that get blocked.
        """
        from scc_cli.git import get_workspace_mount_path

        # Simulate paths like a real user workspace:
        # /Users/dev/projects/myproject                  (main repo)
        # /Users/dev/projects/myproject-worktrees/feature (worktree)
        # Common parent: /Users/dev/projects
        fake_base = Path("/Users/dev/projects")
        fake_worktree = fake_base / "myproject-worktrees" / "feature"
        fake_main_repo = fake_base / "myproject"

        # Mock is_worktree to return True
        # Mock get_worktree_main_repo to return the fake main repo
        # Mock Path.resolve to return the same path (simulate resolved paths)
        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Common parent should be /Users/dev/projects (depth 4, allowed)
            assert mount_path == fake_base
            assert is_expanded is True

    def test_safety_rejects_root_mount(self, tmp_path):
        """Doesn't mount system root directories."""
        from scc_cli.git import get_workspace_mount_path

        # Simulate a worktree whose common parent would be /
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        git_file = worktree / ".git"
        # This points to a completely different location
        git_file.write_text("gitdir: /var/repo/.git/worktrees/feature")

        mount_path, is_expanded = get_workspace_mount_path(worktree)
        # Should fall back to original path due to safety check
        assert mount_path == worktree
        assert is_expanded is False

    def test_safety_rejects_home_mount(self, tmp_path):
        """Doesn't mount /home or /Users."""
        from scc_cli.git import get_workspace_mount_path

        # Create a worktree pointing to main repo at totally different location
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        git_file = worktree / ".git"
        # This would result in common parent being /home or similar
        git_file.write_text("gitdir: /home/otheruser/repo/.git/worktrees/feature")

        mount_path, is_expanded = get_workspace_mount_path(worktree)
        # Should fall back to original path due to safety check
        assert mount_path == worktree
        assert is_expanded is False

    def test_non_git_unchanged(self, tmp_path):
        """Non-git directories return unchanged."""
        from scc_cli.git import get_workspace_mount_path

        mount_path, is_expanded = get_workspace_mount_path(tmp_path)
        assert mount_path == tmp_path
        assert is_expanded is False

    def test_wsl2_worktree_returns_common_parent(self):
        """WSL2 worktrees on Windows filesystem work correctly.

        Uses mocking to simulate WSL2 paths since we can't create
        actual /mnt/c paths on macOS/Linux.

        Requirements for WSL2 /mnt exception:
        - Must have single-letter drive (a-z)
        - Must have depth >= 5 (conservative for safety)
        """
        from scc_cli.git import get_workspace_mount_path

        # Simulate WSL2 paths:
        # /mnt/c/Users/dev/projects/myproject                  (main repo)
        # /mnt/c/Users/dev/projects/myproject-worktrees/feature (worktree)
        # Common parent: /mnt/c/Users/dev/projects (depth 6, allowed)
        fake_base = Path("/mnt/c/Users/dev/projects")
        fake_worktree = fake_base / "myproject-worktrees" / "feature"
        fake_main_repo = fake_base / "myproject"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Common parent should be /mnt/c/Users/dev/projects (depth 6, allowed)
            assert mount_path == fake_base
            assert is_expanded is True

    def test_safety_rejects_shallow_mnt_path(self):
        """Doesn't mount shallow WSL2 paths like /mnt/c or /mnt/c/repo."""
        from scc_cli.git import get_workspace_mount_path

        # Simulate a worktree whose common parent would be too shallow under /mnt
        # /mnt/c/repo and /mnt/c/worktrees would have common parent /mnt/c (depth 3)
        fake_base = Path("/mnt/c")
        fake_worktree = fake_base / "worktrees" / "feature"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Should fall back to original path - /mnt/c is too broad (depth 3)
            assert mount_path == fake_worktree
            assert is_expanded is False

    def test_safety_rejects_depth4_mnt_path(self):
        """Doesn't mount depth-4 WSL2 paths like /mnt/c/dev (conservative)."""
        from scc_cli.git import get_workspace_mount_path

        # /mnt/c/dev (depth 4) is still blocked - we require depth 5+
        # This prevents mounting too broadly on the Windows filesystem
        fake_base = Path("/mnt/c/dev")
        fake_worktree = fake_base / "worktrees" / "feature"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Should fall back - /mnt/c/dev is depth 4, we require >= 5
            assert mount_path == fake_worktree
            assert is_expanded is False

    def test_safety_rejects_non_drive_mnt_paths(self):
        """Doesn't allow /mnt/<non-drive> paths like /mnt/nfs, /mnt/wsl."""
        from scc_cli.git import get_workspace_mount_path

        # /mnt/nfs/... - "nfs" is not a single-letter drive
        # This blocks Linux mount points that happen to be deep
        fake_base = Path("/mnt/nfs/shared/data")
        fake_worktree = fake_base / "worktrees" / "feature"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Should fall back - "nfs" is not a single-letter drive
            assert mount_path == fake_worktree
            assert is_expanded is False

    def test_safety_rejects_wsl_internal_paths(self):
        """Doesn't allow /mnt/wsl/... or /mnt/wslg/... internal paths."""
        from scc_cli.git import get_workspace_mount_path

        # /mnt/wsl/distro/... - WSL internal paths should be blocked
        fake_base = Path("/mnt/wsl/distro/home/user")
        fake_worktree = fake_base / "worktrees" / "feature"
        fake_main_repo = fake_base / "repo"

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Should fall back - "wsl" is not a single-letter drive
            assert mount_path == fake_worktree
            assert is_expanded is False

    def test_linux_home_worktree_returns_common_parent(self):
        """Linux home directory worktrees work correctly.

        On macOS, /home is a firmlink to /System/Volumes/Data/home, so we
        need to mock Path.resolve() to simulate Linux behavior where /home
        is a real directory.
        """
        from scc_cli.git import get_workspace_mount_path

        # Simulate Linux paths:
        # /home/user/projects/myproject                  (main repo)
        # /home/user/projects/myproject-worktrees/feature (worktree)
        # Common parent: /home/user/projects (depth 4, allowed)
        fake_base = Path("/home/user/projects")
        fake_worktree = fake_base / "myproject-worktrees" / "feature"
        fake_main_repo = fake_base / "myproject"

        # Mock resolve() to return the same path (simulating Linux where /home is real)
        def mock_resolve(self):
            return self

        with (
            patch("scc_cli.git.is_worktree", return_value=True),
            patch("scc_cli.git.get_worktree_main_repo", return_value=fake_main_repo),
            patch.object(Path, "resolve", mock_resolve),
        ):
            mount_path, is_expanded = get_workspace_mount_path(fake_worktree)
            # Common parent should be /home/user/projects (depth 4, allowed)
            assert mount_path == fake_base
            assert is_expanded is True


class TestDetectWorkspaceRoot:
    """Tests for detect_workspace_root() smart detection."""

    def test_detects_git_repo_from_subdir(self, tmp_path):
        """Detects workspace root when running from a subdirectory."""
        from scc_cli.git import detect_workspace_root

        # Create a git repo with a subdirectory
        repo = tmp_path / "myproject"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()
        subdir = repo / "src" / "components"
        subdir.mkdir(parents=True)

        # Detect from subdirectory
        root, start_cwd = detect_workspace_root(subdir)

        assert root == repo
        assert start_cwd == subdir.resolve()

    def test_detects_git_repo_at_root(self, tmp_path):
        """Returns repo root when already at repo root."""
        from scc_cli.git import detect_workspace_root

        # Create a git repo
        repo = tmp_path / "myproject"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()

        root, start_cwd = detect_workspace_root(repo)

        assert root == repo
        assert start_cwd == repo.resolve()

    def test_detects_scc_yaml_project(self, tmp_path):
        """Detects workspace via .scc.yaml when git not available."""
        from scc_cli.git import detect_workspace_root

        # Create a non-git project with .scc.yaml
        project = tmp_path / "myproject"
        project.mkdir()
        scc_config = project / ".scc.yaml"
        scc_config.write_text("# SCC project config")
        subdir = project / "lib"
        subdir.mkdir()

        # Mock git not being available
        with patch("scc_cli.git.check_git_installed", return_value=False):
            root, start_cwd = detect_workspace_root(subdir)

        assert root == project
        assert start_cwd == subdir.resolve()

    def test_detects_git_file_worktree(self, tmp_path):
        """Detects workspace when .git is a file (worktree)."""
        from scc_cli.git import detect_workspace_root

        # Create a worktree (has .git file, not directory)
        worktree = tmp_path / "feature-worktree"
        worktree.mkdir()
        git_file = worktree / ".git"
        git_file.write_text("gitdir: /path/to/main/.git/worktrees/feature")
        subdir = worktree / "src"
        subdir.mkdir()

        # Mock git not being available to test fallback to .git file detection
        with patch("scc_cli.git.check_git_installed", return_value=False):
            root, start_cwd = detect_workspace_root(subdir)

        assert root == worktree
        assert start_cwd == subdir.resolve()

    def test_returns_none_for_non_workspace(self, tmp_path):
        """Returns None when no workspace markers found."""
        from scc_cli.git import detect_workspace_root

        # Create a plain directory with no git or scc markers
        plain_dir = tmp_path / "random"
        plain_dir.mkdir()
        nested = plain_dir / "deep" / "path"
        nested.mkdir(parents=True)

        with patch("scc_cli.git.check_git_installed", return_value=False):
            root, start_cwd = detect_workspace_root(nested)

        assert root is None
        assert start_cwd == nested.resolve()

    def test_prefers_git_over_scc_yaml(self, tmp_path):
        """Git detection takes priority over .scc.yaml."""
        from scc_cli.git import detect_workspace_root

        # Create a project with both git and scc.yaml
        project = tmp_path / "myproject"
        project.mkdir()
        git_dir = project / ".git"
        git_dir.mkdir()
        scc_config = project / ".scc.yaml"
        scc_config.write_text("# SCC config")
        subdir = project / "src"
        subdir.mkdir()

        root, start_cwd = detect_workspace_root(subdir)

        # Should detect via git (priority 1)
        assert root == project
        assert start_cwd == subdir.resolve()

    def test_scc_yaml_at_parent_dir(self, tmp_path):
        """Detects .scc.yaml in parent directory."""
        from scc_cli.git import detect_workspace_root

        # Create nested structure with .scc.yaml at top
        project = tmp_path / "bigproject"
        project.mkdir()
        scc_config = project / ".scc.yaml"
        scc_config.write_text("# SCC config")
        deep = project / "packages" / "core" / "src"
        deep.mkdir(parents=True)

        with patch("scc_cli.git.check_git_installed", return_value=False):
            root, start_cwd = detect_workspace_root(deep)

        assert root == project
        assert start_cwd == deep.resolve()

    def test_resolves_symlinks(self, tmp_path):
        """Resolves symbolic links in start directory."""
        from scc_cli.git import detect_workspace_root

        # Create a git repo
        real_project = tmp_path / "real_project"
        real_project.mkdir()
        git_dir = real_project / ".git"
        git_dir.mkdir()

        # Create a symlink to the project
        link = tmp_path / "project_link"
        link.symlink_to(real_project)

        root, start_cwd = detect_workspace_root(link)

        # start_cwd should be resolved (real path)
        assert root == real_project
        assert start_cwd == real_project  # Symlink resolved
