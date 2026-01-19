"""Presentation helpers for launch flow output."""

from __future__ import annotations

from rich.console import Console

from scc_cli.application.launch.output_models import (
    LaunchInfoEvent,
    LaunchOutputViewModel,
    LaunchSuccessEvent,
    LaunchWarningEvent,
)
from scc_cli.application.start_session import StartSessionPlan
from scc_cli.panels import create_warning_panel
from scc_cli.theme import Indicators
from scc_cli.ui.chrome import print_with_layout


def build_sync_output_view_model(plan: StartSessionPlan) -> LaunchOutputViewModel:
    """Build output view model for marketplace sync messages.

    Invariants:
        - Messages mirror existing CLI text for sync warnings and counts.

    Args:
        plan: Start session plan with sync result metadata.

    Returns:
        LaunchOutputViewModel describing sync output to render.
    """
    events: list[LaunchInfoEvent | LaunchWarningEvent | LaunchSuccessEvent] = []
    if plan.sync_result and plan.sync_result.warnings:
        for warning in plan.sync_result.warnings:
            events.append(LaunchWarningEvent(message=warning))
    if plan.sync_result and plan.sync_result.plugins_enabled:
        events.append(
            LaunchSuccessEvent(
                message=(
                    f"{Indicators.get('PASS')} Enabled "
                    f"{len(plan.sync_result.plugins_enabled)} team plugin(s)"
                )
            )
        )
    if plan.sync_result and plan.sync_result.marketplaces_materialized:
        events.append(
            LaunchSuccessEvent(
                message=(
                    f"{Indicators.get('PASS')} Materialized "
                    f"{len(plan.sync_result.marketplaces_materialized)} marketplace(s)"
                )
            )
        )
    return LaunchOutputViewModel(
        events=events,
        sync_result=plan.sync_result,
        sync_error_message=plan.sync_error_message,
    )


def render_launch_output(
    view_model: LaunchOutputViewModel,
    *,
    console: Console,
    json_mode: bool,
) -> None:
    """Render launch output events at the CLI edge.

    Args:
        view_model: Launch output view model.
        console: Console for rendering.
        json_mode: Whether JSON output is enabled (suppresses human output).
    """
    if json_mode:
        return
    if view_model.sync_error_message:
        panel = create_warning_panel(
            "Marketplace Sync Failed",
            view_model.sync_error_message,
            "Team plugins may not be available. Use --dry-run to diagnose.",
        )
        print_with_layout(console, panel, constrain=True)
        return
    if not view_model.events:
        return
    console.print()
    for event in view_model.events:
        if isinstance(event, LaunchWarningEvent):
            print_with_layout(console, f"[yellow]{event.message}[/yellow]")
        else:
            print_with_layout(console, f"[green]{event.message}[/green]")
    console.print()
