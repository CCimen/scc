"""Typed safety-policy loader for host-side org config.

Extracts and validates a ``SafetyPolicy`` from a raw org config dict.
Fail-closed: any parse failure, missing section, or invalid value produces
a default ``SafetyPolicy(action="block")``.

This module intentionally duplicates the ~10 lines of validation logic from
``docker.launch`` so that core has no import dependency on the docker layer.
"""

from __future__ import annotations

from typing import Any

from .contracts import SafetyPolicy

# Valid baseline action values — same set used by docker.launch.
VALID_SAFETY_NET_ACTIONS: frozenset[str] = frozenset({"block", "warn", "allow"})

_DEFAULT_POLICY = SafetyPolicy(action="block")


def load_safety_policy(org_config: dict[str, Any] | None) -> SafetyPolicy:
    """Return a typed ``SafetyPolicy`` extracted from a raw org config dict.

    Parameters
    ----------
    org_config:
        Raw organisation configuration dict as loaded from the JSON cache,
        or ``None`` when no org config is available.

    Returns
    -------
    SafetyPolicy
        Always returns a valid ``SafetyPolicy`` — never ``None``.
        On any parse error, missing key, or invalid value the function
        returns the default fail-closed policy (``action="block"``).
    """
    if org_config is None:
        return _DEFAULT_POLICY

    try:
        if not isinstance(org_config, dict):
            return _DEFAULT_POLICY

        security = org_config.get("security")
        if not isinstance(security, dict):
            return _DEFAULT_POLICY

        safety_net = security.get("safety_net")
        if not isinstance(safety_net, dict):
            return _DEFAULT_POLICY

        raw_action = safety_net.get("action")
        action: str = (
            raw_action
            if isinstance(raw_action, str) and raw_action in VALID_SAFETY_NET_ACTIONS
            else "block"
        )

        # Everything except "action" is treated as a rule setting.
        rules: dict[str, Any] = {k: v for k, v in safety_net.items() if k != "action"}

        return SafetyPolicy(
            action=action,
            rules=rules,
            source="org.security.safety_net",
        )
    except Exception:
        return _DEFAULT_POLICY
