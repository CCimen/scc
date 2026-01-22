"""JSON mapping helpers for config explain output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...application.compute_effective_config import (
    BlockedItem,
    ConfigDecision,
    DelegationDenied,
    EffectiveConfig,
    MCPServer,
)
from ...core import personal_profiles
from ...json_output import build_envelope
from ...kinds import Kind


def build_config_explain_data(
    *,
    org_config: dict[str, Any],
    team_name: str,
    effective: EffectiveConfig,
    enforcement_status: list[dict[str, str]],
    warnings: list[str],
    workspace_path: Path,
) -> dict[str, Any]:
    """Build JSON-ready data for config explain output."""
    org_info = org_config.get("organization", {})
    profile = personal_profiles.load_personal_profile(workspace_path)

    return {
        "organization": {
            "name": org_info.get("name", "Unknown"),
            "id": org_info.get("id", ""),
        },
        "team": team_name,
        "enforcement": enforcement_status,
        "warnings": warnings,
        "effective": {
            "plugins": sorted(effective.plugins),
            "mcp_servers": [_serialize_mcp_server(server) for server in effective.mcp_servers],
            "network_policy": effective.network_policy,
            "session": {
                "timeout_hours": effective.session_config.timeout_hours,
                "auto_resume": effective.session_config.auto_resume,
            },
        },
        "decisions": [_serialize_decision(decision) for decision in effective.decisions],
        "blocked_items": [_serialize_blocked_item(item) for item in effective.blocked_items],
        "denied_additions": [
            _serialize_denied_addition(denied) for denied in effective.denied_additions
        ],
        "personal_profile": _serialize_personal_profile(profile),
    }


def build_config_explain_envelope(
    data: dict[str, Any], *, warnings: list[str] | None = None
) -> dict[str, Any]:
    """Build the JSON envelope for config explain output."""
    return build_envelope(Kind.CONFIG_EXPLAIN, data=data, warnings=warnings or [])


def _serialize_mcp_server(server: MCPServer) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": server.name, "type": server.type}
    if server.url:
        payload["url"] = server.url
    if server.command:
        payload["command"] = server.command
    if server.args:
        payload["args"] = server.args
    if server.env:
        payload["env"] = server.env
    if server.headers:
        payload["headers"] = server.headers
    return payload


def _serialize_decision(decision: ConfigDecision) -> dict[str, Any]:
    return {
        "field": decision.field,
        "value": decision.value,
        "reason": decision.reason,
        "source": decision.source,
    }


def _serialize_blocked_item(item: BlockedItem) -> dict[str, Any]:
    return {
        "item": item.item,
        "blocked_by": item.blocked_by,
        "source": item.source,
        "target_type": item.target_type,
    }


def _serialize_denied_addition(denied: DelegationDenied) -> dict[str, Any]:
    return {
        "item": denied.item,
        "requested_by": denied.requested_by,
        "reason": denied.reason,
        "target_type": denied.target_type,
    }


def _serialize_personal_profile(
    profile: personal_profiles.PersonalProfile | None,
) -> dict[str, Any]:
    if profile is None:
        return {}

    plugins = personal_profiles.extract_personal_plugins(profile)
    return {
        "repo": profile.repo_id,
        "plugins": sorted(plugins),
        "mcp": bool(profile.mcp),
    }
