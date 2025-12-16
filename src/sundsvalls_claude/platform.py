"""
Platform detection and cross-platform utilities.

Handles detection of:
- Operating system (macOS, Linux, Windows, WSL2)
- Path normalization across platforms
- Performance warnings for suboptimal configurations

WSL2 Considerations:
- Files on /mnt/c (Windows filesystem) are significantly slower
- Recommend using ~/projects inside WSL for optimal performance
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple
from enum import Enum


class Platform(Enum):
    """Supported platforms."""

    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    WSL2 = "wsl2"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# Platform Detection
# ═══════════════════════════════════════════════════════════════════════════════


def detect_platform() -> Platform:
    """
    Detect the current platform.

    Returns the most specific platform identifier:
    - WSL2 takes precedence over Linux
    - macOS, Windows, Linux detected by sys.platform
    """
    if is_wsl2():
        return Platform.WSL2

    if sys.platform == "darwin":
        return Platform.MACOS
    elif sys.platform == "win32":
        return Platform.WINDOWS
    elif sys.platform.startswith("linux"):
        return Platform.LINUX

    return Platform.UNKNOWN


def is_wsl2() -> bool:
    """
    Detect if running in WSL2 environment.

    Checks /proc/version for Microsoft kernel signature.
    """
    if sys.platform != "linux":
        return False

    try:
        with open("/proc/version", "r") as f:
            version_info = f.read().lower()
            return "microsoft" in version_info or "wsl" in version_info
    except (FileNotFoundError, PermissionError, OSError):
        return False


def is_wsl1() -> bool:
    """
    Detect if running in WSL1 (legacy) environment.

    WSL1 has "Microsoft" but not "WSL2" in /proc/version.
    """
    if not is_wsl2():
        return False

    try:
        with open("/proc/version", "r") as f:
            version_info = f.read().lower()
            # WSL2 typically has "wsl2" in the version
            return "wsl2" not in version_info and "microsoft" in version_info
    except (FileNotFoundError, PermissionError, OSError):
        return False


def is_macos() -> bool:
    """Check if running on macOS."""
    return sys.platform == "darwin"


def is_linux() -> bool:
    """Check if running on native Linux (not WSL)."""
    return sys.platform.startswith("linux") and not is_wsl2()


def is_windows() -> bool:
    """Check if running on native Windows."""
    return sys.platform == "win32"


def get_platform_name() -> str:
    """Get human-readable platform name."""
    platform = detect_platform()
    names = {
        Platform.MACOS: "macOS",
        Platform.LINUX: "Linux",
        Platform.WINDOWS: "Windows",
        Platform.WSL2: "WSL2 (Windows Subsystem for Linux)",
        Platform.UNKNOWN: "Unknown",
    }
    return names.get(platform, "Unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# Path Operations
# ═══════════════════════════════════════════════════════════════════════════════


def is_windows_mount_path(path: Path) -> bool:
    """
    Check if a path is on the Windows filesystem (via /mnt/c, /mnt/d, etc.).

    In WSL2, paths like /mnt/c/Users/... are on the Windows filesystem
    and have significantly slower I/O performance.
    """
    resolved = path.resolve()
    path_str = str(resolved)

    # Check for /mnt/<drive_letter> pattern
    if path_str.startswith("/mnt/") and len(path_str) > 5:
        # /mnt/c, /mnt/d, etc.
        drive_letter = path_str[5]
        if drive_letter.isalpha() and (len(path_str) == 6 or path_str[6] == "/"):
            return True

    return False


def normalize_path(path: str | Path) -> Path:
    """
    Normalize a path for the current platform.

    - Expands ~ to home directory
    - Resolves to absolute path
    - Handles Windows/Unix path differences
    """
    if isinstance(path, str):
        path = Path(path)

    # Expand user home directory
    path = path.expanduser()

    # Resolve to absolute path
    path = path.resolve()

    return path


def get_recommended_workspace_base() -> Path:
    """
    Get the recommended workspace base directory for the platform.

    - macOS/Linux: ~/projects
    - WSL2: ~/projects (inside WSL, not /mnt/c)
    - Windows: C:\\Users\\<user>\\projects
    """
    if is_wsl2():
        # In WSL2, always use Linux filesystem for performance
        return Path.home() / "projects"
    elif is_windows():
        return Path.home() / "projects"
    else:
        return Path.home() / "projects"


def check_path_performance(path: Path) -> Tuple[bool, Optional[str]]:
    """
    Check if a path has optimal performance characteristics.

    Returns:
        Tuple of (is_optimal, warning_message)
    """
    if not is_wsl2():
        return True, None

    if is_windows_mount_path(path):
        return False, (
            f"Path {path} is on the Windows filesystem.\n"
            "File operations will be significantly slower.\n"
            "Recommendation: Move to ~/projects inside WSL."
        )

    return True, None


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Information
# ═══════════════════════════════════════════════════════════════════════════════


def get_shell() -> str:
    """Get the current shell name."""
    shell = os.environ.get("SHELL", "")
    if shell:
        return Path(shell).name
    return "unknown"


def get_terminal() -> str:
    """Get the current terminal emulator name."""
    term = os.environ.get("TERM_PROGRAM", os.environ.get("TERMINAL", ""))
    if term:
        return term
    return os.environ.get("TERM", "unknown")


def get_home_directory() -> Path:
    """Get the user's home directory."""
    return Path.home()


