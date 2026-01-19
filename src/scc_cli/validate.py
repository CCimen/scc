"""
Schema validation for organization configs.

Provide offline-capable validation using bundled JSON schemas.
Treat $schema field as documentation, not something to fetch at runtime.

Key functions:
- validate_org_config(): Validate org config against the bundled schema
- validate_config_invariants(): Validate governance invariants (enabled ⊆ allowed, enabled ∩ blocked = ∅)
- check_version_compatibility(): Unified version compatibility gate
- check_schema_version(): Check schema version compatibility
- check_min_cli_version(): Check CLI meets minimum version requirement
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import TYPE_CHECKING, Any, cast

from jsonschema import Draft7Validator

from .core.constants import CLI_VERSION, CURRENT_SCHEMA_VERSION
from .core.enums import SeverityLevel

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
        severity: SeverityLevel.ERROR for hard failures, SeverityLevel.WARNING for advisory.
    """

    rule: str
    message: str
    severity: SeverityLevel


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


ORG_SCHEMA_FILENAME = "org-v1.schema.json"


def load_bundled_schema() -> dict[Any, Any]:
    """Load bundled organization schema from package resources."""
    schema_file = files("scc_cli.schemas").joinpath(ORG_SCHEMA_FILENAME)
    try:
        content = schema_file.read_text()
        return cast(dict[Any, Any], json.loads(content))
    except FileNotFoundError:
        raise FileNotFoundError(f"Schema file '{ORG_SCHEMA_FILENAME}' not found")


