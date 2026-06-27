"""Governance pattern matching primitives."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any
from urllib.parse import urlparse


def matches_blocked(item: str, blocked_patterns: list[str]) -> str | None:
    """Return the first case-insensitive fnmatch pattern that matches item."""
    normalized_item = item.strip().casefold()

    for pattern in blocked_patterns:
        normalized_pattern = pattern.strip().casefold()
        if fnmatch(normalized_item, normalized_pattern):
            return pattern
    return None


def mcp_candidates(server: dict[str, Any]) -> list[str]:
    """Collect whole-string MCP candidates for allow/block matching."""
    candidates: list[str] = []
    name = server.get("name", "")
    if name:
        candidates.append(name)
    url = server.get("url", "")
    if url:
        candidates.append(url)
        domain = _extract_domain(url)
        if domain:
            candidates.append(domain)
    command = server.get("command", "")
    if command:
        candidates.append(command)
    return candidates


def is_mcp_allowed(server: dict[str, Any], allowed_patterns: list[str] | None) -> bool:
    """Apply MCP allowlist semantics: None allows all, [] allows none."""
    if allowed_patterns is None:
        return True
    if not allowed_patterns:
        return False
    for candidate in mcp_candidates(server):
        if matches_blocked(candidate, allowed_patterns):
            return True
    return False


def match_blocked_mcp(server: dict[str, Any], blocked_patterns: list[str]) -> str | None:
    """Return the first blocked MCP pattern matching any whole-string candidate."""
    for candidate in mcp_candidates(server):
        matched = matches_blocked(candidate, blocked_patterns)
        if matched:
            return matched
    return None


def _extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or url
