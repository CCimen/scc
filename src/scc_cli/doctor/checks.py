"""Health check functions for the doctor module.

This module contains all check functions organized by category:
- JSON validation helpers
- Environment checks (Git, Docker, WSL2, Workspace)
- Configuration checks
- Organization & Marketplace checks
- Cache & State checks

All check functions return CheckResult or CheckResult | None.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from ..theme import Indicators
from .types import CheckResult, JsonValidationResult

# ═══════════════════════════════════════════════════════════════════════════════
# JSON Validation Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def validate_json_file(file_path: Path) -> JsonValidationResult:
    """
    Validate a JSON file and extract detailed error information.

    Args:
        file_path: Path to the JSON file to validate

    Returns:
        JsonValidationResult with validation status and error details
    """
    if not file_path.exists():
        return JsonValidationResult(valid=True, file_path=file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
        json.loads(content)
        return JsonValidationResult(valid=True, file_path=file_path)
    except json.JSONDecodeError as e:
        code_frame = format_code_frame(content, e.lineno, e.colno, file_path)
        return JsonValidationResult(
            valid=False,
            error_message=e.msg,
            line=e.lineno,
            column=e.colno,
            file_path=file_path,
            code_frame=code_frame,
        )
    except OSError as e:
        return JsonValidationResult(
            valid=False,
            error_message=f"Cannot read file: {e}",
            file_path=file_path,
        )


def format_code_frame(
    content: str,
    error_line: int,
    error_col: int,
    file_path: Path,
    context_lines: int = 2,
) -> str:
    """
    Format a code frame showing the error location with context.

    Creates a visual representation like:
        10 │   "selected_profile": "dev-team",
        11 │   "preferences": {
      → 12 │     "auto_update": true
           │     ^
        13 │     "show_tips": false
        14 │   }

    Args:
        content: The file content
        error_line: Line number where error occurred (1-indexed)
        error_col: Column number where error occurred (1-indexed)
        file_path: Path to the file (for display)
        context_lines: Number of lines to show before/after error

    Returns:
        Formatted code frame string with Rich markup
    """
    lines = content.splitlines()
    total_lines = len(lines)

    # Calculate line range to display
    start_line = max(1, error_line - context_lines)
    end_line = min(total_lines, error_line + context_lines)

    # Calculate padding for line numbers
    max_line_num = end_line
    line_num_width = len(str(max_line_num))

    frame_lines = []

    # Add file path header
    frame_lines.append(f"[dim]File: {file_path}[/dim]")
    frame_lines.append("")

    for line_num in range(start_line, end_line + 1):
        line_content = lines[line_num - 1] if line_num <= total_lines else ""

        # Truncate long lines to prevent secret leakage (keep first 80 chars)
        if len(line_content) > 80:
            line_content = line_content[:77] + "..."

        if line_num == error_line:
            # Error line with arrow indicator
            frame_lines.append(
                f"[bold red]{Indicators.get('ARROW')} {line_num:>{line_num_width}} │[/bold red] "
                f"[white]{_escape_rich(line_content)}[/white]"
            )
            # Caret line pointing to error column
            caret_padding = " " * (line_num_width + 4 + max(0, error_col - 1))
            frame_lines.append(f"[bold red]{caret_padding}^[/bold red]")
        else:
            # Context line
            frame_lines.append(
                f"[dim]  {line_num:>{line_num_width}} │[/dim] "
                f"[dim]{_escape_rich(line_content)}[/dim]"
            )

    return "\n".join(frame_lines)


def _escape_rich(text: str) -> str:
    """Escape Rich markup characters in text."""
    return text.replace("[", "\\[").replace("]", "\\]")


def get_json_error_hints(error_message: str) -> list[str]:
    """
    Get helpful hints based on common JSON error messages.

    Args:
        error_message: The JSON decode error message

    Returns:
        List of helpful hints for fixing the error
    """
    hints = []
    error_lower = error_message.lower()

    if "expecting" in error_lower and "," in error_lower:
        hints.append("Missing comma between values")
    elif "expecting property name" in error_lower:
        hints.append("Trailing comma after last item (not allowed in JSON)")
        hints.append("Missing closing brace or bracket")
    elif "expecting value" in error_lower:
        hints.append("Missing value after colon or comma")
        hints.append("Empty array or object element")
    elif "expecting ':'" in error_lower:
        hints.append("Missing colon after property name")
    elif "unterminated string" in error_lower or "invalid \\escape" in error_lower:
        hints.append("Unclosed string quote or invalid escape sequence")
    elif "extra data" in error_lower:
        hints.append("Multiple root objects (JSON must have single root)")

    if not hints:
        hints.append("Check JSON syntax near the indicated line")

    return hints


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Checks (Git, Docker, WSL2, Workspace)
# ═══════════════════════════════════════════════════════════════════════════════


def check_git() -> CheckResult:
    """Check if Git is installed and accessible."""
    from .. import git as git_module

    if not git_module.check_git_installed():
        return CheckResult(
            name="Git",
            passed=False,
            message="Git is not installed or not in PATH",
            fix_hint="Install Git from https://git-scm.com/downloads",
            fix_url="https://git-scm.com/downloads",
            severity="error",
        )

    version = git_module.get_git_version()
    return CheckResult(
        name="Git",
        passed=True,
        message="Git is installed and accessible",
        version=version,
    )


def check_docker() -> CheckResult:
    """Check if Docker is installed and running."""
    from .. import docker as docker_module

    version = docker_module.get_docker_version()

    if version is None:
        return CheckResult(
            name="Docker",
            passed=False,
            message="Docker is not installed or not running",
            fix_hint="Install Docker Desktop from https://docker.com/products/docker-desktop",
            fix_url="https://docker.com/products/docker-desktop",
            severity="error",
        )

    # Parse and check minimum version
    current = docker_module._parse_version(version)
    required = docker_module._parse_version(docker_module.MIN_DOCKER_VERSION)

    if current < required:
        return CheckResult(
            name="Docker",
            passed=False,
            message=f"Docker version {'.'.join(map(str, current))} is below minimum {docker_module.MIN_DOCKER_VERSION}",
            version=version,
            fix_hint="Update Docker Desktop to the latest version",
            fix_url="https://docker.com/products/docker-desktop",
            severity="error",
        )

    return CheckResult(
        name="Docker",
        passed=True,
        message="Docker is installed and meets version requirements",
        version=version,
    )


def check_docker_sandbox() -> CheckResult:
    """Check if Docker sandbox feature is available."""
    from .. import docker as docker_module

    if not docker_module.check_docker_sandbox():
        return CheckResult(
            name="Docker Sandbox",
            passed=False,
            message="Docker sandbox feature is not available",
            fix_hint=f"Requires Docker Desktop {docker_module.MIN_DOCKER_VERSION}+ with sandbox feature enabled",
            fix_url="https://docs.docker.com/desktop/features/sandbox/",
            severity="error",
        )

    return CheckResult(
        name="Docker Sandbox",
        passed=True,
        message="Docker sandbox feature is available",
    )


def check_docker_running() -> CheckResult:
    """Check if Docker daemon is running."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return CheckResult(
                name="Docker Daemon",
                passed=True,
                message="Docker daemon is running",
            )
        else:
            return CheckResult(
                name="Docker Daemon",
                passed=False,
                message="Docker daemon is not running",
                fix_hint="Start Docker Desktop or run 'sudo systemctl start docker'",
                severity="error",
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return CheckResult(
            name="Docker Daemon",
            passed=False,
            message="Could not connect to Docker daemon",
            fix_hint="Ensure Docker Desktop is running",
            severity="error",
        )


def check_wsl2() -> tuple[CheckResult, bool]:
    """Check WSL2 environment and return (result, is_wsl2)."""
    from .. import platform as platform_module

    is_wsl2 = platform_module.is_wsl2()

    if is_wsl2:
        return (
            CheckResult(
                name="WSL2 Environment",
                passed=True,
                message="Running in WSL2 (recommended for Windows)",
                severity="info",
            ),
            True,
        )

    return (
        CheckResult(
            name="WSL2 Environment",
            passed=True,
            message="Not running in WSL2",
            severity="info",
        ),
        False,
    )


def check_workspace_path(workspace: Path | None = None) -> CheckResult:
    """Check if workspace path is optimal (not on Windows mount in WSL2)."""
    from .. import platform as platform_module

    if workspace is None:
        return CheckResult(
            name="Workspace Path",
            passed=True,
            message="No workspace specified",
            severity="info",
        )

    if platform_module.is_wsl2() and platform_module.is_windows_mount_path(workspace):
        return CheckResult(
            name="Workspace Path",
            passed=False,
            message=f"Workspace is on Windows filesystem: {workspace}",
            fix_hint="Move project to ~/projects inside WSL for better performance",
            severity="warning",
        )

    return CheckResult(
        name="Workspace Path",
        passed=True,
        message=f"Workspace path is optimal: {workspace}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Checks
# ═══════════════════════════════════════════════════════════════════════════════


def check_user_config_valid() -> CheckResult:
    """Check if user configuration file is valid JSON.

    Validates ~/.config/scc/config.json for JSON syntax errors
    and provides helpful error messages with code frames.

    Returns:
        CheckResult with user config validation status.
    """
    from .. import config

    config_file = config.CONFIG_FILE

    if not config_file.exists():
        return CheckResult(
            name="User Config",
            passed=True,
            message="No user config file (using defaults)",
            severity="info",
        )

    result = validate_json_file(config_file)

    if result.valid:
        return CheckResult(
            name="User Config",
            passed=True,
            message=f"User config is valid JSON: {config_file}",
        )

    # Build error message with hints
    error_msg = f"Invalid JSON in {config_file.name}"
    if result.line is not None:
        error_msg += f" at line {result.line}"
        if result.column is not None:
            error_msg += f", column {result.column}"

    # Get helpful hints
    hints = get_json_error_hints(result.error_message or "")
    fix_hint = f"Error: {result.error_message}\n"
    fix_hint += "Hints:\n"
    for hint in hints:
        fix_hint += f"  • {hint}\n"
    fix_hint += f"Edit with: $EDITOR {config_file}"

    return CheckResult(
        name="User Config",
        passed=False,
        message=error_msg,
        fix_hint=fix_hint,
        severity="error",
        code_frame=result.code_frame,
    )


def check_config_directory() -> CheckResult:
    """Check if configuration directory exists and is writable."""
    from .. import config

    config_dir = config.CONFIG_DIR

    if not config_dir.exists():
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            return CheckResult(
                name="Config Directory",
                passed=True,
                message=f"Created config directory: {config_dir}",
            )
        except PermissionError:
            return CheckResult(
                name="Config Directory",
                passed=False,
                message=f"Cannot create config directory: {config_dir}",
                fix_hint="Check permissions on parent directory",
                severity="error",
            )

    # Check if writable
    test_file = config_dir / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return CheckResult(
            name="Config Directory",
            passed=True,
            message=f"Config directory is writable: {config_dir}",
        )
    except (PermissionError, OSError):
        return CheckResult(
            name="Config Directory",
            passed=False,
            message=f"Config directory is not writable: {config_dir}",
            fix_hint=f"Check permissions: chmod 755 {config_dir}",
            severity="error",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Organization & Marketplace Checks
# ═══════════════════════════════════════════════════════════════════════════════


def load_cached_org_config() -> dict[str, Any] | None:
    """Load cached organization config from cache directory.

    Returns:
        Cached org config dict if valid, None otherwise.
    """
    from .. import config

    cache_file = config.CACHE_DIR / "org_config.json"

    if not cache_file.exists():
        return None

    try:
        content = cache_file.read_text()
        return cast(dict[str, Any], json.loads(content))
    except (json.JSONDecodeError, OSError):
        return None


def check_org_config_reachable() -> CheckResult | None:
    """Check if organization config URL is reachable.

    Returns:
        CheckResult if org config is configured, None for standalone mode.
    """
    from .. import config
    from ..remote import fetch_org_config

    user_config = config.load_user_config()

    # Skip for standalone mode
    if user_config.get("standalone"):
        return None

    # Skip if no org source configured
    org_source = user_config.get("organization_source")
    if not org_source:
        return None

    url = org_source.get("url")
    if not url:
        return None

    auth = org_source.get("auth")

    # Try to fetch org config
    try:
        org_config, etag, status = fetch_org_config(url, auth=auth, etag=None)
    except Exception as e:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Failed to fetch org config: {e}",
            fix_hint="Check network connection and URL",
            severity="error",
        )

    if status == 401:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Authentication required (401) for {url}",
            fix_hint="Configure auth with: scc setup",
            severity="error",
        )

    if status == 403:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Access denied (403) for {url}",
            fix_hint="Check your access permissions",
            severity="error",
        )

    if status != 200 or org_config is None:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Failed to fetch org config (status: {status})",
            fix_hint="Check URL and network connection",
            severity="error",
        )

    org_name = org_config.get("organization", {}).get("name", "Unknown")
    return CheckResult(
        name="Org Config",
        passed=True,
        message=f"Connected to: {org_name}",
    )


