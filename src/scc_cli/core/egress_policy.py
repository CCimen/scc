"""Egress plan builder and Squid ACL compiler.

Pure-logic layer that converts network policy mode, destination sets, and
egress rules into a ``NetworkPolicyPlan``, then compiles that plan into a
Squid ACL configuration string.

Security invariants:
- Deny rules always precede allow rules in compiled output.
- Default deny rules cover IP literals, loopback, private CIDRs,
  link-local, and cloud metadata endpoints.
- Final ACL line is ``http_access deny all`` (enforced modes)
  or ``http_access allow all`` (open mode).
"""

from __future__ import annotations

import re

from .contracts import DestinationSet, EgressRule, NetworkPolicyPlan
from .enums import NetworkPolicy

# ---------------------------------------------------------------------------
# Private constants — default deny targets
# ---------------------------------------------------------------------------

_IP_LITERAL_PATTERN: re.Pattern[str] = re.compile(
    r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
)

_PRIVATE_CIDRS: tuple[str, ...] = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)

_LOOPBACK_CIDR: str = "127.0.0.0/8"

_LINK_LOCAL_CIDR: str = "169.254.0.0/16"

_METADATA_ENDPOINT: str = "169.254.169.254"

_DEFAULT_DENY_TARGETS: tuple[tuple[str, str], ...] = (
    (_LOOPBACK_CIDR, "deny loopback"),
    *((cidr, f"deny private CIDR {cidr}") for cidr in _PRIVATE_CIDRS),
    (_LINK_LOCAL_CIDR, "deny link-local"),
    (_METADATA_ENDPOINT, "deny cloud metadata endpoint"),
)
"""Each entry is ``(target, reason)`` for the default deny rule set."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_egress_plan(
    mode: NetworkPolicy,
    destination_sets: tuple[DestinationSet, ...] = (),
    egress_rules: tuple[EgressRule, ...] = (),
) -> NetworkPolicyPlan:
    """Build a ``NetworkPolicyPlan`` from policy mode and optional inputs.

    Parameters
    ----------
    mode:
        The active network policy mode.
    destination_sets:
        Named destination bundles provided by the provider or config.
    egress_rules:
        Additional allow/deny rules supplied by the caller (appended
        after the default deny set when mode is ``WEB_EGRESS_ENFORCED``).

    Returns
    -------
    NetworkPolicyPlan
        A frozen plan suitable for ACL compilation or runtime enforcement.
    """
    if mode is NetworkPolicy.OPEN:
        return NetworkPolicyPlan(
            mode=mode,
            destination_sets=destination_sets,
            egress_rules=(),
            enforced_by_runtime=False,
        )

    if mode is NetworkPolicy.LOCKED_DOWN_WEB:
        return NetworkPolicyPlan(
            mode=mode,
            destination_sets=destination_sets,
            egress_rules=(),
            enforced_by_runtime=True,
            notes=("Agent container uses --network=none; no egress possible.",),
        )

    # WEB_EGRESS_ENFORCED — assemble default deny rules, then caller rules.
    deny_rules = tuple(
        EgressRule(target=target, allow=False, reason=reason)
        for target, reason in _DEFAULT_DENY_TARGETS
    )

    return NetworkPolicyPlan(
        mode=mode,
        destination_sets=destination_sets,
        egress_rules=deny_rules + egress_rules,
        enforced_by_runtime=True,
    )


def compile_squid_acl(plan: NetworkPolicyPlan) -> str:
    """Compile a ``NetworkPolicyPlan`` into a Squid ACL configuration string.

    Squid evaluates rules top-to-bottom, first-match wins. This compiler
    emits deny rules first, then allow rules, and always closes with a
    terminal ``http_access`` directive.

    Parameters
    ----------
    plan:
        The network policy plan to compile.

    Returns
    -------
    str
        Multi-line Squid ACL configuration fragment.
    """
    if plan.mode is NetworkPolicy.OPEN:
        return "http_access allow all\n"

    if plan.mode is NetworkPolicy.LOCKED_DOWN_WEB:
        return "http_access deny all\n"

    # WEB_EGRESS_ENFORCED — build ACL definitions and access lines.
    acl_defs: list[str] = []
    deny_access: list[str] = []
    allow_access: list[str] = []

    deny_counter = 0
    allow_counter = 0

    for rule in plan.egress_rules:
        if not rule.allow:
            deny_counter += 1
            acl_name = f"deny_{deny_counter}"
            acl_defs.append(_acl_definition(acl_name, rule.target))
            deny_access.append(f"http_access deny {acl_name}")
        else:
            allow_counter += 1
            acl_name = f"allow_{allow_counter}"
            acl_defs.append(_acl_definition(acl_name, rule.target))
            allow_access.append(f"http_access allow {acl_name}")

    lines = acl_defs + [""] + deny_access + allow_access + ["http_access deny all", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_cidr(target: str) -> bool:
    """Return True if *target* looks like a CIDR notation (contains ``/``)."""
    return "/" in target


def _is_ip_literal(target: str) -> bool:
    """Return True if *target* is a bare IPv4 address."""
    return bool(_IP_LITERAL_PATTERN.match(target))


def _acl_definition(acl_name: str, target: str) -> str:
    """Return a Squid ``acl`` definition line for the given target."""
    if _is_cidr(target) or _is_ip_literal(target):
        return f"acl {acl_name} dst {target}"
    return f"acl {acl_name} dstdomain {target}"
