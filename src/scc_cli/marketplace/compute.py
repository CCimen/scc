"""
Effective plugin computation for team profiles.

This module provides the core plugin resolution logic:
- BlockedPlugin: Dataclass for blocked plugins with reason/pattern
- EffectivePlugins: Result of computation with enabled/blocked/disabled sets
- compute_effective_plugins(): Pure function for plugin resolution

Order of Operations:
    1. Normalize defaults.enabled_plugins to canonical form
    2. Remove defaults.disabled_plugins from defaults
    3. Add team additions if delegated + allowlisted
    4. Apply security.blocked_plugins (final security gate)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from scc_cli.marketplace.normalize import (
    matches_pattern,
    normalize_plugin,
)

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import OrganizationConfig, TeamConfig


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class TeamNotFoundError(KeyError):
    """Raised when requested team profile is not found in config."""

    def __init__(self, team_id: str, available_teams: list[str]) -> None:
        self.team_id = team_id
        self.available_teams = available_teams
        teams_str = ", ".join(sorted(available_teams)) if available_teams else "none"
        super().__init__(
            f"Team '{team_id}' not found in organization config. Available teams: {teams_str}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BlockedPlugin:
    """A plugin blocked by security policy.

    Attributes:
        plugin_id: The canonical plugin reference (name@marketplace)
        reason: Human-readable explanation from security config
        pattern: The glob pattern that matched this plugin
    """

    plugin_id: str
    reason: str
    pattern: str


@dataclass
class EffectivePlugins:
    """Result of computing effective plugins for a team.

    Attributes:
        enabled: Set of enabled plugin references (name@marketplace)
        blocked: List of BlockedPlugin with reasons
        not_allowed: Plugins rejected by allowed_plugins filter or delegation
        disabled: Plugins removed by disabled_plugins patterns
        extra_marketplaces: List of marketplace IDs to enable
    """

    enabled: set[str] = field(default_factory=set)
    blocked: list[BlockedPlugin] = field(default_factory=list)
    not_allowed: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    extra_marketplaces: list[str] = field(default_factory=list)


def _team_matches_patterns(team_id: str, patterns: list[str]) -> bool:
    """Check if team matches any delegation pattern."""
    if not patterns:
        return False
    for pattern in patterns:
        if pattern == "*" or matches_pattern(team_id, pattern):
            return True
    return False


def _is_plugin_allowed(plugin_ref: str, allowed_plugins: list[str] | None) -> bool:
    """Check if plugin is allowed by allowlist semantics."""
    if allowed_plugins is None:
        return True
    if not allowed_plugins:
        return False
    for pattern in allowed_plugins:
        if matches_pattern(plugin_ref, pattern):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Computation
# ─────────────────────────────────────────────────────────────────────────────


def compute_effective_plugins(
    config: OrganizationConfig,
    team_id: str,
) -> EffectivePlugins:
    """Compute effective plugins for a team based on organization config.

    Order of operations:
        1. Normalize defaults.enabled_plugins
        2. Remove defaults.disabled_plugins from defaults
        3. Add team additional_plugins if delegated + allowed
        4. Apply security.blocked_plugins (final gate)
    """
    if team_id not in config.profiles:
        raise TeamNotFoundError(
            team_id=team_id,
            available_teams=list(config.profiles.keys()),
        )

    profile = config.profiles[team_id]
    defaults = config.defaults
    security = config.security
    org_marketplaces = config.marketplaces or {}

    result = EffectivePlugins()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Normalize defaults.enabled_plugins
    # ─────────────────────────────────────────────────────────────────────────

    default_plugins: set[str] = set()
    for plugin_ref in defaults.enabled_plugins:
        normalized = normalize_plugin(plugin_ref, org_marketplaces)
        default_plugins.add(normalized)

    disabled_patterns = defaults.disabled_plugins or []
    for plugin in list(default_plugins):
        for pattern in disabled_patterns:
            if matches_pattern(plugin, pattern):
                default_plugins.discard(plugin)
                result.disabled.append(plugin)
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Add additional plugins (delegation + allowlist)
    # ─────────────────────────────────────────────────────────────────────────

    additional_plugins: set[str] = set()
    for plugin_ref in profile.additional_plugins:
        normalized = normalize_plugin(plugin_ref, org_marketplaces)
        additional_plugins.add(normalized)

    merged_plugins = default_plugins.copy()

    team_can_add = _team_matches_patterns(
        team_id,
        config.delegation.teams.allow_additional_plugins,
    )

    for plugin in additional_plugins:
        if not team_can_add:
            result.not_allowed.append(plugin)
            continue
        if not _is_plugin_allowed(plugin, defaults.allowed_plugins):
            result.not_allowed.append(plugin)
            continue
        merged_plugins.add(plugin)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Apply security.blocked_plugins (final security gate)
    # ─────────────────────────────────────────────────────────────────────────

    blocked_patterns = security.blocked_plugins
    for plugin in list(merged_plugins):
        for pattern in blocked_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.blocked.append(
                    BlockedPlugin(
                        plugin_id=plugin,
                        reason="Blocked by security policy",
                        pattern=pattern,
                    )
                )
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Collect extra marketplaces
    # ─────────────────────────────────────────────────────────────────────────

    result.extra_marketplaces = list({*defaults.extra_marketplaces})

    result.enabled = merged_plugins
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Federated Computation
# ─────────────────────────────────────────────────────────────────────────────


def compute_effective_plugins_federated(
    config: OrganizationConfig,
    team_id: str,
    team_config: TeamConfig,
) -> EffectivePlugins:
    """Compute effective plugins for a federated team.

    Order of operations:
        1. Start with org defaults.enabled_plugins
        2. Add team config enabled_plugins (delegation + allowlist)
        3. Apply team config disabled_plugins patterns
        4. Apply org defaults.disabled_plugins patterns
        5. Apply org security.blocked_plugins (ALWAYS enforced)
    """
    if team_id not in config.profiles:
        raise TeamNotFoundError(
            team_id=team_id,
            available_teams=list(config.profiles.keys()),
        )

    defaults = config.defaults
    security = config.security
    org_marketplaces = config.marketplaces or {}

    result = EffectivePlugins()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Start with org defaults.enabled_plugins
    # ─────────────────────────────────────────────────────────────────────────

    merged_plugins: set[str] = set()
    for plugin_ref in defaults.enabled_plugins:
        normalized = normalize_plugin(plugin_ref, org_marketplaces)
        merged_plugins.add(normalized)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Add team config enabled_plugins (delegation + allowlist)
    # ─────────────────────────────────────────────────────────────────────────

    team_can_add = _team_matches_patterns(
        team_id,
        config.delegation.teams.allow_additional_plugins,
    )

    for plugin_ref in team_config.enabled_plugins:
        normalized = normalize_plugin(plugin_ref, org_marketplaces)
        if not team_can_add:
            result.not_allowed.append(normalized)
            continue
        if _is_plugin_allowed(normalized, defaults.allowed_plugins):
            merged_plugins.add(normalized)
        else:
            result.not_allowed.append(normalized)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Apply team config disabled_plugins patterns
    # ─────────────────────────────────────────────────────────────────────────

    team_disabled_patterns = team_config.disabled_plugins or []
    for plugin in list(merged_plugins):
        for pattern in team_disabled_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.disabled.append(plugin)
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Apply org defaults.disabled_plugins patterns
    # ─────────────────────────────────────────────────────────────────────────

    defaults_disabled_patterns = defaults.disabled_plugins or []
    for plugin in list(merged_plugins):
        for pattern in defaults_disabled_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.disabled.append(plugin)
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Apply org security.blocked_plugins (ALWAYS enforced)
    # ─────────────────────────────────────────────────────────────────────────

    blocked_patterns = security.blocked_plugins
    for plugin in list(merged_plugins):
        for pattern in blocked_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.blocked.append(
                    BlockedPlugin(
                        plugin_id=plugin,
                        reason="Blocked by security policy",
                        pattern=pattern,
                    )
                )
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Collect extra marketplaces (defaults only)
    # ─────────────────────────────────────────────────────────────────────────

    result.extra_marketplaces = list({*defaults.extra_marketplaces})

    result.enabled = merged_plugins
    return result
