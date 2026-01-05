"""Suspicious directory detection for workspace resolution.

This module provides functions to detect whether a directory is inappropriate
for use as a workspace root. A "suspicious" directory is one that should
require explicit user confirmation before launching a session.

Suspicious directories include:
- User's home directory itself (e.g., /Users/dev, /home/user)
- System directories (/, /tmp, /var, /usr, /etc, /opt, etc.)
- Common non-project locations (Downloads, Desktop, Documents, Library)
- Windows system directories (C:\\, C:\\Windows, C:\\Program Files)
- Drive roots on Windows (D:\\, etc.)

The rationale is:
1. These locations typically don't represent a single project
2. Mounting them into a container exposes too much data
3. Users who explicitly provide such paths should confirm their intent

This logic is extracted from ui/wizard.py's _is_suspicious_directory for reuse
across the codebase without UI dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Unix directories that should NOT be used as workspace
_SUSPICIOUS_DIRS_UNIX: frozenset[str] = frozenset(
    {
        "/",
        "/tmp",
        "/var",
        "/usr",
        "/etc",
        "/opt",
        "/proc",
        "/dev",
        "/sys",
        "/run",
        "/Applications",  # macOS
        "/Library",  # macOS
        "/System",  # macOS
        "/Volumes",  # macOS mount points
        "/mnt",  # Linux mount points
        "/home",  # Parent of all user homes
        "/Users",  # macOS parent of all user homes
    }
)

# Windows directories that should NOT be used as workspace
_SUSPICIOUS_DIRS_WINDOWS: frozenset[str] = frozenset(
    {
        "C:\\",
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\Users",
        "D:\\",
    }
)

# Common non-project locations under home directory
_SUSPICIOUS_HOME_SUBDIRS: tuple[str, ...] = (
    "Downloads",
    "Desktop",
    "Documents",
    "Library",
)


def _safe_resolve(path: Path) -> Path:
    """Safely resolve a path, falling back to absolute() on errors.

    Args:
        path: Path to resolve.

    Returns:
        Resolved path, or absolute path if resolution fails.
    """
    try:
        return path.resolve(strict=False)
    except OSError:
        try:
            return path.absolute()
        except OSError:
            return path


def is_suspicious_directory(path: Path) -> bool:
    """Check if directory is suspicious (should not be used as workspace).

    Cross-platform detection of directories that are likely not project roots:
    - System directories (/, /tmp, C:\\Windows, etc.)
    - User home directory itself
    - Common non-project locations (Downloads, Desktop)

    A "suspicious" workspace requires explicit user confirmation or --force
    to proceed with launch.

    Note: On macOS, paths like /tmp and /var are symlinks to /private/tmp and
    /private/var. We check both the original path string and the resolved path
    to ensure these are detected as suspicious.

    Args:
        path: Directory to check.

    Returns:
        True if this is a suspicious directory.
    """
    resolved = _safe_resolve(path)
    home = _safe_resolve(Path.home())

    # User's home directory itself is suspicious
    if resolved == home:
        return True

    # Get both the original path string and the resolved path string
    # This handles macOS symlinks like /tmp -> /private/tmp
    str_path_original = str(path)
    str_path_resolved = str(resolved)

    # Check platform-specific suspicious directories
    if sys.platform == "win32":
        # Windows: case-insensitive comparison
        str_path_lower = str_path_resolved.lower()
        for suspicious in _SUSPICIOUS_DIRS_WINDOWS:
            if str_path_lower == suspicious.lower():
                return True
        # Also check if it's a drive root (e.g., "D:\")
        if len(str_path_resolved) <= 3 and len(str_path_resolved) >= 2:
            if str_path_resolved[1:3] == ":\\":
                return True
    else:
        # Unix-like systems: check both original and resolved paths
        # This catches /tmp (original) even when it resolves to /private/tmp
        if str_path_original in _SUSPICIOUS_DIRS_UNIX:
            return True
        if str_path_resolved in _SUSPICIOUS_DIRS_UNIX:
            return True

    # Common non-project locations under home
    for subdir in _SUSPICIOUS_HOME_SUBDIRS:
        if resolved == home / subdir:
            return True

    return False


def get_suspicious_reason(path: Path) -> str | None:
    """Get a human-readable reason why a directory is suspicious.

    This provides context for UI error messages explaining why auto-launch
    was blocked or why confirmation is required.

    Note: On macOS, paths like /tmp and /var are symlinks to /private/tmp and
    /private/var. We check both the original path string and the resolved path
    to ensure these are detected and return the user-facing path in the message.

    Args:
        path: Directory to check.

    Returns:
        A human-readable reason string, or None if not suspicious.
    """
    resolved = _safe_resolve(path)
    home = _safe_resolve(Path.home())

    # User's home directory itself
    if resolved == home:
        return "Home directory is too broad - select a specific project"

    # Get both the original path string and the resolved path string
    str_path_original = str(path)
    str_path_resolved = str(resolved)

    # Check platform-specific suspicious directories
    if sys.platform == "win32":
        str_path_lower = str_path_resolved.lower()
        for suspicious in _SUSPICIOUS_DIRS_WINDOWS:
            if str_path_lower == suspicious.lower():
                return f"System directory '{suspicious}' cannot be used as workspace"
        if len(str_path_resolved) <= 3 and len(str_path_resolved) >= 2:
            if str_path_resolved[1:3] == ":\\":
                return f"Drive root '{str_path_resolved}' is too broad - select a specific folder"
    else:
        # Unix-like systems: check both original and resolved paths
        # Return the user-facing path (original) in the error message
        if str_path_original in _SUSPICIOUS_DIRS_UNIX:
            return f"System directory '{str_path_original}' cannot be used as workspace"
        if str_path_resolved in _SUSPICIOUS_DIRS_UNIX:
            return f"System directory '{str_path_resolved}' cannot be used as workspace"

    # Common non-project locations under home
    for subdir in _SUSPICIOUS_HOME_SUBDIRS:
        if resolved == home / subdir:
            return f"'{subdir}' folder is not a typical project location"

    return None