def check_marketplace_auth_available() -> CheckResult | None:
    """Check if marketplace authentication token is available.

    Returns:
        CheckResult if marketplace is configured, None otherwise.
    """
    from .. import config
    from ..remote import resolve_auth

    user_config = config.load_user_config()
    org_config = load_cached_org_config()

    # Skip if no org config
    if org_config is None:
        return None

    # Skip if no profile selected
    profile_name = user_config.get("selected_profile")
    if not profile_name:
        return None

    # Find the profile
    profiles = org_config.get("profiles", {})
    profile = profiles.get(profile_name)
    if not profile:
        return None

    # Find the marketplace
    marketplace_name = profile.get("marketplace")
    marketplaces = org_config.get("marketplaces", [])
    marketplace = None
    for m in marketplaces:
        if m.get("name") == marketplace_name:
            marketplace = m
            break

    if marketplace is None:
        return CheckResult(
            name="Marketplace Auth",
            passed=False,
            message=f"Marketplace '{marketplace_name}' not found in org config",
            severity="error",
        )

    # Check auth requirement
    auth_spec = marketplace.get("auth")

    if auth_spec is None:
        return CheckResult(
            name="Marketplace Auth",
            passed=True,
            message="Public marketplace (no auth needed)",
        )

    # Try to resolve auth
    try:
        token = resolve_auth(auth_spec)
        if token:
            return CheckResult(
                name="Marketplace Auth",
                passed=True,
                message=f"{auth_spec} is set",
            )
        else:
            # Provide helpful hint based on auth type
            if auth_spec.startswith("env:"):
                var_name = auth_spec.split(":", 1)[1]
                hint = f"Set with: export {var_name}=your-token"
            else:
                cmd = auth_spec.split(":", 1)[1] if ":" in auth_spec else auth_spec
                hint = f"Run manually to debug: {cmd}"

            return CheckResult(
                name="Marketplace Auth",
                passed=False,
                message=f"{auth_spec} not set or invalid",
                fix_hint=hint,
                severity="error",
            )
    except Exception as e:
        return CheckResult(
            name="Marketplace Auth",
            passed=False,
            message=f"Auth resolution failed: {e}",
            severity="error",
        )


