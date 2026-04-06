"""Tests for start-time provider choice policy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scc_cli.commands.launch.provider_choice import choose_start_provider
from scc_cli.core.errors import ProviderNotReadyError


def test_explicit_provider_skips_prompt() -> None:
    prompt = MagicMock(return_value="claude")

    result = choose_start_provider(
        cli_flag="codex",
        resume_provider=None,
        workspace_last_used=None,
        config_provider=None,
        connected_provider_ids=("claude", "codex"),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=prompt,
    )

    assert result == "codex"
    prompt.assert_not_called()


def test_resume_provider_beats_connected_auto_choice() -> None:
    result = choose_start_provider(
        cli_flag=None,
        resume_provider="codex",
        workspace_last_used=None,
        config_provider=None,
        connected_provider_ids=("claude",),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=None,
    )

    assert result == "codex"


def test_single_connected_provider_auto_selected() -> None:
    result = choose_start_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used=None,
        config_provider=None,
        connected_provider_ids=("codex",),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=None,
    )

    assert result == "codex"


def test_prompt_used_when_multiple_allowed_and_no_preference() -> None:
    prompt = MagicMock(return_value="claude")

    result = choose_start_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used=None,
        config_provider=None,
        connected_provider_ids=("claude", "codex"),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=prompt,
    )

    assert result == "claude"
    prompt.assert_called_once_with(("claude", "codex"), ("claude", "codex"), None)


def test_cancelled_prompt_returns_none() -> None:
    prompt = MagicMock(return_value=None)

    result = choose_start_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used=None,
        config_provider=None,
        connected_provider_ids=("claude", "codex"),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=prompt,
    )

    assert result is None


def test_explicit_ask_preference_prompts_even_with_workspace_last_used() -> None:
    prompt = MagicMock(return_value="claude")

    result = choose_start_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used="codex",
        config_provider="ask",
        connected_provider_ids=("claude", "codex"),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=prompt,
    )

    assert result == "claude"
    prompt.assert_called_once_with(("claude", "codex"), ("claude", "codex"), "codex")


def test_prompt_preselects_workspace_last_used_when_global_policy_is_ask() -> None:
    prompt = MagicMock(return_value="codex")

    result = choose_start_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used="codex",
        config_provider="ask",
        connected_provider_ids=("claude", "codex"),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=prompt,
    )

    assert result == "codex"
    prompt.assert_called_once_with(("claude", "codex"), ("claude", "codex"), "codex")


def test_explicit_ask_preference_still_auto_selects_single_connected_provider() -> None:
    result = choose_start_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used="codex",
        config_provider="ask",
        connected_provider_ids=("claude",),
        allowed_providers=(),
        non_interactive=False,
        prompt_choice=None,
    )

    assert result == "claude"


def test_non_interactive_multiple_options_fail_closed() -> None:
    with pytest.raises(ProviderNotReadyError, match="Multiple providers are available"):
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
