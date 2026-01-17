"""Composition root wiring SCC adapters."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from scc_cli.adapters.claude_agent_runner import ClaudeAgentRunner
from scc_cli.adapters.docker_sandbox_runtime import DockerSandboxRuntime
from scc_cli.adapters.local_dependency_installer import LocalDependencyInstaller
from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.local_git_client import LocalGitClient
from scc_cli.adapters.requests_fetcher import RequestsFetcher
from scc_cli.adapters.session_store_json import JsonSessionStore
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.clock import Clock
from scc_cli.ports.dependency_installer import DependencyInstaller
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.git_client import GitClient
from scc_cli.ports.remote_fetcher import RemoteFetcher
from scc_cli.ports.sandbox_runtime import SandboxRuntime
from scc_cli.ports.session_store import SessionStore


@dataclass(frozen=True)
class DefaultAdapters:
    """Container for default adapter instances."""

    filesystem: Filesystem
    git_client: GitClient
    dependency_installer: DependencyInstaller
    remote_fetcher: RemoteFetcher
    clock: Clock
    agent_runner: AgentRunner
    sandbox_runtime: SandboxRuntime


@lru_cache(maxsize=1)
def get_default_adapters() -> DefaultAdapters:
    """Return the default adapter wiring for SCC."""

    return DefaultAdapters(
        filesystem=LocalFilesystem(),
        git_client=LocalGitClient(),
        dependency_installer=LocalDependencyInstaller(),
        remote_fetcher=RequestsFetcher(),
        clock=SystemClock(),
        agent_runner=ClaudeAgentRunner(),
        sandbox_runtime=DockerSandboxRuntime(),
    )


def build_session_store(filesystem: Filesystem | None = None) -> SessionStore:
    """Build the default session store adapter.

    Args:
        filesystem: Optional filesystem adapter override.

    Returns:
        SessionStore implementation backed by JSON storage.
    """
    from scc_cli import config

    fs = filesystem or get_default_adapters().filesystem
    return JsonSessionStore(filesystem=fs, sessions_file=config.SESSIONS_FILE)
