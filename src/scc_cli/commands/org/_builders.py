"""Pure builder functions for org commands.

These functions build data structures for JSON output and display.
They have no side effects and are ideal for unit testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def build_validation_data(
    source: str,
    schema_errors: list[str],
    semantic_errors: list[str],
    schema_version: str,
) -> dict[str, Any]:
    """Build validation result data for JSON output.

    Args:
        source: Path or URL of validated config
        schema_errors: List of JSON schema validation errors
        semantic_errors: List of semantic validation errors
        schema_version: Schema version used for validation

    Returns:
        Dictionary with validation results
    """
    is_valid = len(schema_errors) == 0 and len(semantic_errors) == 0
    return {
        "source": source,
        "schema_version": schema_version,
        "valid": is_valid,
        "schema_errors": schema_errors,
        "semantic_errors": semantic_errors,
    }


def check_semantic_errors(config: dict[str, Any]) -> list[str]:
    """Check for semantic errors beyond JSON schema validation.

    Args:
        config: Parsed organization config

    Returns:
        List of semantic error messages
    """
    errors: list[str] = []
    org = config.get("organization", {})

    # Profiles are at TOP LEVEL of config as a DICT (not under "organization")
    # Dict keys are unique, so no duplicate name checking needed
    profiles = config.get("profiles", {})
    profile_names: list[str] = list(profiles.keys())

    # Check if default_profile references existing profile
    default_profile = org.get("default_profile")
    if default_profile and default_profile not in profile_names:
        errors.append(f"default_profile '{default_profile}' references non-existent profile")

    return errors


def build_import_preview_data(
    source: str,
    resolved_url: str,
    config: dict[str, Any],
    validation_errors: list[str],
) -> dict[str, Any]:
    """Build import preview data for display and JSON output.

    Pure function that assembles preview information for an organization config
    before it is imported.

    Args:
        source: Original source string (URL or shorthand like github:org/repo)
        resolved_url: Resolved URL after shorthand expansion
        config: Parsed organization config dict
        validation_errors: List of validation error messages

    Returns:
        Dictionary with preview information including org details and validation status
    """
    org_data = config.get("organization", {})
    profiles_dict = config.get("profiles", {})

    return {
        "source": source,
        "resolved_url": resolved_url,
        "organization": {
            "name": org_data.get("name", ""),
            "id": org_data.get("id", ""),
            "contact": org_data.get("contact", ""),
        },
        "valid": len(validation_errors) == 0,
        "validation_errors": validation_errors,
        "available_profiles": list(profiles_dict.keys()),
        "schema_version": config.get("schema_version", ""),
        "min_cli_version": config.get("min_cli_version", ""),
    }


def build_status_data(
    user_config: dict[str, Any],
    org_config: dict[str, Any] | None,
    cache_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build status data for JSON output and display.

    Pure function that assembles status information from various sources.

    Args:
        user_config: User configuration dict
        org_config: Cached organization config (may be None)
        cache_meta: Cache metadata dict (may be None)

    Returns:
        Dictionary with complete status information
    """
    # Import here to avoid circular imports at module level
    from ...remote import is_cache_valid
    from ...validate import check_version_compatibility

    # Determine mode
    is_standalone = user_config.get("standalone", False) or not user_config.get(
        "organization_source"
    )

    if is_standalone:
        return {
            "mode": "standalone",
            "organization": None,
            "cache": None,
            "version_compatibility": None,
            "selected_profile": None,
            "available_profiles": [],
        }

    # Organization connected mode
    org_source = user_config.get("organization_source", {})
    source_url = org_source.get("url", "")

    # Organization info
    org_info: dict[str, Any] | None = None
    available_profiles: list[str] = []
    if org_config:
        org_data = org_config.get("organization", {})
        org_info = {
            "name": org_data.get("name", "unknown"),
            "id": org_data.get("id", ""),
            "contact": org_data.get("contact", ""),
            "source_url": source_url,
        }
        # Extract available profiles
        profiles_dict = org_config.get("profiles", {})
        available_profiles = list(profiles_dict.keys())
    else:
        org_info = {
            "name": None,
            "source_url": source_url,
        }

    # Cache status
    cache_info: dict[str, Any] | None = None
    if cache_meta:
        org_cache = cache_meta.get("org_config", {})
        cache_info = {
            "fetched_at": org_cache.get("fetched_at"),
            "expires_at": org_cache.get("expires_at"),
            "etag": org_cache.get("etag"),
            "valid": is_cache_valid(cache_meta),
        }

    # Version compatibility
    version_compat: dict[str, Any] | None = None
    if org_config:
        compat = check_version_compatibility(org_config)
        version_compat = {
            "compatible": compat.compatible,
            "blocking_error": compat.blocking_error,
            "warnings": compat.warnings,
            "schema_version": compat.schema_version,
            "min_cli_version": compat.min_cli_version,
            "current_cli_version": compat.current_cli_version,
        }

    return {
        "mode": "organization",
        "organization": org_info,
        "cache": cache_info,
        "version_compatibility": version_compat,
        "selected_profile": user_config.get("selected_profile"),
        "available_profiles": available_profiles,
    }


def build_update_data(
    org_config: dict[str, Any] | None,
    team_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build update result data for JSON output.

    Pure function that assembles update result information.

    Args:
        org_config: Updated organization config (may be None on failure)
        team_results: List of team update results (optional)

    Returns:
        Dictionary with update results including org and team info
    """
    result: dict[str, Any] = {
        "org_updated": org_config is not None,
    }

    if org_config:
        org_data = org_config.get("organization", {})
        result["organization"] = {
            "name": org_data.get("name", ""),
            "id": org_data.get("id", ""),
        }
        result["schema_version"] = org_config.get("schema_version", "")

    if team_results is not None:
        result["teams_updated"] = team_results
        result["teams_success_count"] = sum(1 for t in team_results if t.get("success"))
        result["teams_failed_count"] = sum(1 for t in team_results if not t.get("success"))

    return result


def _parse_config_source(source_dict: dict[str, Any]) -> Any:
    """Parse a config_source dict into the appropriate ConfigSource type.

    Handles discriminated union parsing for github, git, url sources.

    Args:
        source_dict: Raw config_source dict from org config

    Returns:
        ConfigSource object (ConfigSourceGitHub, ConfigSourceGit, or ConfigSourceURL)
    """
    # Import here to avoid circular imports
    from ...marketplace.schema import (
        ConfigSourceGit,
        ConfigSourceGitHub,
        ConfigSourceURL,
    )

    if "github" in source_dict:
        github_data = source_dict["github"]
        # Add source discriminator for Pydantic model
        return ConfigSourceGitHub(source="github", **github_data)
    elif "git" in source_dict:
        git_data = source_dict["git"]
        return ConfigSourceGit(source="git", **git_data)
    elif "url" in source_dict:
        url_data = source_dict["url"]
        return ConfigSourceURL(source="url", **url_data)
    else:
        raise ValueError(f"Unknown config_source type: {list(source_dict.keys())}")
