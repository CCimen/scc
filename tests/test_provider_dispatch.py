"""Tests for provider dispatch wiring in the launch path."""

from __future__ import annotations

from dataclasses import replace

import pytest

from scc_cli.commands.launch.dependencies import build_start_session_dependencies
from scc_cli.core.contracts import RuntimeInfo
from scc_cli.core.errors import (
    InvalidLaunchPlanError,
    InvalidProviderError,
    ProviderNotAllowedError,
)
from scc_cli.core.provider_resolution import resolve_active_provider
from tests.fakes import build_fake_adapters


class TestBuildStartSessionDependenciesDispatch:
    """Provider dispatch via build_start_session_dependencies."""

    def test_empty_provider_id_raises_invalid_provider_error(self) -> None:
        """D032: empty provider_id must fail-closed, not default to Claude."""
        adapters = build_fake_adapters()
        with pytest.raises(InvalidProviderError):
            build_start_session_dependencies(adapters, provider_id="")

    def test_explicit_claude_dispatch(self) -> None:
        adapters = build_fake_adapters()
        deps = build_start_session_dependencies(adapters, provider_id="claude")
        assert deps.agent_provider is adapters.agent_provider

    def test_explicit_codex_dispatch(self) -> None:
        adapters = build_fake_adapters()
        deps = build_start_session_dependencies(adapters, provider_id="codex")
        assert deps.agent_provider is adapters.codex_agent_provider

    def test_unknown_provider_raises_invalid_provider_error(self) -> None:
        """Unknown provider_id not in dispatch table raises InvalidProviderError."""
        adapters = build_fake_adapters()
        with pytest.raises(InvalidProviderError):
            build_start_session_dependencies(adapters, provider_id="unknown")

    def test_codex_dispatch_with_none_codex_provider_raises(self) -> None:
        """If codex_agent_provider is None, dispatch raises InvalidLaunchPlanError."""
        from scc_cli.core.errors import InvalidLaunchPlanError

        adapters = replace(build_fake_adapters(), codex_agent_provider=None)
        with pytest.raises(InvalidLaunchPlanError, match="missing provider wiring"):
            build_start_session_dependencies(adapters, provider_id="codex")


class TestAgentRunnerDispatch:
    """agent_runner dispatched per-provider from the dispatch table."""

    def test_claude_dispatch_uses_claude_agent_runner(self) -> None:
        adapters = build_fake_adapters()
        deps = build_start_session_dependencies(adapters, provider_id="claude")
        assert deps.agent_runner is adapters.agent_runner

    def test_codex_dispatch_uses_codex_agent_runner(self) -> None:
        adapters = build_fake_adapters()
        deps = build_start_session_dependencies(adapters, provider_id="codex")
        assert deps.agent_runner is adapters.codex_agent_runner

    def test_unknown_provider_raises_invalid_provider_error_runner(self) -> None:
        """Unknown provider_id raises before runner dispatch is reached."""
        adapters = build_fake_adapters()
        with pytest.raises(InvalidProviderError):
            build_start_session_dependencies(adapters, provider_id="unknown")

    def test_codex_dispatch_with_none_codex_runner_raises(self) -> None:
        adapters = replace(build_fake_adapters(), codex_agent_runner=None)
        with pytest.raises(InvalidLaunchPlanError, match="missing agent runner wiring"):
            build_start_session_dependencies(adapters, provider_id="codex")


class TestRuntimeInfoThreading:
    """runtime_info threaded from runtime_probe into dependencies."""

    def test_runtime_info_threaded_from_probe(self) -> None:
        """When runtime_probe exists, runtime_info is populated."""
        adapters = build_fake_adapters()
        deps = build_start_session_dependencies(adapters, provider_id="claude")
        # FakeRuntimeProbe returns a RuntimeInfo — verify it landed
        assert deps.runtime_info is not None
        assert isinstance(deps.runtime_info, RuntimeInfo)

    def test_runtime_info_none_when_no_probe(self) -> None:
        """When runtime_probe is None, runtime_info stays None."""
        adapters = replace(build_fake_adapters(), runtime_probe=None)
        deps = build_start_session_dependencies(adapters, provider_id="claude")
        assert deps.runtime_info is None


class TestProviderPolicyInResolveActiveProvider:
    """Policy violation tests via resolve_active_provider (used in flow.py)."""

    def test_allowed_providers_blocks_codex(self) -> None:
        with pytest.raises(ProviderNotAllowedError):
            resolve_active_provider(
                cli_flag="codex",
                config_provider=None,
                allowed_providers=("claude",),
            )

    def test_allowed_providers_permits_claude(self) -> None:
        result = resolve_active_provider(
            cli_flag="claude",
            config_provider=None,
            allowed_providers=("claude",),
        )
        assert result == "claude"

    def test_empty_allowed_providers_permits_all(self) -> None:
        result = resolve_active_provider(
            cli_flag="codex",
            config_provider=None,
            allowed_providers=(),
        )
        assert result == "codex"

    def test_cli_flag_overrides_config(self) -> None:
        result = resolve_active_provider(
            cli_flag="codex",
            config_provider="claude",
        )
        assert result == "codex"

    def test_config_provider_used_when_no_cli_flag(self) -> None:
        result = resolve_active_provider(
            cli_flag=None,
            config_provider="codex",
        )
        assert result == "codex"

    def test_default_is_claude(self) -> None:
        result = resolve_active_provider(
            cli_flag=None,
            config_provider=None,
        )
        assert result == "claude"
