"""Tests for platform detection module.

TDD approach: These tests define expected behavior for:
- WSL1/WSL2 detection (bug fix: is_wsl2 was returning True for WSL1)
- Platform detection across macOS, Linux, Windows, WSL
- Path operations (Windows mount detection, normalization)
- Environment information utilities
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from scc_cli.platform import (
    Platform,
    check_path_performance,
    detect_platform,
    get_cache_dir,
    get_config_dir,
    get_data_dir,
    get_home_directory,
    get_platform_name,
    get_recommended_workspace_base,
    get_shell,
    get_terminal,
    get_terminal_size,
    is_linux,
    is_macos,
    is_wide_terminal,
    is_windows,
    is_windows_mount_path,
    is_wsl1,
    is_wsl2,
    normalize_path,
    supports_colors,
    supports_unicode,
)

# ═══════════════════════════════════════════════════════════════════════════════
# WSL Detection Tests - THE BUG FIX
# ═══════════════════════════════════════════════════════════════════════════════


class TestWSL2Detection:
    """Tests for is_wsl2() function - should return True ONLY for WSL2."""

    def test_wsl2_with_microsoft_standard_wsl2_in_proc_version(self):
        """WSL2 has 'microsoft-standard-WSL2' in /proc/version."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2 (oe-user@oe-host)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            assert is_wsl2() is True

    def test_wsl2_with_wsl2_lowercase_in_proc_version(self):
        """WSL2 detection should be case-insensitive."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-wsl2 (oe-user@oe-host)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            assert is_wsl2() is True

    def test_wsl1_should_not_return_true_for_is_wsl2(self):
        """BUG FIX: WSL1 has 'Microsoft' but NOT 'wsl2' - is_wsl2() should return False."""
        wsl1_version = "Linux version 4.4.0-18362-Microsoft (microsoft@microsoft.com)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl1_version)),
        ):
            # This is the BUG: currently returns True, should return False
            assert is_wsl2() is False

    def test_native_linux_returns_false(self):
        """Native Linux (no Microsoft/WSL in /proc/version) should return False."""
        native_linux = "Linux version 5.4.0-42-generic (buildd@lcy01-amd64)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
        ):
            assert is_wsl2() is False

    def test_macos_returns_false(self):
        """macOS should return False without checking /proc/version."""
        with patch.object(sys, "platform", "darwin"):
            assert is_wsl2() is False

    def test_windows_returns_false(self):
        """Windows should return False without checking /proc/version."""
        with patch.object(sys, "platform", "win32"):
            assert is_wsl2() is False

    def test_file_not_found_returns_false(self):
        """If /proc/version doesn't exist, should return False gracefully."""
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            assert is_wsl2() is False

    def test_permission_error_returns_false(self):
        """If /proc/version can't be read, should return False gracefully."""
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", side_effect=PermissionError),
        ):
            assert is_wsl2() is False

    def test_os_error_returns_false(self):
        """Generic OSError should return False gracefully."""
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", side_effect=OSError),
        ):
            assert is_wsl2() is False