def check_credential_injection() -> CheckResult | None:
    """Check what credentials will be injected into Docker container.

    Shows env var NAMES only, never values. Prevents confusion about
    whether tokens are being passed to the container.

    Returns:
        CheckResult showing injection status, None if no profile.
    """
    from .. import config

    user_config = config.load_user_config()
    org_config = load_cached_org_config()

    # Skip if no org config
    if org_config is None:
        return None

    # Skip if no profile selected
    profile_name = user_config.get("selected_profile")
    if not profile_name:
        return None

    # Find the profile
    profiles = org_config.get("profiles", {})
    profile = profiles.get(profile_name)
    if not profile:
        return None

    # Find the marketplace
    marketplace_name = profile.get("marketplace")
    marketplaces = org_config.get("marketplaces", [])
    marketplace = None
    for m in marketplaces:
        if m.get("name") == marketplace_name:
            marketplace = m
            break

    if marketplace is None:
        return None

    # Check auth requirement
    auth_spec = marketplace.get("auth")

    if auth_spec is None:
        return CheckResult(
            name="Container Injection",
            passed=True,
            message="No credentials needed (public marketplace)",
        )

    # Determine what env vars will be injected
    env_vars = []

    if auth_spec.startswith("env:"):
        var_name = auth_spec.split(":", 1)[1]
        env_vars.append(var_name)

        # Add standard vars based on marketplace type
        marketplace_type = marketplace.get("type")
        if marketplace_type == "gitlab" and var_name != "GITLAB_TOKEN":
            env_vars.append("GITLAB_TOKEN")
        elif marketplace_type == "github" and var_name != "GITHUB_TOKEN":
            env_vars.append("GITHUB_TOKEN")

    if env_vars:
        env_list = ", ".join(env_vars)
        return CheckResult(
            name="Container Injection",
            passed=True,
            message=f"Will inject [{env_list}] into Docker env",
        )
    else:
        return CheckResult(
            name="Container Injection",
            passed=True,
            message="Command-based auth (resolved at runtime)",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Cache & State Checks
# ═══════════════════════════════════════════════════════════════════════════════


def check_cache_readable() -> CheckResult:
    """Check if organization config cache is readable and valid.

    Uses enhanced error display with code frames for JSON syntax errors.

    Returns:
        CheckResult with cache status.
    """
    from .. import config

    cache_file = config.CACHE_DIR / "org_config.json"

    if not cache_file.exists():
        return CheckResult(
            name="Org Cache",
            passed=True,
            message="No cache file (will fetch on first use)",
            severity="info",
        )

    # Use the new validation helper for enhanced error display
    result = validate_json_file(cache_file)

    if result.valid:
        try:
            content = cache_file.read_text()
            org_config = json.loads(content)

            # Calculate fingerprint
            import hashlib

            fingerprint = hashlib.sha256(content.encode()).hexdigest()[:12]

            org_name = org_config.get("organization", {}).get("name", "Unknown")
            return CheckResult(
                name="Org Cache",
                passed=True,
                message=f"Cache valid: {org_name} (fingerprint: {fingerprint})",
            )
        except (json.JSONDecodeError, OSError) as e:
            return CheckResult(
                name="Org Cache",
                passed=False,
                message=f"Cannot read cache file: {e}",
                fix_hint="Run 'scc setup' to refresh organization config",
                severity="error",
            )

    # Invalid JSON - build detailed error message
    error_msg = "Cache file is corrupted (invalid JSON)"
    if result.line is not None:
        error_msg += f" at line {result.line}"
        if result.column is not None:
            error_msg += f", column {result.column}"

    # Get helpful hints
    hints = get_json_error_hints(result.error_message or "")
    fix_hint = f"Error: {result.error_message}\n"
    fix_hint += "Hints:\n"
    for hint in hints:
        fix_hint += f"  • {hint}\n"
    fix_hint += "Fix: Run 'scc setup' to refresh organization config"

    return CheckResult(
        name="Org Cache",
        passed=False,
        message=error_msg,
        fix_hint=fix_hint,
        severity="error",
        code_frame=result.code_frame,
    )


def check_cache_ttl_status() -> CheckResult | None:
    """Check if cache is within TTL (time-to-live).

    Returns:
        CheckResult with TTL status, None if no cache metadata.
    """
    from .. import config

    meta_file = config.CACHE_DIR / "cache_meta.json"

    if not meta_file.exists():
        return None

    try:
        content = meta_file.read_text()
        meta = json.loads(content)
    except (json.JSONDecodeError, OSError):
        return CheckResult(
            name="Cache TTL",
            passed=False,
            message="Cache metadata is corrupted",
            fix_hint="Run 'scc setup' to refresh organization config",
            severity="warning",
        )

    org_meta = meta.get("org_config", {})
    expires_at_str = org_meta.get("expires_at")

    if not expires_at_str:
        return CheckResult(
            name="Cache TTL",
            passed=True,
            message="No expiration set in cache",
            severity="info",
        )

    try:
        # Parse ISO format datetime
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)

        if now < expires_at:
            remaining = expires_at - now
            hours = remaining.total_seconds() / 3600
            return CheckResult(
                name="Cache TTL",
                passed=True,
                message=f"Cache valid for {hours:.1f} more hours",
            )
        else:
            elapsed = now - expires_at
            hours = elapsed.total_seconds() / 3600
            return CheckResult(
                name="Cache TTL",
                passed=False,
                message=f"Cache expired {hours:.1f} hours ago",
                fix_hint="Run 'scc setup' to refresh organization config",
                severity="warning",
            )
    except (ValueError, TypeError):
        return CheckResult(
            name="Cache TTL",
            passed=False,
            message="Invalid expiration date in cache metadata",
            fix_hint="Run 'scc setup' to refresh organization config",
            severity="warning",
        )


