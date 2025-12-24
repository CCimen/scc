"""
Check for updates to scc-cli CLI and organization config.

Two independent update mechanisms:
1. CLI version: Check PyPI (public, always accessible), throttle to once/24h
2. Org config: Check remote URL with ETag, throttle to TTL (1-6h typically)

Design principles:
- Non-blocking: Update checks do not delay CLI startup
- Graceful degradation: Offline = use cache silently
- Cache-first: Always prefer cached data over network errors
- UX-friendly: Clear, non-intrusive update notifications
"""

import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_installed_version
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from rich.console import Console
from rich.panel import Panel

if TYPE_CHECKING:
    pass

# Package name on PyPI
PACKAGE_NAME = "scc-cli"

# PyPI JSON API endpoint
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"

# Timeout for PyPI requests (kept short to avoid hanging CLI)
REQUEST_TIMEOUT = 3

# Throttling: Don't check CLI version more than once per day
CLI_CHECK_INTERVAL_HOURS = 24

# Throttling: Org config check interval (1 hour minimum between checks)
# Note: This is separate from cache TTL. TTL controls staleness,
# this controls how often we even attempt to check.
ORG_CONFIG_CHECK_INTERVAL_HOURS = 1

# Cache directory for update check timestamps
UPDATE_CHECK_CACHE_DIR = Path.home() / ".cache" / "scc"
UPDATE_CHECK_META_FILE = UPDATE_CHECK_CACHE_DIR / "update_check_meta.json"

# Pre-release tag ordering (lower = earlier in release cycle)
_PRERELEASE_ORDER = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3, "c": 3}


@dataclass
class UpdateInfo:
    """Information about available CLI updates."""

    current: str
    latest: str | None
    update_available: bool
    install_method: str  # 'pip', 'pipx', 'uv', 'editable'


@dataclass
class OrgConfigUpdateResult:
    """Result of org config update check."""

    status: str  # 'updated', 'unchanged', 'offline', 'auth_failed', 'no_cache', 'standalone'
    message: str | None = None
    cached_age_hours: float | None = None


@dataclass
class UpdateCheckResult:
    """Combined result of all update checks."""

    cli_update: UpdateInfo | None = None
    org_config: OrgConfigUpdateResult | None = None


def check_for_updates() -> UpdateInfo:
    """
    Check PyPI for updates using stdlib urllib and return update info.

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
    """Return the currently installed version."""
    try:
        return get_installed_version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "0.0.0"


def _fetch_latest_from_pypi() -> str | None:
    """Fetch and return the latest version from the PyPI JSON API."""
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=REQUEST_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
            return cast(str, data["info"]["version"])
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError, KeyError):
        # Network errors, invalid JSON, timeouts, or malformed response
        return None


def _parse_version(v: str) -> tuple[tuple[int, ...], tuple[int, int] | None]:
    """
    Parse a version string into (numeric_parts, prerelease_info).

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
    Compare two versions with proper pre-release handling.

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

    Use sys.prefix, environment variables, and path patterns to determine
    the actual install method, not just which tools exist on the system.

    Returns one of: 'pipx', 'uv', 'pip', 'editable'
    """
    # Check for editable install first (development mode)
    try:
        from importlib.metadata import distribution

        dist = distribution(PACKAGE_NAME)
        # PEP 610: Check for editable install via direct_url.json
        direct_url_text = dist.read_text("direct_url.json")
        if direct_url_text:
            import json as json_mod

            direct_url = json_mod.loads(direct_url_text)
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

    # Check for uv tool install (CLI tools installed via `uv tool install`)
    # These are in ~/.local/share/uv/tools/ or $UV_TOOL_DIR
    uv_tool_indicators = [
        "uv/tools",
        "uv\\tools",  # Windows
        os.environ.get("UV_TOOL_DIR", ""),
    ]
    if any(ind and ind.lower() in prefix for ind in uv_tool_indicators if ind):
        return "uv_tool"

    # Check for uv environment (regular uv pip install in venv)
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
    Return the appropriate update command for the given install method.

    Args:
        method: One of 'pipx', 'uv_tool', 'uv', 'pip', 'editable'

    Returns:
        Shell command to run for updating
    """
    if method == "pipx":
        return f"pipx upgrade {PACKAGE_NAME}"
    elif method == "uv_tool":
        return f"uv tool upgrade {PACKAGE_NAME}"
    elif method == "uv":
        return f"uv pip install --upgrade {PACKAGE_NAME}"
    else:
        return f"pip install --upgrade {PACKAGE_NAME}"


