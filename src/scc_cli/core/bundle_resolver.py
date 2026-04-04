"""Bundle resolution: compute ArtifactRenderPlan from NormalizedOrgConfig.

Pure core function — no imports from marketplace/, adapters/, or commands/.

resolve_render_plan() reads a team's enabled_bundles, resolves each bundle ID
against the org's governed_artifacts catalog, filters by install_intent and
provider compatibility, and returns an ArtifactRenderPlan per bundle.
"""

from __future__ import annotations

from dataclasses import dataclass

from scc_cli.core.governed_artifacts import (
    ArtifactInstallIntent,
    ArtifactKind,
    ArtifactRenderPlan,
    ProviderArtifactBinding,
)
from scc_cli.ports.config_models import GovernedArtifactsCatalog, NormalizedOrgConfig

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
) -> tuple[ArtifactRenderPlan, list[BundleResolutionDiagnostic]]:
    """Resolve one bundle into an ArtifactRenderPlan for the given provider.

    Returns:
        A tuple of (plan, diagnostics) where diagnostics lists skipped artifacts.
    """
    bundle = catalog.bundles.get(bundle_id)
    if bundle is None:
        available = sorted(catalog.bundles.keys())
        diag = BundleResolutionDiagnostic(
            artifact_name=bundle_id,
            reason=f"bundle not found in catalog; available: {available}",
        )
        return (
            ArtifactRenderPlan(bundle_id=bundle_id, provider=provider),
            [diag],
        )

    # If the bundle itself is disabled, skip everything
    if bundle.install_intent == ArtifactInstallIntent.DISABLED:
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
    skipped: list[str] = []
    diagnostics: list[BundleResolutionDiagnostic] = []

    for art_name in bundle.artifacts:
        artifact = catalog.artifacts.get(art_name)
        if artifact is None:
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
            # Skills and MCP servers are portable — they still count as effective
            # even without a provider-specific binding.
            # Native integrations require a binding.
            if artifact.kind == ArtifactKind.NATIVE_INTEGRATION:
                skipped.append(art_name)
                diagnostics.append(
                    BundleResolutionDiagnostic(
                        artifact_name=art_name,
                        reason=f"native_integration has no binding for provider '{provider}'",
                    )
                )
                continue

        effective_artifacts.append(art_name)
        collected_bindings.extend(provider_bindings)

    plan = ArtifactRenderPlan(
        bundle_id=bundle_id,
        provider=provider,
        bindings=tuple(collected_bindings),
        skipped=tuple(skipped),
        effective_artifacts=tuple(effective_artifacts),
    )
    return plan, diagnostics


def resolve_render_plan(
    org_config: NormalizedOrgConfig,
    team_name: str,
    provider: str,
) -> BundleResolutionResult:
    """Resolve all enabled bundles for a team into ArtifactRenderPlans.

    Pure function — reads from NormalizedOrgConfig, produces plans and
    diagnostics. No side effects.

    Args:
        org_config: The normalized org configuration containing the
            governed_artifacts catalog and team profiles.
        team_name: Name of the team profile to resolve bundles for.
        provider: Target provider identifier (e.g. 'claude', 'codex').

    Returns:
        BundleResolutionResult with plans and diagnostics.

    Raises:
        ValueError: If the team profile does not exist in the org config.
    """
    team = org_config.get_profile(team_name)
    if team is None:
        available = org_config.list_profile_names()
        raise ValueError(
            f"Team profile '{team_name}' not found in org config; "
            f"available profiles: {available}"
        )

    catalog = org_config.governed_artifacts

    if not team.enabled_bundles:
        return BundleResolutionResult(plans=(), diagnostics=())

    all_plans: list[ArtifactRenderPlan] = []
    all_diagnostics: list[BundleResolutionDiagnostic] = []

    for bundle_id in team.enabled_bundles:
        plan, diags = _resolve_single_bundle(bundle_id, provider, catalog)
        all_plans.append(plan)
        all_diagnostics.extend(diags)

    return BundleResolutionResult(
        plans=tuple(all_plans),
        diagnostics=tuple(all_diagnostics),
    )