def check_migration_status() -> CheckResult:
    """Check if legacy configuration has been migrated.

    Returns:
        CheckResult with migration status.
    """
    from .. import config

    legacy_dir = config.LEGACY_CONFIG_DIR
    new_dir = config.CONFIG_DIR

    # Both new and legacy exist - warn about cleanup
    if legacy_dir.exists() and new_dir.exists():
        return CheckResult(
            name="Migration",
            passed=False,
            message=f"Legacy config still exists at {legacy_dir}",
            fix_hint="You may delete the old directory manually",
            severity="warning",
        )

    # Only legacy exists - needs migration
    if legacy_dir.exists() and not new_dir.exists():
        return CheckResult(
            name="Migration",
            passed=False,
            message="Config migration needed",
            fix_hint="Run any scc command to trigger automatic migration",
            severity="warning",
        )

    # New config exists or fresh install
    return CheckResult(
        name="Migration",
        passed=True,
        message="No legacy configuration found",
    )


def check_exception_stores() -> CheckResult:
    """Check if exception stores are readable and valid.

    Validates both user and repo exception stores:
    - JSON parse errors
    - Schema version compatibility
    - Backup files from corruption recovery

    Returns:
        CheckResult with exception store status.
    """
    from ..stores.exception_store import RepoStore, UserStore

    issues: list[str] = []
    warnings: list[str] = []

    # Check user store
    user_store = UserStore()
    user_path = user_store.path

    if user_path.exists():
        try:
            user_file = user_store.read()
            if user_file.schema_version > 1:
                warnings.append(f"User store uses newer schema v{user_file.schema_version}")
        except Exception as e:
            issues.append(f"User store corrupt: {e}")

        # Check for backup files indicating past corruption
        backup_pattern = f"{user_path.name}.bak-*"
        backup_dir = user_path.parent
        backups = list(backup_dir.glob(backup_pattern))
        if backups:
            warnings.append(f"Found {len(backups)} user store backup(s)")

    # Check repo store (if in a git repo)
    try:
        repo_store = RepoStore(Path.cwd())
        repo_path = repo_store.path

        if repo_path.exists():
            try:
                repo_file = repo_store.read()
                if repo_file.schema_version > 1:
                    warnings.append(f"Repo store uses newer schema v{repo_file.schema_version}")
            except Exception as e:
                issues.append(f"Repo store corrupt: {e}")

            # Check for backup files
            backup_pattern = f"{repo_path.name}.bak-*"
            backup_dir = repo_path.parent
            backups = list(backup_dir.glob(backup_pattern))
            if backups:
                warnings.append(f"Found {len(backups)} repo store backup(s)")
    except Exception:
        # Not in a repo or repo store not accessible - that's fine
        pass

    # Build result
    if issues:
        return CheckResult(
            name="Exception Stores",
            passed=False,
            message="; ".join(issues),
            fix_hint="Run 'scc exceptions reset --user --yes' to reset corrupt stores",
            severity="error",
        )

    if warnings:
        return CheckResult(
            name="Exception Stores",
            passed=True,
            message="; ".join(warnings),
            fix_hint="Consider upgrading SCC or running 'scc exceptions cleanup'",
            severity="warning",
        )

    return CheckResult(
        name="Exception Stores",
        passed=True,
        message="Exception stores OK",
    )


