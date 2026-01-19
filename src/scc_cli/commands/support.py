"""
Provide CLI commands for support and diagnostics.

Generate support bundles with diagnostic information. Include secret
and path redaction for safe sharing.
"""

from datetime import datetime
from pathlib import Path

import typer

from ..application.support_bundle import (
    SupportBundleDependencies,
    SupportBundleRequest,
    build_support_bundle_manifest,
    create_support_bundle,
)
from ..bootstrap import get_default_adapters
from ..cli_common import console, handle_errors
from ..output_mode import json_output_mode, print_json, set_pretty_mode
from ..presentation.json.support_json import build_support_bundle_envelope

# ─────────────────────────────────────────────────────────────────────────────
# Support App
# ─────────────────────────────────────────────────────────────────────────────

support_app = typer.Typer(
    name="support",
    help="Support and diagnostic commands.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _get_default_bundle_path() -> Path:
    """Get default path for support bundle."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / f"scc-support-bundle-{timestamp}.zip"


# ─────────────────────────────────────────────────────────────────────────────
# Support Bundle Command
# ─────────────────────────────────────────────────────────────────────────────


@support_app.command("bundle")
@handle_errors
def support_bundle_cmd(
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for the bundle zip file",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output manifest as JSON instead of creating zip",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print JSON output (implies --json)",
    ),
    no_redact_paths: bool = typer.Option(
        False,
        "--no-redact-paths",
        help="Don't redact home directory paths",
    ),
) -> None:
    """Generate a support bundle for troubleshooting.

    Creates a zip file containing:
    - System information (platform, Python version)
    - CLI configuration (secrets redacted)
    - Doctor output (health check results)
    - Diagnostic information

    The bundle is safe to share - all sensitive data is redacted.
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    redact_paths_flag = not no_redact_paths
    output_path = Path(output) if output else _get_default_bundle_path()

    # Build dependencies from adapters
    adapters = get_default_adapters()
    dependencies = SupportBundleDependencies(
        filesystem=adapters.filesystem,
        clock=adapters.clock,
        doctor_runner=adapters.doctor_runner,
        archive_writer=adapters.archive_writer,
    )

    request = SupportBundleRequest(
        output_path=output_path,
        redact_paths=redact_paths_flag,
        workspace_path=None,
    )

    if json_output:
        with json_output_mode():
            manifest = build_support_bundle_manifest(request, dependencies=dependencies)
            envelope = build_support_bundle_envelope(manifest)
            print_json(envelope)
            raise typer.Exit(0)

    # Create the bundle zip file
    console.print("[cyan]Generating support bundle...[/cyan]")
    create_support_bundle(request, dependencies=dependencies)

    console.print()
    console.print(f"[green]Support bundle created:[/green] {output_path}")
    console.print()
    console.print("[dim]The bundle contains diagnostic information with secrets redacted.[/dim]")
    console.print("[dim]You can share this file safely with support.[/dim]")

    raise typer.Exit(0)
