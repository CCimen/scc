"""Auth bootstrap helpers for interactive launch flows.

.. deprecated::
    All launch sites now use ``preflight.ensure_launch_ready``.
    This module exists only as a backward-compatible redirect for tests
    that exercise the old ``ensure_provider_auth`` signature.  New code
    should import from ``preflight`` directly.
"""

from __future__ import annotations

from collections.abc import Callable

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
    _ensure_auth,
)


def ensure_provider_auth(
    plan: StartSessionPlan,
    *,
    dependencies: StartSessionDependencies,
    non_interactive: bool,
    show_notice: Callable[[str, str, str], None],
) -> None:
    """Deprecated redirect — delegates to preflight._ensure_auth.

    Builds a minimal LaunchReadiness from the old plan+dependencies params
    so existing tests keep working.  Auth messaging is canonical in
    ``preflight._ensure_auth``; this function adds no user-facing text.
    """
    if plan.resume:
        return

    provider = dependencies.agent_provider
    if provider is None:
        return

    readiness_obj = provider.auth_check()
    if readiness_obj.status != "missing":
        return

    profile = provider.capability_profile()
    provider_id = profile.provider_id

    # Build the LaunchReadiness expected by _ensure_auth
    lr = LaunchReadiness(
        provider_id=provider_id,
        resolution_source=ProviderResolutionSource.EXPLICIT,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.MISSING,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=True,
        launch_ready=False,
    )

    _ensure_auth(
        lr,
        adapters=dependencies,
        non_interactive=non_interactive,
        show_notice=show_notice,
        provider=provider,
    )
