from __future__ import annotations

import json
import platform
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scc_cli import __version__, config
from scc_cli.doctor.core import run_doctor
from scc_cli.doctor.serialization import build_doctor_json_data

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
    return any(pattern.match(key) for pattern in _SECRET_PATTERNS)


def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """Redact secret values from a dictionary."""

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


def redact_paths(data: dict[str, Any], redact: bool = True) -> dict[str, Any]:
    """Redact home directory paths from a dictionary."""

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


def build_bundle_data(
    redact_paths_flag: bool = True,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Build support bundle data."""

    system_info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "platform_release": platform.release(),
        "machine": platform.machine(),
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
    }

    generated_at = datetime.now(timezone.utc).isoformat()

    try:
        user_config = config.load_user_config()
        if isinstance(user_config, dict):
            user_config = redact_secrets(user_config)
    except Exception:
        user_config = {"error": "Failed to load config"}

    try:
        org_config = config.load_cached_org_config()
        if org_config:
            org_config = redact_secrets(org_config)
    except Exception:
        org_config = {"error": "Failed to load org config"}

    try:
        doctor_result = run_doctor(workspace_path)
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

    if workspace_path:
        bundle_data["workspace"] = str(workspace_path)

    if redact_paths_flag:
        bundle_data = redact_paths(bundle_data)

    return bundle_data


def get_default_bundle_path() -> Path:
    """Get default path for support bundle."""

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / f"scc-support-bundle-{timestamp}.zip"


def create_bundle(
    output_path: Path,
    redact_paths_flag: bool = True,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Create a support bundle zip file."""

    bundle_data = build_bundle_data(
        redact_paths_flag=redact_paths_flag,
        workspace_path=workspace_path,
    )

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        manifest_json = json.dumps(bundle_data, indent=2)
        bundle.writestr("manifest.json", manifest_json)

    return bundle_data
