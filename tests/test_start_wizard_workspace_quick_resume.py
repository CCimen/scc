"""Characterization tests for workspace-scoped quick resume flows."""

from pathlib import Path
from unittest.mock import patch

from scc_cli.contexts import WorkContext
from scc_cli.ui.picker import QuickResumeResult
from scc_cli.ui.wizard import WorkspaceSource


def test_workspace_quick_resume_returns_selected_context() -> None:
    from scc_cli.commands.launch import interactive_start

    context = WorkContext(
        team="alpha",
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
        last_session_id="session-1",
    )

    with (
        patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=False),
        patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value={}),
        patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
        patch("scc_cli.commands.launch.flow.teams.list_teams", return_value=[]),
        patch("scc_cli.commands.launch.flow.load_recent_contexts", return_value=[context]),
        patch(
            "scc_cli.ui.wizard.pick_context_quick_resume",
            side_effect=[
                (QuickResumeResult.NEW_SESSION, None),
                (QuickResumeResult.SELECTED, context),
            ],
        ),
        patch("scc_cli.ui.wizard._run_single_select_picker", return_value=WorkspaceSource.RECENT),
        patch(
            "scc_cli.ui.wizard.pick_recent_workspace",
            return_value=str(context.worktree_path),
        ),
        patch("scc_cli.ui.wizard.confirm_with_layout", return_value=True),
    ):
        result = interactive_start(cfg={"selected_profile": "alpha"}, allow_back=False)

    assert result == (
        str(context.worktree_path),
        context.team,
        context.last_session_id,
        None,
    )


def test_workspace_quick_resume_new_session_keeps_workspace() -> None:
    from scc_cli.commands.launch import interactive_start

    context = WorkContext(
        team="alpha",
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
        last_session_id="session-1",
    )

    with (
        patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=False),
        patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value={}),
        patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
        patch("scc_cli.commands.launch.flow.teams.list_teams", return_value=[]),
        patch("scc_cli.commands.launch.flow.load_recent_contexts", return_value=[context]),
        patch(
            "scc_cli.ui.wizard.pick_context_quick_resume",
            side_effect=[
                (QuickResumeResult.NEW_SESSION, None),
                (QuickResumeResult.NEW_SESSION, None),
            ],
        ),
        patch("scc_cli.ui.wizard._run_single_select_picker", return_value=WorkspaceSource.RECENT),
        patch(
            "scc_cli.ui.wizard.pick_recent_workspace",
            return_value=str(context.worktree_path),
        ),
        patch("scc_cli.ui.wizard.confirm_with_layout", return_value=False),
        patch("scc_cli.ui.wizard.prompt_with_layout", return_value=None),
    ):
        result = interactive_start(cfg={"selected_profile": "alpha"}, allow_back=False)

    assert result == (
        str(context.worktree_path),
        "alpha",
        None,
        None,
    )
