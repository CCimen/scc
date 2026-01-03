"""
Backend-specific constants for SCC-CLI.

Centralized location for all backend-specific values that identify the
AI coding assistant being sandboxed. Currently supports Claude Code.

This module enables future extensibility to support other AI coding CLIs
(e.g., Codex, Gemini) by providing a single location to update when
adding new backend support.

Usage:
    from scc_cli.core.constants import AGENT_NAME, SANDBOX_IMAGE
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_package_version

# ─────────────────────────────────────────────────────────────────────────────
# Agent Configuration
# ─────────────────────────────────────────────────────────────────────────────

# The agent binary name inside the container
# This is passed to `docker sandbox run` and `docker exec`
AGENT_NAME = "claude"

# The Docker sandbox template image
SANDBOX_IMAGE = "docker/sandbox-templates:claude-code"

# ─────────────────────────────────────────────────────────────────────────────
# Credential & Storage Paths
# ─────────────────────────────────────────────────────────────────────────────

# Directory name inside user home for agent config/credentials
# Maps to ~/.claude/ on host and /home/agent/.claude/ in container
AGENT_CONFIG_DIR = ".claude"

# Docker volume for persistent sandbox data
SANDBOX_DATA_VOLUME = "docker-claude-sandbox-data"

# Mount point inside the container for the data volume
SANDBOX_DATA_MOUNT = "/mnt/claude-data"

# Safety net policy injection
# This is the filename for the extracted security.safety_net blob (NOT full org config)
SAFETY_NET_POLICY_FILENAME = "effective_policy.json"

# Credential file paths (relative to agent home directory)
CREDENTIAL_PATHS = (
    f"/home/agent/{AGENT_CONFIG_DIR}/.credentials.json",
    f"/home/agent/{AGENT_CONFIG_DIR}/credentials.json",
)

# OAuth credential key in credentials file
OAUTH_CREDENTIAL_KEY = "claudeAiOauth"

# ─────────────────────────────────────────────────────────────────────────────
# Git Integration
# ─────────────────────────────────────────────────────────────────────────────

# Branch prefix for worktrees created by SCC
# Uses product namespace (scc/) not agent namespace (claude/)
WORKTREE_BRANCH_PREFIX = "scc/"

# ─────────────────────────────────────────────────────────────────────────────
# Default Plugin Marketplace
# ─────────────────────────────────────────────────────────────────────────────

# Default GitHub repo for plugins marketplace
DEFAULT_MARKETPLACE_REPO = "sundsvall/claude-plugins-marketplace"

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

# Schema versions this CLI can understand
# v1: Full-featured format with delegation, security policies, marketplace
SUPPORTED_SCHEMA_VERSIONS = ("v1",)

# Current schema version used for validation
CURRENT_SCHEMA_VERSION = "1.0.0"
