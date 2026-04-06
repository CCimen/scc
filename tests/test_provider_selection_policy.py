"""Pure tests for provider selection precedence."""

from __future__ import annotations

import pytest

from scc_cli.application.provider_selection import (
    ProviderSelection,
    resolve_provider_preference,
)
from scc_cli.core.errors import ProviderNotAllowedError


def test_explicit_provider_wins() -> None:
    result = resolve_provider_preference(
        cli_flag="codex",
        resume_provider="claude",
        workspace_last_used="claude",
        global_preferred="claude",
    )
    assert result == ProviderSelection(provider_id="codex", source="explicit")


def test_resume_provider_beats_workspace_and_global() -> None:
    result = resolve_provider_preference(
        cli_flag=None,
        resume_provider="codex",
        workspace_last_used="claude",
        global_preferred="claude",
    )
    assert result == ProviderSelection(provider_id="codex", source="resume")


def test_workspace_last_used_beats_global_preference() -> None:
    result = resolve_provider_preference(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used="codex",
        global_preferred="claude",
    )
    assert result == ProviderSelection(provider_id="codex", source="workspace_last_used")


def test_global_preference_used_when_no_higher_precedence_exists() -> None:
    result = resolve_provider_preference(
        cli_flag=None,
        resume_provider=None,
        workspace_last_used=None,
        global_preferred="codex",
    )
    assert result == ProviderSelection(provider_id="codex", source="global_preferred")


def test_ask_global_preference_returns_none() -> None:
    assert (
        resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            global_preferred="ask",
        )
        is None
    )


def test_explicit_ask_preference_suppresses_workspace_last_used() -> None:
    assert (
        resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            global_preferred="ask",
        )
        is None
    )


def test_allowed_providers_policy_still_applies() -> None:
    with pytest.raises(ProviderNotAllowedError):
        resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            global_preferred=None,
            allowed_providers=("claude",),
        )


def test_unknown_provider_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown provider 'nope'"):
        resolve_provider_preference(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="nope",
            global_preferred=None,
        )
