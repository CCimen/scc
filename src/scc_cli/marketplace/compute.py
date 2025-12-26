"""
Effective plugin computation for team profiles.

This module provides the core plugin resolution logic:
- BlockedPlugin: Dataclass for blocked plugins with reason/pattern
- EffectivePlugins: Result of computation with enabled/blocked/disabled sets
- compute_effective_plugins(): Pure function for plugin resolution

Order of Operations:
    1. Normalize all plugin references to canonical form
    2. Merge defaults.enabled_plugins + profile.additional_plugins
    3. Apply profile.disabled_plugins patterns (removes from merged)
    4. Apply profile.allowed_plugins filter (for additional only)
    5. Apply security.blocked_plugins (final security gate)
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
        not_allowed: Plugins rejected by allowed_plugins filter
        disabled: Plugins removed by disabled_plugins patterns
        extra_marketplaces: List of marketplace IDs to enable
    """

    enabled: set[str] = field(default_factory=set)
    blocked: list[BlockedPlugin] = field(default_factory=list)
    not_allowed: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    extra_marketplaces: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Computation
# ─────────────────────────────────────────────────────────────────────────────


def compute_effective_plugins(
    config: OrganizationConfig,
    team_id: str,
) -> EffectivePlugins:
    """Compute effective plugins for a team based on organization config.

    This is a pure function that determines which plugins a team member
    can use, applying all governance rules in the correct order.

    Order of operations:
        1. Normalize all plugin references
        2. Merge defaults + profile additional plugins
        3. Apply disabled_plugins patterns
        4. Apply allowed_plugins filter (additional only)
        5. Apply security.blocked_plugins

    Args:
        config: Organization configuration with profiles and security
        team_id: The profile/team ID to compute plugins for

    Returns:
        EffectivePlugins with enabled, blocked, disabled, and marketplace info

    Raises:
        TeamNotFoundError: If team_id is not in config.profiles
        AmbiguousMarketplaceError: If bare plugin name with 2+ org marketplaces
    """
    # Validate team exists
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
    # Step 1: Collect all plugins (normalized)
    # ─────────────────────────────────────────────────────────────────────────

    # Normalize defaults.enabled_plugins
    default_plugins: set[str] = set()
    if defaults and defaults.enabled_plugins:
        for plugin_ref in defaults.enabled_plugins:
            normalized = normalize_plugin(plugin_ref, org_marketplaces)
            default_plugins.add(normalized)

    # Normalize profile.additional_plugins
    additional_plugins: set[str] = set()
    if profile.additional_plugins:
        for plugin_ref in profile.additional_plugins:
            normalized = normalize_plugin(plugin_ref, org_marketplaces)
            additional_plugins.add(normalized)

    # Start with defaults as base
    merged_plugins = default_plugins.copy()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Apply disabled_plugins patterns (remove from merged)
    # ─────────────────────────────────────────────────────────────────────────

    disabled_patterns = profile.disabled_plugins or []
    for plugin in list(merged_plugins):
        for pattern in disabled_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.disabled.append(plugin)
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Apply allowed_plugins filter to additional plugins
    # ─────────────────────────────────────────────────────────────────────────

    # allowed_plugins semantics:
    # - None: allow all additional plugins
    # - []: block all additional plugins
    # - ["x", "y"]: only allow x and y from additional
    allowed_plugins = profile.allowed_plugins

    for plugin in additional_plugins:
        # Check if already disabled
        if plugin in result.disabled:
            continue

        if allowed_plugins is None:
            # Allow all
            merged_plugins.add(plugin)
        elif plugin in allowed_plugins:
            # In allowlist
            merged_plugins.add(plugin)
        else:
            # Not in allowlist (includes empty list case)
            result.not_allowed.append(plugin)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Apply security.blocked_plugins (final security gate)
    # ─────────────────────────────────────────────────────────────────────────

    blocked_patterns = security.blocked_plugins if security else []
    blocked_reason = security.blocked_reason if security else "Blocked by security policy"

    for plugin in list(merged_plugins):
        for pattern in blocked_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.blocked.append(
                    BlockedPlugin(
                        plugin_id=plugin,
                        reason=blocked_reason,
                        pattern=pattern,
                    )
                )
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Collect extra marketplaces
    # ─────────────────────────────────────────────────────────────────────────

    marketplace_set: set[str] = set()

    if defaults and defaults.extra_marketplaces:
        marketplace_set.update(defaults.extra_marketplaces)

    if profile.extra_marketplaces:
        marketplace_set.update(profile.extra_marketplaces)

    result.extra_marketplaces = list(marketplace_set)

    # ─────────────────────────────────────────────────────────────────────────
    # Final result
    # ─────────────────────────────────────────────────────────────────────────

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
    """Compute effective plugins for a federated team (6-step precedence).

    This handles teams with external config_source. The key difference from
    inline teams is that federated teams:
    - Use TeamConfig.enabled_plugins instead of profile.additional_plugins
    - Use TeamConfig.disabled_plugins for team-level filtering
    - Are NOT subject to allowed_plugins restrictions (that's for inline only)
    - Are ALWAYS subject to org security.blocked_plugins

    Order of operations (6-step precedence):
        1. Start with org defaults.enabled_plugins
        2. Add team config enabled_plugins
        3. Apply team config disabled_plugins patterns
        4. Apply org defaults.disabled_plugins patterns
        5. SKIP allowed_plugins (federated teams not subject to inline restrictions)
        6. Apply org security.blocked_plugins (ALWAYS enforced)

    Args:
        config: Organization configuration with profiles and security
        team_id: The profile/team ID to compute plugins for
        team_config: External team configuration fetched from config_source

    Returns:
        EffectivePlugins with enabled, blocked, disabled, and marketplace info

    Raises:
        TeamNotFoundError: If team_id is not in config.profiles
    """
    # Validate team exists in org config
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
    # Step 1: Start with org defaults.enabled_plugins
    # ─────────────────────────────────────────────────────────────────────────

    merged_plugins: set[str] = set()
    if defaults and defaults.enabled_plugins:
        for plugin_ref in defaults.enabled_plugins:
            normalized = normalize_plugin(plugin_ref, org_marketplaces)
            merged_plugins.add(normalized)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Add team config enabled_plugins
    # ─────────────────────────────────────────────────────────────────────────

    if team_config.enabled_plugins:
        for plugin_ref in team_config.enabled_plugins:
            normalized = normalize_plugin(plugin_ref, org_marketplaces)
            merged_plugins.add(normalized)

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

    org_disabled_patterns = (defaults.disabled_plugins or []) if defaults else []
    for plugin in list(merged_plugins):
        for pattern in org_disabled_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.disabled.append(plugin)
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: SKIP allowed_plugins (federated teams not subject to this)
    # ─────────────────────────────────────────────────────────────────────────

    # For federated teams, we do NOT apply the allowed_plugins filter.
    # This restriction is only for inline teams using additional_plugins.
    # Federated teams have their own governance via trust grants.

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Apply org security.blocked_plugins (ALWAYS enforced)
    # ─────────────────────────────────────────────────────────────────────────

    blocked_patterns = security.blocked_plugins if security else []
    blocked_reason = security.blocked_reason if security else "Blocked by security policy"

    for plugin in list(merged_plugins):
        for pattern in blocked_patterns:
            if matches_pattern(plugin, pattern):
                merged_plugins.discard(plugin)
                result.blocked.append(
                    BlockedPlugin(
                        plugin_id=plugin,
                        reason=blocked_reason,
                        pattern=pattern,
                    )
                )
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Collect extra marketplaces (from defaults and profile only)
    # ─────────────────────────────────────────────────────────────────────────

    # Note: TeamConfig doesn't have extra_marketplaces - it defines
    # actual marketplace sources via its 'marketplaces' dict instead.
    marketplace_set: set[str] = set()

    if defaults and defaults.extra_marketplaces:
        marketplace_set.update(defaults.extra_marketplaces)

    if profile.extra_marketplaces:
        marketplace_set.update(profile.extra_marketplaces)

    result.extra_marketplaces = list(marketplace_set)

    # ─────────────────────────────────────────────────────────────────────────
    # Final result
    # ─────────────────────────────────────────────────────────────────────────

    result.enabled = merged_plugins
    return result
