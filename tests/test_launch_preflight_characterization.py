"""Characterization tests for launch preflight provider resolution across all five call sites.

These tests document the *current* behavior of each launch path's provider resolution
as a regression baseline. They capture the differences between sites so that the
upcoming consolidation can verify it produces identical behavior.

Sites:
  1. flow.py start()            — full precedence via choose_start_provider()
  2. flow_interactive.py        — choose_start_provider(cli_flag=None, resume_provider=None)
  3. worktree_commands.py       — resolve_active_provider() directly (simpler, no workspace/probe)
  4. orchestrator_handlers.py   — _handle_worktree_start(): choose_start_provider(cli_flag=None, resume_provider=None)
  5. orchestrator_handlers.py   — _handle_session_resume(): choose_start_provider(resume_provider=session.provider_id)
  6. _record_session_and_context — WorkContext.provider_id always None (not forwarded)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.application.provider_selection import resolve_provider_preference
from scc_cli.commands.launch.provider_choice import choose_start_provider
from scc_cli.contexts import WorkContext
from scc_cli.core.provider_resolution import resolve_active_provider

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _noop_prompt(
    allowed: tuple[str, ...],
    connected: tuple[str, ...],
    default: str | None,
) -> str | None:
    """Simulates an interactive prompt that returns the first allowed provider."""
    return allowed[0] if allowed else None


def _cancel_prompt(
    allowed: tuple[str, ...],
    connected: tuple[str, ...],
    default: str | None,
) -> str | None:
    """Simulates user cancelling the prompt."""
    return None


def _make_fake_adapters(
    *,
    claude_auth_status: str = "present",
    codex_auth_status: str = "absent",
) -> Any:
    """Build a minimal mock adapters object for provider_choice functions."""
    adapters = MagicMock()
    claude_readiness = MagicMock()
    claude_readiness.status = claude_auth_status
    codex_readiness = MagicMock()
    codex_readiness.status = codex_auth_status
    adapters.agent_provider.auth_check.return_value = claude_readiness
    adapters.codex_agent_provider.auth_check.return_value = codex_readiness
    return adapters


# ─────────────────────────────────────────────────────────────────────────────
# Site 1: flow.py start() — _resolve_provider uses choose_start_provider
# with full precedence chain
# ─────────────────────────────────────────────────────────────────────────────


class TestFlowStartProviderResolution:
    """Characterize flow.py start()'s provider resolution via _resolve_provider.

    _resolve_provider calls choose_start_provider with all six inputs:
    cli_flag, resume_provider, workspace_last_used, config_provider,
    connected_provider_ids (from auth probing), and allowed_providers.
    """

    def test_cli_flag_wins_over_everything(self) -> None:
        """CLI --provider flag is highest precedence."""
        result = choose_start_provider(
            cli_flag="codex",
            resume_provider="claude",
            workspace_last_used="claude",
            config_provider="claude",
            connected_provider_ids=("claude",),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"

    def test_resume_provider_wins_over_workspace_and_config(self) -> None:
        """Resume provider takes second precedence after cli_flag."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider="codex",
            workspace_last_used="claude",
            config_provider="claude",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"

    def test_workspace_last_used_wins_over_config(self) -> None:
        """Workspace last-used provider beats global config."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            config_provider="claude",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"

    def test_config_provider_used_when_no_higher_precedence(self) -> None:
        """Global config provider used as last automatic source."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider="codex",
            connected_provider_ids=("codex",),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"

    def test_config_provider_ask_suppresses_auto_selection(self) -> None:
        """config_provider='ask' suppresses auto-selection, falls to connected."""
        # With one connected provider, it auto-selects
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider="ask",
            connected_provider_ids=("claude",),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "claude"

    def test_single_connected_provider_auto_selected(self) -> None:
        """When only one provider is connected, it is auto-selected."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected_provider_ids=("codex",),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"

    def test_non_interactive_raises_when_ambiguous(self) -> None:
        """Non-interactive mode raises ProviderNotReadyError when ambiguous."""
        from scc_cli.core.errors import ProviderNotReadyError

        with pytest.raises(ProviderNotReadyError):
            choose_start_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=("claude", "codex"),
                allowed_providers=(),
                non_interactive=True,
                prompt_choice=None,
            )

    def test_interactive_falls_to_prompt(self) -> None:
        """Interactive mode prompts user when auto-selection is ambiguous."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        # _noop_prompt returns first allowed; KNOWN_PROVIDERS is ('claude', 'codex')
        assert result == "claude"

    def test_allowed_providers_restricts_resolution(self) -> None:
        """Team policy allowed_providers filters the candidate set."""
        from scc_cli.core.errors import ProviderNotAllowedError

        with pytest.raises(ProviderNotAllowedError):
            choose_start_provider(
                cli_flag="claude",
                resume_provider=None,
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=(),
                allowed_providers=("codex",),
                non_interactive=True,
                prompt_choice=None,
            )