# ═══════════════════════════════════════════════════════════════════════════════
# Update Check Throttling
# ═══════════════════════════════════════════════════════════════════════════════


def _load_update_check_meta() -> dict[Any, Any]:
    """Load and return update check metadata (timestamps for throttling)."""
    if not UPDATE_CHECK_META_FILE.exists():
        return {}
    try:
        return cast(dict[Any, Any], json.loads(UPDATE_CHECK_META_FILE.read_text()))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_update_check_meta(meta: dict[str, Any]) -> None:
    """Save update check metadata to disk."""
    UPDATE_CHECK_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_CHECK_META_FILE.write_text(json.dumps(meta, indent=2))


def _should_check_cli_updates() -> bool:
    """Return True if enough time has passed since last CLI update check."""
    meta = _load_update_check_meta()
    last_check_str = meta.get("cli_last_check")

    if not last_check_str:
        return True

    try:
        last_check = datetime.fromisoformat(last_check_str)
        now = datetime.now(timezone.utc)
        elapsed = now - last_check
        return elapsed > timedelta(hours=CLI_CHECK_INTERVAL_HOURS)
    except (ValueError, TypeError):
        return True


def _mark_cli_check_done() -> None:
    """Update the timestamp for CLI update check."""
    meta = _load_update_check_meta()
    meta["cli_last_check"] = datetime.now(timezone.utc).isoformat()
    _save_update_check_meta(meta)


def _should_check_org_config() -> bool:
    """Return True if enough time has passed since last org config check."""
    meta = _load_update_check_meta()
    last_check_str = meta.get("org_config_last_check")

    if not last_check_str:
        return True

    try:
        last_check = datetime.fromisoformat(last_check_str)
        now = datetime.now(timezone.utc)
        elapsed = now - last_check
        return elapsed > timedelta(hours=ORG_CONFIG_CHECK_INTERVAL_HOURS)
    except (ValueError, TypeError):
        return True


def _mark_org_config_check_done() -> None:
    """Update the timestamp for org config check."""
    meta = _load_update_check_meta()
    meta["org_config_last_check"] = datetime.now(timezone.utc).isoformat()
    _save_update_check_meta(meta)


# ═══════════════════════════════════════════════════════════════════════════════
# Org Config Update Checking
# ═══════════════════════════════════════════════════════════════════════════════