def supports_unicode() -> bool:
    """
    Check if the terminal supports Unicode characters.

    Returns True if UTF-8 encoding is available.
    """
    encoding = sys.stdout.encoding
    if encoding:
        return encoding.lower() in ("utf-8", "utf8")

    # Check LANG environment variable
    lang = os.environ.get("LANG", "")
    return "utf-8" in lang.lower() or "utf8" in lang.lower()


def supports_colors() -> bool:
    """
    Check if the terminal supports ANSI colors.

    Checks various environment indicators.
    """
    # Rich handles this well, but we can do basic detection
    if os.environ.get("NO_COLOR"):
        return False

    if os.environ.get("FORCE_COLOR"):
        return True

    # Check if stdout is a TTY
    if hasattr(sys.stdout, "isatty") and sys.stdout.isatty():
        return True

    return False


def get_terminal_size() -> Tuple[int, int]:
    """
    Get terminal size (columns, rows).

    Returns (80, 24) as default if detection fails.
    """
    try:
        size = os.get_terminal_size()
        return size.columns, size.lines
    except OSError:
        return 80, 24


def is_wide_terminal(threshold: int = 110) -> bool:
    """
    Check if terminal is wide enough for full layout.

    Args:
        threshold: Minimum columns for "wide" mode (default 110)

    Returns:
        True if terminal width >= threshold
    """
    columns, _ = get_terminal_size()
    return columns >= threshold


# ═══════════════════════════════════════════════════════════════════════════════
# Platform-Specific Paths
# ═══════════════════════════════════════════════════════════════════════════════


def get_config_dir() -> Path:
    """
    Get the platform-appropriate configuration directory.

    - macOS: ~/Library/Application Support/sundsvalls-claude
    - Linux/WSL2: ~/.config/sundsvalls-claude
    - Windows: %APPDATA%\\sundsvalls-claude
    """
    if is_macos():
        return Path.home() / "Library" / "Application Support" / "sundsvalls-claude"
    elif is_windows():
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "sundsvalls-claude"
        return Path.home() / "AppData" / "Roaming" / "sundsvalls-claude"
    else:
        # Linux, WSL2
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "sundsvalls-claude"
        return Path.home() / ".config" / "sundsvalls-claude"


def get_cache_dir() -> Path:
    """
    Get the platform-appropriate cache directory.

    - macOS: ~/Library/Caches/sundsvalls-claude
    - Linux/WSL2: ~/.cache/sundsvalls-claude
    - Windows: %LOCALAPPDATA%\\sundsvalls-claude\\cache
    """
    if is_macos():
        return Path.home() / "Library" / "Caches" / "sundsvalls-claude"
    elif is_windows():
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata) / "sundsvalls-claude" / "cache"
        return Path.home() / "AppData" / "Local" / "sundsvalls-claude" / "cache"
    else:
        # Linux, WSL2
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            return Path(xdg_cache) / "sundsvalls-claude"
        return Path.home() / ".cache" / "sundsvalls-claude"


def get_data_dir() -> Path:
    """
    Get the platform-appropriate data directory.

    - macOS: ~/Library/Application Support/sundsvalls-claude
    - Linux/WSL2: ~/.local/share/sundsvalls-claude
    - Windows: %LOCALAPPDATA%\\sundsvalls-claude\\data
    """
    if is_macos():
        return Path.home() / "Library" / "Application Support" / "sundsvalls-claude"
    elif is_windows():
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata) / "sundsvalls-claude" / "data"
        return Path.home() / "AppData" / "Local" / "sundsvalls-claude" / "data"
    else:
        # Linux, WSL2
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / "sundsvalls-claude"
        return Path.home() / ".local" / "share" / "sundsvalls-claude"
