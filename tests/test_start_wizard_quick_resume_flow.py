"""Characterization tests for quick resume wizard flows."""

from pathlib import Path
from unittest.mock import patch

from scc_cli.contexts import WorkContext
from scc_cli.ui.picker import QuickResumeResult


def test_quick_resume_new_session_moves_to_workspace_source() -> None:
    from scc_cli.commands.launch import interactive_start
    from scc_cli.ui.wizard import WorkspaceSource

    with (
        patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=True),
        patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value={}),
        patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
        patch("scc_cli.commands.launch.flow.teams.list_teams", return_value=[]),
        patch("scc_cli.commands.launch.flow.load_recent_contexts", return_value=[]),
        patch(
            "scc_cli.ui.wizard.pick_context_quick_resume",
            return_value=(QuickResumeResult.NEW_SESSION, None),
        ),
        patch("scc_cli.ui.wizard.pick_workspace_source", return_value=WorkspaceSource.RECENT),
        patch("scc_cli.ui.wizard.pick_recent_workspace", return_value="/repo"),
        patch("scc_cli.ui.wizard.confirm_with_layout", return_value=False),
        patch("scc_cli.ui.wizard.prompt_with_layout", return_value=None),
    ):
        result = interactive_start(cfg={}, allow_back=False)

    assert result == ("/repo", None, None, None)


def test_quick_resume_back_returns_cancelled() -> None:
    from scc_cli.commands.launch import interactive_start

    with (
        patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=True),
        patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value={}),
        patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
        patch("scc_cli.commands.launch.flow.teams.list_teams", return_value=[]),
        patch("scc_cli.commands.launch.flow.load_recent_contexts", return_value=[]),
        patch(
            "scc_cli.ui.wizard.pick_context_quick_resume",
            return_value=(QuickResumeResult.BACK, None),
        ),
    ):
        result = interactive_start(cfg={}, allow_back=False)

    assert result == (None, None, None, None)


def test_quick_resume_selects_context_returns_immediately() -> None:
    from scc_cli.commands.launch import interactive_start

    context = WorkContext(
        team=None,
        repo_root=Path("/repo"),
        worktree_path=Path("/repo"),
        worktree_name="main",
        last_session_id="session-1",
    )

    with (
        patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=True),
        patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value={}),
        patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
        patch("scc_cli.commands.launch.flow.teams.list_teams", return_value=[]),
        patch("scc_cli.commands.launch.flow.load_recent_contexts", return_value=[context]),
        patch(
            "scc_cli.ui.wizard.pick_context_quick_resume",
            return_value=(QuickResumeResult.SELECTED, context),
        ),
        patch("scc_cli.ui.wizard.confirm_with_layout", return_value=True) as confirm,
    ):
        result = interactive_start(cfg={}, allow_back=False)

    assert confirm.call_args is None

    assert result == (
        str(context.worktree_path),
        context.team,
        context.last_session_id,
        None,
    )
