"""Effective config resolution for team profiles (Phase 2: Federation).

This module provides:
- EffectiveConfig: Complete resolved configuration for a team
- ConfigFetchError: Error when fetching federated team config fails
- resolve_effective_config(): Main orchestrator (T2a-18, to be implemented)

EffectiveConfig serves as the unified result type for both inline and federated
team configurations, providing backwards compatibility via to_phase1_format().

Design Decision:
    EffectiveConfig wraps the plugin computation results (from compute.py) with
    additional metadata about the configuration source. This allows the CLI to
    display federated vs inline status, version info, and trust state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from scc_cli.marketplace.compute import (
    BlockedPlugin,
    EffectivePlugins,
    compute_effective_plugins,
    compute_effective_plugins_federated,
)
from scc_cli.marketplace.team_fetch import fetch_team_config_with_fallback
from scc_cli.marketplace.trust import TrustViolationError, validate_team_config_trust

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import (
        ConfigSource,
        MarketplaceSource,
        OrganizationConfig,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class ConfigFetchError(Exception):
    """Error when fetching federated team configuration fails.

    Provides structured error information with remediation hints.
    """

    def __init__(
        self,
        team_id: str,
        source_type: str,
        source_url: str,
        error: str,
    ) -> None:
        self.team_id = team_id
        self.source_type = source_type
        self.source_url = source_url
        self.error = error

        # Build message with remediation hints
        remediation = _get_fetch_remediation(source_type, error)
        message = (
            f"Failed to fetch config for team '{team_id}' from {source_type} "
            f"source ({source_url}): {error}"
        )
        if remediation:
            message += f" {remediation}"

        super().__init__(message)


def _get_fetch_remediation(source_type: str, error: str) -> str:
    """Get remediation hint based on source type and error pattern."""
    error_lower = error.lower()

    # Network issues
    if "network" in error_lower or "connection" in error_lower:
        return "Try 'scc org update --team <name>' to refresh when connected."

    # Cache expired
    if "max_stale_age" in error_lower or "expired" in error_lower:
        return "The cached config has expired. Connect to network to refresh."

    # Git/GitHub specific
    if source_type in ("github", "git"):
        if "clone" in error_lower or "repository" in error_lower:
            return "Check repository access permissions and URL."
        if "branch" in error_lower:
            return "Verify the branch name exists in the repository."
        if "path" in error_lower or "not found" in error_lower:
            return "Check that team-config.json exists at the specified path."

    # URL specific
    if source_type == "url":
        if "401" in error or "unauthorized" in error_lower:
            return "Add authentication headers to config_source."
        if "403" in error or "forbidden" in error_lower:
            return "Check access permissions for the config URL."
        if "404" in error or "not found" in error_lower:
            return "Verify the config URL is correct."

    # Generic fallback
    return "Run 'scc org update --team <name>' to retry fetching."


# ─────────────────────────────────────────────────────────────────────────────
# EffectiveConfig Dataclass
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EffectiveConfig:
    """Complete resolved configuration for a team.

    This is the unified result type for both inline and federated team
    configurations. It contains all the information needed to:
    - Launch Claude Code with the correct plugins
    - Display status information to the user
    - Validate security compliance

    For backwards compatibility, use to_phase1_format() to get the
    (EffectivePlugins, marketplaces) tuple expected by Phase 1 code.

    Attributes:
        team_id: Team/profile identifier
        is_federated: True if config came from external source
        enabled_plugins: Set of enabled plugin references (name@marketplace)
        config_source: External config source (if federated)
        config_commit_sha: Git commit SHA (for git/github sources)
        config_etag: HTTP ETag (for URL sources)
        blocked_plugins: Plugins blocked by security policy
        disabled_plugins: Plugins removed by disabled_plugins patterns
        not_allowed_plugins: Plugins rejected by allowed_plugins filter
        marketplaces: Effective marketplace sources
        extra_marketplaces: Additional marketplace IDs to enable
    """

    # Required fields
    team_id: str
    is_federated: bool
    enabled_plugins: set[str]

    # Optional federation metadata
    config_source: ConfigSource | None = None
    config_commit_sha: str | None = None
    config_etag: str | None = None

    # Cache status (T2b-03: cached configs validated against current org security)
    used_cached_config: bool = False
    cache_is_stale: bool = False
    staleness_warning: str | None = None

    # Plugin filtering results
    blocked_plugins: list[BlockedPlugin] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)
    not_allowed_plugins: list[str] = field(default_factory=list)

    # Marketplace configuration
    marketplaces: dict[str, MarketplaceSource] = field(default_factory=dict)
    extra_marketplaces: list[str] = field(default_factory=list)

    # ─────────────────────────────────────────────────────────────────────────
    # Computed Properties
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def has_security_violations(self) -> bool:
        """Check if any plugins were blocked by security policy.

        Returns:
            True if blocked_plugins is non-empty
        """
        return len(self.blocked_plugins) > 0

    @property
    def plugin_count(self) -> int:
        """Get total number of enabled plugins.

        Returns:
            Count of enabled plugins
        """
        return len(self.enabled_plugins)

    @property
    def source_description(self) -> str:
        """Get human-readable description of config source.

        Returns:
            'inline' for non-federated, or source URL for federated
        """
        if not self.is_federated or self.config_source is None:
            return "inline"

        # Import here to avoid circular imports
        from scc_cli.marketplace.schema import (
            ConfigSourceGit,
            ConfigSourceGitHub,
            ConfigSourceURL,
        )

        if isinstance(self.config_source, ConfigSourceGitHub):
            return f"github.com/{self.config_source.owner}/{self.config_source.repo}"
        elif isinstance(self.config_source, ConfigSourceGit):
            # Normalize git URL for display
            url = self.config_source.url
            if url.startswith("https://"):
                url = url[8:]
            elif url.startswith("git@"):
                url = url[4:].replace(":", "/", 1)
            if url.endswith(".git"):
                url = url[:-4]
            return url
        elif isinstance(self.config_source, ConfigSourceURL):
            # Strip protocol for display
            url = self.config_source.url
            if url.startswith("https://"):
                url = url[8:]
            return url
        else:
            return "unknown"

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1 Compatibility
    # ─────────────────────────────────────────────────────────────────────────

    def to_phase1_format(self) -> tuple[EffectivePlugins, dict[str, MarketplaceSource]]:
        """Convert to Phase 1 format for backwards compatibility.

        This adapter method allows EffectiveConfig to work with existing
        Phase 1 code that expects:
        - EffectivePlugins for plugin computation results
        - dict[str, MarketplaceSource] for marketplace configuration

        Returns:
            Tuple of (EffectivePlugins, marketplaces dict)
        """
        plugins = EffectivePlugins(
            enabled=self.enabled_plugins,
            blocked=self.blocked_plugins,
            not_allowed=self.not_allowed_plugins,
            disabled=self.disabled_plugins,
            extra_marketplaces=self.extra_marketplaces,
        )

        return (plugins, self.marketplaces)


# ─────────────────────────────────────────────────────────────────────────────
# Resolution Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def resolve_effective_config(
    config: OrganizationConfig,
    team_id: str,
) -> EffectiveConfig:
    """Resolve effective configuration for a team (inline or federated).

    This is the main orchestrator for Phase 2 configuration resolution.
    It determines whether a team uses inline or federated configuration
    and applies the appropriate resolution strategy.

    For inline teams (no config_source):
        - Uses compute_effective_plugins() from compute.py
        - Returns EffectiveConfig with is_federated=False

    For federated teams (has config_source):
        - Fetches external team config via fetch_team_config()
        - Uses compute_effective_plugins_federated() from compute.py
        - Returns EffectiveConfig with is_federated=True and metadata

    Args:
        config: Organization configuration with profiles and security
        team_id: The profile/team ID to resolve plugins for

    Returns:
        EffectiveConfig with complete resolved configuration

    Raises:
        TeamNotFoundError: If team_id is not in config.profiles
        RuntimeError: If federated fetch fails
    """
    # Import here to avoid circular imports
    # Validate team exists (this also raises TeamNotFoundError if missing)
    from scc_cli.marketplace.compute import TeamNotFoundError
    from scc_cli.marketplace.schema import TeamConfig

    if team_id not in config.profiles:
        raise TeamNotFoundError(
            team_id=team_id,
            available_teams=list(config.profiles.keys()),
        )

    profile = config.profiles[team_id]
    org_marketplaces = config.marketplaces or {}

    # Check if team has config_source (federated) or not (inline)
    if profile.config_source is None:
        # ─────────────────────────────────────────────────────────────────
        # INLINE TEAM: No external config source
        # ─────────────────────────────────────────────────────────────────
        plugins = compute_effective_plugins(config, team_id)

        return EffectiveConfig(
            team_id=team_id,
            is_federated=False,
            enabled_plugins=plugins.enabled,
            blocked_plugins=plugins.blocked,
            disabled_plugins=plugins.disabled,
            not_allowed_plugins=plugins.not_allowed,
            marketplaces=org_marketplaces,
            extra_marketplaces=plugins.extra_marketplaces,
        )

    else:
        # ─────────────────────────────────────────────────────────────────
        # FEDERATED TEAM: Has external config source
        # ─────────────────────────────────────────────────────────────────
        source = profile.config_source

        # Fetch the external team config with cache fallback (T2b-01+02)
        fallback_result = fetch_team_config_with_fallback(source, team_id)

        if not fallback_result.success or fallback_result.result.team_config is None:
            fetch_result = fallback_result.result
            raise ConfigFetchError(
                team_id=team_id,
                source_type=fetch_result.source_type,
                source_url=fetch_result.source_url,
                error=fetch_result.error or "Unknown fetch error",
            )

        # Extract cache status for caller visibility
        fetch_result = fallback_result.result
        used_cached_config = fallback_result.used_cache
        cache_is_stale = fallback_result.is_stale
        staleness_warning = fallback_result.staleness_warning

        # Parse the fetched config as TeamConfig
        team_config = TeamConfig.model_validate(fetch_result.team_config)

        # Validate team config against trust grants (T2a-27: marketplace collisions)
        trust = profile.trust
        if trust:
            validate_team_config_trust(
                team_config=team_config,
                trust=trust,
                team_name=team_id,
                org_marketplaces=org_marketplaces,
            )

        # Use federated plugin computation
        plugins = compute_effective_plugins_federated(config, team_id, team_config)

        # Build effective marketplaces based on trust grants (T2a-28)
        # If inherit_org_marketplaces=false, org marketplaces are NOT inherited
        effective_marketplaces: dict[str, MarketplaceSource] = {}

        if trust and not trust.inherit_org_marketplaces:
            # T2a-28: Validate that defaults.enabled_plugins don't require org marketplaces
            # when inherit_org_marketplaces=false
            _validate_defaults_dont_need_org_marketplaces(
                config=config,
                org_marketplaces=org_marketplaces,
                team_id=team_id,
            )
        else:
            # inherit_org_marketplaces=true (default) - include org marketplaces
            effective_marketplaces = dict(org_marketplaces)

        # Add team marketplaces if trust allows
        if team_config.marketplaces and trust and trust.allow_additional_marketplaces:
            effective_marketplaces.update(team_config.marketplaces)

        return EffectiveConfig(
            team_id=team_id,
            is_federated=True,
            enabled_plugins=plugins.enabled,
            config_source=source,
            config_commit_sha=fetch_result.commit_sha,
            config_etag=fetch_result.etag,
            # Cache status - T2b-03: note that validate_team_config_trust() above
            # uses CURRENT org security, so cached configs are always validated
            # against the latest org policy
            used_cached_config=used_cached_config,
            cache_is_stale=cache_is_stale,
            staleness_warning=staleness_warning,
            blocked_plugins=plugins.blocked,
            disabled_plugins=plugins.disabled,
            not_allowed_plugins=plugins.not_allowed,
            marketplaces=effective_marketplaces,
            extra_marketplaces=plugins.extra_marketplaces,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def _validate_defaults_dont_need_org_marketplaces(
    config: OrganizationConfig,
    org_marketplaces: dict[str, MarketplaceSource],
    team_id: str,
) -> None:
    """Validate that defaults.enabled_plugins don't require org marketplaces.

    When a federated team sets inherit_org_marketplaces=false, they won't have
    access to org-defined marketplaces. However, defaults.enabled_plugins may
    reference plugins from those marketplaces, creating a conflict.

    This function validates that no such conflict exists.

    Args:
        config: Organization configuration with defaults
        org_marketplaces: Dict of org-defined marketplaces
        team_id: Team name for error messages

    Raises:
        TrustViolationError: If defaults.enabled_plugins reference org marketplaces
    """
    # Import here to avoid circular imports
    from scc_cli.marketplace.constants import IMPLICIT_MARKETPLACES

    if not config.defaults or not config.defaults.enabled_plugins:
        return

    # Check each default plugin for org marketplace references
    conflicting_plugins: list[str] = []
    conflicting_marketplaces: set[str] = set()

    for plugin_ref in config.defaults.enabled_plugins:
        if "@" in plugin_ref:
            # Extract marketplace from plugin@marketplace format
            marketplace_name = plugin_ref.split("@")[1]

            # Skip implicit marketplaces - they're always available
            if marketplace_name in IMPLICIT_MARKETPLACES:
                continue

            # Check if this marketplace is org-defined
            if marketplace_name in org_marketplaces:
                conflicting_plugins.append(plugin_ref)
                conflicting_marketplaces.add(marketplace_name)

    if conflicting_plugins:
        plugins_str = ", ".join(conflicting_plugins)
        marketplaces_str = ", ".join(sorted(conflicting_marketplaces))
        raise TrustViolationError(
            team_name=team_id,
            violation=(
                f"Team has inherit_org_marketplaces=false but defaults.enabled_plugins "
                f"reference org marketplaces. Conflicting plugins: [{plugins_str}]. "
                f"These require org marketplaces: [{marketplaces_str}]. "
                "Either set inherit_org_marketplaces=true or remove these plugins from defaults."
            ),
        )
