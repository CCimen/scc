"""
Schema validation for organization configs.

Provide offline-capable validation using bundled JSON schemas.
Treat $schema field as documentation, not something to fetch at runtime.

Key functions:
- validate_org_config(): Validate org config against bundled schema (org-v1.schema.json)
- validate_config_invariants(): Validate governance invariants (enabled ⊆ allowed, enabled ∩ blocked = ∅)
- check_version_compatibility(): Unified version compatibility gate
- check_schema_version(): Check schema version compatibility
- check_min_cli_version(): Check CLI meets minimum version requirement
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Literal, cast

from jsonschema import Draft7Validator

from .constants import CLI_VERSION, CURRENT_SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Invariant Validation Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class InvariantViolation:
    """Result of a config invariant check.

    Attributes:
        rule: The invariant rule that was violated (e.g., "enabled_must_be_allowed").
        message: Human-readable description of the violation.
        severity: "error" for hard failures, "warning" for advisory.
    """

    rule: str
    message: str
    severity: Literal["error", "warning"]


# ═══════════════════════════════════════════════════════════════════════════════
# Compatibility Result Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class VersionCompatibility:
    """Result of version compatibility check.

    Attributes:
        compatible: Whether the config is usable with this CLI.
        blocking_error: Error message if not compatible (requires upgrade).
        warnings: Non-blocking warnings (e.g., newer minor version).
        schema_version: Detected schema version from config.
        min_cli_version: Minimum CLI version from config, if specified.
        current_cli_version: Current CLI version for reference.
    """

    compatible: bool
    blocking_error: str | None = None
    warnings: list[str] = field(default_factory=list)
    schema_version: str | None = None
    min_cli_version: str | None = None
    current_cli_version: str = CLI_VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Loading
# ═══════════════════════════════════════════════════════════════════════════════


def load_bundled_schema(version: str = "v1") -> dict[Any, Any]:
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
        return cast(dict[Any, Any], json.loads(content))
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema version '{version}' not found")


# ═══════════════════════════════════════════════════════════════════════════════
# Config Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_org_config(config: dict[str, Any], schema_version: str = "v1") -> list[str]:
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


def check_schema_version(config_version: str, cli_version: str) -> tuple[bool, str | None]:
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


def detect_schema_version(config: dict[str, Any]) -> str:
    """
    Detect schema version from config.

    Currently only v1 is supported. This function validates the format
    and always returns "v1" for any valid semver.

    Args:
        config: Organization config dict

    Returns:
        Schema version string (always "v1")

    Raises:
        ValueError: If schema_version format is invalid
    """
    schema_version = config.get("schema_version", "1.0.0")

    # Validate format (must be X.Y.Z semver)
    try:
        parts = schema_version.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid schema_version format: {schema_version}")
        # Validate all parts are integers
        int(parts[0])
        int(parts[1])
        int(parts[2])
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid schema_version format: {schema_version}") from e

    # Only v1 schema is supported
    return "v1"


def check_min_cli_version(min_version: str, cli_version: str) -> tuple[bool, str | None]:
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


# ═══════════════════════════════════════════════════════════════════════════════
# Unified Compatibility Gate
# ═══════════════════════════════════════════════════════════════════════════════


def check_version_compatibility(config: dict[str, Any]) -> VersionCompatibility:
    """Check version compatibility for an org config.

    This is the primary entry point for version validation. It combines:
    1. Schema version check (major version must be supported)
    2. Min CLI version check (CLI must meet minimum requirement)

    The function returns immediately on blocking errors (requires upgrade)
    but collects all warnings for informational purposes.

    Args:
        config: Organization config dict to validate.

    Returns:
        VersionCompatibility result with compatibility status and messages.

    Examples:
        >>> result = check_version_compatibility({"schema_version": "1.0.0"})
        >>> result.compatible
        True

        >>> result = check_version_compatibility({"min_cli_version": "99.0.0"})
        >>> result.compatible
        False
        >>> "upgrade" in result.blocking_error.lower()
        True
    """
    warnings: list[str] = []
    schema_version = config.get("schema_version")
    min_cli_version = config.get("min_cli_version")

    # Check schema version compatibility
    if schema_version:
        try:
            schema_ok, schema_msg = check_schema_version(schema_version, CURRENT_SCHEMA_VERSION)
            if not schema_ok:
                return VersionCompatibility(
                    compatible=False,
                    blocking_error=schema_msg,
                    schema_version=schema_version,
                    min_cli_version=min_cli_version,
                )
            if schema_msg:  # Warning but still compatible
                warnings.append(schema_msg)
        except ValueError as e:
            return VersionCompatibility(
                compatible=False,
                blocking_error=f"Invalid schema_version format: {e}",
                schema_version=schema_version,
                min_cli_version=min_cli_version,
            )

    # Validate schema version is in supported list
    if schema_version:
        detected = detect_schema_version(config)
        if detected not in SUPPORTED_SCHEMA_VERSIONS:
            return VersionCompatibility(
                compatible=False,
                blocking_error=(
                    f"Schema version '{detected}' is not supported. "
                    f"Supported versions: {', '.join(SUPPORTED_SCHEMA_VERSIONS)}"
                ),
                schema_version=schema_version,
                min_cli_version=min_cli_version,
            )

    # Check minimum CLI version
    if min_cli_version:
        try:
            cli_ok, cli_msg = check_min_cli_version(min_cli_version, CLI_VERSION)
            if not cli_ok:
                return VersionCompatibility(
                    compatible=False,
                    blocking_error=cli_msg,
                    schema_version=schema_version,
                    min_cli_version=min_cli_version,
                )
        except ValueError as e:
            return VersionCompatibility(
                compatible=False,
                blocking_error=f"Invalid min_cli_version format: {e}",
                schema_version=schema_version,
                min_cli_version=min_cli_version,
            )

    # All checks passed
    return VersionCompatibility(
        compatible=True,
        warnings=warnings,
        schema_version=schema_version,
        min_cli_version=min_cli_version,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Config Invariant Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_config_invariants(config: dict[str, Any]) -> list[InvariantViolation]:
    """Validate governance invariants on raw dict config.

    This function checks semantic constraints that JSON Schema cannot express:
    - enabled plugins must be subset of allowed (enabled ⊆ allowed)
    - enabled plugins must not be blocked (enabled ∩ blocked = ∅)

    Called AFTER Pydantic structural validation passes in the Validation Gate.
    Works on raw dicts because that's what the CLI uses throughout.

    Args:
        config: Organization config dict (raw, not Pydantic model).

    Returns:
        List of InvariantViolation objects. Empty list means all invariants satisfied.

    Semantics for allowed_plugins:
        - Missing/None: unrestricted (all plugins allowed)
        - []: deny all (no plugins allowed)
        - ["*"]: explicit unrestricted (all plugins allowed via wildcard)
        - ["pattern@marketplace"]: specific whitelist with fnmatch patterns

    Examples:
        >>> config = {"defaults": {"enabled_plugins": ["a@mp"]}}
        >>> validate_config_invariants(config)  # Missing allowed = unrestricted
        []

        >>> config = {"defaults": {"enabled_plugins": ["a@mp"], "allowed_plugins": []}}
        >>> violations = validate_config_invariants(config)  # Empty = deny all
        >>> len(violations) == 1 and violations[0].rule == "enabled_must_be_allowed"
        True
    """
    # Import here to avoid circular dependency
    from scc_cli.marketplace.normalize import matches_pattern

    violations: list[InvariantViolation] = []

    # Extract config sections with safe defaults
    defaults = config.get("defaults", {})
    enabled = defaults.get("enabled_plugins", [])
    allowed = defaults.get("allowed_plugins")  # None = unrestricted

    security = config.get("security", {})
    blocked = security.get("blocked_plugins", [])

    # ─────────────────────────────────────────────────────────────────────────
    # Invariant 1: enabled ⊆ allowed (enabled plugins must be in allowed list)
    # ─────────────────────────────────────────────────────────────────────────
    if allowed is not None:
        if allowed == []:
            # Empty array = nothing allowed (explicit deny all)
            for plugin in enabled:
                violations.append(
                    InvariantViolation(
                        rule="enabled_must_be_allowed",
                        message=(
                            f"Plugin '{plugin}' is enabled but allowed_plugins is empty "
                            "(nothing allowed)"
                        ),
                        severity="error",
                    )
                )
        elif allowed != ["*"]:
            # Specific whitelist - check each enabled plugin against patterns
            for plugin in enabled:
                if not any(matches_pattern(plugin, pattern) for pattern in allowed):
                    violations.append(
                        InvariantViolation(
                            rule="enabled_must_be_allowed",
                            message=f"Plugin '{plugin}' is enabled but not in allowed list",
                            severity="error",
                        )
                    )
        # If allowed == ["*"], all plugins are allowed (explicit unrestricted)

    # ─────────────────────────────────────────────────────────────────────────
    # Invariant 2: enabled ∩ blocked = ∅ (enabled must not be blocked)
    # ─────────────────────────────────────────────────────────────────────────
    for plugin in enabled:
        for pattern in blocked:
            if matches_pattern(plugin, pattern):
                violations.append(
                    InvariantViolation(
                        rule="enabled_not_blocked",
                        message=(
                            f"Plugin '{plugin}' is enabled but matches blocked pattern '{pattern}'"
                        ),
                        severity="error",
                    )
                )
                break  # One match is enough to flag this plugin

    return violations
