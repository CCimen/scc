"""Tests for setup idempotency — re-running scc setup skips already-connected providers.

Verifies:
- _prompt_provider_connections skips providers whose status is 'present'
- _run_provider_onboarding only offers connection for missing providers
- When both are connected, provider connection prompt is skipped entirely
- When one is connected, only the missing one is offered
- Preference prompt only appears when both are connected after onboarding
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scc_cli.core.contracts import AuthReadiness
from scc_cli.setup import (
    _prompt_provider_connections,
    _prompt_provider_preference,
    _run_provider_onboarding,
)


def _readiness(status: str, guidance: str = "") -> AuthReadiness:
    """Build an AuthReadiness with the given status."""
    return AuthReadiness(
        status=status,
        mechanism="test",
        guidance=guidance,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# _prompt_provider_connections — skip logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptProviderConnectionsSkipLogic:
    """Verify _prompt_provider_connections skips already-connected providers."""

    def test_both_present_returns_empty_tuple(self) -> None:
        """When both providers are 'present', no connection prompt is shown."""
        console = MagicMock()
        readiness = {
            "claude": _readiness("present"),
            "codex": _readiness("present"),
        }
        result = _prompt_provider_connections(console, readiness)
        assert result == ()

    def test_claude_present_codex_missing_offers_codex_only(self) -> None:
        """When Claude is present but Codex is missing, only Codex is offered."""
        console = MagicMock()
        readiness = {
            "claude": _readiness("present"),
            "codex": _readiness("missing", "Sign in with Codex CLI"),
        }
        with patch("scc_cli.setup._select_option", return_value=0) as mock_select:
            result = _prompt_provider_connections(console, readiness)

        # Only Codex should be in the options — single provider + skip
        # The first option should be "Connect Codex", second "Skip for now"
        call_args = mock_select.call_args
        options = call_args[0][1]
        option_labels = [opt[0] for opt in options]
        assert "Connect both" not in option_labels
        assert any("Codex" in label for label in option_labels)
        assert any("Claude" not in label or "Skip" in label for label in option_labels)
        assert result == ("codex",)

    def test_codex_present_claude_missing_offers_claude_only(self) -> None:
        """When Codex is present but Claude is missing, only Claude is offered."""
        console = MagicMock()
        readiness = {
            "claude": _readiness("missing", "Sign in via browser"),
            "codex": _readiness("present"),
        }
        with patch("scc_cli.setup._select_option", return_value=0) as mock_select:
            result = _prompt_provider_connections(console, readiness)

        call_args = mock_select.call_args
        options = call_args[0][1]
        option_labels = [opt[0] for opt in options]
        assert "Connect both" not in option_labels
        assert any("Claude" in label for label in option_labels)
        assert result == ("claude",)

    def test_both_missing_offers_connect_both(self) -> None:
        """When both providers are missing, 'Connect both' is offered first."""
        console = MagicMock()
        readiness = {
            "claude": _readiness("missing"),
            "codex": _readiness("missing"),
        }
        with patch("scc_cli.setup._select_option", return_value=0) as mock_select:
            result = _prompt_provider_connections(console, readiness)

        call_args = mock_select.call_args
        options = call_args[0][1]
        option_labels = [opt[0] for opt in options]
        assert "Connect both" in option_labels
        assert result == ("claude", "codex")

    def test_skip_returns_empty_tuple(self) -> None:
        """When user selects 'Skip for now', empty tuple returned."""
        console = MagicMock()
        readiness = {
            "claude": _readiness("missing"),
            "codex": _readiness("missing"),
        }
        # Skip is the last option
        with patch("scc_cli.setup._select_option", return_value=3):
            result = _prompt_provider_connections(console, readiness)
        assert result == ()

    def test_none_select_returns_empty_tuple(self) -> None:
        """When _select_option returns None (escape), empty tuple returned."""
        console = MagicMock()
        readiness = {
            "claude": _readiness("missing"),
        }
        with patch("scc_cli.setup._select_option", return_value=None):
            result = _prompt_provider_connections(console, readiness)
        assert result == ()


# ═══════════════════════════════════════════════════════════════════════════════
# _run_provider_onboarding — full idempotency integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunProviderOnboardingIdempotency:
    """Verify _run_provider_onboarding is idempotent for already-connected providers."""

    def test_both_connected_skips_connections_shows_preference(self) -> None:
        """Re-running setup when both connected should skip connections, show preference prompt."""
        readiness = {
            "claude": _readiness("present"),
            "codex": _readiness("present"),
        }
        mock_runtime = MagicMock()
        mock_adapters = MagicMock()
        mock_adapters.sandbox_runtime = mock_runtime

        with (
            patch("scc_cli.setup.get_default_adapters", return_value=mock_adapters),
            patch(
                "scc_cli.setup.collect_provider_readiness",
                return_value=readiness,
            ),
            patch("scc_cli.setup._prompt_provider_connections") as mock_prompt_conn,
            patch("scc_cli.setup._prompt_provider_preference", return_value="ask"),
            patch("scc_cli.setup.config.get_selected_provider", return_value=None),
            patch("scc_cli.setup.config.set_selected_provider"),
        ):
            # _prompt_provider_connections returns () because both are present
            mock_prompt_conn.return_value = ()
            console = MagicMock()
            result_readiness, result_pref = _run_provider_onboarding(console)

        # No bootstrap_auth calls happened
        mock_adapters.agent_provider.bootstrap_auth.assert_not_called()
        # Preference prompt was shown because both are present on refresh
        assert result_pref == "ask"

    def test_docker_unavailable_skips_entirely(self) -> None:
        """When Docker is unavailable, provider onboarding is entirely skipped."""
        mock_runtime = MagicMock()
        mock_runtime.ensure_available.side_effect = RuntimeError("no docker")
        mock_adapters = MagicMock()
        mock_adapters.sandbox_runtime = mock_runtime

        with (
            patch("scc_cli.setup.get_default_adapters", return_value=mock_adapters),
            patch("scc_cli.setup.config.get_selected_provider", return_value=None),
        ):
            console = MagicMock()
            result_readiness, result_pref = _run_provider_onboarding(console)

        assert result_readiness is None
        assert result_pref is None

    def test_one_connected_only_bootstraps_missing(self) -> None:
        """When Claude is connected, only Codex bootstrap is called."""
        readiness_before = {
            "claude": _readiness("present"),
            "codex": _readiness("missing"),
        }
        readiness_after = {
            "claude": _readiness("present"),
            "codex": _readiness("present"),
        }
        mock_runtime = MagicMock()
        mock_adapters = MagicMock()
        mock_adapters.sandbox_runtime = mock_runtime
        mock_codex_provider = MagicMock()

        with (
            patch("scc_cli.setup.get_default_adapters", return_value=mock_adapters),
            patch(
                "scc_cli.setup.collect_provider_readiness",
                side_effect=[readiness_before, readiness_after],
            ),
            patch(
                "scc_cli.setup.get_agent_provider",
                return_value=mock_codex_provider,
            ),
            patch("scc_cli.setup._prompt_provider_connections", return_value=("codex",)),
            patch("scc_cli.setup._prompt_provider_preference", return_value="codex"),
            patch("scc_cli.setup.config.get_selected_provider", return_value=None),
            patch("scc_cli.setup.config.set_selected_provider"),
        ):
            console = MagicMock()
            result_readiness, result_pref = _run_provider_onboarding(console)

        # bootstrap_auth called once for codex
        mock_codex_provider.bootstrap_auth.assert_called_once()
        assert result_pref == "codex"

    def test_preference_prompt_only_when_both_connected_after_onboarding(self) -> None:
        """Preference prompt only shows when both are connected AFTER onboarding refresh."""
        readiness_before = {
            "claude": _readiness("present"),
            "codex": _readiness("missing"),
        }
        # After onboarding, codex is still missing
        readiness_after = {
            "claude": _readiness("present"),
            "codex": _readiness("missing"),
        }
        mock_runtime = MagicMock()
        mock_adapters = MagicMock()
        mock_adapters.sandbox_runtime = mock_runtime

        with (
            patch("scc_cli.setup.get_default_adapters", return_value=mock_adapters),
            patch(
                "scc_cli.setup.collect_provider_readiness",
                side_effect=[readiness_before, readiness_after],
            ),
            patch("scc_cli.setup._prompt_provider_connections", return_value=()),
            patch("scc_cli.setup._prompt_provider_preference") as mock_pref,
            patch("scc_cli.setup.config.get_selected_provider", return_value=None),
        ):
            console = MagicMock()
            result_readiness, result_pref = _run_provider_onboarding(console)

        # Preference prompt NOT shown because codex is still missing
        mock_pref.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# _prompt_provider_preference — preference persistence
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptProviderPreference:
    """Verify provider preference prompt behavior."""

    def test_returns_ask_for_first_selection(self) -> None:
        """Default selection (index 0) returns 'ask'."""
        console = MagicMock()
        with patch("scc_cli.setup._select_option", return_value=0):
            result = _prompt_provider_preference(console, current=None)
        assert result == "ask"

    def test_returns_claude_for_second_selection(self) -> None:
        """Index 1 returns 'claude'."""
        console = MagicMock()
        with patch("scc_cli.setup._select_option", return_value=1):
            result = _prompt_provider_preference(console, current=None)
        assert result == "claude"

    def test_returns_codex_for_third_selection(self) -> None:
        """Index 2 returns 'codex'."""
        console = MagicMock()
        with patch("scc_cli.setup._select_option", return_value=2):
            result = _prompt_provider_preference(console, current=None)
        assert result == "codex"

    def test_returns_current_on_escape(self) -> None:
        """None (escape) preserves the current preference."""
        console = MagicMock()
        with patch("scc_cli.setup._select_option", return_value=None):
            result = _prompt_provider_preference(console, current="claude")
        assert result == "claude"

    def test_preselects_claude_when_current_is_claude(self) -> None:
        """When current is 'claude', default_index should be 1."""
        console = MagicMock()
        with patch("scc_cli.setup._select_option", return_value=1) as mock_select:
            _prompt_provider_preference(console, current="claude")
        # default parameter should be 1
        call_args = mock_select.call_args
        assert call_args[1].get("default") == 1 or call_args[0][2] == 1

    def test_preselects_codex_when_current_is_codex(self) -> None:
        """When current is 'codex', default_index should be 2."""
        console = MagicMock()
        with patch("scc_cli.setup._select_option", return_value=2) as mock_select:
            _prompt_provider_preference(console, current="codex")
        call_args = mock_select.call_args
        assert call_args[1].get("default") == 2 or call_args[0][2] == 2
