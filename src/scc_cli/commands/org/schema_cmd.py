"""Org schema command for printing bundled schema."""

from __future__ import annotations

import json

import typer

from ...cli_common import console, handle_errors
from ...core.constants import CURRENT_SCHEMA_VERSION
from ...core.exit_codes import EXIT_CONFIG
from ...json_output import build_envelope
from ...kinds import Kind
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel
from ...validate import load_bundled_schema


@handle_errors
def org_schema_cmd(
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
        schema = load_bundled_schema()
    except FileNotFoundError:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_SCHEMA,
                    data={"error": "Bundled schema not found"},
                    ok=False,
                    errors=["Bundled schema not found"],
                )
                print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Schema Not Found",
                "Bundled organization schema is missing.",
                "Reinstall SCC CLI or check your installation.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # JSON envelope output
    if json_output:
        with json_output_mode():
            data = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "schema": schema,
            }
            envelope = build_envelope(Kind.ORG_SCHEMA, data=data)
            print_json(envelope)
            raise typer.Exit(0)

    # Raw schema output (for piping to files or validators)
    print(json.dumps(schema, indent=2))  # noqa: T201
    raise typer.Exit(0)
