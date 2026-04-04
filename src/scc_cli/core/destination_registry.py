"""Provider destination registry — pure mapping from named set IDs to typed DestinationSet objects.

This module defines the canonical set of provider-core destination bundles
and exposes helpers for resolving names to sets and converting sets to
egress allow-rules. No I/O, no side effects — suitable for use in
planning, validation, and diagnostics layers.
"""

from __future__ import annotations

from .contracts import DestinationSet, EgressRule

# ---------------------------------------------------------------------------
# Canonical provider destination sets
# ---------------------------------------------------------------------------

PROVIDER_DESTINATION_SETS: dict[str, DestinationSet] = {
    "anthropic-core": DestinationSet(
        name="anthropic-core",
        destinations=("api.anthropic.com",),
        required=True,
        description="Anthropic API core access",
    ),
    "openai-core": DestinationSet(
        name="openai-core",
        destinations=("api.openai.com",),
        required=True,
        description="OpenAI API core access",
    ),
}


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_destination_sets(
    names: tuple[str, ...],
) -> tuple[DestinationSet, ...]:
    """Resolve an ordered sequence of destination set names to typed objects.

    Args:
        names: Destination set identifiers to look up.

    Returns:
        Ordered tuple of resolved ``DestinationSet`` objects.

    Raises:
        ValueError: If any name is not present in the registry.
    """
    resolved: list[DestinationSet] = []
    for name in names:
        dest_set = PROVIDER_DESTINATION_SETS.get(name)
        if dest_set is None:
            known = ", ".join(sorted(PROVIDER_DESTINATION_SETS))
            raise ValueError(
                f"Unknown destination set {name!r}. Known sets: {known}"
            )
        resolved.append(dest_set)
    return tuple(resolved)


# ---------------------------------------------------------------------------
# Rule generation
# ---------------------------------------------------------------------------


def destination_sets_to_allow_rules(
    sets: tuple[DestinationSet, ...],
) -> tuple[EgressRule, ...]:
    """Convert resolved destination sets into allow-type egress rules.

    Each host in each set becomes a separate ``EgressRule`` with
    ``allow=True``. This keeps rule generation reusable across backends.

    Args:
        sets: Resolved destination set objects.

    Returns:
        Ordered tuple of ``EgressRule`` allow entries.
    """
    rules: list[EgressRule] = []
    for dest_set in sets:
        for host in dest_set.destinations:
            rules.append(
                EgressRule(
                    target=host,
                    allow=True,
                    reason=f"provider-core: {dest_set.name}",
                )
            )
    return tuple(rules)