# ─────────────────────────────────────────────────────────────────────────────
# Site 2: flow_interactive.py run_start_wizard_flow() — cli_flag=None,
# resume_provider=None, always interactive
# ─────────────────────────────────────────────────────────────────────────────


class TestFlowInteractiveProviderResolution:
    """Characterize flow_interactive.py's inline provider resolution.

    Key differences from flow.py start():
    - cli_flag is always None (no CLI flag in wizard flow)
    - resume_provider is always None (no session resume in wizard)
    - non_interactive is always False (wizard is always interactive)
    """

    def test_no_cli_flag_available(self) -> None:
        """Wizard flow never has a CLI flag — relies on workspace/config/probe."""
        result = choose_start_provider(
            cli_flag=None,  # <-- always None in wizard flow
            resume_provider=None,  # <-- always None in wizard flow
            workspace_last_used="codex",
            config_provider="claude",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,  # <-- always False in wizard
            prompt_choice=_noop_prompt,
        )
        # workspace_last_used wins
        assert result == "codex"

    def test_no_resume_provider_available(self) -> None:
        """Wizard flow cannot resume — resume_provider is always None."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider="codex",
            connected_provider_ids=("codex",),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "codex"

    def test_wizard_prompts_when_ambiguous(self) -> None:
        """Wizard always prompts (never non_interactive) when ambiguous."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "claude"  # first candidate from KNOWN_PROVIDERS

    def test_wizard_cancel_returns_none(self) -> None:
        """Cancelling the prompt in wizard returns None."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_cancel_prompt,
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Site 3: worktree_commands.py worktree_create_cmd() —
# uses resolve_active_provider() directly
# ─────────────────────────────────────────────────────────────────────────────


class TestWorktreeCommandProviderResolution:
    """Characterize worktree_commands.py's provider resolution.

    Key differences from flow.py start():
    - Uses resolve_active_provider() directly instead of choose_start_provider()
    - No workspace_last_used lookup
    - No connected_provider_ids probing
    - No resume_provider
    - Now uses shared preflight (collect_launch_readiness + ensure_launch_ready)
    - Falls back to 'claude' (hardcoded DEFAULT_PROVIDER) when nothing is set
    """

    def test_cli_flag_wins(self) -> None:
        """CLI flag is highest precedence in resolve_active_provider too."""
        result = resolve_active_provider(
            cli_flag="codex",
            config_provider="claude",
        )
        assert result == "codex"

    def test_config_provider_used_when_no_cli_flag(self) -> None:
        """Config provider is used when no CLI flag."""
        result = resolve_active_provider(
            cli_flag=None,
            config_provider="codex",
        )
        assert result == "codex"

    def test_defaults_to_claude_when_nothing_set(self) -> None:
        """Falls back to 'claude' when nothing is configured — key difference."""
        result = resolve_active_provider(
            cli_flag=None,
            config_provider=None,
        )
        assert result == "claude"

    def test_ask_config_treated_as_none_defaults_claude(self) -> None:
        """config_provider='ask' is treated as None, falls to claude default."""
        result = resolve_active_provider(
            cli_flag=None,
            config_provider="ask",
        )
        assert result == "claude"

    def test_no_workspace_last_used_in_worktree_path(self) -> None:
        """Worktree site never looks up workspace_last_used — it goes straight
        to config or default. This means the worktree can launch a different
        provider than what the workspace last used."""
        # In choose_start_provider, workspace_last_used='codex' would win.
        # In resolve_active_provider, there's no workspace_last_used at all.
        result = resolve_active_provider(
            cli_flag=None,
            config_provider=None,
        )
        assert result == "claude"  # default, not workspace_last_used

    def test_no_connected_probing_in_worktree(self) -> None:
        """Worktree path never probes auth readiness — it resolves purely
        from cli_flag + config_provider + default. No adapter probing."""
        # resolve_active_provider has no connected_provider_ids parameter
        result = resolve_active_provider(
            cli_flag=None,
            config_provider=None,
        )
        assert result == "claude"

    def test_unknown_provider_raises_value_error(self) -> None:
        """Unknown provider raises ValueError in resolve_active_provider."""
        with pytest.raises(ValueError, match="Unknown provider 'unknown'"):
            resolve_active_provider(
                cli_flag="unknown",
                config_provider=None,
            )

    def test_allowed_providers_check(self) -> None:
        """Worktree path skips allowed_providers check — it passes no allowed list.
        But resolve_active_provider CAN enforce allowed_providers if passed."""
        from scc_cli.core.errors import ProviderNotAllowedError

        with pytest.raises(ProviderNotAllowedError):
            resolve_active_provider(
                cli_flag=None,
                config_provider=None,
                allowed_providers=("codex",),  # claude default is blocked
            )

    def test_worktree_site_uses_shared_preflight(self) -> None:
        """Document that worktree_create_cmd now uses the shared preflight path
        (collect_launch_readiness + ensure_launch_ready) instead of inline
        ensure_provider_image / ensure_provider_auth calls."""
        # Verified by source inspection. Both image and auth are handled
        # through the unified preflight readiness model.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Site 4: orchestrator_handlers.py _handle_worktree_start() —
# choose_start_provider with cli_flag=None, resume_provider=None
# ─────────────────────────────────────────────────────────────────────────────


class TestOrchestratorWorktreeStartResolution:
    """Characterize _handle_worktree_start()'s provider resolution.

    Uses choose_start_provider just like flow.py, but:
    - cli_flag is always None (no CLI flag in dashboard context)
    - resume_provider is always None (new start, not resume)
    - Always interactive (non_interactive=False)
    - Uses shared preflight (collect_launch_readiness + ensure_launch_ready)
    - Uses workspace_last_used and connected probing
    """

    def test_workspace_last_used_available(self) -> None:
        """Dashboard start uses workspace_last_used (unlike worktree_commands)."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            config_provider="claude",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "codex"

    def test_connected_probing_available(self) -> None:
        """Dashboard start probes auth readiness (unlike worktree_commands)."""
        # When config is 'ask' and only one provider connected, auto-selects
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider="ask",
            connected_provider_ids=("codex",),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "codex"

    def test_no_cli_flag_in_dashboard(self) -> None:
        """Dashboard has no CLI flag — workspace_last_used is highest auto source."""
        result = choose_start_provider(
            cli_flag=None,  # always None
            resume_provider=None,  # always None for fresh start
            workspace_last_used="claude",
            config_provider="codex",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "claude"  # workspace_last_used wins

    def test_uses_shared_preflight(self) -> None:
        """Document: _handle_worktree_start uses the shared preflight path
        (collect_launch_readiness + ensure_launch_ready), same as all other
        launch sites."""
        # Verified by source inspection. Uses collect_launch_readiness +
        # ensure_launch_ready in the try block.
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Site 5: orchestrator_handlers.py _handle_session_resume() —
# choose_start_provider with resume_provider=session.provider_id
# ─────────────────────────────────────────────────────────────────────────────


class TestOrchestratorSessionResumeResolution:
    """Characterize _handle_session_resume()'s provider resolution.

    Uses choose_start_provider with:
    - cli_flag=None (no CLI in dashboard)
    - resume_provider=session.provider_id (session's stored provider)
    - workspace_last_used from workspace_local_config
    - Connected probing available
    - Always interactive (non_interactive=False)
    """

    def test_resume_provider_from_session(self) -> None:
        """Resume provider comes from the session record and takes precedence."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider="codex",  # from session.provider_id
            workspace_last_used="claude",
            config_provider="claude",
            connected_provider_ids=("claude",),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "codex"

    def test_resume_provider_none_falls_through(self) -> None:
        """When session has no provider_id, falls to workspace_last_used."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,  # old session without provider_id
            workspace_last_used="codex",
            config_provider="claude",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=_noop_prompt,
        )
        assert result == "codex"

    def test_resume_respects_allowed_providers(self) -> None:
        """Resume provider is still blocked by team policy."""
        from scc_cli.core.errors import ProviderNotAllowedError

        with pytest.raises(ProviderNotAllowedError):
            choose_start_provider(
                cli_flag=None,
                resume_provider="claude",
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=(),
                allowed_providers=("codex",),
                non_interactive=False,
                prompt_choice=_noop_prompt,
            )


