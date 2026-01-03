"""Cache and state health checks for doctor module.

Checks for cache validity, TTL, migration status, exception stores, and proxy.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..types import CheckResult
from .json_helpers import get_json_error_hints, validate_json_file


def check_cache_readable() -> CheckResult:
    """Check if organization config cache is readable and valid.

    Uses enhanced error display with code frames for JSON syntax errors.

    Returns:
        CheckResult with cache status.
    """
    from ... import config

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
    from ... import config

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
    from ... import config

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
    from ...stores.exception_store import RepoStore, UserStore

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
