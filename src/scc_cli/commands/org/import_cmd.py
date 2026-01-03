"""Organization import command implementation.

Provides the org import command for importing organization configurations
from URLs or shorthands.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import requests
import typer
from rich.table import Table

from ...cli_common import console, handle_errors
from ...config import load_user_config, save_user_config
from ...core.exit_codes import EXIT_CONFIG, EXIT_VALIDATION
from ...json_output import build_envelope
from ...kinds import Kind
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel, create_success_panel
from ...remote import save_to_cache
from ...source_resolver import ResolveError, resolve_source
from ...validate import validate_org_config
from ._builders import build_import_preview_data

if TYPE_CHECKING:
    pass


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
                "\n".join(f"* {e}" for e in validation_errors),
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
        console.print("\n[green]Configuration is valid[/green]")
    else:
        console.print("\n[red]Configuration is invalid[/red]")
        for error in preview.get("validation_errors", []):
            console.print(f"  [red]* {error}[/red]")

    console.print("\n[dim]Use 'scc org import <source>' without --preview to import[/dim]\n")
