"""Domain enums for SCC CLI.

Centralized location for string-based enums that replace magic strings
throughout the codebase. All enums inherit from str to maintain
JSON serialization compatibility.
"""

from __future__ import annotations

from enum import Enum


class SeverityLevel(str, Enum):
    """Severity levels for doctor checks, validation, and warnings."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class MCPServerType(str, Enum):
    """MCP server transport types."""

    SSE = "sse"
    STDIO = "stdio"
    HTTP = "http"


class TargetType(str, Enum):
    """Target types for blocked/denied items."""

    PLUGIN = "plugin"
    MCP_SERVER = "mcp_server"


class RequestSource(str, Enum):
    """Source of config additions (team or project level)."""

    TEAM = "team"
    PROJECT = "project"


class CredentialStatus(str, Enum):
    """Status of team credentials."""

    VALID = "valid"
    EXPIRED = "expired"
    EXPIRING = "expiring"


class GovernanceStatus(str, Enum):
    """Governance status for teams."""

    BLOCKED = "blocked"
    WARNING = "warning"


class OrgConfigUpdateStatus(str, Enum):
    """Status of organization config update checks."""

    UPDATED = "updated"
    UNCHANGED = "unchanged"
    OFFLINE = "offline"
    AUTH_FAILED = "auth_failed"
    NO_CACHE = "no_cache"
    STANDALONE = "standalone"
    THROTTLED = "throttled"


class DiffItemStatus(str, Enum):
    """Status of items in a diff."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class DiffItemSection(str, Enum):
    """Sections for diff items."""

    PLUGINS = "plugins"
    MCP_SERVERS = "mcp_servers"
    MARKETPLACES = "marketplaces"


class MarketplaceSourceType(str, Enum):
    """Marketplace source types."""

    GITHUB = "github"
    GIT = "git"
    URL = "url"


class NetworkPolicy(str, Enum):
    """Network policy options."""

    CORP_PROXY_ONLY = "corp-proxy-only"
    UNRESTRICTED = "unrestricted"
    ISOLATED = "isolated"


class DecisionResult(str, Enum):
    """Evaluation decision results."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    DENIED = "denied"