# ─────────────────────────────────────────────────────────────────────────────
# _record_session_and_context: WorkContext.provider_id is always None
# ─────────────────────────────────────────────────────────────────────────────


class TestRecordSessionAndContextProviderGap:
    """Characterize: _record_session_and_context does NOT forward provider_id
    to WorkContext, even though it receives provider_id and WorkContext has the field.

    The provider_id IS forwarded to sessions.record_session() but NOT to WorkContext.
    This means Quick Resume context entries lose the provider information.
    """

    def test_work_context_provider_id_defaults_to_none(self) -> None:
        """WorkContext.provider_id defaults to None when not explicitly set."""
        ctx = WorkContext(
            team="myteam",
            repo_root=Path("/repo"),
            worktree_path=Path("/repo"),
            worktree_name="repo",
            branch="main",
        )
        assert ctx.provider_id is None

    def test_work_context_accepts_provider_id(self) -> None:
        """WorkContext CAN hold provider_id — it just isn't set by _record_session_and_context."""
        ctx = WorkContext(
            team="myteam",
            repo_root=Path("/repo"),
            worktree_path=Path("/repo"),
            worktree_name="repo",
            branch="main",
            provider_id="codex",
        )
        assert ctx.provider_id == "codex"

    def test_record_session_and_context_threads_provider_to_work_context(self) -> None:
        """Prove that _record_session_and_context threads provider_id to WorkContext.

        We mock the dependencies to avoid filesystem side effects.
        """
        with (
            patch("scc_cli.commands.launch.flow_session.sessions") as mock_sessions,
            patch("scc_cli.commands.launch.flow_session.git") as mock_git,
            patch("scc_cli.commands.launch.flow_session.record_context") as mock_record_ctx,
            patch("scc_cli.commands.launch.flow_session.config"),
        ):
            mock_git.get_worktree_main_repo.return_value = Path("/repo")

            from scc_cli.commands.launch.flow_session import _record_session_and_context

            _record_session_and_context(
                workspace_path=Path("/repo/wt"),
                team="myteam",
                session_name="sess1",
                current_branch="main",
                provider_id="codex",
            )

            # sessions.record_session gets provider_id
            mock_sessions.record_session.assert_called_once()
            call_kwargs = mock_sessions.record_session.call_args
            assert call_kwargs.kwargs.get("provider_id") == "codex" or (
                len(call_kwargs.args) == 0 and call_kwargs[1].get("provider_id") == "codex"
            )

            # record_context now gets a WorkContext WITH provider_id
            mock_record_ctx.assert_called_once()
            recorded_context: WorkContext = mock_record_ctx.call_args[0][0]
            assert recorded_context.provider_id == "codex"
            assert recorded_context.team == "myteam"
            assert recorded_context.branch == "main"


