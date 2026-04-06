"""Characterization tests for application/compute_effective_config.py.

Lock the current public API behavior of the config merge engine before
S02 surgery begins. Covers: pattern matching, delegation checks,
plugin/MCP filtering, network policy layering, session config merge,
and the full compute_effective_config pipeline.
"""

from __future__ import annotations

from scc_cli.application.compute_effective_config import EffectiveConfig as AppEffectiveConfig
from scc_cli.application.compute_effective_config import (
    compute_effective_config,
    is_mcp_allowed,
    is_network_mcp,
    is_plugin_allowed,
    is_project_delegated,
    is_team_delegated_for_mcp,
    is_team_delegated_for_plugins,
    match_blocked_mcp,
    matches_blocked,
    matches_blocked_plugin,
    matches_plugin_pattern,
    mcp_candidates,
    record_network_policy_decision,
    validate_stdio_server,
)
from scc_cli.core.enums import MCPServerType

# ═══════════════════════════════════════════════════════════════════════════════
# Pattern matching helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestMatchesBlocked:
    """matches_blocked: casefold fnmatch on item vs patterns."""

    def test_exact_match(self) -> None:
        assert matches_blocked("evil-plugin", ["evil-plugin"]) == "evil-plugin"

    def test_wildcard_match(self) -> None:
        assert matches_blocked("evil-plugin", ["evil-*"]) == "evil-*"

    def test_case_insensitive(self) -> None:
        assert matches_blocked("Evil-Plugin", ["evil-plugin"]) == "evil-plugin"

    def test_no_match_returns_none(self) -> None:
        assert matches_blocked("good-plugin", ["evil-*"]) is None

    def test_empty_patterns_returns_none(self) -> None:
        assert matches_blocked("anything", []) is None

    def test_whitespace_stripped(self) -> None:
        assert matches_blocked("  evil  ", ["evil"]) == "evil"


class TestMatchesPluginPattern:
    """matches_plugin_pattern: bare names match any marketplace."""

    def test_exact_ref_match(self) -> None:
        assert matches_plugin_pattern("tool@marketplace", "tool@marketplace") is True

    def test_bare_pattern_matches_any_marketplace(self) -> None:
        assert matches_plugin_pattern("tool@marketplace", "tool") is True

    def test_bare_pattern_wildcard(self) -> None:
        assert matches_plugin_pattern("my-tool@marketplace", "my-*") is True

    def test_no_match(self) -> None:
        assert matches_plugin_pattern("tool@marketplace", "other") is False

    def test_empty_ref_returns_false(self) -> None:
        assert matches_plugin_pattern("", "tool") is False

    def test_empty_pattern_returns_false(self) -> None:
        assert matches_plugin_pattern("tool@mp", "") is False


class TestIsPluginAllowed:
    """is_plugin_allowed: None means all allowed, empty means none allowed."""

    def test_none_allowlist_allows_all(self) -> None:
        assert is_plugin_allowed("anything@mp", None) is True

    def test_empty_allowlist_blocks_all(self) -> None:
        assert is_plugin_allowed("anything@mp", []) is False

    def test_matching_pattern_allows(self) -> None:
        assert is_plugin_allowed("tool@mp", ["tool"]) is True

    def test_non_matching_pattern_blocks(self) -> None:
        assert is_plugin_allowed("other@mp", ["tool"]) is False


class TestMatchesBlockedPlugin:
    """matches_blocked_plugin: plugin-aware pattern matching."""

    def test_blocked_by_pattern(self) -> None:
        assert matches_blocked_plugin("evil@mp", ["evil"]) == "evil"

    def test_not_blocked(self) -> None:
        assert matches_blocked_plugin("good@mp", ["evil"]) is None


class TestMcpCandidates:
    """mcp_candidates: collects name, url, domain, command for matching."""

    def test_all_fields(self) -> None:
        server = {
            "name": "my-mcp",
            "url": "https://example.com/api",
            "command": "/usr/bin/mcp",
        }
        candidates = mcp_candidates(server)
        assert "my-mcp" in candidates
        assert "https://example.com/api" in candidates
        assert "example.com" in candidates
        assert "/usr/bin/mcp" in candidates

    def test_empty_server(self) -> None:
        assert mcp_candidates({}) == []

    def test_name_only(self) -> None:
        candidates = mcp_candidates({"name": "simple"})
        assert candidates == ["simple"]