def check_proxy_environment() -> CheckResult:
    """Check for proxy environment variables.

    This is an informational check that detects common proxy configurations.
    It never fails - just provides visibility into the environment.

    Returns:
        CheckResult with proxy environment info (always passes, severity=info).
    """
    proxy_vars = {
        "HTTP_PROXY": os.environ.get("HTTP_PROXY"),
        "http_proxy": os.environ.get("http_proxy"),
        "HTTPS_PROXY": os.environ.get("HTTPS_PROXY"),
        "https_proxy": os.environ.get("https_proxy"),
        "NO_PROXY": os.environ.get("NO_PROXY"),
        "no_proxy": os.environ.get("no_proxy"),
    }

    # Find which ones are set
    configured = {k: v for k, v in proxy_vars.items() if v}

    if configured:
        # Summarize what's configured
        proxy_names = ", ".join(configured.keys())
        message = f"Proxy configured: {proxy_names}"
    else:
        message = "No proxy environment variables detected"

    return CheckResult(
        name="Proxy Environment",
        passed=True,
        message=message,
        severity="info",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Check Orchestration
# ═══════════════════════════════════════════════════════════════════════════════


def run_all_checks() -> list[CheckResult]:
    """Run all health checks and return list of results.

    Includes both environment checks and organization/marketplace checks.

    Returns:
        List of all CheckResult objects (excluding None results).
    """
    results: list[CheckResult] = []

    # Environment checks
    results.append(check_git())
    results.append(check_docker())
    results.append(check_docker_sandbox())
    results.append(check_docker_running())

    wsl2_result, _ = check_wsl2()
    results.append(wsl2_result)

    results.append(check_config_directory())

    # User config validation (JSON syntax check)
    results.append(check_user_config_valid())

    # Organization checks (may return None)
    org_check = check_org_config_reachable()
    if org_check is not None:
        results.append(org_check)

    auth_check = check_marketplace_auth_available()
    if auth_check is not None:
        results.append(auth_check)

    injection_check = check_credential_injection()
    if injection_check is not None:
        results.append(injection_check)

    # Cache checks
    results.append(check_cache_readable())

    ttl_check = check_cache_ttl_status()
    if ttl_check is not None:
        results.append(ttl_check)

    # Migration check
    results.append(check_migration_status())

    # Exception stores check
    results.append(check_exception_stores())

    return results
