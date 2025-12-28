"""
Constants for marketplace and plugin management.

This module defines:
- IMPLICIT_MARKETPLACES: Built-in marketplaces that Claude Code knows about
- EXIT_CODES: Semantic exit codes for marketplace operations
- Path constants for cache and state files
"""

from typing import Final

# ─────────────────────────────────────────────────────────────────────────────
# Implicit Marketplaces
# ─────────────────────────────────────────────────────────────────────────────

# Marketplaces that Claude Code supports natively without explicit configuration.
# These are NEVER written to settings.local.json and don't count toward ambiguity
# when resolving unqualified plugin names.
#
# Per research.md RQ-10:
# - Implicit marketplaces are always available
# - Don't need to be written to extraKnownMarketplaces
# - Unqualified plugins can resolve here when no org marketplaces exist
IMPLICIT_MARKETPLACES: Final[frozenset[str]] = frozenset(
    {
        "claude-plugins-official",
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Exit Codes
# ─────────────────────────────────────────────────────────────────────────────

# Semantic exit codes for marketplace operations.
# These align with existing SCC exit code conventions.
#
# Usage:
#     from scc_cli.marketplace.constants import EXIT_CODES
#     sys.exit(EXIT_CODES["validation_error"])
EXIT_CODES: Final[dict[str, int]] = {
    # Success
    "success": 0,
    # User errors (2)
    "validation_error": 2,  # Schema validation failed
    "invalid_plugin_ref": 2,  # Malformed plugin reference
    "ambiguous_marketplace": 2,  # Plugin ref needs explicit @marketplace
    # Prerequisite errors (3)
    "network_error": 3,  # Cannot fetch remote config
    "git_unavailable": 3,  # Git not installed for git: sources
    # Tool errors (4)
    "git_clone_failed": 4,  # Git clone/fetch failed
    "http_fetch_failed": 4,  # HTTP download failed
    "materialization_failed": 4,  # Failed to materialize marketplace
    # Internal errors (5)
    "internal_error": 5,  # Bug in SCC
    # Policy violations (6)
    "blocked_by_policy": 6,  # Plugin blocked by security policy
}


# ─────────────────────────────────────────────────────────────────────────────
# Path Constants
# ─────────────────────────────────────────────────────────────────────────────

# Directory name for materialized marketplaces (under project's .claude/)
# Per research.md RQ-2: Must be project-local for Docker sandbox visibility
MARKETPLACE_CACHE_DIR: Final[str] = ".scc-marketplaces"

# Filename for tracking SCC-managed entries in settings
# Per research.md RQ-7: Enables non-destructive merge
MANAGED_STATE_FILE: Final[str] = ".scc-managed.json"

# Filename for marketplace manifest tracking materialization state
MANIFEST_FILE: Final[str] = ".manifest.json"


# ─────────────────────────────────────────────────────────────────────────────
# TTL and Caching
# ─────────────────────────────────────────────────────────────────────────────

# Default TTL for org config freshness (24 hours in seconds)
# Per research.md RQ-6: Time-based staleness detection
DEFAULT_ORG_CONFIG_TTL_SECONDS: Final[int] = 24 * 60 * 60

# Minimum TTL to prevent excessive re-fetching (1 hour)
MIN_ORG_CONFIG_TTL_SECONDS: Final[int] = 1 * 60 * 60