def check_org_config_update(
    user_config: dict[str, Any], force: bool = False
) -> OrgConfigUpdateResult:
    """
    Check for org config updates using ETag conditional fetch.

    Handle these scenarios:
    - On corporate network: Fetch org config with auth token, update cache
    - Off VPN (offline): Use cached config, skip update check silently
    - Auth token expired/invalid: Use cached config, show warning
    - Never fetched + offline: Return 'no_cache' status

    Args:
        user_config: User config dict with organization_source
        force: Force check even if throttle interval hasn't elapsed

    Returns:
        OrgConfigUpdateResult with status and optional message
    """
    # Import here to avoid circular imports
    from scc_cli import remote

    # Standalone mode - no org config to update
    if user_config.get("standalone"):
        return OrgConfigUpdateResult(status="standalone")

    # No organization source configured
    org_source = user_config.get("organization_source")
    if not org_source:
        return OrgConfigUpdateResult(status="standalone")

    url = org_source.get("url")
    if not url:
        return OrgConfigUpdateResult(status="standalone")

    auth_spec = org_source.get("auth")

    # Check throttle (unless forced)
    if not force and not _should_check_org_config():
        # Return early - too soon to check
        return OrgConfigUpdateResult(status="throttled")

    # Try to load existing cache
    cached_config, meta = remote.load_from_cache()

    # Calculate cache age if available
    cached_age_hours = None
    if meta and meta.get("org_config", {}).get("fetched_at"):
        try:
            fetched_at = datetime.fromisoformat(meta["org_config"]["fetched_at"])
            now = datetime.now(timezone.utc)
            cached_age_hours = (now - fetched_at).total_seconds() / 3600
        except (ValueError, TypeError):
            pass

    # Resolve auth
    auth = remote.resolve_auth(auth_spec) if auth_spec else None

    # Get cached ETag for conditional request
    etag = meta.get("org_config", {}).get("etag") if meta else None

    # Attempt to fetch with ETag
    try:
        config, new_etag, status = remote.fetch_org_config(url, auth=auth, etag=etag)
    except Exception:
        # Network error - use cache silently
        _mark_org_config_check_done()
        if cached_config:
            return OrgConfigUpdateResult(
                status="offline",
                cached_age_hours=cached_age_hours,
            )
        return OrgConfigUpdateResult(status="no_cache")

    # Mark check as done
    _mark_org_config_check_done()

    # 304 Not Modified - cache is current
    if status == 304:
        return OrgConfigUpdateResult(
            status="unchanged",
            cached_age_hours=cached_age_hours,
        )

    # 200 OK - new config available
    if status == 200 and config is not None:
        # Save to cache
        ttl_hours = config.get("defaults", {}).get("cache_ttl_hours", 24)
        remote.save_to_cache(config, url, new_etag, ttl_hours)
        return OrgConfigUpdateResult(
            status="updated",
            message="Organization config updated from remote",
        )

    # 401/403 - auth failed
    if status in (401, 403):
        if cached_config:
            return OrgConfigUpdateResult(
                status="auth_failed",
                message="Auth failed for org config, using cached version",
                cached_age_hours=cached_age_hours,
            )
        return OrgConfigUpdateResult(
            status="auth_failed",
            message="Auth failed and no cached config available",
        )

    # Other errors - use cache if available
    if cached_config:
        return OrgConfigUpdateResult(
            status="offline",
            cached_age_hours=cached_age_hours,
        )

    return OrgConfigUpdateResult(status="no_cache")


# ═══════════════════════════════════════════════════════════════════════════════
# Combined Update Check
# ═══════════════════════════════════════════════════════════════════════════════


def check_all_updates(user_config: dict[str, Any], force: bool = False) -> UpdateCheckResult:
    """
    Check for all available updates (CLI and org config).

    Use this as the main entry point for update checking.

    Args:
        user_config: User config dict
        force: Force checks even if throttle intervals haven't elapsed

    Returns:
        UpdateCheckResult with CLI and org config update info
    """
    result = UpdateCheckResult()

    # Check CLI updates (throttled)
    if force or _should_check_cli_updates():
        result.cli_update = check_for_updates()
        _mark_cli_check_done()

    # Check org config updates (throttled)
    result.org_config = check_org_config_update(user_config, force=force)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# UX-Friendly Console Output
# ═══════════════════════════════════════════════════════════════════════════════


