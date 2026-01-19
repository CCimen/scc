"""Composition root wiring SCC adapters."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from scc_cli.adapters.claude_agent_runner import ClaudeAgentRunner
from scc_cli.adapters.docker_sandbox_runtime import DockerSandboxRuntime
from scc_cli.adapters.local_config_store import LocalConfigStore
from scc_cli.adapters.local_dependency_installer import LocalDependencyInstaller
from scc_cli.adapters.local_doctor_runner import LocalDoctorRunner
from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.local_git_client import LocalGitClient
from scc_cli.adapters.personal_profile_service_local import LocalPersonalProfileService
from scc_cli.adapters.requests_fetcher import RequestsFetcher
from scc_cli.adapters.session_store_json import JsonSessionStore
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.adapters.zip_archive_writer import ZipArchiveWriter
from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.archive_writer import ArchiveWriter
from scc_cli.ports.clock import Clock
from scc_cli.ports.config_store import ConfigStore
from scc_cli.ports.dependency_installer import DependencyInstaller
from scc_cli.ports.doctor_runner import DoctorRunner
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.git_client import GitClient
from scc_cli.ports.personal_profile_service import PersonalProfileService
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
    personal_profile_service: PersonalProfileService
    doctor_runner: DoctorRunner
    archive_writer: ArchiveWriter
    config_store: ConfigStore


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
        personal_profile_service=LocalPersonalProfileService(),
        doctor_runner=LocalDoctorRunner(),
        archive_writer=ZipArchiveWriter(),
        config_store=LocalConfigStore(),
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
