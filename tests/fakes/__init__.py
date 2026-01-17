"""Test fakes for SCC ports."""

from __future__ import annotations

from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.local_git_client import LocalGitClient
from scc_cli.adapters.requests_fetcher import RequestsFetcher
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.bootstrap import DefaultAdapters
from tests.fakes.fake_agent_runner import FakeAgentRunner
from tests.fakes.fake_sandbox_runtime import FakeSandboxRuntime


def build_fake_adapters() -> DefaultAdapters:
    """Return default adapters wired with fakes."""
    return DefaultAdapters(
        filesystem=LocalFilesystem(),
        git_client=LocalGitClient(),
        remote_fetcher=RequestsFetcher(),
        clock=SystemClock(),
        agent_runner=FakeAgentRunner(),
        sandbox_runtime=FakeSandboxRuntime(),
    )
