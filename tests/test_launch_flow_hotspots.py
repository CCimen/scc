"""Guardrail tests for launch-flow resume hotspot extraction."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scc_cli.application.launch import (
    StartWizardConfig,
    StartWizardContext,
    StartWizardState,
    StartWizardStep,
)
from scc_cli.commands.launch.flow_types import WizardResumeContext
from scc_cli.contexts import WorkContext
from scc_cli.ui.wizard import (
    StartWizardAction,
    StartWizardAnswer,
    StartWizardAnswerKind,
    WorkspaceSource,
)

FLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "scc_cli"
    / "commands"
    / "launch"
    / "flow_interactive.py"
)
MAX_INTERACTIVE_START_LINES = 550


def _interactive_start_node() -> ast.FunctionDef:
    tree = ast.parse(FLOW_PATH.read_text(encoding="utf-8"), filename=str(FLOW_PATH))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "interactive_start":
            return node
    raise AssertionError("interactive_start not found")


def _resume_context(
    *,
    standalone_mode: bool = False,
    allow_back: bool = False,
    effective_team: str | None = None,
    team_override: str | None = None,
) -> WizardResumeContext:
    return WizardResumeContext(
        standalone_mode=standalone_mode,
        allow_back=allow_back,
        effective_team=effective_team,
        team_override=team_override,
        active_team_label=effective_team or "standalone",
        active_team_context=f"Team: {effective_team or 'standalone'}",
        current_branch=None,
    )


def test_interactive_start_resume_hotspot_stays_extracted() -> None:
    """interactive_start should delegate resume branches instead of inlining them again."""
    node = _interactive_start_node()
    line_count = (node.end_lineno or 0) - node.lineno + 1
    nested_functions = sorted(
        child.name
        for child in ast.walk(node)
        if isinstance(child, ast.FunctionDef) and child is not node
    )

    assert line_count <= MAX_INTERACTIVE_START_LINES
    assert nested_functions == []


def test_handle_top_level_quick_resume_rejects_non_context_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed quick-resume answers should fail loudly in the extracted helper."""
    import scc_cli.commands.launch.wizard_resume as wizard_resume
    from scc_cli.application.launch import initialize_start_wizard

    context = WorkContext(
        team=None,
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
    )
    state = initialize_start_wizard(
        StartWizardConfig(
            quick_resume_enabled=True,
            team_selection_required=False,
            allow_back=False,
        )
    )
    monkeypatch.setattr(wizard_resume, "load_recent_contexts", lambda *args, **kwargs: [context])
    monkeypatch.setattr(
        wizard_resume,
        "render_start_wizard_prompt",
        lambda *args, **kwargs: StartWizardAnswer(
            kind=StartWizardAnswerKind.SELECTED,
            value="not-a-context",
        ),
    )

    with pytest.raises(wizard_resume.ResumeWizardError):
        wizard_resume.handle_top_level_quick_resume(
            state,
            render_context=_resume_context(standalone_mode=True),
            show_all_teams=False,
        )


def test_prompt_workspace_quick_resume_rejects_non_boolean_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cross-team confirmation must stay boolean so helpers cannot take the wrong branch."""
    import scc_cli.commands.launch.wizard_resume as wizard_resume

    context = WorkContext(
        team="alpha",
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
        last_session_id="session-1",
    )
    answers = iter(
        [
            StartWizardAnswer(kind=StartWizardAnswerKind.SELECTED, value=context),
            StartWizardAnswer(kind=StartWizardAnswerKind.SELECTED, value="yes"),
        ]
    )
    monkeypatch.setattr(wizard_resume, "load_recent_contexts", lambda *args, **kwargs: [context])
    monkeypatch.setattr(
        wizard_resume,
        "render_start_wizard_prompt",
        lambda *args, **kwargs: next(answers),
    )

    with pytest.raises(wizard_resume.ResumeWizardError):
        wizard_resume.prompt_workspace_quick_resume(
            "/repo",
            team="beta",
            render_context=_resume_context(effective_team="beta"),
        )


def test_resolve_workspace_resume_back_returns_to_workspace_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workspace quick-resume back-navigation should leave the picker step active."""
    import scc_cli.commands.launch.wizard_resume as wizard_resume

    state = StartWizardState(
        step=StartWizardStep.WORKSPACE_PICKER,
        context=StartWizardContext(team="alpha", workspace_source=WorkspaceSource.RECENT),
        config=StartWizardConfig(
            quick_resume_enabled=True,
            team_selection_required=True,
            allow_back=False,
        ),
    )
    monkeypatch.setattr(
        wizard_resume,
        "prompt_workspace_quick_resume",
        lambda *args, **kwargs: StartWizardAnswer(kind=StartWizardAnswerKind.BACK),
    )

    resolution, show_all_teams = wizard_resume.resolve_workspace_resume(
        state,
        "/repo",
        workspace_source=WorkspaceSource.RECENT,
        render_context=_resume_context(effective_team="alpha"),
        show_all_teams=False,
    )

    assert resolution is None
    assert show_all_teams is False


def test_resolve_workspace_resume_switch_team_resets_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Team-switch from workspace quick resume should clear workspace state and filters."""
    import scc_cli.commands.launch.wizard_resume as wizard_resume

    state = StartWizardState(
        step=StartWizardStep.WORKSPACE_PICKER,
        context=StartWizardContext(
            team="alpha",
            workspace_source=WorkspaceSource.RECENT,
            workspace="/repo",
        ),
        config=StartWizardConfig(
            quick_resume_enabled=True,
            team_selection_required=True,
            allow_back=False,
        ),
    )
    monkeypatch.setattr(
        wizard_resume,
        "prompt_workspace_quick_resume",
        lambda *args, **kwargs: StartWizardAnswer(
            kind=StartWizardAnswerKind.SELECTED,
            value=StartWizardAction.SWITCH_TEAM,
        ),
    )

    resolution, show_all_teams = wizard_resume.resolve_workspace_resume(
        state,
        "/repo",
        workspace_source=WorkspaceSource.RECENT,
        render_context=_resume_context(effective_team="alpha"),
        show_all_teams=True,
    )

    assert isinstance(resolution, StartWizardState)
    assert resolution.step is StartWizardStep.TEAM_SELECTION
    assert resolution.context.team is None
    assert resolution.context.workspace is None
    assert show_all_teams is False
