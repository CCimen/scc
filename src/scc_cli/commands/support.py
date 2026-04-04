"""
Provide CLI commands for support and diagnostics.

Generate support bundles with diagnostic information and inspect the
recent launch-audit sink without opening raw JSONL files by hand.
"""

from __future__ import annotations

from pathlib import Path

import typer

from .. import config
from ..application.launch.audit_log import (
    LaunchAuditDiagnostics,
    LaunchAuditEventRecord,
    read_launch_audit_diagnostics,
)
from ..application.support_bundle import (
    SupportBundleRequest,
    build_default_support_bundle_dependencies,
    build_support_bundle_manifest,
    create_support_bundle,
    get_default_support_bundle_path,
)
from ..cli_common import console, handle_errors
from ..output_mode import json_output_mode, print_json, set_pretty_mode
from ..presentation.json.launch_audit_json import build_launch_audit_envelope
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


def _render_launch_audit_human(diagnostics: LaunchAuditDiagnostics) -> None:
    """Render launch-audit diagnostics for human readers."""
    console.print(f"[bold cyan]Launch audit[/bold cyan]\nSink: {diagnostics.sink_path}")

    if diagnostics.state == "unavailable":
        console.print("State: unavailable")
        if diagnostics.error:
            console.print(f"Error: {diagnostics.error}")
        else:
            console.print("No launch-audit file exists yet.")
        return

    if diagnostics.state == "empty":
        console.print("State: empty")
        console.print("The launch-audit file exists, but it has no records yet.")
        return

    console.print("State: available")
    console.print(f"Recent scan lines: {diagnostics.scanned_line_count}")
    console.print(f"Malformed records in recent scan: {diagnostics.malformed_line_count}")
    if diagnostics.last_malformed_line is not None:
        console.print(f"Last malformed line in recent scan: {diagnostics.last_malformed_line}")

    console.print()
    console.print("[bold]Last failure[/bold]")
    if diagnostics.last_failure is None:
        console.print("No failed launch event was found in the recent scan.")
    else:
        _render_launch_audit_event(diagnostics.last_failure)

    console.print()
    console.print(f"[bold]Recent events[/bold] (limit {diagnostics.requested_limit})")
    if len(diagnostics.recent_events) == 0:
        console.print("No recent launch events matched the requested limit.")
        return

    for event in diagnostics.recent_events:
        _render_launch_audit_event(event)
        console.print()


def _render_launch_audit_event(event: LaunchAuditEventRecord) -> None:
    provider = event.provider_id or "unknown"
    console.print(
        f"- {event.occurred_at} [{event.severity}] {event.event_type} "
        f"provider={provider} line={event.line_number}"
    )
    console.print(f"  {event.message}")
    if event.failure_reason:
        console.print(f"  Failure reason: {event.failure_reason}")


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
    - Launch-audit diagnostics

    The bundle is safe to share by default.
    """
    if pretty:
        json_output = True
        set_pretty_mode(True)

    redact_paths_flag = not no_redact_paths
    output_path = Path(output) if output else get_default_support_bundle_path()

    dependencies = build_default_support_bundle_dependencies()

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

    console.print("[cyan]Generating support bundle...[/cyan]")
    create_support_bundle(request, dependencies=dependencies)

    console.print()
    console.print(f"[green]Support bundle created:[/green] {output_path}")
    console.print()
    console.print("[dim]The bundle contains diagnostic information with secrets redacted.[/dim]")
    console.print("[dim]You can share this file safely with support.[/dim]")

    raise typer.Exit(0)


# ─────────────────────────────────────────────────────────────────────────────
# Launch Audit Command
# ─────────────────────────────────────────────────────────────────────────────


@support_app.command("launch-audit")
@handle_errors
def support_launch_audit_cmd(
    limit: int = typer.Option(
        10,
        "--limit",
        min=0,
        help="Maximum number of recent launch events to show.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output diagnostics as JSON.",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print JSON output (implies --json).",
    ),
) -> None:
    """Show recent launch-audit diagnostics from SCC's durable JSONL sink."""
    if pretty:
        json_output = True
        set_pretty_mode(True)

    diagnostics = read_launch_audit_diagnostics(
        audit_path=config.LAUNCH_AUDIT_FILE,
        limit=limit,
        redact_paths=True,
    )

    if json_output:
        with json_output_mode():
            print_json(build_launch_audit_envelope(diagnostics))
            raise typer.Exit(0)

    _render_launch_audit_human(diagnostics)
    raise typer.Exit(0)
