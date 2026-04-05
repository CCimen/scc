"""Fake AgentRunner for tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scc_cli.ports.models import AgentCommand, AgentSettings


class FakeAgentRunner:
    """Simple AgentRunner stub for unit tests."""

    def build_settings(self, config: dict[str, Any], *, path: Path) -> AgentSettings:
        rendered = json.dumps(config, indent=2, sort_keys=True).encode()
        return AgentSettings(rendered_bytes=rendered, path=path, suffix=".json")

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        return AgentCommand(argv=["fake-agent"], env={}, workdir=settings.path.parent)

    def describe(self) -> str:
        return "Fake agent runner"