# ═══════════════════════════════════════════════════════════════════════════════
# Config Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_org_config(config: dict[str, Any]) -> list[str]:
    """Validate org config against bundled schema.

    Args:
        config: Organization config dict to validate

    Returns:
        List of error strings. Empty list means config is valid.
    """
    schema = load_bundled_schema()
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
    """Check schema version compatibility.

    The CLI only supports a single schema version. The config version must
    match the CLI's current schema version exactly.

    Args:
        config_version: Schema version from org config (e.g., "1.0.0")
        cli_version: Current CLI schema version (e.g., "1.0.0")

    Returns:
        Tuple of (compatible: bool, message: str | None)
    """
    try:
        parse_semver(config_version)
    except ValueError as exc:
        return (False, f"Invalid schema_version format: {exc}")

    if config_version != cli_version:
        return (
            False,
            f"Unsupported schema_version '{config_version}'. Expected {cli_version}.",
        )

    return (True, None)


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
    if not schema_version:
        return VersionCompatibility(
            compatible=False,
            blocking_error="schema_version is required in org config",
            schema_version=None,
            min_cli_version=min_cli_version,
        )

    schema_ok, schema_msg = check_schema_version(schema_version, CURRENT_SCHEMA_VERSION)
    if not schema_ok:
        return VersionCompatibility(
            compatible=False,
            blocking_error=schema_msg,
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
    - Additional plugins must respect allowlists
    - Security blocklists must not conflict with enabled plugins
    - MCP servers must respect allowlists and blocklists
    """
    from urllib.parse import urlparse

    from scc_cli.marketplace.normalize import (
        AmbiguousMarketplaceError,
        InvalidPluginRefError,
        matches_pattern,
        normalize_plugin,
    )

    violations: list[InvariantViolation] = []

    defaults = config.get("defaults", {})
    security = config.get("security", {})
    profiles = config.get("profiles", {})
    org_marketplaces = config.get("marketplaces", {})

    allowed_plugins = defaults.get("allowed_plugins")
    blocked_plugins = security.get("blocked_plugins", [])

    allowed_mcp_servers = defaults.get("allowed_mcp_servers")
    blocked_mcp_servers = security.get("blocked_mcp_servers", [])

    def normalize_plugin_safe(ref: str, context: str) -> str | None:
        try:
            return normalize_plugin(ref, org_marketplaces)
        except (AmbiguousMarketplaceError, InvalidPluginRefError, ValueError) as exc:
            violations.append(
                InvariantViolation(
                    rule="invalid_plugin_reference",
                    message=f"{context} plugin '{ref}' is invalid: {exc}",
                    severity=SeverityLevel.ERROR,
                )
            )
            return None

    def is_allowed_by_patterns(value: str, patterns: list[str] | None) -> bool:
        if patterns is None:
            return True
        if not patterns:
            return False
        return any(matches_pattern(value, pattern) for pattern in patterns)

    def any_allowed(values: list[str], patterns: list[str] | None) -> bool:
        if patterns is None:
            return True
        if not patterns:
            return False
        for candidate in values:
            if any(matches_pattern(candidate, pattern) for pattern in patterns):
                return True
        return False

    def mcp_candidates(server: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        name = server.get("name", "")
        if name:
            candidates.append(name)
        url = server.get("url", "")
        if url:
            candidates.append(url)
            parsed = urlparse(url)
            if parsed.netloc:
                candidates.append(parsed.netloc)
        command = server.get("command", "")
        if command:
            candidates.append(command)
        return candidates

    # ─────────────────────────────────────────────────────────────────────────
    # Plugins: enforce allowlist for team additions
    # ─────────────────────────────────────────────────────────────────────────
    for team_name, profile in profiles.items():
        for plugin_ref in profile.get("additional_plugins", []) or []:
            normalized = normalize_plugin_safe(plugin_ref, f"Team '{team_name}'")
            if not normalized:
                continue
            if not is_allowed_by_patterns(normalized, allowed_plugins):
                violations.append(
                    InvariantViolation(
                        rule="additional_plugin_not_allowed",
                        message=(
                            f"Team '{team_name}' plugin '{normalized}' is not allowed by defaults.allowed_plugins"
                        ),
                        severity=SeverityLevel.ERROR,
                    )
                )

            for pattern in blocked_plugins:
                if matches_pattern(normalized, pattern):
                    violations.append(
                        InvariantViolation(
                            rule="plugin_blocked",
                            message=(
                                f"Team '{team_name}' plugin '{normalized}' matches blocked pattern '{pattern}'"
                            ),
                            severity=SeverityLevel.ERROR,
                        )
                    )
                    break

    # Ensure org defaults are not blocked
    for plugin_ref in defaults.get("enabled_plugins", []) or []:
        normalized = normalize_plugin_safe(plugin_ref, "Defaults")
        if not normalized:
            continue
        for pattern in blocked_plugins:
            if matches_pattern(normalized, pattern):
                violations.append(
                    InvariantViolation(
                        rule="plugin_blocked",
                        message=(
                            f"Default plugin '{normalized}' matches blocked pattern '{pattern}'"
                        ),
                        severity=SeverityLevel.ERROR,
                    )
                )
                break

    # ─────────────────────────────────────────────────────────────────────────
    # MCP servers: enforce allowlist and blocklist for team additions
    # ─────────────────────────────────────────────────────────────────────────
    for team_name, profile in profiles.items():
        for server in profile.get("additional_mcp_servers", []) or []:
            candidates = mcp_candidates(server)
            if not candidates:
                violations.append(
                    InvariantViolation(
                        rule="mcp_missing_identifier",
                        message=f"Team '{team_name}' MCP server entry is missing identifiers",
                        severity=SeverityLevel.ERROR,
                    )
                )
                continue

            if not any_allowed(candidates, allowed_mcp_servers):
                allowed = allowed_mcp_servers
                allowed_desc = "[]" if allowed == [] else "defaults.allowed_mcp_servers"
                violations.append(
                    InvariantViolation(
                        rule="mcp_not_allowed",
                        message=(
                            f"Team '{team_name}' MCP server '{candidates[0]}' is not allowed by {allowed_desc}"
                        ),
                        severity=SeverityLevel.ERROR,
                    )
                )

            for pattern in blocked_mcp_servers:
                if any(matches_pattern(candidate, pattern) for candidate in candidates):
                    violations.append(
                        InvariantViolation(
                            rule="mcp_blocked",
                            message=(
                                f"Team '{team_name}' MCP server '{candidates[0]}' matches blocked pattern '{pattern}'"
                            ),
                            severity=SeverityLevel.ERROR,
                        )
                    )
                    break

    return violations
