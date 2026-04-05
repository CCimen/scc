"""
Product-level constants for SCC-CLI.

Holds version information, schema version, and the worktree branch prefix.
Provider-specific runtime values (images, volumes, mount paths, credential
keys) live in the adapter modules that use them.

Usage:
    from scc_cli.core.constants import CLI_VERSION, CURRENT_SCHEMA_VERSION
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_package_version

# ─────────────────────────────────────────────────────────────────────────────
# Git Integration
# ─────────────────────────────────────────────────────────────────────────────

# Branch prefix for worktrees created by SCC
# Uses product namespace (scc/) not agent namespace (claude/)
WORKTREE_BRANCH_PREFIX = "scc/"

# ─────────────────────────────────────────────────────────────────────────────
# Version Information
# ─────────────────────────────────────────────────────────────────────────────

# Fallback version for editable installs and dev checkouts
# Keep in sync with pyproject.toml as last resort
_FALLBACK_VERSION = "1.5.0"


def _get_version() -> str:
    """Get CLI version from package metadata with meaningful fallback.

    Returns:
        Version string from installed package, or fallback with dev suffix
        for editable installs where package metadata is unavailable.
    """
    try:
        return get_package_version("scc-cli")
    except PackageNotFoundError:
        # Editable install or dev checkout - still provide meaningful version
        return f"{_FALLBACK_VERSION}-dev (no package metadata)"


CLI_VERSION = _get_version()

# Current schema version used for validation
CURRENT_SCHEMA_VERSION = "1.0.0"
