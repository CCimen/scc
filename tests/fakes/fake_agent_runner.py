"""Fake AgentRunner for tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scc_cli.ports.models import AgentCommand, AgentSettings


class FakeAgentRunner:
    """Simple AgentRunner stub for unit tests."""

    def build_settings(self, config: dict[str, Any], *, path: Path) -> AgentSettings:
        return AgentSettings(content=config, path=path)

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        return AgentCommand(argv=["fake-agent"], env={}, workdir=settings.path.parent)

    def describe(self) -> str:
        return "Fake agent runner"
