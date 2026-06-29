"""Session resolution and personal profile helpers for the launch flow.

Extracted from flow.py to reduce module size. Contains:
- _resolve_session_selection: handles --select, --resume, and interactive entry
- _apply_personal_profile / _build_personal_profile_request / _render_*
- _prompt_for_session_selection
- _record_session_and_context
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypeAlias, cast

import typer

from ... import config, sessions
from ...application.launch import (
    ApplyPersonalProfileConfirmation,
    ApplyPersonalProfileDependencies,
    ApplyPersonalProfileRequest,
    ApplyPersonalProfileResult,
    SelectSessionDependencies,
    SelectSessionRequest,
    SelectSessionResult,
    SessionSelectionItem,
    SessionSelectionMode,
    SessionSelectionPrompt,
    SessionSelectionWarningOutcome,
    apply_personal_profile,
    select_session,
)
from ...application.sessions import SessionService
from ...bootstrap import get_default_adapters
from ...cli_common import console, err_console
from ...contexts import WorkContext, record_context
from ...core.enums import TargetType
from ...core.exit_codes import EXIT_USAGE
from ...output_mode import print_human, print_json
from ...ports.personal_profile_service import PersonalProfileService
from ...presentation.json.profile_json import build_profile_apply_envelope
from ...services import git
from ...ui.chrome import print_with_layout
from ...ui.gate import is_interactive_allowed
from ...ui.picker import pick_session
from ...ui.prompts import confirm_with_layout

SessionSelectionResolution: TypeAlias = tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    bool,
    bool,
    str | None,
]


def _empty_session_resolution(team: str | None) -> SessionSelectionResolution:
    return None, team, None, None, False, False, None


def _cancelled_session_resolution(team: str | None) -> SessionSelectionResolution:
    return None, team, None, None, True, False, None


def _auto_detect_workspace(team: str | None) -> SessionSelectionResolution | None:
    from ...application.workspace import ResolveWorkspaceRequest, resolve_workspace

    context = resolve_workspace(ResolveWorkspaceRequest(cwd=Path.cwd(), workspace_arg=None))
    if context is None:
        return None
    return str(context.workspace_root), team, None, None, False, True, None


def _effective_session_team(
    *,
    team: str | None,
    cfg: dict[str, Any],
    standalone_override: bool,
) -> str | None:
    if standalone_override:
        return None
    return team or cast(str | None, cfg.get("selected_profile"))


def _render_missing_effective_team(command: str) -> None:
    console.print(
        "[yellow]No active team selected.[/yellow] "
        f"Run 'scc team switch' or pass --team to {command}."
    )


def _render_no_recent_sessions(*, json_mode: bool) -> None:
    if not json_mode:
        console.print("[yellow]No recent sessions found.[/yellow]")


def _session_result_resolution(
    outcome: SelectSessionResult,
    *,
    team: str | None,
    standalone_override: bool,
    json_mode: bool,
    label: str,
) -> SessionSelectionResolution:
    selected = outcome.session
    resolved_team = team or selected.team
    if standalone_override:
        resolved_team = None
    if not json_mode:
        print_with_layout(console, f"[dim]{label}: {selected.workspace}[/dim]")
    return selected.workspace, resolved_team, None, None, False, False, selected.provider_id


def _resolve_interactive_workspace_entry(
    cfg: dict[str, Any],
    *,
    team: str | None,
    json_mode: bool,
    standalone_override: bool,
    no_interactive: bool,
    dry_run: bool,
) -> SessionSelectionResolution:
    if dry_run:
        detected = _auto_detect_workspace(team)
        if detected is not None:
            return detected
        err_console.print(
            "[red]Error:[/red] No workspace could be auto-detected.\n"
            "[dim]Provide a workspace path: scc start --dry-run /path/to/project[/dim]",
            highlight=False,
        )
        raise typer.Exit(EXIT_USAGE)

    if not is_interactive_allowed(
        json_mode=json_mode,
        no_interactive_flag=no_interactive,
    ):
        detected = _auto_detect_workspace(team)
        if detected is not None:
            return detected

        err_console.print(
            "[red]Error:[/red] Interactive mode requires a terminal (TTY).\n"
            "[dim]Provide a workspace path: scc start /path/to/project[/dim]",
            highlight=False,
        )
        raise typer.Exit(EXIT_USAGE)

    from .flow_interactive import interactive_start

    adapters = get_default_adapters()
    workspace_result, team, session_name, worktree_name = cast(
        tuple[str | None, str | None, str | None, str | None],
        interactive_start(
            cfg,
            standalone_override=standalone_override,
            team_override=team,
            git_client=adapters.git_client,
        ),
    )
    if workspace_result is None:
        return _cancelled_session_resolution(team)
    return workspace_result, team, session_name, worktree_name, False, False, None


def _resolve_selected_session(
    cfg: dict[str, Any],
    *,
    team: str | None,
    json_mode: bool,
    standalone_override: bool,
    no_interactive: bool,
    dependencies: SelectSessionDependencies,
) -> SessionSelectionResolution:
    if not is_interactive_allowed(
        json_mode=json_mode,
        no_interactive_flag=no_interactive,
    ):
        console.print(
            "[red]Error:[/red] --select requires a terminal (TTY).\n"
            "[dim]Use --resume to auto-select most recent session.[/dim]",
            highlight=False,
        )
        raise typer.Exit(EXIT_USAGE)

    effective_team = _effective_session_team(
        team=team,
        cfg=cfg,
        standalone_override=standalone_override,
    )
    if effective_team is None and not standalone_override:
        if not json_mode:
            _render_missing_effective_team("select")
        return _empty_session_resolution(team)

    outcome = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.SELECT,
            team=effective_team,
            include_all=False,
            limit=10,
        ),
        dependencies=dependencies,
    )

    if isinstance(outcome, SessionSelectionWarningOutcome):
        _render_no_recent_sessions(json_mode=json_mode)
        return _empty_session_resolution(team)

    if isinstance(outcome, SessionSelectionPrompt):
        selected_item = _prompt_for_session_selection(outcome)
        if selected_item is None:
            return _cancelled_session_resolution(team)
        outcome = select_session(
            SelectSessionRequest(
                mode=SessionSelectionMode.SELECT,
                team=effective_team,
                include_all=False,
                limit=10,
                selection=selected_item,
            ),
            dependencies=dependencies,
        )

    if isinstance(outcome, SelectSessionResult):
        return _session_result_resolution(
            outcome,
            team=team,
            standalone_override=standalone_override,
            json_mode=json_mode,
            label="Selected",
        )

    return _empty_session_resolution(team)


def _resolve_resumed_session(
    cfg: dict[str, Any],
    *,
    team: str | None,
    json_mode: bool,
    standalone_override: bool,
    dependencies: SelectSessionDependencies,
) -> SessionSelectionResolution:
    effective_team = _effective_session_team(
        team=team,
        cfg=cfg,
        standalone_override=standalone_override,
    )
    if effective_team is None and not standalone_override:
        if not json_mode:
            _render_missing_effective_team("resume")
        return _empty_session_resolution(team)

    outcome = select_session(
        SelectSessionRequest(
            mode=SessionSelectionMode.RESUME,
            team=effective_team,
            include_all=False,
            limit=50,
        ),
        dependencies=dependencies,
    )

    if isinstance(outcome, SessionSelectionWarningOutcome):
        _render_no_recent_sessions(json_mode=json_mode)
        return _empty_session_resolution(team)

    if isinstance(outcome, SelectSessionResult):
        return _session_result_resolution(
            outcome,
            team=team,
            standalone_override=standalone_override,
            json_mode=json_mode,
            label="Resuming",
        )

    return _empty_session_resolution(team)


def _resolve_session_selection(
    workspace: str | None,
    team: str | None,
    resume: bool,
    select: bool,
    cfg: dict[str, Any],
    *,
    json_mode: bool = False,
    standalone_override: bool = False,
    no_interactive: bool = False,
    dry_run: bool = False,
    session_service: SessionService,
) -> SessionSelectionResolution:
    """Handle session selection logic for --select, --resume, and interactive modes.

    Returns:
        Tuple of (
            workspace,
            team,
            session_name,
            worktree_name,
            cancelled,
            was_auto_detected,
            session_provider_id,
        )
    """
    select_dependencies = SelectSessionDependencies(session_service=session_service)

    if workspace is None and not resume and not select:
        return _resolve_interactive_workspace_entry(
            cfg,
            team=team,
            json_mode=json_mode,
            standalone_override=standalone_override,
            no_interactive=no_interactive,
            dry_run=dry_run,
        )

    if select and workspace is None:
        return _resolve_selected_session(
            cfg,
            team=team,
            json_mode=json_mode,
            standalone_override=standalone_override,
            no_interactive=no_interactive,
            dependencies=select_dependencies,
        )

    if resume and workspace is None:
        return _resolve_resumed_session(
            cfg,
            team=team,
            json_mode=json_mode,
            standalone_override=standalone_override,
            dependencies=select_dependencies,
        )

    return workspace, team, None, None, False, False, None


def _apply_personal_profile(
    workspace_path: Path,
    *,
    org_config: dict[str, Any] | None,
    json_mode: bool,
    non_interactive: bool,
    profile_service: PersonalProfileService,
) -> tuple[str | None, bool]:
    """Apply personal profile if available.

    Returns (profile_id, applied).
    """
    request = _build_personal_profile_request(
        workspace_path,
        json_mode=json_mode,
        non_interactive=non_interactive,
        confirm_apply=None,
        org_config=org_config,
    )
    dependencies = ApplyPersonalProfileDependencies(profile_service=profile_service)

    while True:
        outcome = apply_personal_profile(request, dependencies=dependencies)
        if isinstance(outcome, ApplyPersonalProfileConfirmation):
            _render_personal_profile_confirmation(outcome, json_mode=json_mode)
            confirm = confirm_with_layout(
                console,
                outcome.request.prompt,
                default=outcome.default_response,
            )
            request = _build_personal_profile_request(
                workspace_path,
                json_mode=json_mode,
                non_interactive=non_interactive,
                confirm_apply=confirm,
                org_config=org_config,
            )
            continue

        if isinstance(outcome, ApplyPersonalProfileResult):
            _render_personal_profile_result(outcome, json_mode=json_mode)
            return outcome.profile_id, outcome.applied

        return None, False


def _build_personal_profile_request(
    workspace_path: Path,
    *,
    json_mode: bool,
    non_interactive: bool,
    confirm_apply: bool | None,
    org_config: dict[str, Any] | None,
) -> ApplyPersonalProfileRequest:
    return ApplyPersonalProfileRequest(
        workspace_path=workspace_path,
        interactive_allowed=is_interactive_allowed(
            json_mode=json_mode,
            no_interactive_flag=non_interactive,
        ),
        confirm_apply=confirm_apply,
        org_config=org_config,
    )


def _render_personal_profile_confirmation(
    outcome: ApplyPersonalProfileConfirmation, *, json_mode: bool
) -> None:
    if json_mode:
        return
    if outcome.message:
        console.print(outcome.message)


def _render_personal_profile_result(
    outcome: ApplyPersonalProfileResult, *, json_mode: bool
) -> None:
    if json_mode:
        envelope = build_profile_apply_envelope(outcome)
        print_json(envelope)
        return
    if outcome.skipped_items:
        for skipped in outcome.skipped_items:
            label = "plugin" if skipped.target_type == TargetType.PLUGIN else "MCP server"
            console.print(f"[yellow]Skipped {label} '{skipped.item}': {skipped.reason}[/yellow]")
    if outcome.message:
        console.print(outcome.message)


def _prompt_for_session_selection(prompt: SessionSelectionPrompt) -> SessionSelectionItem | None:
    items = [option.value for option in prompt.request.options if option.value is not None]
    if not items:
        return None
    summaries = [item.summary for item in items]
    selected = pick_session(
        summaries,
        title=prompt.request.title,
        subtitle=prompt.request.subtitle,
    )
    if selected is None:
        return None
    try:
        index = summaries.index(selected)
    except ValueError:
        return None
    return items[index]


def _record_session_and_context(
    workspace_path: Path,
    team: str | None,
    session_name: str | None,
    current_branch: str | None,
    provider_id: str | None = None,
) -> None:
    """Record session metadata and quick-resume context."""
    sessions.record_session(
        workspace=str(workspace_path),
        team=team,
        session_name=session_name,
        container_name=None,
        branch=current_branch,
        provider_id=provider_id,
    )
    repo_root = git.get_worktree_main_repo(workspace_path) or workspace_path
    worktree_name = workspace_path.name
    context = WorkContext(
        team=team,
        repo_root=repo_root,
        worktree_path=workspace_path,
        worktree_name=worktree_name,
        branch=current_branch,
        last_session_id=session_name,
        provider_id=provider_id,
    )
    try:
        record_context(context)
    except (OSError, ValueError) as exc:
        print_human(
            "[yellow]Warning:[/yellow] Could not save Quick Resume context.",
            highlight=False,
        )
        print_human(f"[dim]{exc}[/dim]", highlight=False)
        logging.debug(f"Failed to record context for Quick Resume: {exc}")
    if team:
        try:
            config.set_workspace_team(str(workspace_path), team)
        except (OSError, ValueError) as exc:
            print_human(
                "[yellow]Warning:[/yellow] Could not save workspace team preference.",
                highlight=False,
            )
            print_human(f"[dim]{exc}[/dim]", highlight=False)
            logging.debug(f"Failed to store workspace team mapping: {exc}")
