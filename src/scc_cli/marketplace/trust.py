"""Trust validation for federated team configurations (Phase 2).

This module provides:
- TrustViolationError: Raised when a team violates org trust grants
- SecurityViolationError: Raised when org security policies are violated
- validate_marketplace_source(): Validate marketplace URL against patterns
- validate_team_config_trust(): Two-layer validation for team configs
- get_source_url(): Extract URL from any MarketplaceSource type

Trust Model:
    Orgs define trust grants that control what teams can do:
    - inherit_org_marketplaces: Can team use org's marketplaces?
    - allow_additional_marketplaces: Can team define their own?
    - marketplace_source_patterns: Which URLs are allowed for team marketplaces?

Security Model:
    Org security rules (blocked_plugins, etc.) are ALWAYS enforced,
    regardless of team configuration or trust grants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scc_cli.marketplace.constants import IMPLICIT_MARKETPLACES
from scc_cli.marketplace.normalize import (
    matches_any_url_pattern,
    normalize_url_for_matching,
)

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import (
        MarketplaceSource,
        TeamConfig,
        TrustGrant,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class TrustViolationError(ValueError):
    """Raised when a federated team violates org trust grants.

    This occurs when a team:
    - Defines marketplaces without allow_additional_marketplaces
    - Uses marketplace sources not matching allowed patterns
    - Defines a marketplace name that conflicts with org/implicit marketplaces
    """

    def __init__(self, team_name: str, violation: str) -> None:
        self.team_name = team_name
        self.violation = violation
        super().__init__(f"Trust violation for team '{team_name}': {violation}")


class SecurityViolationError(ValueError):
    """Raised when org security policies are violated.

    This occurs when:
    - A plugin matches security.blocked_plugins pattern
    - A plugin references a blocked marketplace
    - Other org-level security rules are violated

    Security rules are ALWAYS enforced, regardless of trust grants.
    """

    def __init__(self, plugin_ref: str, reason: str) -> None:
        self.plugin_ref = plugin_ref
        self.reason = reason
        super().__init__(f"Security violation: Plugin '{plugin_ref}' blocked - {reason}")


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def get_source_url(source: MarketplaceSource) -> str | None:
    """Extract URL from any MarketplaceSource type for pattern matching.

    Args:
        source: Any MarketplaceSource variant (GitHub, Git, URL, Directory)

    Returns:
        Normalized URL string for remote sources, None for directory sources

    Examples:
        >>> get_source_url(MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"))
        'github.com/org/plugins'

        >>> get_source_url(MarketplaceSourceDirectory(source="directory", path="/local"))
        None
    """
    # Import here to avoid circular imports
    from scc_cli.marketplace.schema import (
        MarketplaceSourceDirectory,
        MarketplaceSourceGit,
        MarketplaceSourceGitHub,
        MarketplaceSourceURL,
    )

    if isinstance(source, MarketplaceSourceGitHub):
        # Construct GitHub URL: github.com/owner/repo
        return f"github.com/{source.owner}/{source.repo}"

    if isinstance(source, MarketplaceSourceGit):
        # Normalize the git clone URL
        return normalize_url_for_matching(source.url)

    if isinstance(source, MarketplaceSourceURL):
        # Normalize the HTTPS URL
        return normalize_url_for_matching(source.url)

    if isinstance(source, MarketplaceSourceDirectory):
        # Directory sources are local, no URL to match
        return None

    # Unknown source type - shouldn't happen with proper typing
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────


def validate_marketplace_source(
    source: MarketplaceSource,
    allowed_patterns: list[str],
    team_name: str,
) -> None:
    """Validate a marketplace source against allowed URL patterns.

    Directory sources are always allowed (org-local).
    Remote sources must match at least one allowed pattern.

    Args:
        source: MarketplaceSource to validate
        allowed_patterns: List of URL glob patterns (with ** support)
        team_name: Team name for error messages

    Raises:
        TrustViolationError: If source doesn't match any allowed pattern
    """
    url = get_source_url(source)

    # Directory sources are org-local, always allowed
    if url is None:
        return

    # Remote sources must match an allowed pattern
    if not allowed_patterns:
        raise TrustViolationError(
            team_name=team_name,
            violation=(
                f"Marketplace source '{url}' not allowed (no patterns defined). "
                "Ask org admin to add marketplace_source_patterns to the team's trust grant."
            ),
        )

    matched = matches_any_url_pattern(url, allowed_patterns)
    if matched is None:
        patterns_str = ", ".join(allowed_patterns)
        raise TrustViolationError(
            team_name=team_name,
            violation=(
                f"Marketplace source '{url}' doesn't match any allowed pattern. "
                f"Allowed patterns: [{patterns_str}]. "
                "Ask org admin to add a matching pattern, or use an allowed source."
            ),
        )


def validate_team_config_trust(
    team_config: TeamConfig,
    trust: TrustGrant,
    team_name: str,
    org_marketplaces: dict[str, Any],
) -> None:
    """Validate team config against trust grants (two-layer validation).

    Layer 1: Check if team is allowed to define marketplaces at all
    Layer 2: Validate each marketplace source against allowed patterns

    Also checks for marketplace name collisions with:
    - Org-defined marketplaces (keys in org_marketplaces)
    - Implicit marketplaces (claude-plugins-official, etc.)

    Args:
        team_config: External team configuration to validate
        trust: Trust grant from org to this team
        team_name: Team name for error messages
        org_marketplaces: Dict of org-defined marketplaces (for collision check)

    Raises:
        TrustViolationError: If team violates any trust constraint
    """
    # No marketplaces defined - nothing to validate
    if not team_config.marketplaces:
        return

    # Layer 1: Check if team is allowed to define marketplaces
    if not trust.allow_additional_marketplaces:
        names = list(team_config.marketplaces.keys())
        raise TrustViolationError(
            team_name=team_name,
            violation=(
                f"Team defines marketplaces ({names}) but trust grant has "
                "allow_additional_marketplaces=False. Ask org admin to enable."
            ),
        )

    # Check for marketplace name collisions
    for mp_name in team_config.marketplaces:
        # Collision with org marketplace?
        if mp_name in org_marketplaces:
            raise TrustViolationError(
                team_name=team_name,
                violation=(
                    f"Team marketplace '{mp_name}' conflicts with org-defined marketplace. "
                    "Choose a different name."
                ),
            )

        # Collision with implicit marketplace?
        if mp_name in IMPLICIT_MARKETPLACES:
            raise TrustViolationError(
                team_name=team_name,
                violation=(
                    f"Team marketplace '{mp_name}' conflicts with implicit marketplace. "
                    f"Reserved names: {list(IMPLICIT_MARKETPLACES)}. Choose a different name."
                ),
            )

    # Layer 2: Validate each marketplace source against allowed patterns
    for mp_name, source in team_config.marketplaces.items():
        validate_marketplace_source(
            source=source,
            allowed_patterns=trust.marketplace_source_patterns,
            team_name=team_name,
        )
