"""
Marketplace and plugin management for SCC.

This package provides organization-level plugin governance with:
- Multi-source marketplace definitions (GitHub, Git, URL, directory)
- Team-based plugin sets with org defaults inheritance
- Security policies (blocked plugins with audit trail)
- Project-local materialization for Docker sandbox compatibility

Public API:
    - Schema models: OrgConfig, MarketplaceSource, TeamProfile, SecurityConfig
    - Constants: IMPLICIT_MARKETPLACES, EXIT_CODES
    - Normalization: normalize_plugin(), matches_pattern()
    - Computation: compute_effective_plugins(), EffectivePlugins
    - Materialization: materialize_marketplace(), MaterializedMarketplace
    - Settings: render_settings(), merge_settings()
    - State: ManagedState, load_managed_state(), save_managed_state()

Example:
    >>> from scc_cli.marketplace import OrgConfig, compute_effective_plugins
    >>> config = OrgConfig.model_validate(json_data)
    >>> effective = compute_effective_plugins(config, team_id="backend")
    >>> print(effective.enabled_plugins)
"""

from scc_cli.marketplace.compute import (
    BlockedPlugin,
    EffectivePlugins,
    TeamNotFoundError,
    compute_effective_plugins,
)
from scc_cli.marketplace.constants import (
    EXIT_CODES,
    IMPLICIT_MARKETPLACES,
    MANAGED_STATE_FILE,
    MARKETPLACE_CACHE_DIR,
)

# Managed State
from scc_cli.marketplace.managed import (
    ManagedState,
    clear_managed_state,
    load_managed_state,
    save_managed_state,
)

# Materialization
from scc_cli.marketplace.materialize import (
    GitNotAvailableError,
    InvalidMarketplaceError,
    MaterializationError,
    MaterializedMarketplace,
    materialize_marketplace,
)
from scc_cli.marketplace.normalize import (
    AmbiguousMarketplaceError,
    InvalidPluginRefError,
    matches_any_pattern,
    matches_pattern,
    normalize_plugin,
)

# Rendering
from scc_cli.marketplace.render import (
    check_conflicts,
    merge_settings,
    render_settings,
)
from scc_cli.marketplace.schema import (
    DefaultsConfig,
    MarketplaceSource,
    MarketplaceSourceDirectory,
    MarketplaceSourceGit,
    MarketplaceSourceGitHub,
    MarketplaceSourceURL,
    OrganizationConfig,
    SecurityConfig,
    TeamProfile,
)

__all__ = [
    # Constants
    "EXIT_CODES",
    "IMPLICIT_MARKETPLACES",
    "MARKETPLACE_CACHE_DIR",
    "MANAGED_STATE_FILE",
    # Schema models
    "OrganizationConfig",
    "MarketplaceSource",
    "MarketplaceSourceGitHub",
    "MarketplaceSourceGit",
    "MarketplaceSourceURL",
    "MarketplaceSourceDirectory",
    "TeamProfile",
    "SecurityConfig",
    "DefaultsConfig",
    # Normalization
    "normalize_plugin",
    "matches_pattern",
    "matches_any_pattern",
    "InvalidPluginRefError",
    "AmbiguousMarketplaceError",
    # Computation
    "compute_effective_plugins",
    "EffectivePlugins",
    "BlockedPlugin",
    "TeamNotFoundError",
    # Materialization
    "materialize_marketplace",
    "MaterializedMarketplace",
    "MaterializationError",
    "GitNotAvailableError",
    "InvalidMarketplaceError",
    # Rendering
    "render_settings",
    "merge_settings",
    "check_conflicts",
    # Managed state
    "ManagedState",
    "load_managed_state",
    "save_managed_state",
    "clear_managed_state",
]
