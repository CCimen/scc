"""Support bundle use case for diagnostics output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scc_cli import __version__, config
from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics
from scc_cli.application.safety_audit import read_safety_audit_diagnostics
from scc_cli.core.errors import SCCError
from scc_cli.core.safety_policy_loader import load_safety_policy
from scc_cli.doctor.serialization import build_doctor_json_data
from scc_cli.ports.archive_writer import ArchiveWriter
from scc_cli.ports.clock import Clock
from scc_cli.ports.doctor_runner import DoctorRunner
from scc_cli.ports.filesystem import Filesystem

SUPPORT_BUNDLE_AUDIT_LIMIT = 5

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


def get_default_support_bundle_path(
    *,
    working_directory: Path | None = None,
    current_time: datetime | None = None,
) -> Path:
    """Return the default output path for a support bundle archive."""
    timestamp = (current_time or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return (working_directory or Path.cwd()) / f"scc-support-bundle-{timestamp}.zip"


@dataclass(frozen=True)
class SupportBundleDependencies:
    """Dependencies for the support bundle use case."""

    filesystem: Filesystem
    clock: Clock
    doctor_runner: DoctorRunner
    archive_writer: ArchiveWriter
    launch_audit_path: Path = config.LAUNCH_AUDIT_FILE


def build_default_support_bundle_dependencies() -> SupportBundleDependencies:
    """Build support-bundle dependencies from the composition root."""
    from scc_cli.bootstrap import get_default_adapters

    adapters = get_default_adapters()
    return SupportBundleDependencies(
        filesystem=adapters.filesystem,
        clock=adapters.clock,
        doctor_runner=adapters.doctor_runner,
        archive_writer=adapters.archive_writer,
    )


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


def _load_raw_org_config_for_bundle() -> dict[str, Any] | None:
    """Load raw org config for the safety section (fail-safe)."""
    try:
        return config.load_cached_org_config()
    except Exception:
        return None


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


def _build_launch_audit_manifest_section(
    *,
    audit_path: Path,
    redact_paths_flag: bool,
) -> dict[str, Any]:
    diagnostics = read_launch_audit_diagnostics(
        audit_path=audit_path,
        limit=SUPPORT_BUNDLE_AUDIT_LIMIT,
        redact_paths=redact_paths_flag,
    )
    return diagnostics.to_dict()


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

    try:
        launch_audit = _build_launch_audit_manifest_section(
            audit_path=dependencies.launch_audit_path,
            redact_paths_flag=request.redact_paths,
        )
    except Exception as exc:
        launch_audit = {
            "sink_path": str(dependencies.launch_audit_path),
            "state": "unavailable",
            "requested_limit": SUPPORT_BUNDLE_AUDIT_LIMIT,
            "scanned_line_count": 0,
            "malformed_line_count": 0,
            "last_malformed_line": None,
            "recent_events": [],
            "last_failure": None,
            "error": f"Failed to read launch audit: {exc}",
        }
        if request.redact_paths:
            launch_audit = redact_paths(launch_audit)

    # Effective egress diagnostics
    runtime_backend = "unavailable"
    try:
        from scc_cli.bootstrap import get_default_adapters

        adapters = get_default_adapters()
        probe = adapters.runtime_probe
        if probe is not None:
            probe_info = probe.probe()
            runtime_backend = probe_info.preferred_backend or "unavailable"
    except Exception:
        pass

    network_policy: str | None = None
    try:
        if isinstance(user_config, dict):
            network_policy = user_config.get("network_policy") or user_config.get(
                "network", {}
            ).get("policy")
    except Exception:
        pass

    resolved_destination_sets: list[str] = []
    try:
        from scc_cli.core.destination_registry import PROVIDER_DESTINATION_SETS

        resolved_destination_sets = sorted(PROVIDER_DESTINATION_SETS.keys())
    except Exception:
        pass

    effective_egress: dict[str, Any] = {
        "runtime_backend": runtime_backend,
        "network_policy": network_policy,
        "resolved_destination_sets": resolved_destination_sets,
    }

    # Safety: effective policy + recent safety audit events
    try:
        raw_org_config = _load_raw_org_config_for_bundle()
        policy = load_safety_policy(raw_org_config)
        safety_audit_diag = read_safety_audit_diagnostics(
            audit_path=dependencies.launch_audit_path,
            limit=SUPPORT_BUNDLE_AUDIT_LIMIT,
            redact_paths=request.redact_paths,
        )
        safety_section: dict[str, Any] = {
            "effective_policy": {
                "action": policy.action,
                "source": policy.source,
            },
            "recent_audit": safety_audit_diag.to_dict(),
        }
    except Exception as exc:
        safety_section = {"error": f"Failed to load safety diagnostics: {exc}"}

    # Governed-artifact diagnostics
    try:
        from scc_cli.doctor.checks.artifacts import build_artifact_diagnostics_summary

        artifact_diagnostics: dict[str, Any] = build_artifact_diagnostics_summary()
    except Exception as exc:
        artifact_diagnostics = {"error": f"Failed to load artifact diagnostics: {exc}"}

    bundle_data: dict[str, Any] = {
        "generated_at": generated_at,
        "cli_version": __version__,
        "system": system_info,
        "config": user_config,
        "org_config": org_config,
        "doctor": doctor_data,
        "launch_audit": launch_audit,
        "effective_egress": effective_egress,
        "safety": safety_section,
        "governed_artifacts": artifact_diagnostics,
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
