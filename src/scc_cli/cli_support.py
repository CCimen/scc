"""
Provide CLI commands for support and diagnostics.

Generate support bundles with diagnostic information. Include secret
and path redaction for safe sharing.
"""

import json
import platform
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from . import __version__, config, doctor
from .cli_common import console, handle_errors
from .json_output import build_envelope
from .kinds import Kind
from .output_mode import json_output_mode, print_json, set_pretty_mode

# ─────────────────────────────────────────────────────────────────────────────
# Support App
# ─────────────────────────────────────────────────────────────────────────────

support_app = typer.Typer(
    name="support",
    help="Support and diagnostic commands.",
    no_args_is_help=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Secret Redaction (Pure Function)
# ─────────────────────────────────────────────────────────────────────────────

# Keys that should have their values redacted
SECRET_KEY_PATTERNS = [
    r"^auth$",
    r".*token.*",
    r".*api[_-]?key.*",
    r".*apikey.*",
    r".*password.*",
    r".*secret.*",
    r"^authorization$",
    r".*credential.*",
]

# Compiled regex patterns (case-insensitive)
_SECRET_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SECRET_KEY_PATTERNS]


def _is_secret_key(key: str) -> bool:
    """Check if a key name indicates a secret value."""
    return any(pattern.match(key) for pattern in _SECRET_PATTERNS)


def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Redact secret values from a dictionary.

    Recursively processes nested dicts and lists.

    Args:
        data: Dictionary potentially containing secrets

    Returns:
        Copy of dict with secret values replaced by [REDACTED]
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        if _is_secret_key(key) and isinstance(value, str):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = redact_secrets(value)
        elif isinstance(value, list):
            result[key] = [
                redact_secrets(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            result[key] = value

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Path Redaction (Pure Function)
# ─────────────────────────────────────────────────────────────────────────────


def redact_paths(data: dict[str, Any], redact: bool = True) -> dict[str, Any]:
    """Redact home directory paths from a dictionary.

    Replaces absolute paths containing the home directory with ~ prefix.

    Args:
        data: Dictionary potentially containing paths
        redact: If False, return data unchanged

    Returns:
        Copy of dict with home paths redacted
    """
    if not redact:
        return data

    home = str(Path.home())
    result: dict[str, Any] = {}

    for key, value in data.items():
        if isinstance(value, str) and home in value:
            result[key] = value.replace(home, "~")
        elif isinstance(value, dict):
            result[key] = redact_paths(value, redact=redact)
        elif isinstance(value, list):
            result[key] = [
                redact_paths(item, redact=redact)
                if isinstance(item, dict)
                else (item.replace(home, "~") if isinstance(item, str) and home in item else item)
                for item in value
            ]
        else:
            result[key] = value

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Bundle Data Collection (Pure Function)
# ─────────────────────────────────────────────────────────────────────────────


def build_bundle_data(
    redact_paths_flag: bool = True,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Build support bundle data.

    Collects system info, config, doctor output, and other diagnostics.
    All secrets are automatically redacted.

    Args:
        redact_paths_flag: Whether to redact home directory paths
        workspace_path: Optional workspace to include in diagnostics

    Returns:
        Dictionary with all bundle data
    """
    # System information
    system_info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
    }

    # CLI version
    cli_version = __version__

    # Timestamp
    generated_at = datetime.now(timezone.utc).isoformat()

    # Load and redact config
    try:
        user_config = config.load_config()
        user_config = redact_secrets(user_config)
    except Exception:
        user_config = {"error": "Failed to load config"}

    # Load and redact org config
    try:
        org_config = config.load_cached_org_config()
        if org_config:
            org_config = redact_secrets(org_config)
    except Exception:
        org_config = {"error": "Failed to load org config"}

    # Run doctor checks
    try:
        doctor_result = doctor.run_doctor(workspace_path)
        doctor_data = doctor.build_doctor_json_data(doctor_result)
    except Exception as e:
        doctor_data = {"error": f"Failed to run doctor: {e}"}

    # Build bundle data
    bundle_data: dict[str, Any] = {
        "generated_at": generated_at,
        "cli_version": cli_version,
        "system": system_info,
        "config": user_config,
        "org_config": org_config,
        "doctor": doctor_data,
    }

    # Include workspace info if provided
    if workspace_path:
        bundle_data["workspace"] = str(workspace_path)

    # Apply path redaction if enabled
    if redact_paths_flag:
        bundle_data = redact_paths(bundle_data)

    return bundle_data


# ─────────────────────────────────────────────────────────────────────────────
# Bundle File Creation
# ─────────────────────────────────────────────────────────────────────────────


def get_default_bundle_path() -> Path:
    """Get default path for support bundle.

    Returns:
        Path with timestamp-based filename
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / f"scc-support-bundle-{timestamp}.zip"


def create_bundle(
    output_path: Path,
    redact_paths_flag: bool = True,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Create a support bundle zip file.

    Args:
        output_path: Path for the output zip file
        redact_paths_flag: Whether to redact home directory paths
        workspace_path: Optional workspace to include in diagnostics

    Returns:
        The bundle data that was written to the manifest
    """
    bundle_data = build_bundle_data(
        redact_paths_flag=redact_paths_flag,
        workspace_path=workspace_path,
    )

    # Create zip file with manifest
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_json = json.dumps(bundle_data, indent=2)
        zf.writestr("manifest.json", manifest_json)

    return bundle_data


# ─────────────────────────────────────────────────────────────────────────────
# Support Bundle Command
# ─────────────────────────────────────────────────────────────────────────────


@support_app.command("bundle")
@handle_errors
def support_bundle_cmd(
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for the bundle zip file",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output manifest as JSON instead of creating zip",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print JSON output (implies --json)",
    ),
    no_redact_paths: bool = typer.Option(
        False,
        "--no-redact-paths",
        help="Don't redact home directory paths",
    ),
) -> None:
    """Generate a support bundle for troubleshooting.

    Creates a zip file containing:
    - System information (platform, Python version)
    - CLI configuration (secrets redacted)
    - Doctor output (health check results)
    - Diagnostic information

    The bundle is safe to share - all sensitive data is redacted.
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    redact_paths_flag = not no_redact_paths

    if json_output:
        with json_output_mode():
            bundle_data = build_bundle_data(redact_paths_flag=redact_paths_flag)
            envelope = build_envelope(Kind.SUPPORT_BUNDLE, data=bundle_data)
            print_json(envelope)
            raise typer.Exit(0)

    # Create the bundle zip file
    output_path = Path(output) if output else get_default_bundle_path()

    console.print("[cyan]Generating support bundle...[/cyan]")
    create_bundle(
        output_path=output_path,
        redact_paths_flag=redact_paths_flag,
    )

    console.print()
    console.print(f"[green]Support bundle created:[/green] {output_path}")
    console.print()
    console.print("[dim]The bundle contains diagnostic information with secrets redacted.[/dim]")
    console.print("[dim]You can share this file safely with support.[/dim]")

    raise typer.Exit(0)
