"""Auth bootstrap helpers for interactive launch flows."""

from __future__ import annotations

from collections.abc import Callable

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.provider_resolution import get_provider_display_name


def ensure_provider_auth(
    plan: StartSessionPlan,
    *,
    dependencies: StartSessionDependencies,
    non_interactive: bool,
    show_notice: Callable[[str, str, str], None],
) -> None:
    """Perform provider-owned auth bootstrap when launch needs it."""
    if plan.resume:
        return

    provider = dependencies.agent_provider
    if provider is None:
        return

    readiness = provider.auth_check()
    if readiness.status != "missing":
        return

    profile = provider.capability_profile()
    provider_id = profile.provider_id
    display_name = get_provider_display_name(provider_id)

    if non_interactive:
        raise ProviderNotReadyError(
            provider_id=provider_id,
            user_message=f"{display_name} auth cache is missing and this start is non-interactive.",
            suggested_action=(
                f"Run 'scc start --provider {provider_id}' interactively once and "
                "complete the one-time browser sign-in."
            ),
        )

    show_notice(
        f"Authenticating {display_name}",
        (
            f"No reusable {display_name} auth cache was found for this sandbox.\n\n"
            f"SCC will open the normal {display_name} browser sign-in flow now. "
            f"After sign-in completes, {display_name} will launch automatically."
        ),
        (
            "Future starts reuse the provider auth cache from the persistent "
            f"{display_name} volume."
        ),
    )
    provider.bootstrap_auth()
