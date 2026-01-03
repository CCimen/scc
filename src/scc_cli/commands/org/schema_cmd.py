"""Org schema command for printing bundled schema."""

from __future__ import annotations

import json

import typer

from ...cli_common import console, handle_errors
from ...core.exit_codes import EXIT_CONFIG
from ...json_output import build_envelope
from ...kinds import Kind
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel
from ...validate import load_bundled_schema


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
    print(json.dumps(schema, indent=2))  # noqa: T201
    raise typer.Exit(0)
