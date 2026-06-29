"""Characterization tests for launch command flows.

These tests capture current launch flow behavior and protect against accidental
changes during ownership cleanup.

Targets:
  - commands/launch/flow.py start(): CLI entrypoint
  - commands/launch/flow_interactive.py interactive_start(): wizard flow

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

import typer

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


class TestStartWizardFlowCompletion:
    """Characterize the wizard handoff to the shared prepared-launch completion owner."""

    def _patch_wizard_setup(
        self,
        *,
        tmp_path: Path,
        monkeypatch: Any,
    ) -> tuple[Any, MagicMock, MagicMock]:
        import scc_cli.commands.launch.flow_interactive as flow

        adapters = MagicMock()
        plan = MagicMock()
        plan.current_branch = "main"
        plan.resolver_result.is_mount_expanded = False
        dependencies = MagicMock()

        monkeypatch.setattr(flow.setup, "is_setup_needed", lambda: False)
        monkeypatch.setattr(flow.config, "load_user_config", lambda: {})
        monkeypatch.setattr(flow, "get_default_adapters", lambda: adapters)
        monkeypatch.setattr(
            flow,
            "interactive_start",
            lambda *args, **kwargs: (str(tmp_path), "platform", "demo", None),
        )
        monkeypatch.setattr(flow, "validate_and_resolve_workspace", lambda value: tmp_path)
        monkeypatch.setattr(
            flow,
            "prepare_workspace",
            lambda path, worktree_name, install_deps: tmp_path,
        )
        monkeypatch.setattr(flow, "_configure_team_settings", lambda *args, **kwargs: None)
        monkeypatch.setattr(flow.config, "is_standalone_mode", lambda: True)
        monkeypatch.setattr(flow.config, "get_selected_provider", lambda: "codex")
        monkeypatch.setattr(flow, "resolve_launch_provider", lambda **kwargs: ("codex", "explicit"))
        monkeypatch.setattr(
            flow,
            "collect_launch_readiness",
            lambda *args, **kwargs: MagicMock(launch_ready=True),
        )
        monkeypatch.setattr(
            flow,
            "prepare_live_start_plan",
            lambda *args, **kwargs: (dependencies, plan),
        )
        monkeypatch.setattr(flow, "build_sync_output_view_model", lambda plan: object())
        monkeypatch.setattr(flow, "render_launch_output", lambda *args, **kwargs: None)

        return flow, plan, dependencies

    def _run_with_completion(
        self,
        *,
        tmp_path: Path,
        monkeypatch: Any,
        decision: Any,
        message: str | None = None,
    ) -> tuple[Any, Any, Any, Any, Any]:
        from scc_cli.commands.launch.completion import PreparedLaunchCompletionResult

        flow, plan, dependencies = self._patch_wizard_setup(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
        )
        captured_request: dict[str, Any] = {}

        def complete_launch(request: Any, *, console: Any) -> PreparedLaunchCompletionResult:
            captured_request["request"] = request
            return PreparedLaunchCompletionResult(decision=decision, message=message)

        monkeypatch.setattr(flow, "complete_prepared_launch", complete_launch)

        return flow, flow.run_start_wizard_flow(), captured_request["request"], plan, dependencies

    def test_keep_existing_completion_returns_wizard_keep_existing(
        self,
        tmp_path: Path,
        monkeypatch: Any,
    ) -> None:
        from scc_cli.commands.launch.completion import PreparedLaunchCompletionDecision

        flow, result, request, plan, dependencies = self._run_with_completion(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            decision=PreparedLaunchCompletionDecision.KEPT_EXISTING,
            message="Kept existing sandbox",
        )
        assert result.decision is flow.StartWizardFlowDecision.KEPT_EXISTING
        assert result.message == "Kept existing sandbox"
        assert request.workspace_path == tmp_path
        assert request.team == "platform"
        assert request.session_name == "demo"
        assert request.current_branch == "main"
        assert request.provider_id == "codex"
        assert request.start_plan is plan
        assert request.dependencies is dependencies
        assert request.record_session is True
        assert request.is_resume is False
        assert request.json_mode is False
        assert request.non_interactive is False

    def test_cancelled_completion_returns_wizard_cancelled_and_prints_notice(
        self,
        tmp_path: Path,
        monkeypatch: Any,
        capfd: Any,
    ) -> None:
        from scc_cli.commands.launch.completion import PreparedLaunchCompletionDecision

        flow, result, _request, _plan, _dependencies = self._run_with_completion(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            decision=PreparedLaunchCompletionDecision.CANCELLED,
            message="Start cancelled",
        )

        captured = capfd.readouterr()
        assert result.decision is flow.StartWizardFlowDecision.CANCELLED
        assert result.message == "Start cancelled"
        assert "Cancelled." in captured.out + captured.err

    def test_launched_completion_returns_wizard_launched(
        self,
        tmp_path: Path,
        monkeypatch: Any,
    ) -> None:
        from scc_cli.commands.launch.completion import PreparedLaunchCompletionDecision

        flow, result, _request, _plan, _dependencies = self._run_with_completion(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            decision=PreparedLaunchCompletionDecision.LAUNCHED,
        )

        assert result.decision is flow.StartWizardFlowDecision.LAUNCHED
        assert result.message is None

    def test_launch_completion_records_then_finalizes_and_persists_provider(
        self,
        tmp_path: Path,
        monkeypatch: Any,
    ) -> None:
        import scc_cli.commands.launch.completion as completion
        from scc_cli.commands.launch.conflict_resolution import (
            LaunchConflictDecision,
            LaunchConflictResolution,
        )

        flow, plan, dependencies = self._patch_wizard_setup(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
        )
        call_order: list[str] = []
        mock_resolve_conflict = MagicMock(
            return_value=LaunchConflictResolution(
                decision=LaunchConflictDecision.PROCEED,
                plan=plan,
            )
        )
        mock_record = MagicMock(side_effect=lambda *args, **kwargs: call_order.append("record"))
        mock_show_panel = MagicMock(side_effect=lambda *args, **kwargs: call_order.append("panel"))
        mock_finalize = MagicMock(side_effect=lambda *args, **kwargs: call_order.append("finalize"))
        mock_persist = MagicMock(side_effect=lambda *args, **kwargs: call_order.append("persist"))
        monkeypatch.setattr(
            completion.conflict_resolution,
            "resolve_launch_conflict",
            mock_resolve_conflict,
        )
        monkeypatch.setattr(
            completion.flow_session,
            "_record_session_and_context",
            mock_record,
        )
        monkeypatch.setattr(completion.render, "show_launch_panel", mock_show_panel)
        monkeypatch.setattr(completion.app_launch, "finalize_launch", mock_finalize)
        monkeypatch.setattr(
            completion.workspace_local_config,
            "set_workspace_last_used_provider",
            mock_persist,
        )

        result = flow.run_start_wizard_flow()

        assert result.decision is flow.StartWizardFlowDecision.LAUNCHED
        assert call_order == ["record", "panel", "finalize", "persist"]
        mock_record.assert_called_once_with(
            tmp_path,
            "platform",
            "demo",
            "main",
            provider_id="codex",
        )
        mock_finalize.assert_called_once_with(plan, dependencies=dependencies)
        mock_persist.assert_called_once_with(tmp_path, "codex")


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
            "scc_cli.commands.launch.flow_session._resolve_session_selection",
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
        from scc_cli.commands.launch.flow_session import _resolve_session_selection

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

    @patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=False)
    def test_non_interactive_auto_detects_workspace(self, mock_gate: MagicMock) -> None:
        """Non-interactive start uses resolver auto-detection before failing."""
        from scc_cli.commands.launch.flow_session import _resolve_session_selection

        mock_session_svc = MagicMock()

        with patch("scc_cli.application.workspace.resolve_workspace") as mock_resolve:
            mock_resolve.return_value = MagicMock(workspace_root=Path("/auto/detected"))

            result = _resolve_session_selection(
                workspace=None,
                team="platform",
                resume=False,
                select=False,
                cfg={},
                json_mode=False,
                standalone_override=False,
                no_interactive=True,
                dry_run=False,
                session_service=mock_session_svc,
            )

        workspace, team, session_name, worktree_name, cancelled, was_auto, session_provider = result
        assert workspace == "/auto/detected"
        assert team == "platform"
        assert cancelled is False
        assert was_auto is True
        assert session_provider is None
        mock_gate.assert_called_once_with(json_mode=False, no_interactive_flag=True)

    @patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=False)
    def test_non_interactive_no_auto_detect_exits_usage(self, mock_gate: MagicMock) -> None:
        """Non-interactive start exits usage when no workspace can be detected."""
        from scc_cli.commands.launch.flow_session import _resolve_session_selection

        mock_session_svc = MagicMock()

        with patch("scc_cli.application.workspace.resolve_workspace", return_value=None):
            try:
                _resolve_session_selection(
                    workspace=None,
                    team=None,
                    resume=False,
                    select=False,
                    cfg={},
                    json_mode=False,
                    standalone_override=False,
                    no_interactive=True,
                    dry_run=False,
                    session_service=mock_session_svc,
                )
            except typer.Exit as exc:
                assert exc.exit_code == EXIT_USAGE
            else:
                raise AssertionError("expected typer.Exit")

        mock_gate.assert_called_once_with(json_mode=False, no_interactive_flag=True)

    def test_explicit_workspace_passthrough(self) -> None:
        """Explicit workspace arg passes through without session selection."""
        from scc_cli.commands.launch.flow_session import _resolve_session_selection

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
        from scc_cli.commands.launch.flow_session import _resolve_session_selection

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
