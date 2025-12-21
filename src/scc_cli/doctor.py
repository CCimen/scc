"""
System health checks and prerequisite validation.

The doctor module provides comprehensive health checks for all
prerequisites needed to run Claude Code in Docker sandboxes.

Philosophy: "Fast feedback, clear guidance"
- Check all prerequisites quickly
- Provide clear pass/fail indicators
- Offer actionable fix suggestions

New checks (v2):
- Organization config reachability
- Marketplace authentication availability
- Credential injection verification
- Cache status and TTL checks
- Migration status checks
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .remote import fetch_org_config, resolve_auth

# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    passed: bool
    message: str
    version: str | None = None
    fix_hint: str | None = None
    fix_url: str | None = None
    severity: str = "error"  # "error", "warning", "info"


@dataclass
class DoctorResult:
    """Complete health check results."""

    git_ok: bool = False
    git_version: str | None = None
    docker_ok: bool = False
    docker_version: str | None = None
    sandbox_ok: bool = False
    wsl2_detected: bool = False
    windows_path_warning: bool = False
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """Check if all critical prerequisites pass."""
        return self.git_ok and self.docker_ok and self.sandbox_ok

    @property
    def error_count(self) -> int:
        """Count of failed critical checks."""
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")

    @property
    def warning_count(self) -> int:
        """Count of warnings."""
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")


# ═══════════════════════════════════════════════════════════════════════════════
# Health Checks
# ═══════════════════════════════════════════════════════════════════════════════


def check_git() -> CheckResult:
    """Check if Git is installed and accessible."""
    from . import git as git_module

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
    from . import docker as docker_module

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
    from . import docker as docker_module

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
    from . import platform as platform_module

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
    from . import platform as platform_module

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


def check_config_directory() -> CheckResult:
    """Check if configuration directory exists and is writable."""
    from . import config

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
# Organization & Marketplace Health Checks (v2)
# ═══════════════════════════════════════════════════════════════════════════════


def load_cached_org_config() -> dict | None:
    """Load cached organization config from cache directory.

    Returns:
        Cached org config dict if valid, None otherwise.
    """
    cache_file = config.CACHE_DIR / "org_config.json"

    if not cache_file.exists():
        return None

    try:
        content = cache_file.read_text()
        return cast(dict[Any, Any], json.loads(content))
    except (json.JSONDecodeError, OSError):
        return None


def check_org_config_reachable() -> CheckResult | None:
    """Check if organization config URL is reachable.

    Returns:
        CheckResult if org config is configured, None for standalone mode.
    """
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


def check_cache_readable() -> CheckResult:
    """Check if organization config cache is readable and valid.

    Returns:
        CheckResult with cache status.
    """
    cache_file = config.CACHE_DIR / "org_config.json"

    if not cache_file.exists():
        return CheckResult(
            name="Cache",
            passed=True,
            message="No cache file (will fetch on first use)",
            severity="info",
        )

    try:
        content = cache_file.read_text()
        org_config = json.loads(content)

        # Calculate fingerprint
        import hashlib

        fingerprint = hashlib.sha256(content.encode()).hexdigest()[:12]

        org_name = org_config.get("organization", {}).get("name", "Unknown")
        return CheckResult(
            name="Cache",
            passed=True,
            message=f"Cache valid: {org_name} (fingerprint: {fingerprint})",
        )
    except json.JSONDecodeError:
        return CheckResult(
            name="Cache",
            passed=False,
            message="Cache file is corrupted (invalid JSON)",
            fix_hint="Run 'scc teams --sync' to refresh",
            severity="error",
        )
    except OSError as e:
        return CheckResult(
            name="Cache",
            passed=False,
            message=f"Cannot read cache file: {e}",
            severity="error",
        )


def check_cache_ttl_status() -> CheckResult | None:
    """Check if cache is within TTL (time-to-live).

    Returns:
        CheckResult with TTL status, None if no cache metadata.
    """
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
            fix_hint="Run 'scc teams --sync' to refresh",
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
                fix_hint="Run 'scc teams --sync' to refresh",
                severity="warning",
            )
    except (ValueError, TypeError):
        return CheckResult(
            name="Cache TTL",
            passed=False,
            message="Invalid expiration date in cache metadata",
            fix_hint="Run 'scc teams --sync' to refresh",
            severity="warning",
        )


def check_migration_status() -> CheckResult:
    """Check if legacy configuration has been migrated.

    Returns:
        CheckResult with migration status.
    """
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
    from pathlib import Path

    from .stores.exception_store import RepoStore, UserStore

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


def run_all_checks() -> list[CheckResult]:
    """Run all health checks and return list of results.

    Includes both environment checks and organization/marketplace checks.

    Returns:
        List of all CheckResult objects (excluding None results).
    """
    results = []

    # Environment checks
    results.append(check_git())
    results.append(check_docker())
    results.append(check_docker_sandbox())
    results.append(check_docker_running())

    wsl2_result, _ = check_wsl2()
    results.append(wsl2_result)

    results.append(check_config_directory())

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


# ═══════════════════════════════════════════════════════════════════════════════
# Main Doctor Function
# ═══════════════════════════════════════════════════════════════════════════════


def run_doctor(workspace: Path | None = None) -> DoctorResult:
    """
    Run all health checks and return comprehensive results.

    Args:
        workspace: Optional workspace path to check for optimization

    Returns:
        DoctorResult with all check results
    """
    result = DoctorResult()

    # Git check
    git_check = check_git()
    result.checks.append(git_check)
    result.git_ok = git_check.passed
    result.git_version = git_check.version

    # Docker check
    docker_check = check_docker()
    result.checks.append(docker_check)
    result.docker_ok = docker_check.passed
    result.docker_version = docker_check.version

    # Docker daemon check (only if Docker is installed)
    if result.docker_ok:
        daemon_check = check_docker_running()
        result.checks.append(daemon_check)
        if not daemon_check.passed:
            result.docker_ok = False

    # Docker sandbox check (only if Docker is OK)
    if result.docker_ok:
        sandbox_check = check_docker_sandbox()
        result.checks.append(sandbox_check)
        result.sandbox_ok = sandbox_check.passed
    else:
        result.sandbox_ok = False

    # WSL2 check
    wsl2_check, is_wsl2 = check_wsl2()
    result.checks.append(wsl2_check)
    result.wsl2_detected = is_wsl2

    # Workspace path check (if WSL2 and workspace provided)
    if workspace:
        path_check = check_workspace_path(workspace)
        result.checks.append(path_check)
        result.windows_path_warning = not path_check.passed and path_check.severity == "warning"

    # Config directory check
    config_check = check_config_directory()
    result.checks.append(config_check)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Beautiful Rich UI Rendering
# ═══════════════════════════════════════════════════════════════════════════════


def render_doctor_results(console: Console, result: DoctorResult) -> None:
    """
    Render doctor results with beautiful Rich formatting.

    Uses consistent styling with the rest of the CLI:
    - Cyan for info/brand
    - Green for success
    - Yellow for warnings
    - Red for errors
    """
    # Header
    console.print()

    # Build results table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Status", width=8, justify="center")
    table.add_column("Check", min_width=20)
    table.add_column("Details", min_width=30)

    for check in result.checks:
        # Status icon with color
        if check.passed:
            status = Text("  ", style="bold green")
        elif check.severity == "warning":
            status = Text("  ", style="bold yellow")
        else:
            status = Text("  ", style="bold red")

        # Check name
        name = Text(check.name, style="white")

        # Details with version and message
        details = Text()
        if check.version:
            details.append(f"{check.version}\n", style="cyan")
        details.append(check.message, style="dim" if check.passed else "white")

        if not check.passed and check.fix_hint:
            details.append(f"\n{check.fix_hint}", style="yellow")

        table.add_row(status, name, details)

    # Wrap table in panel
    title_style = "bold green" if result.all_ok else "bold red"
    title_text = "System Health Check" if result.all_ok else "System Health Check - Issues Found"

    panel = Panel(
        table,
        title=f"[{title_style}]{title_text}[/{title_style}]",
        border_style="green" if result.all_ok else "red",
        padding=(1, 1),
    )

    console.print(panel)

    # Summary line
    if result.all_ok:
        console.print()
        console.print(
            "  [bold green]All prerequisites met![/bold green] [dim]Ready to run Claude Code.[/dim]"
        )
    else:
        console.print()
        summary_parts = []
        if result.error_count > 0:
            summary_parts.append(f"[bold red]{result.error_count} error(s)[/bold red]")
        if result.warning_count > 0:
            summary_parts.append(f"[bold yellow]{result.warning_count} warning(s)[/bold yellow]")

        console.print(f"  Found {' and '.join(summary_parts)}. ", end="")
        console.print("[dim]Fix the issues above to continue.[/dim]")

    console.print()


def render_doctor_compact(console: Console, result: DoctorResult) -> None:
    """
    Render compact doctor results for inline display.

    Used during startup to show quick status.
    """
    checks = []

    # Git
    if result.git_ok:
        checks.append("[green]Git[/green]")
    else:
        checks.append("[red]Git[/red]")

    # Docker
    if result.docker_ok:
        checks.append("[green]Docker[/green]")
    else:
        checks.append("[red]Docker[/red]")

    # Sandbox
    if result.sandbox_ok:
        checks.append("[green]Sandbox[/green]")
    else:
        checks.append("[red]Sandbox[/red]")

    console.print(f"  [dim]Prerequisites:[/dim] {' | '.join(checks)}")


def render_quick_status(console: Console, result: DoctorResult) -> None:
    """
    Render a single-line status for quick checks.

    Returns immediately with pass/fail indicator.
    """
    if result.all_ok:
        console.print("[green]  All systems operational[/green]")
    else:
        failed = [c.name for c in result.checks if not c.passed and c.severity == "error"]
        console.print(f"[red]  Issues detected:[/red] {', '.join(failed)}")


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Check Functions
# ═══════════════════════════════════════════════════════════════════════════════


def quick_check() -> bool:
    """
    Perform a quick prerequisite check.

    Returns True if all critical prerequisites are met.
    Used for fast startup validation.
    """
    result = run_doctor()
    return result.all_ok


def is_first_run() -> bool:
    """
    Check if this is the first run of scc.

    Returns True if config directory doesn't exist or is empty.
    """
    from . import config

    config_dir = config.CONFIG_DIR

    if not config_dir.exists():
        return True

    # Check if config file exists
    config_file = config.CONFIG_FILE
    return not config_file.exists()
