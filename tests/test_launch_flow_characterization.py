"""Characterization tests for commands/launch/flow.py.

These tests capture the current behavior of the launch flow module
before S02 surgery decomposes it. They protect against accidental behavior
changes during the split.

Target: src/scc_cli/commands/launch/flow.py
  - start() (293 lines): CLI entrypoint
  - interactive_start() (534 lines): wizard flow

Since both functions are deeply coupled to TTY interactions, Rich UI, and
the full bootstrap stack, we test the pure logic they delegate to:
  - _resolve_session_selection early-return paths (mocked dependencies)
  - Application-layer wizard state machine (initialize/apply/step)
  - start() CLI integration via typer test runner (key error paths)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from scc_cli.application.launch import (
    BackRequested,
    QuickResumeDismissed,
    SessionNameEntered,
    StartWizardConfig,
    StartWizardStep,
    TeamSelected,
    WorkspaceSelected,
    WorkspaceSourceChosen,
    WorktreeSelected,
    apply_start_wizard_event,
    initialize_start_wizard,
)
from scc_cli.core.exit_codes import EXIT_CANCELLED, EXIT_CONFIG, EXIT_USAGE
from scc_cli.ui.wizard import WorkspaceSource

# ═══════════════════════════════════════════════════════════════════════════════
# Wizard State Machine (application layer)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartWizardStateMachine:
    """Characterize the start wizard state transitions that interactive_start delegates to."""

    def test_initialize_with_quick_resume_starts_there(self) -> None:
        """When quick_resume_enabled, wizard starts at QUICK_RESUME step."""
        config = StartWizardConfig(
            quick_resume_enabled=True,
            team_selection_required=False,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        assert state.step is StartWizardStep.QUICK_RESUME

    def test_initialize_without_quick_resume_starts_at_team(self) -> None:
        """When quick_resume disabled but team required, starts at TEAM_SELECTION."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=True,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        assert state.step is StartWizardStep.TEAM_SELECTION

    def test_initialize_no_resume_no_team_goes_to_workspace(self) -> None:
        """When both quick_resume and team_selection disabled, goes to WORKSPACE_SOURCE."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=False,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        assert state.step is StartWizardStep.WORKSPACE_SOURCE

    def test_quick_resume_dismissed_advances_to_team_or_workspace(self) -> None:
        """Dismissing quick resume moves forward."""
        config = StartWizardConfig(
            quick_resume_enabled=True,
            team_selection_required=True,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(state, QuickResumeDismissed())
        assert state.step is StartWizardStep.TEAM_SELECTION

    def test_team_selected_advances_to_workspace_source(self) -> None:
        """After team selection, wizard advances to workspace source step."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=True,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(state, TeamSelected(team="my-team"))
        assert state.step is StartWizardStep.WORKSPACE_SOURCE
        assert state.context.team == "my-team"

    def test_team_selected_none_in_standalone(self) -> None:
        """Standalone mode: TeamSelected(team=None) still advances."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=True,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(state, TeamSelected(team=None))
        assert state.step is StartWizardStep.WORKSPACE_SOURCE
        assert state.context.team is None

    def test_workspace_source_chosen_advances_to_picker(self) -> None:
        """Choosing a workspace source advances to WORKSPACE_PICKER."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=False,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(
            state, WorkspaceSourceChosen(source=WorkspaceSource.RECENT)
        )
        assert state.step is StartWizardStep.WORKSPACE_PICKER

    def test_back_from_workspace_source_returns_to_team(self) -> None:
        """BackRequested from WORKSPACE_SOURCE → back to TEAM_SELECTION if team was required."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=True,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(state, TeamSelected(team="t"))
        assert state.step is StartWizardStep.WORKSPACE_SOURCE
        state = apply_start_wizard_event(state, BackRequested())
        assert state.step is StartWizardStep.TEAM_SELECTION

    def test_workspace_selected_advances_to_worktree_decision(self) -> None:
        """WorkspaceSelected in WORKSPACE_PICKER → WORKTREE_DECISION step."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=False,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(
            state, WorkspaceSourceChosen(source=WorkspaceSource.RECENT)
        )
        assert state.step is StartWizardStep.WORKSPACE_PICKER
        state = apply_start_wizard_event(state, WorkspaceSelected(workspace="/my/proj"))
        assert state.step is StartWizardStep.WORKTREE_DECISION
        assert state.context.workspace == "/my/proj"

    def test_worktree_selected_advances_to_session_name(self) -> None:
        """WorktreeSelected in WORKTREE_DECISION → SESSION_NAME step."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=False,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(
            state, WorkspaceSourceChosen(source=WorkspaceSource.RECENT)
        )
        state = apply_start_wizard_event(state, WorkspaceSelected(workspace="/proj"))
        state = apply_start_wizard_event(state, WorktreeSelected(worktree_name=None))
        assert state.step is StartWizardStep.SESSION_NAME

    def test_session_name_entered_completes_wizard(self) -> None:
        """SessionNameEntered → COMPLETE step."""
        config = StartWizardConfig(
            quick_resume_enabled=False,
            team_selection_required=False,
            allow_back=False,
        )
        state = initialize_start_wizard(config)
        state = apply_start_wizard_event(
            state, WorkspaceSourceChosen(source=WorkspaceSource.RECENT)
        )
        state = apply_start_wizard_event(state, WorkspaceSelected(workspace="/proj"))
        state = apply_start_wizard_event(state, WorktreeSelected(worktree_name=None))
        state = apply_start_wizard_event(state, SessionNameEntered(session_name="my-session"))
        assert state.step is StartWizardStep.COMPLETE
        assert state.context.session_name == "my-session"


# ═══════════════════════════════════════════════════════════════════════════════
# start() CLI error paths (via typer test runner)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartCLIErrorPaths:
    """Characterize start() early-exit behavior via CLI invocation."""

    def test_debug_flag_after_command_shows_usage_error(self, cli_runner: Any, app: Any) -> None:
        """Passing --debug after 'start' shows helpful error about global flag placement."""
        result = cli_runner.invoke(app, ["start", "--debug"])
        assert result.exit_code == EXIT_USAGE

    @patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value=None)
    def test_offline_without_cache_exits_config_error(
        self,
        mock_cache: MagicMock,
        cli_runner: Any,
        app: Any,
    ) -> None:
        """--offline without cached org config exits with EXIT_CONFIG."""
        result = cli_runner.invoke(app, ["start", "--offline"])
        assert result.exit_code == EXIT_CONFIG

    @patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False)
    @patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={})
    @patch("scc_cli.commands.launch.flow.get_default_adapters")
    @patch("scc_cli.commands.launch.flow.sessions.get_session_service")
    @patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=False)
    @patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=True)
    def test_non_interactive_no_workspace_dry_run_resolves_or_errors(
        self,
        mock_standalone: MagicMock,
        mock_interactive: MagicMock,
        mock_session_svc: MagicMock,
        mock_adapters: MagicMock,
        mock_cfg: MagicMock,
        mock_setup: MagicMock,
        cli_runner: Any,
        app: Any,
    ) -> None:
        """--standalone --dry-run without workspace tries auto-detect → exits with usage error if not in a git repo."""
        with patch(
            "scc_cli.commands.launch.flow._resolve_session_selection",
            return_value=(None, None, None, None, False, False, None),
        ):
            result = cli_runner.invoke(app, ["start", "--standalone", "--dry-run"])
            # No workspace resolved → EXIT_USAGE or EXIT_CANCELLED
            assert result.exit_code in {EXIT_USAGE, EXIT_CANCELLED}


# ═══════════════════════════════════════════════════════════════════════════════
# _resolve_session_selection logic (unit-level)
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveSessionSelection:
    """Characterize _resolve_session_selection return structure."""

    @patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=False)
    def test_dry_run_auto_detects_workspace(self, mock_gate: MagicMock) -> None:
        """--dry-run without workspace tries resolve_workspace auto-detection."""
        from scc_cli.commands.launch.flow import _resolve_session_selection

        mock_session_svc = MagicMock()

        with patch("scc_cli.application.workspace.resolve_workspace") as mock_resolve:
            mock_resolve.return_value = MagicMock(workspace_root=Path("/auto/detected"))

            result = _resolve_session_selection(
                workspace=None,
                team=None,
                resume=False,
                select=False,
                cfg={},
                json_mode=False,
                standalone_override=False,
                no_interactive=True,
                dry_run=True,
                session_service=mock_session_svc,
            )
            workspace, team, session_name, worktree_name, cancelled, was_auto, session_provider = (
                result
            )
            assert workspace == "/auto/detected"
            assert was_auto is True
            assert cancelled is False
            assert session_provider is None

    def test_explicit_workspace_passthrough(self) -> None:
        """Explicit workspace arg passes through without session selection."""
        from scc_cli.commands.launch.flow import _resolve_session_selection

        mock_session_svc = MagicMock()

        result = _resolve_session_selection(
            workspace="/my/project",
            team="my-team",
            resume=False,
            select=False,
            cfg={},
            json_mode=False,
            standalone_override=False,
            no_interactive=False,
            dry_run=False,
            session_service=mock_session_svc,
        )
        workspace, team, session_name, worktree_name, cancelled, was_auto, session_provider = result
        assert workspace == "/my/project"
        assert team == "my-team"
        assert cancelled is False
        assert was_auto is False
        assert session_provider is None

    @patch("scc_cli.commands.launch.flow_session.select_session")
    def test_resume_no_active_team_returns_none(self, mock_select: MagicMock) -> None:
        """--resume with no team and no selected_profile → returns None workspace."""
        from scc_cli.commands.launch.flow import _resolve_session_selection

        mock_session_svc = MagicMock()

        result = _resolve_session_selection(
            workspace=None,
            team=None,
            resume=True,
            select=False,
            cfg={},
            json_mode=False,
            standalone_override=False,
            no_interactive=False,
            dry_run=False,
            session_service=mock_session_svc,
        )
        workspace, team, session_name, worktree_name, cancelled, was_auto, session_provider = result
        assert workspace is None
        assert cancelled is False
        assert session_provider is None
