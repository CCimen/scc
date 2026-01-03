"""Organization init command implementation.

Provides the org init command for generating organization configuration
skeletons from templates.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from ...cli_common import console, handle_errors
from ...core.exit_codes import EXIT_CONFIG
from ...json_output import build_envelope
from ...kinds import Kind
from ...org_templates import (
    TemplateNotFoundError,
    TemplateVars,
    list_templates,
    render_template_string,
)
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel, create_success_panel, create_warning_panel


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
