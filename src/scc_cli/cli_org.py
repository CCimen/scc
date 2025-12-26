"""
Provide CLI commands for organization administration.

Validate and inspect organization configurations including schema validation
and semantic checks.
"""

import json
from pathlib import Path
from typing import Any

import requests
import typer
from rich.table import Table

from .cli_common import console, handle_errors
from .config import load_user_config, save_user_config
from .constants import CLI_VERSION
from .exit_codes import EXIT_CONFIG, EXIT_VALIDATION
from .json_output import build_envelope
from .kinds import Kind
from .marketplace.team_fetch import fetch_team_config
from .org_templates import (
    TemplateNotFoundError,
    TemplateVars,
    list_templates,
    render_template_string,
)
from .output_mode import json_output_mode, print_json, set_pretty_mode
from .panels import create_error_panel, create_success_panel, create_warning_panel
from .remote import is_cache_valid, load_from_cache, load_org_config, save_to_cache
from .source_resolver import ResolveError, resolve_source
from .validate import check_version_compatibility, load_bundled_schema, validate_org_config

# ─────────────────────────────────────────────────────────────────────────────
# Org App
# ─────────────────────────────────────────────────────────────────────────────

org_app = typer.Typer(
    name="org",
    help="Organization configuration management and validation.",
    no_args_is_help=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Pure Functions
# ─────────────────────────────────────────────────────────────────────────────


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
    profiles = org.get("profiles", [])

    # Check for duplicate profile names
    profile_names: list[str] = []
    for profile in profiles:
        name = profile.get("name", "")
        if name in profile_names:
            errors.append(f"Duplicate profile name: '{name}'")
        else:
            profile_names.append(name)

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
    from .marketplace.schema import (
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


# ─────────────────────────────────────────────────────────────────────────────
# Org Commands
# ─────────────────────────────────────────────────────────────────────────────


@org_app.command("validate")
@handle_errors
def org_validate_cmd(
    source: str = typer.Argument(..., help="Path to config file to validate"),
    schema_version: str = typer.Option(
        "v1", "--schema-version", "-s", help="Schema version (default: v1)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Validate an organization configuration file.

    Performs both JSON schema validation and semantic checks.

    Examples:
        scc org validate ./org-config.json
        scc org validate ./org-config.json --json
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Load config file
    config_path = Path(source).expanduser().resolve()
    if not config_path.exists():
        if json_output:
            with json_output_mode():
                data = build_validation_data(
                    source=source,
                    schema_errors=[f"File not found: {source}"],
                    semantic_errors=[],
                    schema_version=schema_version,
                )
                envelope = build_envelope(Kind.ORG_VALIDATION, data=data, ok=False)
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("File Not Found", f"Cannot find config file: {source}"))
        raise typer.Exit(EXIT_CONFIG)

    # Parse JSON
    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as e:
        if json_output:
            with json_output_mode():
                data = build_validation_data(
                    source=source,
                    schema_errors=[f"Invalid JSON: {e}"],
                    semantic_errors=[],
                    schema_version=schema_version,
                )
                envelope = build_envelope(Kind.ORG_VALIDATION, data=data, ok=False)
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("Invalid JSON", f"Failed to parse JSON: {e}"))
        raise typer.Exit(EXIT_CONFIG)

    # Validate against schema
    schema_errors = validate_org_config(config, schema_version)

    # Check semantic errors (only if schema is valid)
    semantic_errors: list[str] = []
    if not schema_errors:
        semantic_errors = check_semantic_errors(config)

    # Build result data
    data = build_validation_data(
        source=source,
        schema_errors=schema_errors,
        semantic_errors=semantic_errors,
        schema_version=schema_version,
    )

    # JSON output mode
    if json_output:
        with json_output_mode():
            is_valid = data["valid"]
            all_errors = schema_errors + semantic_errors
            envelope = build_envelope(
                Kind.ORG_VALIDATION,
                data=data,
                ok=is_valid,
                errors=all_errors if not is_valid else None,
            )
            print_json(envelope)
            raise typer.Exit(0 if is_valid else EXIT_VALIDATION)

    # Human-readable output
    if data["valid"]:
        console.print(
            create_success_panel(
                "Validation Passed",
                {
                    "Source": source,
                    "Schema Version": schema_version,
                    "Status": "Valid",
                },
            )
        )
        raise typer.Exit(0)

    # Show errors
    if schema_errors:
        console.print(
            create_error_panel(
                "Schema Validation Failed",
                "\n".join(f"• {e}" for e in schema_errors),
            )
        )

    if semantic_errors:
        console.print(
            create_warning_panel(
                "Semantic Issues",
                "\n".join(f"• {e}" for e in semantic_errors),
            )
        )

    raise typer.Exit(EXIT_VALIDATION)


@org_app.command("update")
@handle_errors
def org_update_cmd(
    team: str | None = typer.Option(
        None, "--team", "-t", help="Refresh a specific federated team's config"
    ),
    all_teams: bool = typer.Option(
        False, "--all-teams", "-a", help="Refresh all federated team configs"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Refresh organization config and optionally team configs.

    By default, refreshes the organization config from its remote source.
    With --team or --all-teams, also refreshes federated team configurations.

    Examples:
        scc org update              # Refresh org config only
        scc org update --team dev   # Also refresh 'dev' team config
        scc org update --all-teams  # Refresh all federated team configs
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Load user config
    user_config = load_user_config()

    # Check for standalone mode
    is_standalone = user_config.get("standalone", False)
    if is_standalone:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_UPDATE,
                    data={"error": "Cannot update in standalone mode"},
                    ok=False,
                    errors=["CLI is running in standalone mode"],
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Standalone Mode",
                "Cannot update organization config in standalone mode.",
                hint="Use 'scc setup' to connect to an organization.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Check for organization source
    org_source = user_config.get("organization_source")
    if not org_source:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_UPDATE,
                    data={"error": "No organization source configured"},
                    ok=False,
                    errors=["No organization source configured"],
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "No Organization",
                "No organization source is configured.",
                hint="Use 'scc setup' to connect to an organization.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Force refresh org config
    org_config = load_org_config(user_config, force_refresh=True)
    if org_config is None:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_UPDATE,
                    data=build_update_data(None),
                    ok=False,
                    errors=["Failed to fetch organization config"],
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Update Failed",
                "Failed to fetch organization config from remote.",
                hint="Check network connection and organization URL.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Get profiles from org config
    profiles = org_config.get("profiles", {})

    # Handle --team option (single team update)
    team_results: list[dict[str, Any]] | None = None
    if team is not None:
        # Validate team exists
        if team not in profiles:
            if json_output:
                with json_output_mode():
                    envelope = build_envelope(
                        Kind.ORG_UPDATE,
                        data=build_update_data(org_config),
                        ok=False,
                        errors=[f"Team '{team}' not found in organization config"],
                    )
                    print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
            console.print(
                create_error_panel(
                    "Team Not Found",
                    f"Team '{team}' not found in organization config.",
                    hint=f"Available teams: {', '.join(profiles.keys())}",
                )
            )
            raise typer.Exit(EXIT_CONFIG)

        profile = profiles[team]
        config_source_dict = profile.get("config_source")

        # Check if team is federated
        if config_source_dict is None:
            team_results = [{"team": team, "success": True, "inline": True}]
            if json_output:
                with json_output_mode():
                    data = build_update_data(org_config, team_results)
                    envelope = build_envelope(Kind.ORG_UPDATE, data=data)
                    print_json(envelope)
                raise typer.Exit(0)
            console.print(
                create_warning_panel(
                    "Inline Team",
                    f"Team '{team}' is not federated (inline config).",
                    hint="Inline teams don't have external configs to refresh.",
                )
            )
            raise typer.Exit(0)

        # Fetch team config
        try:
            config_source = _parse_config_source(config_source_dict)
            result = fetch_team_config(config_source, team)
            if result.success:
                team_results = [
                    {
                        "team": team,
                        "success": True,
                        "commit_sha": result.commit_sha,
                    }
                ]
            else:
                team_results = [
                    {
                        "team": team,
                        "success": False,
                        "error": result.error,
                    }
                ]
                if json_output:
                    with json_output_mode():
                        data = build_update_data(org_config, team_results)
                        envelope = build_envelope(
                            Kind.ORG_UPDATE,
                            data=data,
                            ok=False,
                            errors=[f"Failed to fetch team config: {result.error}"],
                        )
                        print_json(envelope)
                    raise typer.Exit(EXIT_CONFIG)
                console.print(
                    create_error_panel(
                        "Team Update Failed",
                        f"Failed to fetch config for team '{team}'.",
                        hint=str(result.error),
                    )
                )
                raise typer.Exit(EXIT_CONFIG)
        except Exception as e:
            if json_output:
                with json_output_mode():
                    envelope = build_envelope(
                        Kind.ORG_UPDATE,
                        data=build_update_data(org_config),
                        ok=False,
                        errors=[f"Error parsing config source: {e}"],
                    )
                    print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
            console.print(create_error_panel("Config Error", f"Error parsing config source: {e}"))
            raise typer.Exit(EXIT_CONFIG)

    # Handle --all-teams option
    elif all_teams:
        team_results = []
        federated_teams = [
            (name, profile)
            for name, profile in profiles.items()
            if profile.get("config_source") is not None
        ]

        if not federated_teams:
            team_results = []
            if json_output:
                with json_output_mode():
                    data = build_update_data(org_config, team_results)
                    envelope = build_envelope(Kind.ORG_UPDATE, data=data)
                    print_json(envelope)
                raise typer.Exit(0)
            console.print(
                create_warning_panel(
                    "No Federated Teams",
                    "No federated teams found in organization config.",
                    hint="All teams use inline configuration.",
                )
            )
            raise typer.Exit(0)

        # Fetch all federated team configs
        for team_name, profile in federated_teams:
            config_source_dict = profile["config_source"]
            try:
                config_source = _parse_config_source(config_source_dict)
                result = fetch_team_config(config_source, team_name)
                if result.success:
                    team_results.append(
                        {
                            "team": team_name,
                            "success": True,
                            "commit_sha": result.commit_sha,
                        }
                    )
                else:
                    team_results.append(
                        {
                            "team": team_name,
                            "success": False,
                            "error": result.error,
                        }
                    )
            except Exception as e:
                team_results.append(
                    {
                        "team": team_name,
                        "success": False,
                        "error": str(e),
                    }
                )

    # Build output data
    data = build_update_data(org_config, team_results)

    # JSON output
    if json_output:
        with json_output_mode():
            # Determine overall success
            has_team_failures = team_results is not None and any(
                not t.get("success") for t in team_results
            )
            envelope = build_envelope(
                Kind.ORG_UPDATE,
                data=data,
                ok=not has_team_failures,
            )
            print_json(envelope)
        raise typer.Exit(0)

    # Human-readable output
    org_data = org_config.get("organization", {})
    org_name = org_data.get("name", "Unknown")

    if team_results is None:
        # Org-only update
        console.print(
            create_success_panel(
                "Organization Updated",
                {
                    "Organization": org_name,
                    "Status": "Refreshed from remote",
                },
            )
        )
    else:
        # Team updates included
        success_count = sum(1 for t in team_results if t.get("success"))
        failed_count = len(team_results) - success_count

        if failed_count == 0:
            console.print(
                create_success_panel(
                    "Update Complete",
                    {
                        "Organization": org_name,
                        "Teams Updated": str(success_count),
                    },
                )
            )
        else:
            console.print(
                create_warning_panel(
                    "Partial Update",
                    f"Organization updated. {success_count} team(s) succeeded, {failed_count} failed.",
                )
            )

    raise typer.Exit(0)


@org_app.command("schema")
@handle_errors
def org_schema_cmd(
    schema_version: str = typer.Option(
        "v1", "--version", "-v", help="Schema version to print (default: v1)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Print the bundled organization config schema.

    Useful for understanding the expected configuration format
    or for use with external validators.

    Examples:
        scc org schema
        scc org schema --json
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Load schema
    try:
        schema = load_bundled_schema(schema_version)
    except FileNotFoundError:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_SCHEMA,
                    data={"error": f"Schema version '{schema_version}' not found"},
                    ok=False,
                    errors=[f"Schema version '{schema_version}' not found"],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Schema Not Found",
                f"Schema version '{schema_version}' does not exist.",
                "Available version: v1",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # JSON envelope output
    if json_output:
        with json_output_mode():
            data = {
                "schema_version": schema_version,
                "schema": schema,
            }
            envelope = build_envelope(Kind.ORG_SCHEMA, data=data)
            print_json(envelope)
            raise typer.Exit(0)

    # Raw schema output (for piping to files or validators)
    print(json.dumps(schema, indent=2))
    raise typer.Exit(0)


@org_app.command("status")
@handle_errors
def org_status_cmd(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Show current organization configuration status.

    Displays connection mode (standalone or organization), cache freshness,
    version compatibility, and selected profile.

    Examples:
        scc org status
        scc org status --json
        scc org status --pretty
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Load configuration data
    user_config = load_user_config()
    org_config, cache_meta = load_from_cache()

    # Build status data
    status_data = build_status_data(user_config, org_config, cache_meta)

    # JSON output mode
    if json_output:
        with json_output_mode():
            envelope = build_envelope(Kind.ORG_STATUS, data=status_data)
            print_json(envelope)
            raise typer.Exit(0)

    # Human-readable output
    _render_status_human(status_data)
    raise typer.Exit(0)


def _render_status_human(status: dict[str, Any]) -> None:
    """Render status data as human-readable Rich output.

    Args:
        status: Status data from build_status_data
    """
    # Mode header
    mode = status["mode"]
    if mode == "standalone":
        console.print("\n[bold cyan]Organization Status[/bold cyan]")
        console.print("  Mode: [yellow]Standalone[/yellow] (no organization configured)")
        console.print("\n  [dim]Tip: Run 'scc setup' to connect to an organization[/dim]\n")
        return

    # Organization mode
    console.print("\n[bold cyan]Organization Status[/bold cyan]")

    # Create a table for organization info
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")

    # Organization info
    org = status.get("organization", {})
    if org:
        org_name = org.get("name") or "[not fetched]"
        table.add_row("Organization", f"[bold]{org_name}[/bold]")
        table.add_row("Source URL", org.get("source_url", "[not configured]"))

    # Selected profile
    profile = status.get("selected_profile")
    if profile:
        table.add_row("Selected Profile", f"[green]{profile}[/green]")
    else:
        table.add_row("Selected Profile", "[yellow]None[/yellow]")

    # Available profiles
    available = status.get("available_profiles", [])
    if available:
        table.add_row("Available Profiles", ", ".join(available))

    console.print(table)

    # Cache status
    cache = status.get("cache")
    if cache:
        console.print("\n[bold]Cache Status[/bold]")
        cache_table = Table(show_header=False, box=None, padding=(0, 2))
        cache_table.add_column("Key", style="dim")
        cache_table.add_column("Value")

        if cache.get("valid"):
            cache_table.add_row("Status", "[green]✓ Fresh[/green]")
        else:
            cache_table.add_row("Status", "[yellow]⚠ Expired[/yellow]")

        if cache.get("fetched_at"):
            cache_table.add_row("Fetched At", cache["fetched_at"])
        if cache.get("expires_at"):
            cache_table.add_row("Expires At", cache["expires_at"])

        console.print(cache_table)
    else:
        console.print("\n[yellow]Cache:[/yellow] Not fetched yet")
        console.print(
            "  [dim]Run 'scc start' or 'scc doctor' to fetch the organization config[/dim]"
        )

    # Version compatibility
    compat = status.get("version_compatibility")
    if compat:
        console.print("\n[bold]Version Compatibility[/bold]")
        compat_table = Table(show_header=False, box=None, padding=(0, 2))
        compat_table.add_column("Key", style="dim")
        compat_table.add_column("Value")

        if compat.get("compatible"):
            compat_table.add_row("Status", "[green]✓ Compatible[/green]")
        else:
            if compat.get("blocking_error"):
                compat_table.add_row("Status", "[red]✗ Incompatible[/red]")
                compat_table.add_row("Error", f"[red]{compat['blocking_error']}[/red]")
            else:
                compat_table.add_row("Status", "[yellow]⚠ Warnings[/yellow]")

        if compat.get("schema_version"):
            compat_table.add_row("Schema Version", compat["schema_version"])
        if compat.get("min_cli_version"):
            compat_table.add_row("Min CLI Version", compat["min_cli_version"])
        compat_table.add_row("Current CLI", compat.get("current_cli_version", CLI_VERSION))

        # Show warnings if any
        warnings = compat.get("warnings", [])
        for warning in warnings:
            console.print(f"  [yellow]⚠ {warning}[/yellow]")

        console.print(compat_table)

    console.print()  # Final newline


@org_app.command("import")
@handle_errors
def org_import_cmd(
    source: str = typer.Argument(..., help="URL or shorthand (e.g., github:org/repo)"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Preview import without saving"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Import an organization configuration from a URL.

    Supports direct URLs and shorthands like github:org/repo.
    Use --preview to validate without saving.

    Examples:
        scc org import https://example.com/org-config.json
        scc org import github:acme/configs
        scc org import github:acme/configs --preview
        scc org import https://example.com/org.json --json
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Resolve source URL (handles shorthands like github:org/repo)
    resolved = resolve_source(source)
    if isinstance(resolved, ResolveError):
        error_msg = resolved.message
        if resolved.suggestion:
            error_msg = f"{resolved.message}\n{resolved.suggestion}"
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_IMPORT_PREVIEW if preview else Kind.ORG_IMPORT,
                    data={"error": error_msg, "source": source},
                    ok=False,
                    errors=[error_msg],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("Invalid Source", error_msg))
        raise typer.Exit(EXIT_CONFIG)

    resolved_url = resolved.resolved_url

    # Fetch the config from URL
    try:
        response = requests.get(resolved_url, timeout=30)
    except requests.RequestException as e:
        error_msg = f"Failed to fetch config: {e}"
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_IMPORT_PREVIEW if preview else Kind.ORG_IMPORT,
                    data={"error": error_msg, "source": source, "resolved_url": resolved_url},
                    ok=False,
                    errors=[error_msg],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("Network Error", error_msg))
        raise typer.Exit(EXIT_CONFIG)

    # Check HTTP status
    if response.status_code == 404:
        error_msg = f"Config not found at {resolved_url}"
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_IMPORT_PREVIEW if preview else Kind.ORG_IMPORT,
                    data={"error": error_msg, "source": source, "resolved_url": resolved_url},
                    ok=False,
                    errors=[error_msg],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("Not Found", error_msg))
        raise typer.Exit(EXIT_CONFIG)

    if response.status_code != 200:
        error_msg = f"HTTP {response.status_code} from {resolved_url}"
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_IMPORT_PREVIEW if preview else Kind.ORG_IMPORT,
                    data={"error": error_msg, "source": source, "resolved_url": resolved_url},
                    ok=False,
                    errors=[error_msg],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("HTTP Error", error_msg))
        raise typer.Exit(EXIT_CONFIG)

    # Parse JSON response
    try:
        config = response.json()
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in response: {e}"
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_IMPORT_PREVIEW if preview else Kind.ORG_IMPORT,
                    data={"error": error_msg, "source": source, "resolved_url": resolved_url},
                    ok=False,
                    errors=[error_msg],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(create_error_panel("Invalid JSON", error_msg))
        raise typer.Exit(EXIT_CONFIG)

    # Validate config against schema
    validation_errors = validate_org_config(config, "v1")

    # Build preview data
    preview_data = build_import_preview_data(
        source=source,
        resolved_url=resolved_url,
        config=config,
        validation_errors=validation_errors,
    )

    # Preview mode: show info without saving
    if preview:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(Kind.ORG_IMPORT_PREVIEW, data=preview_data)
                print_json(envelope)
                raise typer.Exit(0)

        # Human-readable preview
        _render_import_preview(preview_data)
        raise typer.Exit(0)

    # Import mode: validate and save
    if not preview_data["valid"]:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_IMPORT,
                    data=preview_data,
                    ok=False,
                    errors=validation_errors,
                )
                print_json(envelope)
                raise typer.Exit(EXIT_VALIDATION)
        console.print(
            create_error_panel(
                "Validation Failed",
                "\n".join(f"• {e}" for e in validation_errors),
            )
        )
        raise typer.Exit(EXIT_VALIDATION)

    # Save to user config
    user_config = load_user_config()
    user_config["organization_source"] = {
        "url": resolved_url,
        "auth": getattr(resolved, "auth_spec", None),
    }
    user_config["standalone"] = False
    save_user_config(user_config)

    # Cache the fetched config
    etag = response.headers.get("ETag")
    save_to_cache(config, source_url=resolved_url, etag=etag, ttl_hours=24)

    # Build import result data
    import_data = {
        **preview_data,
        "imported": True,
    }

    if json_output:
        with json_output_mode():
            envelope = build_envelope(Kind.ORG_IMPORT, data=import_data)
            print_json(envelope)
            raise typer.Exit(0)

    # Human-readable success
    org_name = preview_data["organization"]["name"] or "organization"
    console.print(
        create_success_panel(
            "Import Successful",
            {
                "Organization": org_name,
                "Source": source,
                "Profiles": ", ".join(preview_data["available_profiles"]) or "None",
            },
        )
    )
    raise typer.Exit(0)


def _render_import_preview(preview: dict[str, Any]) -> None:
    """Render import preview as human-readable Rich output.

    Args:
        preview: Preview data from build_import_preview_data
    """
    console.print("\n[bold cyan]Organization Config Preview[/bold cyan]")

    # Create info table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")

    org = preview.get("organization", {})
    table.add_row("Organization", f"[bold]{org.get('name') or '[unnamed]'}[/bold]")

    if preview["source"] != preview["resolved_url"]:
        table.add_row("Source", preview["source"])
        table.add_row("Resolved URL", preview["resolved_url"])
    else:
        table.add_row("Source", preview["source"])

    if preview.get("schema_version"):
        table.add_row("Schema Version", preview["schema_version"])
    if preview.get("min_cli_version"):
        table.add_row("Min CLI Version", preview["min_cli_version"])

    profiles = preview.get("available_profiles", [])
    if profiles:
        table.add_row("Available Profiles", ", ".join(profiles))

    console.print(table)

    # Validation status
    if preview["valid"]:
        console.print("\n[green]✓ Configuration is valid[/green]")
    else:
        console.print("\n[red]✗ Configuration is invalid[/red]")
        for error in preview.get("validation_errors", []):
            console.print(f"  [red]• {error}[/red]")

    console.print("\n[dim]Use 'scc org import <source>' without --preview to import[/dim]\n")


# ─────────────────────────────────────────────────────────────────────────────
# Init Command
# ─────────────────────────────────────────────────────────────────────────────


@org_app.command("init")
@handle_errors
def org_init_cmd(
    template: str = typer.Option(
        "minimal",
        "--template",
        "-t",
        help="Template to use (minimal, teams, strict, reference).",
    ),
    org_name: str = typer.Option(
        "my-org",
        "--org-name",
        "-n",
        help="Organization name for template substitution.",
    ),
    org_domain: str = typer.Option(
        "example.com",
        "--org-domain",
        "-d",
        help="Organization domain for template substitution.",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Print generated config to stdout instead of writing to file.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write config to specified file path.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing file without prompting.",
    ),
    list_templates_flag: bool = typer.Option(
        False,
        "--list-templates",
        "-l",
        help="List available templates and exit.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON envelope format.",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print JSON output with indentation.",
    ),
) -> None:
    """Generate an organization config skeleton from templates.

    Templates provide starting points for organization configurations:
    - minimal: Simple quickstart with sensible defaults
    - teams: Multi-team setup with delegation
    - strict: Security-focused for regulated industries
    - reference: Complete reference with all fields documented

    Examples:
        scc org init --list-templates          # Show available templates
        scc org init --stdout                  # Print minimal config to stdout
        scc org init -t teams --stdout         # Print teams template
        scc org init -o org.json               # Write to org.json
        scc org init -n acme -d acme.com -o .  # Customize and write
    """
    if pretty:
        set_pretty_mode(True)

    # Handle --list-templates
    if list_templates_flag:
        _handle_list_templates(json_output)
        return

    # Require either --stdout or --output
    if not stdout and output is None:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_INIT,
                    data={"error": "Must specify --stdout or --output"},
                    ok=False,
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_warning_panel(
                "Output Required",
                "Must specify either --stdout or --output to generate config.",
                hint="Use --list-templates to see available templates.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Generate config from template
    try:
        vars = TemplateVars(org_name=org_name, org_domain=org_domain)
        config_json = render_template_string(template, vars)
    except TemplateNotFoundError as e:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_INIT,
                    data={
                        "error": str(e),
                        "available_templates": e.available,
                    },
                    ok=False,
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Template Not Found",
                str(e),
                hint=f"Available templates: {', '.join(e.available)}",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Handle --stdout
    if stdout:
        if json_output:
            # In JSON mode with --stdout, just print the raw config
            # The config itself is the output, not wrapped in envelope
            console.print(config_json)
        else:
            console.print(config_json)
        raise typer.Exit(0)

    # Handle --output
    if output is not None:
        # Resolve output path
        if output.is_dir():
            output_path = output / "org-config.json"
        else:
            output_path = output

        # Check for existing file
        if output_path.exists() and not force:
            if json_output:
                with json_output_mode():
                    envelope = build_envelope(
                        Kind.ORG_INIT,
                        data={
                            "error": f"File already exists: {output_path}",
                            "file": str(output_path),
                        },
                        ok=False,
                    )
                    print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
            console.print(
                create_error_panel(
                    "File Exists",
                    f"File already exists: {output_path}",
                    hint="Use --force to overwrite.",
                )
            )
            raise typer.Exit(EXIT_CONFIG)

        # Write file
        output_path.write_text(config_json)

        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_INIT,
                    data={
                        "file": str(output_path),
                        "template": template,
                        "org_name": org_name,
                        "org_domain": org_domain,
                    },
                )
                print_json(envelope)
        else:
            console.print(
                create_success_panel(
                    "Config Created",
                    {
                        "File": str(output_path),
                        "Template": template,
                    },
                )
            )
        raise typer.Exit(0)


def _handle_list_templates(json_output: bool) -> None:
    """Handle --list-templates flag.

    Args:
        json_output: Whether to output JSON envelope format.
    """
    templates = list_templates()

    if json_output:
        with json_output_mode():
            template_data = [
                {
                    "name": t.name,
                    "description": t.description,
                    "level": t.level,
                    "use_case": t.use_case,
                }
                for t in templates
            ]
            envelope = build_envelope(
                Kind.ORG_TEMPLATE_LIST,
                data={"templates": template_data},
            )
            print_json(envelope)
        raise typer.Exit(0)

    # Human-readable output
    console.print("\n[bold cyan]Available Organization Config Templates[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Template", style="cyan")
    table.add_column("Level")
    table.add_column("Description")

    for t in templates:
        level_style = {
            "beginner": "green",
            "intermediate": "yellow",
            "advanced": "red",
            "reference": "blue",
        }.get(t.level, "")
        table.add_row(
            t.name,
            f"[{level_style}]{t.level}[/{level_style}]" if level_style else t.level,
            t.description,
        )

    console.print(table)
    console.print("\n[dim]Use: scc org init --template <name> --stdout[/dim]\n")
    raise typer.Exit(0)
