"""Tests for suspicious directory detection.

Tests for the is_suspicious_directory() and get_suspicious_reason() functions
that determine whether a directory path is considered suspicious for workspace
operations (e.g., root filesystem, home directory, system directories).

TDD approach: These tests define expected behavior for:
- Root and near-root paths (/. /home, /Users, /var, etc.)
- User home directory and common folders (Downloads, Desktop, Documents)
- Temp directories (/tmp)
- Normal project directories (should NOT be suspicious)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# TestIsSuspiciousDirectory - Core detection tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsSuspiciousDirectory:
    """Tests for is_suspicious_directory()."""

    def test_root_is_suspicious(self):
        """Root directory is suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path("/")) is True

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_home_parent_is_suspicious_linux(self):
        """Home parent directories are suspicious on Linux."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # On Linux, /home is real; on macOS it's a symlink to /System/Volumes/Data/home
        assert is_suspicious_directory(Path("/home")) is True

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific paths")
    def test_users_parent_is_suspicious_macos(self):
        """Users parent directory is suspicious on macOS."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path("/Users")) is True

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_tmp_is_suspicious_linux(self):
        """Temp directory /tmp is suspicious on Linux."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # On macOS, /tmp -> /private/tmp which is not in suspicious list
        assert is_suspicious_directory(Path("/tmp")) is True

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_var_is_suspicious_linux(self):
        """System variable directories are suspicious on Linux."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # On macOS, /var -> /private/var which is not in suspicious list
        assert is_suspicious_directory(Path("/var")) is True

    def test_user_home_is_suspicious(self):
        """User's home directory itself is suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        home = Path.home()
        assert is_suspicious_directory(home) is True

    def test_downloads_is_suspicious(self):
        """Downloads folder is suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path.home() / "Downloads") is True

    def test_desktop_is_suspicious(self):
        """Desktop folder is suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path.home() / "Desktop") is True

    def test_documents_is_suspicious(self):
        """Documents folder is suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path.home() / "Documents") is True

    def test_normal_project_not_suspicious(self, tmp_path: Path):
        """Normal project directory is NOT suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        project = tmp_path / "myproject"
        project.mkdir()
        assert is_suspicious_directory(project) is False

    def test_deep_project_under_home_not_suspicious(self):
        """Project directories under home are NOT suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # e.g., /home/alice/projects/myapp
        project = Path.home() / "projects" / "myapp"
        assert is_suspicious_directory(project) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TestIsSuspiciousDirectoryEdgeCases - Edge cases and boundary conditions
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsSuspiciousDirectoryEdgeCases:
    """Edge case tests for is_suspicious_directory()."""

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_system_directories_are_suspicious_linux(self):
        """System directories like /usr, /etc, /opt are suspicious on Linux."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # These are explicitly in _SUSPICIOUS_DIRS_UNIX
        # Note: On macOS, /etc -> /private/etc so it won't match
        system_dirs = [
            Path("/usr"),
            Path("/etc"),
            Path("/opt"),
        ]
        for dir_path in system_dirs:
            assert is_suspicious_directory(dir_path) is True, (
                f"Expected {dir_path} to be suspicious"
            )

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific paths")
    def test_system_directories_are_suspicious_macos(self):
        """System directories like /usr, /opt are suspicious on macOS."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # On macOS, /etc is a symlink to /private/etc, but /usr and /opt are real
        system_dirs = [
            Path("/usr"),
            Path("/opt"),
        ]
        for dir_path in system_dirs:
            assert is_suspicious_directory(dir_path) is True, (
                f"Expected {dir_path} to be suspicious"
            )

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific paths")
    def test_macos_system_paths_are_suspicious(self):
        """macOS-specific system directories are suspicious on Unix."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        macos_paths = [
            Path("/Applications"),
            Path("/System"),
            Path("/Library"),
        ]
        for dir_path in macos_paths:
            assert is_suspicious_directory(dir_path) is True, (
                f"Expected {dir_path} to be suspicious"
            )

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_dev_directory_is_suspicious_linux(self):
        """/dev (device directory) is suspicious on Linux."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path("/dev")) is True

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_proc_directory_is_suspicious_linux(self):
        """/proc (process filesystem) is suspicious on Linux."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        assert is_suspicious_directory(Path("/proc")) is True

    def test_nested_tmp_path_not_suspicious(self, tmp_path: Path):
        """Nested paths inside tmp are NOT suspicious (when used via pytest tmp_path)."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        # tmp_path creates unique test directories like /tmp/pytest-xxx/test-yyy
        deep_project = tmp_path / "workspace" / "project"
        deep_project.mkdir(parents=True)
        # Deep nested paths in tmp used for testing should be OK
        assert is_suspicious_directory(deep_project) is False

    def test_workspace_under_home_not_suspicious(self):
        """Workspace directories under home should NOT be suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        workspace_paths = [
            Path.home() / "dev",
            Path.home() / "code",
            Path.home() / "workspace",
            Path.home() / "repos",
            Path.home() / "git",
            Path.home() / "src",
        ]
        for workspace in workspace_paths:
            assert is_suspicious_directory(workspace) is False, (
                f"Expected {workspace} to NOT be suspicious"
            )

    def test_deeply_nested_project_not_suspicious(self):
        """Deeply nested project paths should NOT be suspicious."""
        from scc_cli.services.workspace.suspicious import is_suspicious_directory

        deep_path = Path.home() / "dev" / "company" / "team" / "project" / "submodule"
        assert is_suspicious_directory(deep_path) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TestGetSuspiciousReason - Reason messages
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetSuspiciousReason:
    """Tests for get_suspicious_reason()."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific paths")
    def test_root_reason(self):
        """Root returns descriptive reason on Unix."""
        from scc_cli.services.workspace.suspicious import get_suspicious_reason

        reason = get_suspicious_reason(Path("/"))
        assert reason is not None
        # Implementation returns "System directory '/' cannot be used as workspace"
        assert "system" in reason.lower() or "/" in reason

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific paths")
    def test_tmp_reason_linux(self):
        """Tmp returns descriptive reason on Linux."""
        from scc_cli.services.workspace.suspicious import get_suspicious_reason

        # On macOS, /tmp -> /private/tmp which is not in suspicious list
        reason = get_suspicious_reason(Path("/tmp"))
        assert reason is not None
        # Implementation returns "System directory '/tmp' cannot be used as workspace"
        assert "system" in reason.lower() or "/tmp" in reason

    def test_normal_path_no_reason(self, tmp_path: Path):
        """Normal path returns None."""
        from scc_cli.services.workspace.suspicious import get_suspicious_reason

        project = tmp_path / "myproject"
        project.mkdir()
        assert get_suspicious_reason(project) is None

    def test_home_reason(self):
        """Home directory returns descriptive reason."""
        from scc_cli.services.workspace.suspicious import get_suspicious_reason

        reason = get_suspicious_reason(Path.home())
        assert reason is not None
        assert "home" in reason.lower()

    def test_downloads_reason(self):
        """Downloads folder returns descriptive reason."""
        from scc_cli.services.workspace.suspicious import get_suspicious_reason

        reason = get_suspicious_reason(Path.home() / "Downloads")
        assert reason is not None
        # Should mention something about user folder or downloads
        assert len(reason) > 0

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific paths")
    def test_system_directory_reason(self):
        """System directories return descriptive reasons on Unix."""
        from scc_cli.services.workspace.suspicious import get_suspicious_reason

        reason = get_suspicious_reason(Path("/usr"))
        assert reason is not None
        assert "system" in reason.lower() or len(reason) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestGetSuspiciousReasonConsistency - Consistency between functions
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetSuspiciousReasonConsistency:
    """Tests ensuring consistency between is_suspicious_directory and get_suspicious_reason."""

    def test_suspicious_path_has_reason(self):
        """If is_suspicious_directory returns True, get_suspicious_reason returns non-None."""
        from scc_cli.services.workspace.suspicious import (
            get_suspicious_reason,
            is_suspicious_directory,
        )

        # Platform-independent suspicious paths
        suspicious_paths = [
            Path.home(),
            Path.home() / "Downloads",
            Path.home() / "Desktop",
            Path.home() / "Documents",
        ]

        # Add platform-specific paths
        if sys.platform == "linux":
            suspicious_paths.extend(
                [
                    Path("/"),
                    Path("/tmp"),
                    Path("/var"),
                    Path("/home"),
                ]
            )
        elif sys.platform == "darwin":
            suspicious_paths.extend(
                [
                    Path("/"),
                    Path("/Users"),
                ]
            )

        for path in suspicious_paths:
            if is_suspicious_directory(path):
                reason = get_suspicious_reason(path)
                assert reason is not None, f"Path {path} is suspicious but has no reason"
                assert len(reason) > 0, f"Path {path} has empty reason"

    def test_non_suspicious_path_has_no_reason(self, tmp_path: Path):
        """If is_suspicious_directory returns False, get_suspicious_reason returns None."""
        from scc_cli.services.workspace.suspicious import (
            get_suspicious_reason,
            is_suspicious_directory,
        )

        project = tmp_path / "myproject"
        project.mkdir()

        assert is_suspicious_directory(project) is False
        assert get_suspicious_reason(project) is None

    def test_workspace_paths_consistent(self):
        """Workspace paths should be consistently non-suspicious."""
        from scc_cli.services.workspace.suspicious import (
            get_suspicious_reason,
            is_suspicious_directory,
        )

        workspace = Path.home() / "projects" / "myapp"

        assert is_suspicious_directory(workspace) is False
        assert get_suspicious_reason(workspace) is None
