"""Support bundle use case for diagnostics output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scc_cli import __version__
from scc_cli.core.errors import SCCError
from scc_cli.doctor.serialization import build_doctor_json_data
from scc_cli.ports.archive_writer import ArchiveWriter
from scc_cli.ports.clock import Clock
from scc_cli.ports.doctor_runner import DoctorRunner
from scc_cli.ports.filesystem import Filesystem

# ─────────────────────────────────────────────────────────────────────────────
# Redaction Patterns and Helpers
# ─────────────────────────────────────────────────────────────────────────────

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

_SECRET_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in SECRET_KEY_PATTERNS]


def _is_secret_key(key: str) -> bool:
    """Check if a key matches secret patterns."""
    return any(pattern.match(key) for pattern in _SECRET_PATTERNS)


def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Redact secret values from a dictionary.

    Recursively traverses the dictionary and replaces values for keys
    matching secret patterns (auth, token, api_key, password, etc.)
    with '[REDACTED]'.

    Args:
        data: Dictionary to redact secrets from.

    Returns:
        New dictionary with secret values redacted.
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


def redact_paths(data: dict[str, Any], *, redact: bool = True) -> dict[str, Any]:
    """Redact home directory paths from a dictionary.

    Recursively traverses the dictionary and replaces home directory paths
    with '~' for privacy.

    Args:
        data: Dictionary to redact paths from.
        redact: If False, returns data unchanged.

    Returns:
        New dictionary with home paths redacted.
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
# Use Case Types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SupportBundleDependencies:
    """Dependencies for the support bundle use case."""

    filesystem: Filesystem
    clock: Clock
    doctor_runner: DoctorRunner
    archive_writer: ArchiveWriter


@dataclass(frozen=True)
class SupportBundleRequest:
    """Inputs for generating a support bundle."""

    output_path: Path
    redact_paths: bool
    workspace_path: Path | None = None


@dataclass(frozen=True)
class SupportBundleResult:
    """Result of support bundle generation."""

    manifest: dict[str, Any]


def _load_user_config(filesystem: Filesystem, path: Path) -> dict[str, Any]:
    try:
        if not filesystem.exists(path):
            return {}
        content = filesystem.read_text(path)
        result = json.loads(content)
        if isinstance(result, dict):
            return result
        return {"error": "Config is not a dictionary"}
    except (OSError, json.JSONDecodeError):
        return {"error": "Failed to load config"}


def build_support_bundle_manifest(
    request: SupportBundleRequest,
    *,
    dependencies: SupportBundleDependencies,
) -> dict[str, Any]:
    """Assemble the support bundle manifest without writing files."""
    system_info = {
        "platform": __import__("platform").system(),
        "platform_version": __import__("platform").version(),
        "platform_release": __import__("platform").release(),
        "machine": __import__("platform").machine(),
        "python_version": __import__("sys").version,
        "python_implementation": __import__("platform").python_implementation(),
    }

    generated_at = dependencies.clock.now().isoformat()

    user_config_path = Path.home() / ".scc" / "config.json"
    user_config = _load_user_config(dependencies.filesystem, user_config_path)
    user_config = redact_secrets(user_config) if isinstance(user_config, dict) else user_config

    org_config_path = Path.home() / ".scc" / "org.json"
    org_config = _load_user_config(dependencies.filesystem, org_config_path)
    org_config = redact_secrets(org_config) if isinstance(org_config, dict) else org_config

    try:
        doctor_result = dependencies.doctor_runner.run(
            str(request.workspace_path) if request.workspace_path else None
        )
        doctor_data = build_doctor_json_data(doctor_result)
    except Exception as exc:
        doctor_data = {"error": f"Failed to run doctor: {exc}"}

    bundle_data: dict[str, Any] = {
        "generated_at": generated_at,
        "cli_version": __version__,
        "system": system_info,
        "config": user_config,
        "org_config": org_config,
        "doctor": doctor_data,
    }

    if request.workspace_path:
        bundle_data["workspace"] = str(request.workspace_path)

    if request.redact_paths:
        bundle_data = redact_paths(bundle_data)

    return bundle_data


def create_support_bundle(
    request: SupportBundleRequest,
    *,
    dependencies: SupportBundleDependencies,
) -> SupportBundleResult:
    """Generate a support bundle and write the archive manifest."""
    manifest = build_support_bundle_manifest(request, dependencies=dependencies)
    manifest_json = json.dumps(manifest, indent=2)

    try:
        dependencies.archive_writer.write_manifest(str(request.output_path), manifest_json)
    except Exception as exc:
        raise SCCError(
            user_message="Failed to write support bundle",
            suggested_action="Check the output path and try again",
            debug_context=str(exc),
        ) from exc

    return SupportBundleResult(manifest=manifest)