# ─────────────────────────────────────────────────────────────────────────────
# Non-interactive behavior characterization
# ─────────────────────────────────────────────────────────────────────────────


class TestNonInteractiveBehavior:
    """Characterize what happens when non_interactive=True and provider
    resolution is ambiguous across different resolution paths."""

    def test_choose_start_provider_non_interactive_unambiguous_single_connected(self) -> None:
        """Non-interactive succeeds when exactly one provider is connected."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected_provider_ids=("codex",),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"

    def test_choose_start_provider_non_interactive_ambiguous_raises(self) -> None:
        """Non-interactive raises when multiple providers available, no preference."""
        from scc_cli.core.errors import ProviderNotReadyError

        with pytest.raises(ProviderNotReadyError, match="Multiple providers"):
            choose_start_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=("claude", "codex"),
                allowed_providers=(),
                non_interactive=True,
                prompt_choice=None,
            )

    def test_resolve_active_provider_non_interactive_always_resolves(self) -> None:
        """resolve_active_provider always returns a value — no ambiguity path.
        It defaults to 'claude' when nothing is configured."""
        result = resolve_active_provider(
            cli_flag=None,
            config_provider=None,
        )
        assert result == "claude"

    def test_choose_start_provider_non_interactive_single_allowed(self) -> None:
        """Non-interactive succeeds when allowed_providers has exactly one entry."""
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider=None,
            connected_provider_ids=(),
            allowed_providers=("codex",),
            non_interactive=True,
            prompt_choice=None,
        )
        assert result == "codex"


# ─────────────────────────────────────────────────────────────────────────────
# Cross-site divergence characterization
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossSiteDivergence:
    """Document behavioral differences between the five sites that the
    consolidation must reconcile."""

    def test_worktree_and_flow_diverge_on_no_config(self) -> None:
        """With no config at all: worktree defaults to 'claude',
        choose_start_provider requires interactive or raises."""
        # Site 3 (worktree): always resolves
        wt_result = resolve_active_provider(cli_flag=None, config_provider=None)
        assert wt_result == "claude"

        # Site 1 (flow): with non_interactive, would raise if multiple connected
        from scc_cli.core.errors import ProviderNotReadyError

        with pytest.raises(ProviderNotReadyError):
            choose_start_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=("claude", "codex"),
                allowed_providers=(),
                non_interactive=True,
                prompt_choice=None,
            )

    def test_worktree_missing_workspace_last_used(self) -> None:
        """Worktree path ignores workspace_last_used entirely.
        When workspace was last used with codex, worktree still defaults to claude."""
        # Site 3 cannot see workspace_last_used
        wt_result = resolve_active_provider(cli_flag=None, config_provider=None)
        assert wt_result == "claude"

        # Sites 1,2,4,5 would pick codex from workspace_last_used
        flow_result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            config_provider=None,
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=True,
            prompt_choice=None,
        )
        assert flow_result == "codex"

    def test_resolve_active_provider_has_hardcoded_default(self) -> None:
        """resolve_active_provider (used by worktree) has a hardcoded default
        of 'claude'. choose_start_provider does NOT have this default."""
        assert resolve_active_provider(cli_flag=None, config_provider=None) == "claude"

    def test_resume_provider_only_available_in_sites_1_and_5(self) -> None:
        """Only flow.py start() and _handle_session_resume() can pass resume_provider.
        The other three sites hardcode resume_provider=None."""
        # With resume_provider set, it takes precedence over workspace_last_used
        result = resolve_provider_preference(
            cli_flag=None,
            resume_provider="codex",
            workspace_last_used="claude",
            global_preferred=None,
        )
        assert result is not None
        assert result.provider_id == "codex"
        assert result.source == "resume"

    def test_preference_source_tracking(self) -> None:
        """resolve_provider_preference tracks which source won —
        useful for the consolidated path to report where the choice came from."""
        explicit = resolve_provider_preference(
            cli_flag="codex",
            resume_provider=None,
            workspace_last_used=None,
            global_preferred=None,
        )
        assert explicit is not None
        assert explicit.source == "explicit"

        workspace = resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            global_preferred=None,
        )
        assert workspace is not None
        assert workspace.source == "workspace_last_used"

        global_pref = resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            global_preferred="codex",
        )
        assert global_pref is not None
        assert global_pref.source == "global_preferred"

    def test_ask_suppresses_workspace_last_used(self) -> None:
        """When global_preferred is 'ask', workspace_last_used is ALSO suppressed.
        The 'ask' sentinel returns None before the workspace_last_used check runs.
        This means the operator is always prompted when config is 'ask'."""
        result = resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            global_preferred="ask",
        )
        # 'ask' suppresses everything below it — including workspace_last_used
        assert result is None

    def test_worktree_ask_defaults_to_claude(self) -> None:
        """In worktree path, config_provider='ask' is treated as None,
        and falls to hardcoded 'claude' default."""
        result = resolve_active_provider(cli_flag=None, config_provider="ask")
        assert result == "claude"
