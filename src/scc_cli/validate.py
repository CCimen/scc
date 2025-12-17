"""
Schema validation for organization configs.

Provides offline-capable validation using bundled JSON schemas.
Treats $schema field as documentation, not something to fetch at runtime.

Key functions:
- validate_org_config(): Validate org config against bundled schema
- check_schema_version(): Check schema version compatibility
- check_min_cli_version(): Check CLI meets minimum version requirement
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import TYPE_CHECKING

from jsonschema import Draft7Validator

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Loading
# ═══════════════════════════════════════════════════════════════════════════════


def load_bundled_schema(version: str = "v1") -> dict:
    """
    Load schema from package resources.

    Args:
        version: Schema version (default: "v1")

    Returns:
        Schema dict

    Raises:
        FileNotFoundError: If schema version doesn't exist
    """
    schema_file = files("scc_cli.schemas").joinpath(f"org-{version}.schema.json")
    try:
        content = schema_file.read_text()
        return json.loads(content)
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema version '{version}' not found")


# ═══════════════════════════════════════════════════════════════════════════════
# Config Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_org_config(config: dict, schema_version: str = "v1") -> list[str]:
    """
    Validate org config against bundled schema.

    Args:
        config: Organization config dict to validate
        schema_version: Schema version to validate against (default: "v1")

    Returns:
        List of error strings. Empty list means config is valid.
    """
    schema = load_bundled_schema(schema_version)
    validator = Draft7Validator(schema)

    errors = []
    for error in validator.iter_errors(config):
        # Include config path for easy debugging
        path = "/".join(str(p) for p in error.path) or "(root)"
        errors.append(f"{path}: {error.message}")

    return errors


# ═══════════════════════════════════════════════════════════════════════════════
# Version Compatibility Checks
# ═══════════════════════════════════════════════════════════════════════════════


def parse_semver(version_string: str) -> tuple[int, int, int]:
    """
    Parse semantic version string into tuple of (major, minor, patch).

    Args:
        version_string: Version string in format "X.Y.Z"

    Returns:
        Tuple of (major, minor, patch) integers

    Raises:
        ValueError: If version string is not valid semver format
    """
    try:
        parts = version_string.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid semver format: {version_string}")
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid semver format: {version_string}") from e


def check_schema_version(
    config_version: str, cli_version: str
) -> tuple[bool, str | None]:
    """
    Check schema version compatibility.

    Compatibility rules:
    - Same major version: compatible
    - Config major > CLI major: incompatible (need CLI upgrade)
    - CLI major > Config major: compatible (CLI is newer)
    - Higher minor in config: compatible with warning (ignore unknown fields)

    Args:
        config_version: Schema version from org config (e.g., "1.5.0")
        cli_version: Current CLI schema version (e.g., "1.2.0")

    Returns:
        Tuple of (compatible: bool, message: str | None)
    """
    config_major, config_minor, _ = parse_semver(config_version)
    cli_major, cli_minor, _ = parse_semver(cli_version)

    # Different major versions: check if upgrade needed
    if config_major > cli_major:
        return (
            False,
            f"Config requires schema v{config_major}.x but CLI only supports v{cli_major}.x. "
            f"Please upgrade SCC CLI.",
        )

    # Config minor version higher than CLI: warn but continue
    if config_major == cli_major and config_minor > cli_minor:
        return (
            True,
            f"Config uses schema {config_version}, CLI supports {cli_version}. "
            f"Some features may be ignored.",
        )

    # Compatible
    return (True, None)


def check_min_cli_version(
    min_version: str, cli_version: str
) -> tuple[bool, str | None]:
    """
    Check if CLI meets minimum version requirement.

    Args:
        min_version: Minimum required CLI version (from config)
        cli_version: Current CLI version

    Returns:
        Tuple of (ok: bool, message: str | None)
    """
    min_major, min_minor, min_patch = parse_semver(min_version)
    cli_major, cli_minor, cli_patch = parse_semver(cli_version)

    # Compare version tuples
    min_tuple = (min_major, min_minor, min_patch)
    cli_tuple = (cli_major, cli_minor, cli_patch)

    if cli_tuple < min_tuple:
        return (
            False,
            f"Config requires SCC CLI >= {min_version}, but you have {cli_version}. "
            f"Please upgrade SCC CLI.",
        )

    return (True, None)
