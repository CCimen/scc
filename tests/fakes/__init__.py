"""Test fakes for SCC ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scc_cli.adapters.local_config_store import LocalConfigStore
from scc_cli.adapters.local_dependency_installer import LocalDependencyInstaller
from scc_cli.adapters.local_doctor_runner import LocalDoctorRunner
from scc_cli.adapters.local_filesystem import LocalFilesystem
from scc_cli.adapters.local_git_client import LocalGitClient
from scc_cli.adapters.personal_profile_service_local import LocalPersonalProfileService
from scc_cli.adapters.requests_fetcher import RequestsFetcher
from scc_cli.adapters.system_clock import SystemClock
from scc_cli.adapters.zip_archive_writer import ZipArchiveWriter
from scc_cli.bootstrap import DefaultAdapters
from scc_cli.core.contracts import AuditEvent
from scc_cli.ports.platform_probe import PlatformProbe
from tests.fakes.fake_agent_provider import FakeAgentProvider
from tests.fakes.fake_agent_runner import FakeAgentRunner
from tests.fakes.fake_runtime_probe import FakeRuntimeProbe
from tests.fakes.fake_safety_adapter import FakeSafetyAdapter
from tests.fakes.fake_safety_engine import FakeSafetyEngine
from tests.fakes.fake_sandbox_runtime import FakeSandboxRuntime


@dataclass
class FakeAuditEventSink:
    """In-memory audit sink for CLI and integration tests."""

    events: list[AuditEvent] = field(default_factory=list)

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def describe_destination(self) -> str:
        return "memory://launch-events"


class FakePlatformProbe(PlatformProbe):
    """Configurable platform probe for workspace validation tests."""

    def __init__(self, is_wsl2: bool, is_optimal: bool) -> None:
        self._is_wsl2 = is_wsl2
        self._is_optimal = is_optimal

    def is_wsl2(self) -> bool:
        return self._is_wsl2

    def check_path_performance(self, path: Path) -> tuple[bool, str | None]:
        if self._is_optimal:
            return True, None
        return False, "warning"


def build_fake_adapters() -> DefaultAdapters:
    """Return default adapters wired with fakes."""
    return DefaultAdapters(
        filesystem=LocalFilesystem(),
        git_client=LocalGitClient(),
        dependency_installer=LocalDependencyInstaller(),
        remote_fetcher=RequestsFetcher(),
        clock=SystemClock(),
        agent_runner=FakeAgentRunner(),
        agent_provider=FakeAgentProvider(),
        sandbox_runtime=FakeSandboxRuntime(),
        personal_profile_service=LocalPersonalProfileService(),
        doctor_runner=LocalDoctorRunner(),
        archive_writer=ZipArchiveWriter(),
        config_store=LocalConfigStore(),
        audit_event_sink=FakeAuditEventSink(),
        codex_agent_provider=FakeAgentProvider(),
        codex_agent_runner=FakeAgentRunner(),
        runtime_probe=FakeRuntimeProbe(),
        safety_engine=FakeSafetyEngine(),
        claude_safety_adapter=FakeSafetyAdapter(),
        codex_safety_adapter=FakeSafetyAdapter(),
    )
