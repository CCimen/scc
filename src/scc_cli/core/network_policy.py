"""Network policy helpers for ordering and comparison."""

from __future__ import annotations

from collections.abc import Mapping

from .enums import NetworkPolicy

_NETWORK_POLICY_ORDER = {
    NetworkPolicy.UNRESTRICTED.value: 0,
    NetworkPolicy.CORP_PROXY_ONLY.value: 1,
    NetworkPolicy.ISOLATED.value: 2,
}


def policy_rank(policy: str | None) -> int:
    """Return numeric rank for policy (higher = more restrictive)."""
    if policy is None:
        return -1
    return _NETWORK_POLICY_ORDER.get(policy, -1)


def is_more_or_equal_restrictive(candidate: str, baseline: str) -> bool:
    """Return True if candidate is as or more restrictive than baseline."""
    return policy_rank(candidate) >= policy_rank(baseline)


def collect_proxy_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Collect proxy environment variables for container injection."""
    import os

    source = env or os.environ
    proxy_env: dict[str, str] = {}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        value = source.get(key) or source.get(key.lower())
        if value:
            proxy_env[key] = value
    return proxy_env
