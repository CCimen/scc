"""Tests for bootstrap adapter wiring."""

from __future__ import annotations

from scc_cli.adapters.claude_agent_runner import ClaudeAgentRunner
from scc_cli.adapters.docker_sandbox_runtime import DockerSandboxRuntime
from scc_cli.adapters.local_dependency_installer import LocalDependencyInstaller
from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.local_git_client import LocalGitClient
from scc_cli.adapters.personal_profile_service_local import LocalPersonalProfileService
from scc_cli.adapters.requests_fetcher import RequestsFetcher
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.bootstrap import DefaultAdapters, get_default_adapters


def test_get_default_adapters_returns_expected_types() -> None:
    adapters = get_default_adapters()

    assert isinstance(adapters, DefaultAdapters)
    assert isinstance(adapters.filesystem, LocalFilesystem)
    assert isinstance(adapters.git_client, LocalGitClient)
    assert isinstance(adapters.dependency_installer, LocalDependencyInstaller)
    assert isinstance(adapters.remote_fetcher, RequestsFetcher)
    assert isinstance(adapters.clock, SystemClock)
    assert isinstance(adapters.agent_runner, ClaudeAgentRunner)
    assert isinstance(adapters.sandbox_runtime, DockerSandboxRuntime)
    assert isinstance(adapters.personal_profile_service, LocalPersonalProfileService)
