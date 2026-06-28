"""Typed models produced by effective configuration computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeAlias

from scc_cli.core.enums import TargetType

ConfigTraceValue: TypeAlias = str | int | bool | None


@dataclass
class ConfigDecision:
    """Tracks where a config value came from."""

    field: str
    value: ConfigTraceValue
    reason: str
    source: str


@dataclass
class IgnoredPolicyChange:
    """Tracks a requested config policy value that was rejected."""

    field: str
    requested_value: ConfigTraceValue
    effective_value: ConfigTraceValue
    source: str
    reason: str


@dataclass
class BlockedItem:
    """Tracks an item blocked by security pattern."""

    item: str
    blocked_by: str
    source: str
    target_type: str = TargetType.PLUGIN


@dataclass
class DelegationDenied:
    """Tracks an addition denied due to delegation rules."""

    item: str
    requested_by: str
    reason: str
    target_type: str = TargetType.PLUGIN


@dataclass
class MCPServer:
    """Represents an MCP server configuration."""

    name: str
    type: str
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None


@dataclass
class SessionConfig:
    """Session configuration."""

    timeout_hours: int | None = None
    auto_resume: bool | None = None


@dataclass
class EffectiveConfig:
    """Computed configuration after org, team, and project merge."""

    plugins: set[str] = field(default_factory=set)
    mcp_servers: list[MCPServer] = field(default_factory=list)
    network_policy: str | None = None
    session_config: SessionConfig = field(default_factory=SessionConfig)
    decisions: list[ConfigDecision] = field(default_factory=list)
    blocked_items: list[BlockedItem] = field(default_factory=list)
    denied_additions: list[DelegationDenied] = field(default_factory=list)
    ignored_policy_changes: list[IgnoredPolicyChange] = field(default_factory=list)


@dataclass
class StdioValidationResult:
    """Result of validating a stdio MCP server configuration."""

    blocked: bool
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
