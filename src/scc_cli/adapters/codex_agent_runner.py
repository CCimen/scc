"""Codex CLI adapter for AgentRunner port."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scc_cli.adapters.codex_launch import build_codex_container_argv
from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.models import AgentCommand, AgentSettings

DEFAULT_SETTINGS_PATH = Path("/home/agent/.codex/config.toml")


def _serialize_toml(config: dict[str, Any]) -> bytes:
    """Serialize a flat dict to TOML bytes.

    Supports str, bool, int, and float values.  Nested dicts produce
    ``[section]`` headers.  This is intentionally minimal — Codex
    config.toml is a flat key-value surface.
    """
    lines: list[str] = []
    nested: dict[str, dict[str, Any]] = {}
    for key in sorted(config):
        val = config[key]
        if isinstance(val, dict):
            nested[key] = val
        else:
            lines.append(_toml_kv(key, val))
    for section in sorted(nested):
        lines.append(f"\n[{section}]")
        for key in sorted(nested[section]):
            lines.append(_toml_kv(key, nested[section][key]))
    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text.encode()


def _toml_kv(key: str, val: Any) -> str:
    if isinstance(val, bool):
        return f"{key} = {'true' if val else 'false'}"
    if isinstance(val, (int, float)):
        return f"{key} = {val}"
    return f'{key} = "{val}"'


class CodexAgentRunner(AgentRunner):
    """AgentRunner implementation for OpenAI Codex CLI."""

    # Keys that SCC always injects into the Codex config layer.
    # D040: force file-based auth caching so auth.json persists in the
    # provider volume (/home/agent/.codex/) across container restarts.
    _SCC_MANAGED_DEFAULTS: dict[str, Any] = {
        "cli_auth_credentials_store": "file",
    }

    def build_settings(
        self, config: dict[str, Any], *, path: Path = DEFAULT_SETTINGS_PATH
    ) -> AgentSettings:
        # D040: merge SCC-managed defaults *under* caller-supplied values
        # so that governed config can override if needed, but the file-based
        # auth store is always present when no explicit override exists.
        merged = {**self._SCC_MANAGED_DEFAULTS, **config}
        rendered = _serialize_toml(merged)
        return AgentSettings(rendered_bytes=rendered, path=path, suffix=".toml")

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        # SCC's container isolation is the hard enforcement boundary.
        # Interactive auth bootstrap happens before launch; the steady-state
        # container command is the real Codex TUI plus SCC's bypass flag.
        return AgentCommand(
            argv=list(build_codex_container_argv()),
            env={},
            workdir=settings.path.parent,
        )

    def describe(self) -> str:
        return "Codex"
