"""Pure provider selection precedence for setup and launch flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scc_cli.core.provider_resolution import KNOWN_PROVIDERS, resolve_active_provider

ProviderSelectionSource = Literal[
    "explicit",
    "resume",
    "workspace_last_used",
    "global_preferred",
]


@dataclass(frozen=True)
class ProviderSelection:
    """Resolved provider together with the source that selected it."""

    provider_id: str
    source: ProviderSelectionSource


def resolve_provider_preference(
    *,
    cli_flag: str | None,
    resume_provider: str | None,
    workspace_last_used: str | None,
    global_preferred: str | None,
    allowed_providers: tuple[str, ...] = (),
) -> ProviderSelection | None:
    """Resolve the highest-precedence provider preference.

    Returns ``None`` when no preference exists or when the global preference is
    the explicit sentinel ``"ask"``. An explicit ``"ask"`` preference
    intentionally suppresses workspace last-used auto-selection so the operator
    is prompted whenever multiple providers are viable.
    """
    if cli_flag is not None:
        return ProviderSelection(
            provider_id=resolve_active_provider(cli_flag, None, allowed_providers),
            source="explicit",
        )
    if resume_provider is not None:
        return ProviderSelection(
            provider_id=resolve_active_provider(resume_provider, None, allowed_providers),
            source="resume",
        )
    if global_preferred == "ask":
        return None
    if workspace_last_used is not None:
        return ProviderSelection(
            provider_id=resolve_active_provider(workspace_last_used, None, allowed_providers),
            source="workspace_last_used",
        )
    if global_preferred is None:
        return None
    if global_preferred not in KNOWN_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{global_preferred}'. Known providers: {', '.join(KNOWN_PROVIDERS)}"
        )
    return ProviderSelection(
        provider_id=resolve_active_provider(global_preferred, None, allowed_providers),
        source="global_preferred",
    )