class TestIsMcpAllowed:
    """is_mcp_allowed: checks all candidates against allowed patterns."""

    def test_none_allows_all(self) -> None:
        assert is_mcp_allowed({"name": "anything"}, None) is True

    def test_empty_blocks_all(self) -> None:
        assert is_mcp_allowed({"name": "anything"}, []) is False

    def test_name_match_allows(self) -> None:
        assert is_mcp_allowed({"name": "my-mcp"}, ["my-*"]) is True

    def test_no_match_blocks(self) -> None:
        assert is_mcp_allowed({"name": "other"}, ["my-*"]) is False


class TestMatchBlockedMcp:
    """match_blocked_mcp: returns matching pattern for blocked server."""

    def test_blocked_by_name(self) -> None:
        assert match_blocked_mcp({"name": "evil-mcp"}, ["evil-*"]) == "evil-*"

    def test_blocked_by_url(self) -> None:
        result = match_blocked_mcp({"name": "ok", "url": "https://evil.com"}, ["*evil*"])
        assert result == "*evil*"

    def test_not_blocked(self) -> None:
        assert match_blocked_mcp({"name": "good"}, ["evil-*"]) is None


class TestIsNetworkMcp:
    """is_network_mcp: SSE and HTTP require network."""

    def test_sse_requires_network(self) -> None:
        assert is_network_mcp({"type": MCPServerType.SSE}) is True

    def test_http_requires_network(self) -> None:
        assert is_network_mcp({"type": MCPServerType.HTTP}) is True

    def test_stdio_no_network(self) -> None:
        assert is_network_mcp({"type": MCPServerType.STDIO}) is False

    def test_missing_type_no_network(self) -> None:
        assert is_network_mcp({}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Delegation checks
# ═══════════════════════════════════════════════════════════════════════════════


class TestDelegation:
    """Delegation checks for plugins, MCP, and project overrides."""

    def test_team_delegated_for_plugins_when_allowed(self) -> None:
        org = {"delegation": {"teams": {"allow_additional_plugins": ["team-*"]}}}
        assert is_team_delegated_for_plugins(org, "team-alpha") is True

    def test_team_not_delegated_for_plugins(self) -> None:
        org = {"delegation": {"teams": {"allow_additional_plugins": []}}}
        assert is_team_delegated_for_plugins(org, "team-alpha") is False

    def test_team_delegated_for_plugins_no_team_name(self) -> None:
        org = {"delegation": {"teams": {"allow_additional_plugins": ["*"]}}}
        assert is_team_delegated_for_plugins(org, None) is False

    def test_team_delegated_for_mcp_when_allowed(self) -> None:
        org = {"delegation": {"teams": {"allow_additional_mcp_servers": ["team-*"]}}}
        assert is_team_delegated_for_mcp(org, "team-alpha") is True

    def test_team_not_delegated_for_mcp(self) -> None:
        org = {"delegation": {"teams": {"allow_additional_mcp_servers": []}}}
        assert is_team_delegated_for_mcp(org, "team-alpha") is False

    def test_project_delegated_when_fully_enabled(self) -> None:
        org = {
            "delegation": {"projects": {"inherit_team_delegation": True}},
            "profiles": {"team-a": {"delegation": {"allow_project_overrides": True}}},
        }
        allowed, reason = is_project_delegated(org, "team-a")
        assert allowed is True
        assert reason == ""

    def test_project_not_delegated_org_disabled(self) -> None:
        org = {"delegation": {"projects": {"inherit_team_delegation": False}}}
        allowed, reason = is_project_delegated(org, "team-a")
        assert allowed is False
        assert "inherit_team_delegation" in reason

    def test_project_not_delegated_team_disabled(self) -> None:
        org = {
            "delegation": {"projects": {"inherit_team_delegation": True}},
            "profiles": {"team-a": {"delegation": {"allow_project_overrides": False}}},
        }
        allowed, reason = is_project_delegated(org, "team-a")
        assert allowed is False
        assert "allow_project_overrides" in reason

    def test_project_not_delegated_no_team(self) -> None:
        org = {}
        allowed, reason = is_project_delegated(org, None)
        assert allowed is False


# ═══════════════════════════════════════════════════════════════════════════════
# validate_stdio_server
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateStdioServer:
    """stdio MCP validation gates: feature gate, absolute path, prefix allowlist."""

    def test_blocked_when_not_enabled(self) -> None:
        result = validate_stdio_server(
            {"command": "/usr/bin/mcp", "type": "stdio"},
            {"security": {"allow_stdio_mcp": False}},
        )
        assert result.blocked is True
        assert "disabled" in result.reason

    def test_blocked_when_no_security_section(self) -> None:
        result = validate_stdio_server({"command": "/usr/bin/mcp"}, {})
        assert result.blocked is True

    def test_blocked_for_relative_path(self) -> None:
        result = validate_stdio_server(
            {"command": "relative/mcp"},
            {"security": {"allow_stdio_mcp": True}},
        )
        assert result.blocked is True
        assert "absolute" in result.reason

    def test_allowed_absolute_path_no_prefix_check(self) -> None:
        result = validate_stdio_server(
            {"command": "/usr/bin/mcp"},
            {"security": {"allow_stdio_mcp": True}},
        )
        assert result.blocked is False

    def test_warning_for_nonexistent_host_path(self) -> None:
        result = validate_stdio_server(
            {"command": "/nonexistent/path/to/mcp"},
            {"security": {"allow_stdio_mcp": True}},
        )
        assert result.blocked is False
        assert any("not found" in w.lower() for w in result.warnings)


# ═══════════════════════════════════════════════════════════════════════════════
# record_network_policy_decision
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordNetworkPolicyDecision:
    """record_network_policy_decision replaces any prior network_policy decision."""

    def test_adds_decision(self) -> None:
        result = AppEffectiveConfig()
        record_network_policy_decision(result, policy="open", reason="test", source="test")
        network_decisions = [d for d in result.decisions if d.field == "network_policy"]
        assert len(network_decisions) == 1
        assert network_decisions[0].value == "open"

    def test_replaces_prior_decision(self) -> None:
        result = AppEffectiveConfig()
        record_network_policy_decision(result, policy="first", reason="a", source="a")
        record_network_policy_decision(result, policy="second", reason="b", source="b")
        network_decisions = [d for d in result.decisions if d.field == "network_policy"]
        assert len(network_decisions) == 1
        assert network_decisions[0].value == "second"


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_config — full pipeline
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectiveConfig:
    """End-to-end merge: org defaults → team overrides → project overrides."""

    def test_empty_org_returns_empty_result(self) -> None:
        result = compute_effective_config({}, None)
        assert len(result.plugins) == 0
        assert len(result.mcp_servers) == 0
        assert result.network_policy is None

    def test_org_defaults_populate_plugins(self) -> None:
        org = {"defaults": {"enabled_plugins": ["plugin-a@mp", "plugin-b@mp"]}}
        result = compute_effective_config(org, None)
        assert "plugin-a@mp" in result.plugins
        assert "plugin-b@mp" in result.plugins

    def test_security_blocked_plugins_removed(self) -> None:
        org = {
            "defaults": {"enabled_plugins": ["good@mp", "evil@mp"]},
            "security": {"blocked_plugins": ["evil*"]},
        }
        result = compute_effective_config(org, None)
        assert "good@mp" in result.plugins
        assert "evil@mp" not in result.plugins
        assert any(b.item == "evil@mp" for b in result.blocked_items)

    def test_org_default_network_policy(self) -> None:
        org = {"defaults": {"network_policy": "open"}}
        result = compute_effective_config(org, None)
        assert result.network_policy == "open"

    def test_team_overrides_network_policy_when_more_restrictive(self) -> None:
        org = {
            "defaults": {"network_policy": "open"},
            "profiles": {"team-a": {"network_policy": "locked-down-web"}},
        }
        result = compute_effective_config(org, "team-a")
        assert result.network_policy == "locked-down-web"

    def test_team_plugins_added_when_delegated(self) -> None:
        org = {
            "delegation": {"teams": {"allow_additional_plugins": ["team-a"]}},
            "profiles": {"team-a": {"additional_plugins": ["extra@mp"]}},
        }
        result = compute_effective_config(org, "team-a")
        assert "extra@mp" in result.plugins

    def test_team_plugins_denied_when_not_delegated(self) -> None:
        org = {
            "delegation": {"teams": {"allow_additional_plugins": []}},
            "profiles": {"team-a": {"additional_plugins": ["extra@mp"]}},
        }
        result = compute_effective_config(org, "team-a")
        assert "extra@mp" not in result.plugins
        assert any(d.item == "extra@mp" for d in result.denied_additions)

    def test_project_plugins_added_when_fully_delegated(self) -> None:
        org = {
            "delegation": {
                "teams": {"allow_additional_plugins": ["team-a"]},
                "projects": {"inherit_team_delegation": True},
            },
            "profiles": {"team-a": {"delegation": {"allow_project_overrides": True}}},
        }
        project = {"additional_plugins": ["proj-plugin@mp"]}
        result = compute_effective_config(org, "team-a", project_config=project)
        assert "proj-plugin@mp" in result.plugins

    def test_project_plugins_denied_when_no_delegation(self) -> None:
        org = {"delegation": {"projects": {"inherit_team_delegation": False}}}
        project = {"additional_plugins": ["proj-plugin@mp"]}
        result = compute_effective_config(org, "team-a", project_config=project)
        assert "proj-plugin@mp" not in result.plugins
        assert any(d.item == "proj-plugin@mp" for d in result.denied_additions)

    def test_session_config_org_default(self) -> None:
        org = {"defaults": {"session": {"timeout_hours": 8, "auto_resume": True}}}
        result = compute_effective_config(org, None)
        assert result.session_config.timeout_hours == 8
        assert result.session_config.auto_resume is True

    def test_session_config_team_override(self) -> None:
        org = {
            "defaults": {"session": {"timeout_hours": 8}},
            "profiles": {"team-a": {"session": {"timeout_hours": 4}}},
        }
        result = compute_effective_config(org, "team-a")
        assert result.session_config.timeout_hours == 4

    def test_team_mcp_server_added_when_delegated(self) -> None:
        org = {
            "delegation": {"teams": {"allow_additional_mcp_servers": ["team-a"]}},
            "profiles": {
                "team-a": {
                    "additional_mcp_servers": [
                        {
                            "name": "my-mcp",
                            "type": MCPServerType.SSE,
                            "url": "https://mcp.example.com",
                        }
                    ]
                }
            },
        }
        result = compute_effective_config(org, "team-a")
        assert any(s.name == "my-mcp" for s in result.mcp_servers)

    def test_team_mcp_server_denied_when_not_delegated(self) -> None:
        org = {
            "delegation": {"teams": {"allow_additional_mcp_servers": []}},
            "profiles": {"team-a": {"additional_mcp_servers": [{"name": "my-mcp", "type": "sse"}]}},
        }
        result = compute_effective_config(org, "team-a")
        assert not any(s.name == "my-mcp" for s in result.mcp_servers)

    def test_disabled_plugins_excluded(self) -> None:
        org = {
            "defaults": {
                "enabled_plugins": ["a@mp", "b@mp"],
                "disabled_plugins": ["b@mp"],
            }
        }
        result = compute_effective_config(org, None)
        assert "a@mp" in result.plugins
        assert "b@mp" not in result.plugins

    def test_decisions_tracked(self) -> None:
        org = {"defaults": {"enabled_plugins": ["p@mp"]}}
        result = compute_effective_config(org, None)
        plugin_decisions = [d for d in result.decisions if d.field == "plugins"]
        assert len(plugin_decisions) == 1
        assert plugin_decisions[0].value == "p@mp"
        assert plugin_decisions[0].source == "org.defaults"
