"""Update checking for scc-cli CLI (stdlib only)."""

import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_installed_version

# Package name on PyPI
PACKAGE_NAME = "scc-cli"

# PyPI JSON API endpoint
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"

# Timeout for PyPI requests (kept short to avoid hanging CLI)
REQUEST_TIMEOUT = 3

# Pre-release tag ordering (lower = earlier in release cycle)
_PRERELEASE_ORDER = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3, "c": 3}


@dataclass
class UpdateInfo:
    """Information about available updates."""

    current: str
    latest: str | None
    update_available: bool
    install_method: str  # 'pip', 'pipx', 'uv', 'editable'


def check_for_updates() -> UpdateInfo:
    """
    Check PyPI for updates using stdlib urllib.

    Returns:
        UpdateInfo with current version, latest version, and update status
    """
    current = _get_current_version()
    latest = _fetch_latest_from_pypi()
    method = _detect_install_method()

    update_available = False
    if latest:
        update_available = _compare_versions(current, latest) < 0

    return UpdateInfo(
        current=current,
        latest=latest,
        update_available=update_available,
        install_method=method,
    )


def _get_current_version() -> str:
    """Get the currently installed version."""
    try:
        return get_installed_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"


def _fetch_latest_from_pypi() -> str | None:
    """Fetch latest version from PyPI JSON API (stdlib)."""
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["info"]["version"]
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError, KeyError):
        # Network errors, invalid JSON, timeouts, or malformed response
        return None


def _parse_version(v: str) -> tuple[tuple[int, ...], tuple[int, int] | None]:
    """
    Parse version string into (numeric_parts, prerelease_info).

    Examples:
        "1.0.0" -> ((1, 0, 0), None)
        "1.0.0rc1" -> ((1, 0, 0), (3, 1))  # rc=3 in order, number=1
        "1.0.0a2" -> ((1, 0, 0), (1, 2))   # a=1 in order, number=2
        "1.0.0.dev1" -> ((1, 0, 0), (0, 1))  # dev=0 in order, number=1
    """
    # Normalize: replace common separators
    v = v.lower().replace("-", ".").replace("_", ".")

    # Extract numeric parts and any pre-release suffix
    # Pattern: digits optionally followed by prerelease tag
    parts: list[int] = []
    prerelease: tuple[int, int] | None = None

    # Split by dots and process each segment
    segments = v.split(".")[:4]  # Limit to 4 segments

    for segment in segments:
        # Check for pre-release tag embedded in segment (e.g., "0rc1")
        match = re.match(r"^(\d+)([a-z]+)(\d*)$", segment)
        if match:
            num, tag, tag_num = match.groups()
            parts.append(int(num))
            if tag in _PRERELEASE_ORDER:
                prerelease = (_PRERELEASE_ORDER[tag], int(tag_num) if tag_num else 0)
            break
        elif segment.isdigit():
            parts.append(int(segment))
        elif segment in _PRERELEASE_ORDER:
            # Standalone tag like ".dev1" after split
            prerelease = (_PRERELEASE_ORDER[segment], 0)
            break
        elif re.match(r"^([a-z]+)(\d*)$", segment):
            # Tag with optional number like "dev1"
            m = re.match(r"^([a-z]+)(\d*)$", segment)
            if m:
                tag, tag_num = m.groups()
                if tag in _PRERELEASE_ORDER:
                    prerelease = (_PRERELEASE_ORDER[tag], int(tag_num) if tag_num else 0)
            break
        else:
            # Unknown format, try to extract leading digits
            num_str = ""
            for char in segment:
                if char.isdigit():
                    num_str += char
                else:
                    break
            if num_str:
                parts.append(int(num_str))

    # Ensure at least 3 parts for comparison
    while len(parts) < 3:
        parts.append(0)

    return (tuple(parts), prerelease)


def _compare_versions(v1: str, v2: str) -> int:
    """
    Compare versions with proper pre-release handling (stdlib, no packaging dep).

    Pre-release versions (dev, alpha, beta, rc) are LESS than the final release.
    Example: 1.0.0rc1 < 1.0.0 < 1.0.1

    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    parts1, pre1 = _parse_version(v1)
    parts2, pre2 = _parse_version(v2)

    # Compare numeric parts first
    if parts1 != parts2:
        return (parts1 > parts2) - (parts1 < parts2)

    # Same numeric version - check pre-release status
    # Final release (no prerelease) > any prerelease
    if pre1 is None and pre2 is None:
        return 0
    if pre1 is None:
        return 1  # v1 is final release, v2 is prerelease -> v1 > v2
    if pre2 is None:
        return -1  # v1 is prerelease, v2 is final release -> v1 < v2

    # Both are prereleases - compare them
    return (pre1 > pre2) - (pre1 < pre2)


def _detect_install_method() -> str:
    """
    Detect how the package was installed by checking the environment context.

    Uses sys.prefix, environment variables, and path patterns to determine
    the actual install method, not just which tools exist on the system.

    Returns one of: 'pipx', 'uv', 'pip', 'editable'
    """
    # Check for editable install first (development mode)
    try:
        from importlib.metadata import distribution

        dist = distribution(PACKAGE_NAME)
        # PEP 610: Check for editable install via direct_url.json
        if dist.read_text("direct_url.json"):
            import json as json_mod

            direct_url = json_mod.loads(dist.read_text("direct_url.json"))
            if direct_url.get("dir_info", {}).get("editable", False):
                return "editable"
    except Exception:
        pass

    # Get the prefix path where this Python is installed
    prefix = sys.prefix.lower()

    # Check for pipx environment (pipx creates venvs in specific locations)
    # Common patterns: ~/.local/pipx/venvs/, ~/.local/share/pipx/venvs/
    pipx_indicators = [
        "pipx/venvs",
        "pipx\\venvs",  # Windows
        os.environ.get("PIPX_HOME", ""),
        os.environ.get("PIPX_LOCAL_VENVS", ""),
    ]
    if any(ind and ind.lower() in prefix for ind in pipx_indicators if ind):
        return "pipx"

    # Check for uv environment
    # uv uses UV_PYTHON_INSTALL_DIR and creates venvs differently
    uv_indicators = [
        os.environ.get("UV_PYTHON_INSTALL_DIR", ""),
        os.environ.get("UV_CACHE_DIR", ""),
    ]
    # uv environments often have .uv in the path or UV env vars set
    if ".uv" in prefix or any(ind for ind in uv_indicators if ind):
        return "uv"

    # Check if uv is available and likely the preferred tool
    # (only if we can't detect pipx context)
    if shutil.which("uv"):
        return "uv"

    # Check if pipx is available as fallback
    if shutil.which("pipx"):
        return "pipx"

    # Default to pip
    return "pip"


def get_update_command(method: str) -> str:
    """
    Return the appropriate update command for the install method.

    Args:
        method: One of 'pipx', 'uv', 'pip', 'editable'

    Returns:
        Shell command to run for updating
    """
    if method == "pipx":
        return f"pipx upgrade {PACKAGE_NAME}"
    elif method == "uv":
        return f"uv pip install --upgrade {PACKAGE_NAME}"
    else:
        return f"pip install --upgrade {PACKAGE_NAME}"