def render_update_notification(console: Console, result: UpdateCheckResult) -> None:
    """
    Render update notifications in a UX-friendly way.

    Design principles:
    - Non-intrusive: Use a single line for most cases
    - Actionable: Show exact command to run
    - Quiet on success: Produce no noise when everything is current

    Args:
        console: Rich Console instance
        result: UpdateCheckResult from check_all_updates()
    """
    # CLI update notification
    if result.cli_update and result.cli_update.update_available:
        cli = result.cli_update
        update_cmd = get_update_command(cli.install_method)
        console.print(
            f"[cyan]⬆ Update available:[/cyan] "
            f"scc-cli [dim]{cli.current}[/dim] → [green]{cli.latest}[/green]  "
            f"[dim]Run: {update_cmd}[/dim]"
        )

    # Org config notifications (only show warnings/errors)
    if result.org_config:
        org = result.org_config

        if org.status == "updated":
            console.print("[green]✓[/green] Organization config updated")

        elif org.status == "auth_failed" and org.cached_age_hours is not None:
            age_str = _format_age(org.cached_age_hours)
            console.print(
                f"[yellow]⚠ Auth failed for org config, using cached version ({age_str} old)[/yellow]"
            )

        elif org.status == "auth_failed":
            console.print("[red]✗ Auth failed and no cached config available. Run: scc setup[/red]")

        elif org.status == "no_cache":
            console.print(
                "[yellow]⚠ No organization config cached. Run: scc setup when on network[/yellow]"
            )

        # Don't show anything for 'unchanged', 'offline', 'standalone', 'throttled'
        # - These are normal states that don't need user attention


def render_update_status_panel(console: Console, result: UpdateCheckResult) -> None:
    """
    Render a detailed update status panel for the `scc update` command.

    Args:
        console: Rich Console instance
        result: UpdateCheckResult from check_all_updates()
    """
    lines = []

    # CLI Version section
    lines.append("[bold]CLI Version[/bold]")
    if result.cli_update:
        cli = result.cli_update
        if cli.update_available:
            lines.append(f"  Current: {cli.current}")
            lines.append(f"  Latest:  [green]{cli.latest}[/green] [cyan](update available)[/cyan]")
            lines.append(f"  Update:  [dim]{get_update_command(cli.install_method)}[/dim]")
        else:
            lines.append(f"  [green]✓[/green] {cli.current} (up to date)")
    else:
        lines.append("  [dim]Not checked (throttled)[/dim]")

    lines.append("")

    # Org Config section
    lines.append("[bold]Organization Config[/bold]")
    if result.org_config:
        org = result.org_config

        if org.status == "standalone":
            lines.append("  [dim]Standalone mode (no org config)[/dim]")

        elif org.status == "updated":
            lines.append("  [green]✓[/green] Updated from remote")

        elif org.status == "unchanged":
            if org.cached_age_hours is not None:
                age_str = _format_age(org.cached_age_hours)
                lines.append(f"  [green]✓[/green] Current (cached {age_str} ago)")
            else:
                lines.append("  [green]✓[/green] Current (unchanged)")

        elif org.status == "offline":
            if org.cached_age_hours is not None:
                age_str = _format_age(org.cached_age_hours)
                lines.append(f"  [yellow]⚠[/yellow] Using cached config ({age_str} old)")
                lines.append("  [dim]Remote check failed (offline?)[/dim]")
            else:
                lines.append("  [yellow]⚠[/yellow] Offline, using cached config")

        elif org.status == "auth_failed":
            if org.cached_age_hours is not None:
                age_str = _format_age(org.cached_age_hours)
                lines.append(f"  [yellow]⚠[/yellow] Auth failed, using cached ({age_str} old)")
            else:
                lines.append("  [red]✗[/red] Auth failed, no cache available")
            lines.append("  [dim]Check your auth token or run: scc setup[/dim]")

        elif org.status == "no_cache":
            lines.append("  [red]✗[/red] No cached config available")
            lines.append("  [dim]Run: scc setup when on network[/dim]")

        elif org.status == "throttled":
            lines.append("  [dim]Not checked (throttled)[/dim]")
    else:
        lines.append("  [dim]Not checked[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="[bold]Update Status[/bold]",
        border_style="blue",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()


def _format_age(hours: float) -> str:
    """Format an age in hours as a human-readable string."""
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif hours < 24:
        h = int(hours)
        return f"{h} hour{'s' if h != 1 else ''}"
    else:
        days = int(hours / 24)
        return f"{days} day{'s' if days != 1 else ''}"
