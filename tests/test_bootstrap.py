"""Tests for bootstrap adapter wiring."""

from __future__ import annotations

from dataclasses import replace

import pytest

from scc_cli.adapters.claude_agent_runner import ClaudeAgentRunner
from scc_cli.adapters.docker_sandbox_runtime import DockerSandboxRuntime
from scc_cli.adapters.local_audit_event_sink import LocalAuditEventSink
from scc_cli.adapters.local_dependency_installer import LocalDependencyInstaller
from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.local_git_client import LocalGitClient
from scc_cli.adapters.oci_sandbox_runtime import OciSandboxRuntime
from scc_cli.adapters.personal_profile_service_local import LocalPersonalProfileService
from scc_cli.adapters.requests_fetcher import RequestsFetcher
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.bootstrap import DefaultAdapters, get_default_adapters
from scc_cli.commands.launch.dependencies import build_start_session_dependencies
from scc_cli.core.errors import InvalidLaunchPlanError, LaunchAuditUnavailableError
from tests.fakes import build_fake_adapters


def test_get_default_adapters_returns_expected_types() -> None:
    adapters = get_default_adapters()

    assert isinstance(adapters, DefaultAdapters)
    assert isinstance(adapters.filesystem, LocalFilesystem)
    assert isinstance(adapters.git_client, LocalGitClient)
    assert isinstance(adapters.dependency_installer, LocalDependencyInstaller)
    assert isinstance(adapters.remote_fetcher, RequestsFetcher)
    assert isinstance(adapters.clock, SystemClock)
    assert isinstance(adapters.agent_runner, ClaudeAgentRunner)
    assert isinstance(adapters.sandbox_runtime, (DockerSandboxRuntime, OciSandboxRuntime))
    assert isinstance(adapters.personal_profile_service, LocalPersonalProfileService)
    assert isinstance(adapters.audit_event_sink, LocalAuditEventSink)


# ---------------------------------------------------------------------------
# S01 seam boundary — these tests describe the target state for T02/T03.
# They are expected to fail until DefaultAdapters gains agent_provider wiring.
# ---------------------------------------------------------------------------


def test_default_adapters_exposes_agent_provider() -> None:
    """DefaultAdapters should expose an agent_provider satisfying the AgentProvider protocol.

    This characterizes the S01 target: the composition root must wire a provider
    adapter so the launch flow can call prepare_launch without importing Claude
    internals directly.
    """
    adapters = get_default_adapters()

    provider = adapters.agent_provider

    # The returned object must conform to AgentProvider protocol
    assert hasattr(provider, "capability_profile")
    assert hasattr(provider, "prepare_launch")
    profile = provider.capability_profile()
    assert profile.provider_id != ""
    assert profile.required_destination_set != ""


def test_build_start_session_dependencies_requires_provider_wiring() -> None:
    adapters = replace(build_fake_adapters(), agent_provider=None)

    with pytest.raises(InvalidLaunchPlanError, match="missing provider wiring"):
        build_start_session_dependencies(adapters)


def test_build_start_session_dependencies_requires_audit_sink_wiring() -> None:
    adapters = replace(build_fake_adapters(), audit_event_sink=None)

    with pytest.raises(LaunchAuditUnavailableError):
        build_start_session_dependencies(adapters)


def test_build_start_session_dependencies_threads_provider_and_sink() -> None:
    adapters = build_fake_adapters()

    dependencies = build_start_session_dependencies(adapters)

    assert dependencies.agent_provider is adapters.agent_provider
    assert dependencies.audit_event_sink is adapters.audit_event_sink
