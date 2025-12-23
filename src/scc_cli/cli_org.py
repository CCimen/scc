"""
CLI Org Admin Commands.

Commands for validating and inspecting organization configurations.
"""

import json
from pathlib import Path
from typing import Any

import typer

from .cli_common import console, handle_errors
from .exit_codes import EXIT_CONFIG, EXIT_VALIDATION
from .json_output import build_envelope
from .kinds import Kind
from .output_mode import json_output_mode, print_json, set_pretty_mode
from .panels import create_error_panel, create_success_panel, create_warning_panel
from .validate import load_bundled_schema, validate_org_config

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


# ─────────────────────────────────────────────────────────────────────────────
# Org Commands
# ─────────────────────────────────────────────────────────────────────────────


@org_app.command("validate")
@handle_errors
def org_validate_cmd(
    source: str = typer.Argument(..., help="Path to config file to validate"),
    schema_version: str = typer.Option(
        "v1", "--schema-version", "-s", help="Schema version (v1, v2)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Validate an organization configuration file.

    Performs both JSON schema validation and semantic checks.

    Examples:
        scc org validate ./org-config.json
        scc org validate ./org-config.json --schema-version v2
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


@org_app.command("schema")
@handle_errors
def org_schema_cmd(
    schema_version: str = typer.Option(
        "v1", "--version", "-v", help="Schema version to print (v1, v2)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Print the bundled organization config schema.

    Useful for understanding the expected configuration format
    or for use with external validators.

    Examples:
        scc org schema
        scc org schema --version v2
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
                "Available versions: v1, v2",
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
