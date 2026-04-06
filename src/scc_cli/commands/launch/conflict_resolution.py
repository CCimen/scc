"""Interactive resolution for live sandbox launch conflicts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
from pathlib import Path

from rich.console import Console

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.core.errors import ExistingSandboxConflictError
from scc_cli.panels import create_info_panel, create_warning_panel
from scc_cli.ports.models import SandboxConflict
from scc_cli.ui.chrome import print_with_layout
from scc_cli.ui.gate import is_interactive_allowed
from scc_cli.ui.list_screen import ListItem, ListScreen


class LaunchConflictDecision(Enum):
    """User-facing resolution for an existing live sandbox."""

    PROCEED = auto()
    KEEP_EXISTING = auto()
    CANCELLED = auto()


@dataclass(frozen=True)
class LaunchConflictResolution:
    """Outcome from resolving a launch conflict."""

    decision: LaunchConflictDecision
    plan: StartSessionPlan
    conflict: SandboxConflict | None = None


class _ConflictAction(Enum):
    KEEP = auto()
    REPLACE = auto()
    CANCEL = auto()


def resolve_launch_conflict(
    plan: StartSessionPlan,
    *,
    dependencies: StartSessionDependencies,
    console: Console,
    display_name: str,
    json_mode: bool,
    non_interactive: bool,
) -> LaunchConflictResolution:
    """Resolve an already-running sandbox before launch-side effects begin."""
    sandbox_spec = plan.sandbox_spec
    if sandbox_spec is None:
        return LaunchConflictResolution(decision=LaunchConflictDecision.PROCEED, plan=plan)

    conflict = dependencies.sandbox_runtime.detect_launch_conflict(sandbox_spec)
    if conflict is None:
        return LaunchConflictResolution(decision=LaunchConflictDecision.PROCEED, plan=plan)

    container_name = conflict.handle.name or conflict.handle.sandbox_id
    if not is_interactive_allowed(
        json_mode=json_mode,
        no_interactive_flag=non_interactive,
    ):
        raise ExistingSandboxConflictError(
            container_name=container_name,
            suggested_action=(
                f"Use 'scc start --fresh' to replace it, 'scc stop {container_name}' "
                "to stop it, or retry in an interactive terminal to choose."
            ),
        )

    action = _prompt_for_conflict(
        console=console,
        conflict=conflict,
        display_name=display_name,
        workspace=plan.workspace_path,
    )
    if action is _ConflictAction.REPLACE:
        print_with_layout(
            console,
            "[dim]Replacing existing sandbox with a fresh launch...[/dim]",
        )
        refreshed_spec = replace(sandbox_spec, force_new=True)
        return LaunchConflictResolution(
            decision=LaunchConflictDecision.PROCEED,
            plan=replace(plan, sandbox_spec=refreshed_spec),
            conflict=conflict,
        )
    if action is _ConflictAction.KEEP:
        _render_keep_existing_message(
            console=console,
            display_name=display_name,
            container_name=container_name,
        )
        return LaunchConflictResolution(
            decision=LaunchConflictDecision.KEEP_EXISTING,
            plan=plan,
            conflict=conflict,
        )
    return LaunchConflictResolution(
        decision=LaunchConflictDecision.CANCELLED,
        plan=plan,
        conflict=conflict,
    )


def _prompt_for_conflict(
    *,
    console: Console,
    conflict: SandboxConflict,
    display_name: str,
    workspace: Path,
) -> _ConflictAction:
    """Prompt the user to resolve a live sandbox conflict."""
    container_name = conflict.handle.name or conflict.handle.sandbox_id
    details = [
        f"A {display_name} sandbox is already active for this workspace.",
        "",
        f"Workspace: {workspace}",
        f"Container: {container_name}",
    ]
    if conflict.process_summary:
        details.append(f"Active process: {conflict.process_summary}")
    details.append("")
    details.append("Replacing it will stop the running sandbox.")

    console.print()
    print_with_layout(
        console,
        create_warning_panel(
            "Existing Sandbox Found",
            "\n".join(details),
            "Choose whether to keep it, replace it, or cancel this start request.",
        ),
        constrain=True,
    )
    console.print()

    items = [
        ListItem(
            value=_ConflictAction.KEEP,
            label="Keep existing sandbox",
            description="Leave the running sandbox untouched and return to the shell.",
        ),
        ListItem(
            value=_ConflictAction.REPLACE,
            label="Replace existing sandbox",
            description="Stop the current sandbox and launch a fresh one here (--fresh).",
        ),
        ListItem(
            value=_ConflictAction.CANCEL,
            label="Cancel",
            description="Do nothing and exit this start request.",
        ),
    ]
    selection = ListScreen(items, title="Resolve Launch Conflict", viewport_height=6).run()
    if selection is None:
        return _ConflictAction.CANCEL
    if isinstance(selection, list):  # Defensive: SINGLE_SELECT should never return a list.
        return _ConflictAction.CANCEL
    return selection


def _render_keep_existing_message(
    *,
    console: Console,
    display_name: str,
    container_name: str,
) -> None:
    """Explain what 'keep existing' means and what to do next."""
    console.print()
    print_with_layout(
        console,
        create_info_panel(
            "Kept Existing Sandbox",
            f"Left the running {display_name} sandbox untouched:\n{container_name}",
            (
                f"Use 'scc start --fresh' to replace it, 'scc stop {container_name}' "
                "to stop it, or 'scc list -i' to inspect running sandboxes."
            ),
        ),
        constrain=True,
    )
    console.print()
