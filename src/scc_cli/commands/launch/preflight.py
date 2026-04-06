"""Shared launch preflight: typed readiness model with pure/side-effect separation.

This module provides a clean three-function split for launch preflight:

1. ``resolve_launch_provider()`` — pure decision: who are we launching?
2. ``collect_launch_readiness()`` — side-effect read: what's the current state?
3. ``ensure_launch_ready()`` — side-effect write: fix gaps or fail clearly.

Architecture guard (D046): command-layer only. No imports from core/ except
types and errors. No provider-specific behavior — dispatches to
provider_image.py and auth_bootstrap.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from scc_cli.commands.launch.provider_choice import (
    choose_start_provider,
    collect_provider_readiness,
    connected_provider_ids,
    prompt_for_provider_choice,
)
from scc_cli.core.contracts import AuthReadiness
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.ports.config_models import NormalizedOrgConfig

# ─────────────────────────────────────────────────────────────────────────────
# Typed readiness model
# ─────────────────────────────────────────────────────────────────────────────


class ImageStatus(Enum):
    """Whether the provider container image is locally available."""

    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"


class AuthStatus(Enum):
    """Whether the provider auth cache is usable."""

    PRESENT = "present"
    MISSING = "missing"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class ProviderResolutionSource(Enum):
    """How the provider was resolved for this launch."""

    EXPLICIT = "explicit"
    RESUME = "resume"
    WORKSPACE_LAST_USED = "workspace_last_used"
    GLOBAL_PREFERRED = "global_preferred"
    AUTO_SINGLE = "auto_single"
    PROMPTED = "prompted"


@dataclass(frozen=True)
class LaunchReadiness:
    """Fully typed snapshot of launch readiness for one provider.

    Derived booleans prevent callers from re-implementing status→action logic.
    ``launch_ready`` is True only when both image and auth are present.
    """

    provider_id: str
    resolution_source: ProviderResolutionSource
    image_status: ImageStatus
    auth_status: AuthStatus
    requires_image_bootstrap: bool
    requires_auth_bootstrap: bool
    launch_ready: bool


# ─────────────────────────────────────────────────────────────────────────────
# Pure decision functions (no I/O)
# ─────────────────────────────────────────────────────────────────────────────


def allowed_provider_ids(
    normalized_org: NormalizedOrgConfig | None,
    team: str | None,
) -> tuple[str, ...]:
    """Return the allowed providers for the active team, or all when unrestricted.

    Moved from flow._allowed_provider_ids to make it a public, reusable contract.
    """
    if normalized_org is not None and team:
        team_profile = normalized_org.get_profile(team)
        if team_profile is not None:
            return team_profile.allowed_providers
    return ()


def resolve_launch_provider(
    *,
    cli_flag: str | None,
    resume_provider: str | None,
    workspace_path: Path | None,
    config_provider: str | None,
    normalized_org: NormalizedOrgConfig | None,
    team: str | None,
    adapters: Any,
    non_interactive: bool,
) -> tuple[str | None, ProviderResolutionSource]:
    """Resolve provider for a launch request with standard precedence.

    Returns (provider_id, source) — the resolved provider and how it was chosen.
    Pure data assembly → delegates to choose_start_provider().
    """
    allowed = allowed_provider_ids(normalized_org, team)

    # workspace_last_used requires a valid workspace path
    workspace_last_used: str | None = None
    if workspace_path is not None:
        from scc_cli.workspace_local_config import get_workspace_last_used_provider

        workspace_last_used = get_workspace_last_used_provider(workspace_path)

    connected = connected_provider_ids(adapters, allowed_providers=allowed)

    # Track which source resolved the provider by wrapping the prompt callback
    source_holder: list[ProviderResolutionSource] = []

    def tracking_prompt(
        candidates: tuple[str, ...],
        connected_ids: tuple[str, ...],
        default: str | None,
    ) -> str | None:
        source_holder.append(ProviderResolutionSource.PROMPTED)
        return prompt_for_provider_choice(candidates, connected_ids, default)

    provider_id = choose_start_provider(
        cli_flag=cli_flag,
        resume_provider=resume_provider,
        workspace_last_used=workspace_last_used,
        config_provider=config_provider,
        connected_provider_ids=connected,
        allowed_providers=allowed,
        non_interactive=non_interactive,
        prompt_choice=tracking_prompt,
    )

    if source_holder:
        return provider_id, ProviderResolutionSource.PROMPTED

    # Determine source from what was provided
    source = _infer_resolution_source(
        provider_id=provider_id,
        cli_flag=cli_flag,
        resume_provider=resume_provider,
        workspace_last_used=workspace_last_used,
        config_provider=config_provider,
        connected=connected,
        allowed=allowed,
    )
    return provider_id, source


def _infer_resolution_source(
    *,
    provider_id: str | None,
    cli_flag: str | None,
    resume_provider: str | None,
    workspace_last_used: str | None,
    config_provider: str | None,
    connected: tuple[str, ...],
    allowed: tuple[str, ...],
) -> ProviderResolutionSource:
    """Infer which precedence tier produced the resolved provider_id.

    Mirrors the precedence in resolve_provider_preference + auto-single fallback.
    """
    if provider_id is None:
        # No resolution — return EXPLICIT as a sentinel (caller checks None)
        return ProviderResolutionSource.EXPLICIT

    if cli_flag is not None and cli_flag == provider_id:
        return ProviderResolutionSource.EXPLICIT
    if resume_provider is not None and resume_provider == provider_id:
        return ProviderResolutionSource.RESUME
    if workspace_last_used is not None and workspace_last_used == provider_id:
        return ProviderResolutionSource.WORKSPACE_LAST_USED
    if config_provider is not None and config_provider == provider_id:
        return ProviderResolutionSource.GLOBAL_PREFERRED

    # Auto-single: only one provider was connected or allowed
    from scc_cli.core.provider_resolution import KNOWN_PROVIDERS

    candidates = allowed or KNOWN_PROVIDERS
    connected_allowed = tuple(pid for pid in connected if pid in candidates)
    if len(connected_allowed) == 1 or len(candidates) == 1:
        return ProviderResolutionSource.AUTO_SINGLE

    return ProviderResolutionSource.EXPLICIT


# ─────────────────────────────────────────────────────────────────────────────
# Readiness collection (reads adapter state, no mutations)
# ─────────────────────────────────────────────────────────────────────────────


def _auth_readiness_to_status(readiness: AuthReadiness | None) -> AuthStatus:
    """Map the existing AuthReadiness contract to the typed AuthStatus enum."""
    if readiness is None:
        return AuthStatus.UNKNOWN
    status = readiness.status
    if status == "present":
        return AuthStatus.PRESENT
    if status == "missing":
        return AuthStatus.MISSING
    if status == "expired":
        return AuthStatus.EXPIRED
    return AuthStatus.UNKNOWN


def _check_image_available(provider_id: str) -> ImageStatus:
    """Probe whether the provider container image exists locally.

    Uses provider_image._provider_image_exists() but catches all subprocess
    errors to return UNKNOWN rather than crash the readiness check.
    """
    try:
        from scc_cli.commands.launch.provider_image import _provider_image_exists
        from scc_cli.core.provider_registry import get_runtime_spec

        spec = get_runtime_spec(provider_id)
        if _provider_image_exists(spec.image_ref):
            return ImageStatus.AVAILABLE
        return ImageStatus.MISSING
    except Exception:
        return ImageStatus.UNKNOWN


def collect_launch_readiness(
    provider_id: str,
    resolution_source: ProviderResolutionSource,
    adapters: Any,
) -> LaunchReadiness:
    """Check image availability and auth readiness, return typed state.

    No fixing, no side effects — just reads current state.
    """
    image_status = _check_image_available(provider_id)

    # Get auth readiness for this specific provider
    readiness_map = collect_provider_readiness(
        adapters, allowed_providers=(provider_id,)
    )
    auth_readiness = readiness_map.get(provider_id)
    auth_status = _auth_readiness_to_status(auth_readiness)

    requires_image = image_status == ImageStatus.MISSING
    requires_auth = auth_status in (AuthStatus.MISSING, AuthStatus.EXPIRED)

    return LaunchReadiness(
        provider_id=provider_id,
        resolution_source=resolution_source,
        image_status=image_status,
        auth_status=auth_status,
        requires_image_bootstrap=requires_image,
        requires_auth_bootstrap=requires_auth,
        launch_ready=(not requires_image and not requires_auth),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Side-effect function (fixes gaps or fails)
# ─────────────────────────────────────────────────────────────────────────────


def ensure_launch_ready(
    readiness: LaunchReadiness,
    *,
    adapters: Any,
    console: Any,
    non_interactive: bool,
    show_notice: Any,
) -> None:
    """Fix launch readiness gaps or raise typed errors.

    Uses readiness.requires_image_bootstrap / requires_auth_bootstrap
    to decide — no re-probing. In non-interactive mode: raises typed
    ProviderNotReadyError with actionable guidance instead of prompting.

    The ``adapters`` parameter provides access to the provider adapter
    for performing auth bootstrap (browser sign-in flow).
    """
    if readiness.launch_ready:
        return

    if readiness.requires_image_bootstrap:
        from scc_cli.commands.launch.provider_image import ensure_provider_image

        ensure_provider_image(
            readiness.provider_id,
            console=console,
            non_interactive=non_interactive,
            show_notice=show_notice,
        )

    if readiness.requires_auth_bootstrap:
        _ensure_auth(
            readiness,
            adapters=adapters,
            non_interactive=non_interactive,
            show_notice=show_notice,
        )


def _ensure_auth(
    readiness: LaunchReadiness,
    *,
    adapters: Any,
    non_interactive: bool,
    show_notice: Any,
) -> None:
    """Handle auth bootstrap for a provider with missing/expired auth.

    Non-interactive: raises ProviderNotReadyError with actionable guidance.
    Interactive: shows the notice, then calls provider.bootstrap_auth()
    to trigger the browser sign-in flow.
    """
    from scc_cli.commands.launch.dependencies import get_agent_provider
    from scc_cli.core.provider_resolution import get_provider_display_name

    display_name = get_provider_display_name(readiness.provider_id)

    if non_interactive:
        raise ProviderNotReadyError(
            provider_id=readiness.provider_id,
            user_message=(
                f"{display_name} auth cache is {readiness.auth_status.value} "
                f"and this start is non-interactive."
            ),
            suggested_action=(
                f"Run 'scc start --provider {readiness.provider_id}' interactively "
                "once and complete the one-time browser sign-in."
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

    provider = get_agent_provider(adapters, readiness.provider_id)
    if provider is not None:
        try:
            provider.bootstrap_auth()
        except ProviderNotReadyError:
            raise
        except Exception as exc:
            raise ProviderNotReadyError(
                provider_id=readiness.provider_id,
                user_message=(
                    f"{display_name} auth bootstrap failed: {exc}"
                ),
                suggested_action=(
                    f"Run 'scc start --provider {readiness.provider_id}' interactively "
                    "to complete the browser sign-in. If the issue persists, "
                    f"run 'scc doctor --provider {readiness.provider_id}' to diagnose."
                ),
            ) from exc
