"""Org validate command for schema and semantic validation."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ...cli_common import console, handle_errors
from ...core.exit_codes import EXIT_CONFIG, EXIT_VALIDATION
from ...json_output import build_envelope
from ...kinds import Kind
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel, create_success_panel, create_warning_panel
from ...validate import validate_org_config
from ._builders import build_validation_data, check_semantic_errors


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