class TestWSL1Detection:
    """Tests for is_wsl1() function - should return True ONLY for WSL1."""

    def test_wsl1_with_microsoft_no_wsl2_returns_true(self):
        """WSL1 has 'Microsoft' but NOT 'wsl2' in /proc/version."""
        wsl1_version = "Linux version 4.4.0-18362-Microsoft (microsoft@microsoft.com)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl1_version)),
        ):
            assert is_wsl1() is True

    def test_wsl2_should_not_return_true_for_is_wsl1(self):
        """WSL2 has 'wsl2' in /proc/version - is_wsl1() should return False."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2 (oe-user@oe-host)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            assert is_wsl1() is False

    def test_native_linux_returns_false(self):
        """Native Linux should return False for is_wsl1()."""
        native_linux = "Linux version 5.4.0-42-generic (buildd@lcy01-amd64)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
        ):
            assert is_wsl1() is False

    def test_macos_returns_false(self):
        """macOS should return False for is_wsl1()."""
        with patch.object(sys, "platform", "darwin"):
            assert is_wsl1() is False

    def test_windows_returns_false(self):
        """Windows should return False for is_wsl1()."""
        with patch.object(sys, "platform", "win32"):
            assert is_wsl1() is False

    def test_file_not_found_returns_false(self):
        """If /proc/version doesn't exist, should return False gracefully."""
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", side_effect=FileNotFoundError),
        ):
            assert is_wsl1() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Platform Detection Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetectPlatform:
    """Tests for detect_platform() function."""

    def test_detects_macos(self):
        """macOS should be detected correctly."""
        with patch.object(sys, "platform", "darwin"):
            assert detect_platform() == Platform.MACOS

    def test_detects_windows(self):
        """Windows should be detected correctly."""
        with patch.object(sys, "platform", "win32"):
            assert detect_platform() == Platform.WINDOWS

    def test_detects_native_linux(self):
        """Native Linux (not WSL) should be detected correctly."""
        native_linux = "Linux version 5.4.0-42-generic (buildd@lcy01-amd64)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
        ):
            assert detect_platform() == Platform.LINUX

    def test_detects_wsl2(self):
        """WSL2 should be detected as Platform.WSL2."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2 (oe-user@oe-host)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            assert detect_platform() == Platform.WSL2

    def test_wsl1_detected_as_linux_not_wsl2(self):
        """WSL1 should be detected as Platform.LINUX (no WSL1 enum), not WSL2."""
        wsl1_version = "Linux version 4.4.0-18362-Microsoft (microsoft@microsoft.com)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl1_version)),
        ):
            # WSL1 should NOT be Platform.WSL2 - that's the bug
            # Since there's no Platform.WSL1, it should fall back to LINUX
            result = detect_platform()
            assert result != Platform.WSL2
            assert result == Platform.LINUX

    def test_unknown_platform(self):
        """Unknown platform should return Platform.UNKNOWN."""
        with (
            patch.object(sys, "platform", "freebsd"),
            patch("scc_cli.platform.is_wsl2", return_value=False),
        ):
            assert detect_platform() == Platform.UNKNOWN


class TestPlatformHelpers:
    """Tests for individual platform helper functions."""

    def test_is_macos_on_macos(self):
        """is_macos() should return True on macOS."""
        with patch.object(sys, "platform", "darwin"):
            assert is_macos() is True

    def test_is_macos_on_linux(self):
        """is_macos() should return False on Linux."""
        with patch.object(sys, "platform", "linux"):
            assert is_macos() is False

    def test_is_windows_on_windows(self):
        """is_windows() should return True on Windows."""
        with patch.object(sys, "platform", "win32"):
            assert is_windows() is True

    def test_is_windows_on_linux(self):
        """is_windows() should return False on Linux."""
        with patch.object(sys, "platform", "linux"):
            assert is_windows() is False

    def test_is_linux_on_native_linux(self):
        """is_linux() should return True on native Linux."""
        native_linux = "Linux version 5.4.0-42-generic (buildd@lcy01-amd64)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
        ):
            assert is_linux() is True

    def test_is_linux_on_wsl2_returns_false(self):
        """is_linux() should return False on WSL2 (it's not native Linux)."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2 (oe-user@oe-host)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            assert is_linux() is False

    def test_is_linux_on_macos(self):
        """is_linux() should return False on macOS."""
        with patch.object(sys, "platform", "darwin"):
            assert is_linux() is False


class TestGetPlatformName:
    """Tests for get_platform_name() function."""

    def test_macos_name(self):
        """macOS should return 'macOS' as platform name."""
        with patch.object(sys, "platform", "darwin"):
            assert get_platform_name() == "macOS"

    def test_windows_name(self):
        """Windows should return 'Windows' as platform name."""
        with patch.object(sys, "platform", "win32"):
            assert get_platform_name() == "Windows"

    def test_linux_name(self):
        """Native Linux should return 'Linux' as platform name."""
        native_linux = "Linux version 5.4.0-42-generic (buildd@lcy01-amd64)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
        ):
            assert get_platform_name() == "Linux"

    def test_wsl2_name(self):
        """WSL2 should return full WSL2 description."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2 (oe-user@oe-host)"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            assert "WSL2" in get_platform_name()


# ═══════════════════════════════════════════════════════════════════════════════
# Path Operations Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWindowsMountPath:
    """Tests for is_windows_mount_path() function."""

    def test_mnt_c_is_windows_mount(self):
        """Path on /mnt/c should be detected as Windows mount."""
        assert is_windows_mount_path(Path("/mnt/c/Users/test")) is True

    def test_mnt_d_is_windows_mount(self):
        """Path on /mnt/d should be detected as Windows mount."""
        assert is_windows_mount_path(Path("/mnt/d/projects")) is True

    def test_home_is_not_windows_mount(self):
        """Path in home directory should NOT be Windows mount."""
        with patch.object(Path, "resolve", return_value=Path("/home/user/projects")):
            # Create a mock that returns the resolved path
            path = MagicMock(spec=Path)
            path.resolve.return_value = Path("/home/user/projects")
            assert is_windows_mount_path(path) is False

    def test_tmp_is_not_windows_mount(self):
        """Path in /tmp should NOT be Windows mount."""
        with patch.object(Path, "resolve", return_value=Path("/tmp/workspace")):
            path = MagicMock(spec=Path)
            path.resolve.return_value = Path("/tmp/workspace")
            assert is_windows_mount_path(path) is False

    def test_mnt_without_drive_letter_is_not_windows_mount(self):
        """Path like /mnt/data (not a drive letter) should NOT be Windows mount."""
        with patch.object(Path, "resolve", return_value=Path("/mnt/data")):
            path = MagicMock(spec=Path)
            path.resolve.return_value = Path("/mnt/data")
            # /mnt/data starts with /mnt/ but "data" is not a single letter
            result = is_windows_mount_path(path)
            # This depends on implementation - "d" is a valid drive letter
            # but the path continues with "ata" making it /mnt/data
            assert result is False


class TestNormalizePath:
    """Tests for normalize_path() function."""

    def test_normalizes_string_path(self):
        """String paths should be converted to Path objects."""
        result = normalize_path("/tmp/test")
        assert isinstance(result, Path)

    def test_normalizes_path_object(self):
        """Path objects should remain Path objects."""
        result = normalize_path(Path("/tmp/test"))
        assert isinstance(result, Path)

    def test_expands_tilde(self):
        """Tilde (~) should be expanded to home directory."""
        result = normalize_path("~/projects")
        assert str(result).startswith(str(Path.home()))

    def test_resolves_to_absolute(self):
        """Relative paths should be resolved to absolute."""
        result = normalize_path("relative/path")
        assert result.is_absolute()


class TestCheckPathPerformance:
    """Tests for check_path_performance() function."""

    def test_optimal_on_non_wsl(self):
        """On non-WSL systems, all paths should be optimal."""
        with (
            patch.object(sys, "platform", "darwin"),
        ):
            is_optimal, warning = check_path_performance(Path("/Users/test"))
            assert is_optimal is True
            assert warning is None

    def test_wsl2_linux_path_is_optimal(self):
        """On WSL2, Linux filesystem paths should be optimal."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
            patch("scc_cli.platform.is_windows_mount_path", return_value=False),
        ):
            is_optimal, warning = check_path_performance(Path("/home/user/projects"))
            assert is_optimal is True
            assert warning is None

    def test_wsl2_windows_mount_is_not_optimal(self):
        """On WSL2, Windows mount paths should show warning."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
            patch("scc_cli.platform.is_windows_mount_path", return_value=True),
        ):
            is_optimal, warning = check_path_performance(Path("/mnt/c/Users/test"))
            assert is_optimal is False
            assert warning is not None
            assert "Windows filesystem" in warning


class TestGetRecommendedWorkspaceBase:
    """Tests for get_recommended_workspace_base() function."""

    def test_macos_workspace(self):
        """macOS should recommend ~/projects."""
        with patch.object(sys, "platform", "darwin"):
            result = get_recommended_workspace_base()
            assert result == Path.home() / "projects"

    def test_wsl2_workspace_is_linux_path(self):
        """WSL2 should recommend ~/projects (Linux filesystem, not /mnt/c)."""
        wsl2_version = "Linux version 5.15.90.1-microsoft-standard-WSL2"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=wsl2_version)),
        ):
            result = get_recommended_workspace_base()
            assert result == Path.home() / "projects"
            assert not str(result).startswith("/mnt/")


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Information Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnvironmentInfo:
    """Tests for environment information functions."""

    def test_get_shell_from_env(self):
        """get_shell() should return shell name from SHELL env var."""
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            assert get_shell() == "bash"

    def test_get_shell_zsh(self):
        """get_shell() should handle zsh correctly."""
        with patch.dict(os.environ, {"SHELL": "/usr/bin/zsh"}):
            assert get_shell() == "zsh"

    def test_get_shell_unknown_when_missing(self):
        """get_shell() should return 'unknown' when SHELL not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Need to also clear SHELL if it exists
            env_copy = os.environ.copy()
            env_copy.pop("SHELL", None)
            with patch.dict(os.environ, env_copy, clear=True):
                assert get_shell() == "unknown"

    def test_get_terminal_from_term_program(self):
        """get_terminal() should return TERM_PROGRAM if set."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}, clear=False):
            assert get_terminal() == "iTerm.app"

    def test_get_home_directory(self):
        """get_home_directory() should return Path.home()."""
        assert get_home_directory() == Path.home()

    def test_supports_unicode_with_utf8(self):
        """supports_unicode() should return True for UTF-8 encoding."""
        mock_stdout = MagicMock()
        mock_stdout.encoding = "utf-8"
        with patch.object(sys, "stdout", mock_stdout):
            assert supports_unicode() is True

    def test_supports_unicode_with_ascii(self):
        """supports_unicode() should return False for ASCII encoding."""
        mock_stdout = MagicMock()
        mock_stdout.encoding = "ascii"
        with (
            patch.object(sys, "stdout", mock_stdout),
            patch.dict(os.environ, {"LANG": "C"}, clear=True),
        ):
            assert supports_unicode() is False

    def test_supports_colors_with_force_color(self):
        """supports_colors() should return True when FORCE_COLOR is set."""
        with patch.dict(os.environ, {"FORCE_COLOR": "1"}):
            assert supports_colors() is True

    def test_supports_colors_with_no_color(self):
        """supports_colors() should return False when NO_COLOR is set."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert supports_colors() is False

    def test_get_terminal_size_default(self):
        """get_terminal_size() should return (80, 24) on error."""
        with patch("os.get_terminal_size", side_effect=OSError):
            assert get_terminal_size() == (80, 24)

    def test_is_wide_terminal_with_wide_terminal(self):
        """is_wide_terminal() should return True for wide terminals."""
        with patch("scc_cli.platform.get_terminal_size", return_value=(120, 40)):
            assert is_wide_terminal(threshold=110) is True

    def test_is_wide_terminal_with_narrow_terminal(self):
        """is_wide_terminal() should return False for narrow terminals."""
        with patch("scc_cli.platform.get_terminal_size", return_value=(80, 24)):
            assert is_wide_terminal(threshold=110) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Platform-Specific Directory Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlatformDirectories:
    """Tests for platform-specific directory functions."""

    def test_config_dir_macos(self):
        """macOS config dir should be ~/Library/Application Support/scc-cli."""
        with patch.object(sys, "platform", "darwin"):
            result = get_config_dir()
            assert "Library" in str(result)
            assert "Application Support" in str(result)
            assert "scc-cli" in str(result)

    def test_config_dir_linux_with_xdg(self):
        """Linux config dir should respect XDG_CONFIG_HOME."""
        native_linux = "Linux version 5.4.0-42-generic"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
            patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}),
        ):
            result = get_config_dir()
            assert str(result) == "/custom/config/scc-cli"

    def test_config_dir_linux_default(self):
        """Linux config dir should default to ~/.config/scc-cli."""
        native_linux = "Linux version 5.4.0-42-generic"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
            patch.dict(os.environ, {}, clear=True),
        ):
            # Clear XDG_CONFIG_HOME
            env_copy = os.environ.copy()
            env_copy.pop("XDG_CONFIG_HOME", None)
            with patch.dict(os.environ, env_copy, clear=True):
                result = get_config_dir()
                assert ".config/scc-cli" in str(result)

    def test_config_dir_windows(self):
        """Windows config dir should use APPDATA."""
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}),
        ):
            result = get_config_dir()
            assert "scc-cli" in str(result)

    def test_cache_dir_macos(self):
        """macOS cache dir should be ~/Library/Caches/scc-cli."""
        with patch.object(sys, "platform", "darwin"):
            result = get_cache_dir()
            assert "Library" in str(result)
            assert "Caches" in str(result)
            assert "scc-cli" in str(result)

    def test_cache_dir_linux_with_xdg(self):
        """Linux cache dir should respect XDG_CACHE_HOME."""
        native_linux = "Linux version 5.4.0-42-generic"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
            patch.dict(os.environ, {"XDG_CACHE_HOME": "/custom/cache"}),
        ):
            result = get_cache_dir()
            assert str(result) == "/custom/cache/scc-cli"

    def test_data_dir_macos(self):
        """macOS data dir should be ~/Library/Application Support/scc-cli."""
        with patch.object(sys, "platform", "darwin"):
            result = get_data_dir()
            assert "Library" in str(result)
            assert "Application Support" in str(result)

    def test_data_dir_linux_with_xdg(self):
        """Linux data dir should respect XDG_DATA_HOME."""
        native_linux = "Linux version 5.4.0-42-generic"
        with (
            patch.object(sys, "platform", "linux"),
            patch("builtins.open", mock_open(read_data=native_linux)),
            patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/data"}),
        ):
            result = get_data_dir()
            assert str(result) == "/custom/data/scc-cli"
