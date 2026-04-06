"""Bundle resolution: compute ArtifactRenderPlan from NormalizedOrgConfig.

Pure core function — no imports from marketplace/, adapters/, or commands/.

resolve_render_plan() reads a team's enabled_bundles, resolves each bundle ID
against the org's governed_artifacts catalog, filters by install_intent and
provider compatibility, and returns an ArtifactRenderPlan per bundle.

Fail-closed semantics:
- Missing bundle ID → BundleResolutionError with available alternatives.
- Disabled bundle → skip with audit diagnostic (not an error).
- Invalid artifact reference → InvalidArtifactReferenceError blocks the bundle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from scc_cli.core.errors import (
    BundleResolutionError,
    InvalidArtifactReferenceError,
)
from scc_cli.core.governed_artifacts import (
    ArtifactInstallIntent,
    ArtifactKind,
    ArtifactRenderPlan,
    PortableArtifact,
    ProviderArtifactBinding,
)
from scc_cli.ports.config_models import GovernedArtifactsCatalog, NormalizedOrgConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolution diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BundleResolutionDiagnostic:
    """Diagnostic info about why an artifact was skipped during resolution."""

    artifact_name: str
    reason: str


@dataclass(frozen=True)
class BundleResolutionResult:
    """Complete resolution result for a team's enabled bundles.

    Contains the render plans (one per resolved bundle) plus diagnostics
    about what was skipped or could not be resolved.
    """

    plans: tuple[ArtifactRenderPlan, ...]
    diagnostics: tuple[BundleResolutionDiagnostic, ...]


# ---------------------------------------------------------------------------
# Resolution logic
# ---------------------------------------------------------------------------


def _resolve_single_bundle(
    bundle_id: str,
    provider: str,
    catalog: GovernedArtifactsCatalog,
    *,
    fail_closed: bool = False,
) -> tuple[ArtifactRenderPlan, list[BundleResolutionDiagnostic]]:
    """Resolve one bundle into an ArtifactRenderPlan for the given provider.

    Args:
        bundle_id: The bundle identifier to resolve.
        provider: Target provider (e.g. ``'claude'``, ``'codex'``).
        catalog: Governed artifacts catalog to resolve against.
        fail_closed: If True, missing bundles and invalid artifact references
            raise typed exceptions instead of producing diagnostics.

    Returns:
        A tuple of (plan, diagnostics) where diagnostics lists skipped artifacts.

    Raises:
        BundleResolutionError: If ``fail_closed`` is True and the bundle
            is not found in the catalog.
        InvalidArtifactReferenceError: If ``fail_closed`` is True and an
            artifact referenced by the bundle does not exist in the catalog.
    """
    bundle = catalog.bundles.get(bundle_id)
    if bundle is None:
        available = sorted(catalog.bundles.keys())
        if fail_closed:
            raise BundleResolutionError(
                bundle_id=bundle_id,
                available_bundles=tuple(available),
            )
        diag = BundleResolutionDiagnostic(
            artifact_name=bundle_id,
            reason=f"bundle not found in catalog; available: {available}",
        )
        return (
            ArtifactRenderPlan(bundle_id=bundle_id, provider=provider),
            [diag],
        )

    # If the bundle itself is disabled, skip everything (audit-logged, not error)
    if bundle.install_intent == ArtifactInstallIntent.DISABLED:
        logger.info("Bundle '%s' is disabled — skipping", bundle_id)
        diag = BundleResolutionDiagnostic(
            artifact_name=bundle_id,
            reason="bundle install_intent is disabled",
        )
        return (
            ArtifactRenderPlan(bundle_id=bundle_id, provider=provider),
            [diag],
        )

    effective_artifacts: list[str] = []
    collected_bindings: list[ProviderArtifactBinding] = []
    collected_portable: list[PortableArtifact] = []
    skipped: list[str] = []
    diagnostics: list[BundleResolutionDiagnostic] = []

    for art_name in bundle.artifacts:
        artifact = catalog.artifacts.get(art_name)
        if artifact is None:
            if fail_closed:
                raise InvalidArtifactReferenceError(
                    bundle_id=bundle_id,
                    artifact_name=art_name,
                    reason="artifact not found in governed artifacts catalog",
                )
            skipped.append(art_name)
            diagnostics.append(
                BundleResolutionDiagnostic(
                    artifact_name=art_name,
                    reason="artifact not found in catalog",
                )
            )
            continue

        # Check install_intent — disabled and request-only are skipped
        if artifact.install_intent == ArtifactInstallIntent.DISABLED:
            skipped.append(art_name)
            diagnostics.append(
                BundleResolutionDiagnostic(
                    artifact_name=art_name,
                    reason="artifact install_intent is disabled",
                )
            )
            continue

        if artifact.install_intent == ArtifactInstallIntent.REQUEST_ONLY:
            skipped.append(art_name)
            diagnostics.append(
                BundleResolutionDiagnostic(
                    artifact_name=art_name,
                    reason="artifact install_intent is request-only (not auto-rendered)",
                )
            )
            continue

        # Find provider-compatible bindings
        art_bindings = catalog.bindings.get(art_name, ())
        provider_bindings = tuple(b for b in art_bindings if b.provider == provider)

        if not provider_bindings:
            # Artifact exists but has no binding for this provider.
            # Native integrations always require a binding — skip them.
            if artifact.kind == ArtifactKind.NATIVE_INTEGRATION:
                skipped.append(art_name)
                diagnostics.append(
                    BundleResolutionDiagnostic(
                        artifact_name=art_name,
                        reason=f"native_integration has no binding for provider '{provider}'",
                    )
                )
                continue

            # Skills and MCP servers are portable — they can be rendered
            # from their source metadata without a provider-specific
            # binding (D023). Include them in portable_artifacts so
            # renderers can project them into provider-native surfaces.
            if artifact.kind in (ArtifactKind.SKILL, ArtifactKind.MCP_SERVER):
                collected_portable.append(
                    PortableArtifact(
                        name=artifact.name,
                        kind=artifact.kind,
                        source_type=artifact.source_type,
                        source_url=artifact.source_url,
                        source_path=artifact.source_path,
                        source_ref=artifact.source_ref,
                        version=artifact.version,
                    )
                )

        effective_artifacts.append(art_name)
        collected_bindings.extend(provider_bindings)

    plan = ArtifactRenderPlan(
        bundle_id=bundle_id,
        provider=provider,
        bindings=tuple(collected_bindings),
        skipped=tuple(skipped),
        effective_artifacts=tuple(effective_artifacts),
        portable_artifacts=tuple(collected_portable),
    )
    return plan, diagnostics


def resolve_render_plan(
    org_config: NormalizedOrgConfig,
    team_name: str,
    provider: str,
    *,
    fail_closed: bool = False,
) -> BundleResolutionResult:
    """Resolve all enabled bundles for a team into ArtifactRenderPlans.

    Pure function — reads from NormalizedOrgConfig, produces plans and
    diagnostics. No side effects.

    Args:
        org_config: The normalized org configuration containing the
            governed_artifacts catalog and team profiles.
        team_name: Name of the team profile to resolve bundles for.
        provider: Target provider identifier (e.g. 'claude', 'codex').
        fail_closed: If True, missing bundles and invalid artifact references
            raise typed exceptions (``BundleResolutionError``,
            ``InvalidArtifactReferenceError``) instead of producing
            diagnostics. Default is False for backward compatibility.

    Returns:
        BundleResolutionResult with plans and diagnostics.

    Raises:
        ValueError: If the team profile does not exist in the org config.
        BundleResolutionError: If ``fail_closed`` is True and a bundle
            referenced by the team does not exist in the catalog.
        InvalidArtifactReferenceError: If ``fail_closed`` is True and a
            bundle contains an artifact that does not exist in the catalog.
    """
    team = org_config.get_profile(team_name)
    if team is None:
        available = org_config.list_profile_names()
        raise ValueError(
            f"Team profile '{team_name}' not found in org config; available profiles: {available}"
        )

    catalog = org_config.governed_artifacts

    if not team.enabled_bundles:
        return BundleResolutionResult(plans=(), diagnostics=())

    all_plans: list[ArtifactRenderPlan] = []
    all_diagnostics: list[BundleResolutionDiagnostic] = []

    for bundle_id in team.enabled_bundles:
        plan, diags = _resolve_single_bundle(bundle_id, provider, catalog, fail_closed=fail_closed)
        all_plans.append(plan)
        all_diagnostics.extend(diags)

    return BundleResolutionResult(
        plans=tuple(all_plans),
        diagnostics=tuple(all_diagnostics),
    )
