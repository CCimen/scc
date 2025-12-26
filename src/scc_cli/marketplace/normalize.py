"""
Plugin reference normalization and pattern matching utilities.

This module provides:
- normalize_plugin(): Convert plugin references to canonical form
- matches_pattern(): Glob pattern matching for plugin filtering

Plugin Reference Formats:
    - `name@marketplace`: Standard format (canonical)
    - `@marketplace/name`: npm-style format (normalized to standard)
    - `name`: Auto-resolved based on org marketplaces

Auto-Resolution Rules:
    - 0 org marketplaces → resolves to `claude-plugins-official`
    - 1 org marketplace → auto-resolves to that marketplace
    - 2+ marketplaces → explicit `@marketplace` required (raises AmbiguousMarketplaceError)
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import MarketplaceSource


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class InvalidPluginRefError(ValueError):
    """Raised when a plugin reference is malformed."""

    def __init__(self, ref: str, reason: str) -> None:
        self.ref = ref
        self.reason = reason
        super().__init__(f"Invalid plugin reference '{ref}': {reason}")


class AmbiguousMarketplaceError(ValueError):
    """Raised when plugin ref needs explicit marketplace qualifier."""

    def __init__(self, plugin_name: str, available_marketplaces: list[str]) -> None:
        self.plugin_name = plugin_name
        self.available_marketplaces = available_marketplaces
        marketplaces_str = ", ".join(sorted(available_marketplaces))
        super().__init__(
            f"Ambiguous plugin reference '{plugin_name}': "
            f"specify marketplace explicitly (available: {marketplaces_str}). "
            f"Use '{plugin_name}@<marketplace>' or '@<marketplace>/{plugin_name}'."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Normalization
# ─────────────────────────────────────────────────────────────────────────────


def normalize_plugin(
    ref: str,
    org_marketplaces: dict[str, Any],
) -> str:
    """Normalize a plugin reference to canonical 'name@marketplace' format.

    Supports three input formats:
    - `name@marketplace`: Already canonical, returned as-is
    - `@marketplace/name`: npm-style, converted to canonical
    - `name`: Auto-resolved based on org marketplace count

    Args:
        ref: Plugin reference in any supported format
        org_marketplaces: Dict of org-defined marketplaces (keys are marketplace names)

    Returns:
        Canonical plugin reference in 'name@marketplace' format

    Raises:
        InvalidPluginRefError: If reference is malformed
        AmbiguousMarketplaceError: If 2+ org marketplaces and no explicit qualifier

    Examples:
        >>> normalize_plugin("code-review@internal", {})
        'code-review@internal'

        >>> normalize_plugin("@internal/code-review", {})
        'code-review@internal'

        >>> normalize_plugin("tool", {"internal": {...}})
        'tool@internal'

        >>> normalize_plugin("tool", {})  # No org marketplaces
        'tool@claude-plugins-official'
    """
    # Strip whitespace
    ref = ref.strip()

    # Validate not empty
    if not ref:
        raise InvalidPluginRefError(ref, "plugin reference cannot be empty")

    # Check for double @@ which is always invalid
    if "@@" in ref:
        raise InvalidPluginRefError(ref, "invalid double '@' in reference")

    # Parse the reference format
    if ref.startswith("@"):
        # npm-style: @marketplace/name
        return _parse_npm_style(ref)
    elif "@" in ref:
        # Standard format: name@marketplace
        return _parse_standard_format(ref)
    else:
        # Bare name: auto-resolve marketplace
        return _auto_resolve_marketplace(ref, org_marketplaces)


def _parse_npm_style(ref: str) -> str:
    """Parse @marketplace/name format to canonical form.

    Args:
        ref: Plugin reference starting with @

    Returns:
        Canonical 'name@marketplace' format

    Raises:
        InvalidPluginRefError: If format is invalid
    """
    # Remove leading @
    without_at = ref[1:]

    # Split on first /
    if "/" not in without_at:
        raise InvalidPluginRefError(ref, "npm-style format requires '/' separator")

    parts = without_at.split("/", 1)
    marketplace = parts[0]
    name = parts[1]

    # Validate parts
    if not marketplace:
        raise InvalidPluginRefError(ref, "marketplace name cannot be empty")
    if not name:
        raise InvalidPluginRefError(ref, "plugin name cannot be empty")

    return f"{name}@{marketplace}"


def _parse_standard_format(ref: str) -> str:
    """Parse name@marketplace format, validating structure.

    Args:
        ref: Plugin reference containing @

    Returns:
        Validated canonical format (same as input if valid)

    Raises:
        InvalidPluginRefError: If format is invalid
    """
    # Split on first @ only
    parts = ref.split("@", 1)
    name = parts[0]
    marketplace = parts[1]

    # Validate parts
    if not name:
        raise InvalidPluginRefError(ref, "plugin name cannot be empty")
    if not marketplace:
        raise InvalidPluginRefError(ref, "marketplace name cannot be empty")

    return f"{name}@{marketplace}"


def _auto_resolve_marketplace(
    plugin_name: str,
    org_marketplaces: dict[str, Any],
) -> str:
    """Auto-resolve marketplace for bare plugin name.

    Resolution rules:
    - 0 org marketplaces → claude-plugins-official
    - 1 org marketplace → that marketplace
    - 2+ marketplaces → raise AmbiguousMarketplaceError

    Args:
        plugin_name: Bare plugin name without marketplace
        org_marketplaces: Dict of org-defined marketplaces

    Returns:
        Canonical plugin reference with resolved marketplace

    Raises:
        AmbiguousMarketplaceError: If 2+ org marketplaces defined
    """
    # Validate plugin name
    if not plugin_name:
        raise InvalidPluginRefError(plugin_name, "plugin name cannot be empty")

    # Count org marketplaces (implicit marketplaces don't count)
    marketplace_count = len(org_marketplaces)

    if marketplace_count == 0:
        # No org marketplaces → use implicit official
        return f"{plugin_name}@claude-plugins-official"
    elif marketplace_count == 1:
        # Exactly one org marketplace → auto-resolve to it
        marketplace_name = next(iter(org_marketplaces.keys()))
        return f"{plugin_name}@{marketplace_name}"
    else:
        # 2+ org marketplaces → ambiguous, require explicit
        raise AmbiguousMarketplaceError(
            plugin_name,
            list(org_marketplaces.keys()),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pattern Matching
# ─────────────────────────────────────────────────────────────────────────────


def matches_pattern(plugin_ref: str, pattern: str) -> bool:
    """Check if a plugin reference matches a glob pattern.

    Uses fnmatch for glob-style pattern matching:
    - `*` matches any sequence of characters
    - `?` matches any single character
    - `[seq]` matches any character in seq
    - `[!seq]` matches any character not in seq

    Args:
        plugin_ref: Canonical plugin reference (name@marketplace)
        pattern: Glob pattern to match against

    Returns:
        True if plugin matches pattern, False otherwise

    Examples:
        >>> matches_pattern("code-review@internal", "*@internal")
        True

        >>> matches_pattern("tool-v1@org", "tool-v?@*")
        True

        >>> matches_pattern("other@external", "*@internal")
        False
    """
    # Handle empty cases
    if not plugin_ref or not pattern:
        return False

    # Use fnmatch for glob-style matching with case-insensitive comparison
    # Documentation requires Unicode-aware casefolding for security patterns
    # to prevent bypass attempts using case variations (e.g., "MALICIOUS-*" vs "malicious-*")
    return fnmatch.fnmatch(plugin_ref.casefold(), pattern.casefold())


def matches_any_pattern(plugin_ref: str, patterns: list[str]) -> str | None:
    """Check if a plugin reference matches any pattern in a list.

    Args:
        plugin_ref: Canonical plugin reference (name@marketplace)
        patterns: List of glob patterns to match against

    Returns:
        First matching pattern, or None if no match

    Examples:
        >>> matches_any_pattern("tool@internal", ["*@external", "*@internal"])
        '*@internal'

        >>> matches_any_pattern("tool@other", ["*@internal"])
        None
    """
    for pattern in patterns:
        if matches_pattern(plugin_ref, pattern):
            return pattern
    return None


# ─────────────────────────────────────────────────────────────────────────────
# URL Pattern Matching (Phase 2: Federated Team Configs)
# ─────────────────────────────────────────────────────────────────────────────


def normalize_url_for_matching(url: str) -> str:
    """Normalize a URL for pattern matching.

    Normalization steps:
    1. Remove protocol (https://, http://)
    2. Convert git@host:path format to host/path
    3. Lowercase the host portion (path case preserved)
    4. Remove trailing .git suffix

    Args:
        url: URL in any format (HTTPS, HTTP, SSH git@)

    Returns:
        Normalized URL string for pattern matching

    Examples:
        >>> normalize_url_for_matching("https://github.com/sundsvall/plugins")
        'github.com/sundsvall/plugins'

        >>> normalize_url_for_matching("git@github.com:sundsvall/plugins.git")
        'github.com/sundsvall/plugins'
    """
    if not url:
        return ""

    normalized = url

    # Remove protocol prefix
    if normalized.startswith("https://"):
        normalized = normalized[8:]
    elif normalized.startswith("http://"):
        normalized = normalized[7:]

    # Convert git@host:path to host/path
    if normalized.startswith("git@"):
        normalized = normalized[4:]
        # Replace first : with / (the colon separates host from path in SSH URLs)
        if ":" in normalized:
            normalized = normalized.replace(":", "/", 1)

    # Remove trailing .git
    if normalized.endswith(".git"):
        normalized = normalized[:-4]

    # Lowercase the host portion only (preserve path case)
    if "/" in normalized:
        parts = normalized.split("/", 1)
        host = parts[0].lower()
        path = parts[1]
        normalized = f"{host}/{path}"
    else:
        normalized = normalized.lower()

    return normalized


def fnmatch_with_globstar(text: str, pattern: str) -> bool:
    """Extended fnmatch supporting globstar (**) for recursive matching.

    Globstar rules:
    - ** matches zero or more path segments (including /)
    - * matches within a single segment (no /)
    - Other fnmatch patterns work normally

    Args:
        text: Text to match against
        pattern: Glob pattern with optional ** support

    Returns:
        True if text matches pattern

    Examples:
        >>> fnmatch_with_globstar("github.com/a/b/c/repo", "github.com/**/repo")
        True

        >>> fnmatch_with_globstar("github.com/org/repo", "github.com/*/repo")
        True
    """
    if not text or not pattern:
        return False

    import re

    # Apply Unicode-aware casefolding for case-insensitive matching
    # This prevents bypass attempts using case variations in URL patterns
    text = text.casefold()
    pattern = pattern.casefold()

    # Convert glob pattern to regex
    # Key insight: * must NOT cross / boundaries, ** CAN cross them
    regex = ""
    i = 0

    while i < len(pattern):
        # Check for ** (globstar)
        if pattern[i : i + 2] == "**":
            # Lookahead/behind to determine context
            has_slash_before = i > 0 and pattern[i - 1] == "/"
            has_slash_after = i + 2 < len(pattern) and pattern[i + 2] == "/"

            if has_slash_before and has_slash_after:
                # /**/ - matches zero or more segments
                # The preceding / is already in regex, consume the following /
                # Pattern: (?:[^/]+/)* matches x/ or x/y/ or empty
                regex += "(?:[^/]+/)*"
                i += 3  # Skip ** and the following /
            elif has_slash_before:
                # /** at end - matches zero or more segments after /
                regex += "(?:[^/]+(?:/[^/]+)*)?$"
                i += 2
            elif has_slash_after:
                # **/ at start - matches zero or more segments before /
                regex += "(?:[^/]+/)*"
                i += 3  # Skip ** and the following /
            else:
                # Standalone ** - matches anything
                regex += ".*"
                i += 2

        elif pattern[i] == "*":
            # Single * - matches within segment (no /)
            regex += "[^/]*"
            i += 1

        elif pattern[i] == "?":
            # ? - matches single char except /
            regex += "[^/]"
            i += 1

        elif pattern[i] == "[":
            # Character class - find matching ]
            end = pattern.find("]", i + 1)
            if end != -1:
                regex += pattern[i : end + 1]
                i = end + 1
            else:
                regex += re.escape(pattern[i])
                i += 1

        else:
            # Literal character
            regex += re.escape(pattern[i])
            i += 1

    try:
        return bool(re.match(f"^{regex}$", text))
    except re.error:
        return False


def matches_url_pattern(url: str, pattern: str) -> bool:
    """Check if a URL matches a pattern with globstar support.

    Combines URL normalization with globstar matching:
    1. Normalizes the URL (removes protocol, handles SSH format)
    2. Uses fnmatch_with_globstar for pattern matching

    Args:
        url: URL to match (HTTPS, HTTP, or SSH format)
        pattern: Glob pattern (host/path format, supports ** and *)

    Returns:
        True if normalized URL matches pattern

    Examples:
        >>> matches_url_pattern("https://github.com/sundsvall/plugins", "github.com/sundsvall/**")
        True

        >>> matches_url_pattern("git@github.com:org/repo.git", "github.com/org/**")
        True
    """
    if not url or not pattern:
        return False

    normalized = normalize_url_for_matching(url)
    return fnmatch_with_globstar(normalized, pattern)


def matches_any_url_pattern(url: str, patterns: list[str]) -> str | None:
    """Check if a URL matches any pattern in a list.

    Args:
        url: URL to match
        patterns: List of glob patterns

    Returns:
        First matching pattern, or None if no match

    Examples:
        >>> matches_any_url_pattern("https://github.com/org/repo", ["github.com/**"])
        'github.com/**'

        >>> matches_any_url_pattern("https://other.com/repo", ["github.com/**"])
        None
    """
    for pattern in patterns:
        if matches_url_pattern(url, pattern):
            return pattern
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Source URL Extraction (Phase 2: Federated Team Configs)
# ─────────────────────────────────────────────────────────────────────────────


def get_source_url(source: MarketplaceSource) -> str:
    """Extract URL from any MarketplaceSource type for pattern matching.

    Converts the various source types to a normalized URL format suitable
    for matching against trust grant patterns.

    Args:
        source: MarketplaceSource of any type (GitHub, Git, URL, Directory)

    Returns:
        URL string for pattern matching:
        - GitHub: github.com/{owner}/{repo}
        - Git: the url field directly
        - URL: the url field directly
        - Directory: the path field (for local sources)

    Examples:
        >>> from scc_cli.marketplace.schema import MarketplaceSourceGitHub
        >>> source = MarketplaceSourceGitHub(source="github", owner="org", repo="plugins")
        >>> get_source_url(source)
        'https://github.com/org/plugins'

        >>> from scc_cli.marketplace.schema import MarketplaceSourceGit
        >>> source = MarketplaceSourceGit(source="git", url="https://gitlab.example.se/ai/plugins.git")
        >>> get_source_url(source)
        'https://gitlab.example.se/ai/plugins.git'
    """
    # Import here to avoid circular imports
    from scc_cli.marketplace.schema import (
        MarketplaceSourceDirectory,
        MarketplaceSourceGit,
        MarketplaceSourceGitHub,
        MarketplaceSourceURL,
    )

    if isinstance(source, MarketplaceSourceGitHub):
        # Build GitHub URL from owner/repo
        return f"https://github.com/{source.owner}/{source.repo}"

    elif isinstance(source, MarketplaceSourceGit):
        # Use the Git URL directly
        return source.url

    elif isinstance(source, MarketplaceSourceURL):
        # Use the URL directly
        return source.url

    elif isinstance(source, MarketplaceSourceDirectory):
        # Use the path for local directories
        return source.path

    else:
        # Fallback for unknown types - should not happen
        return ""
