"""Governed-artifact diagnostics for the doctor module.

Reports:
1. Active team context and enabled bundles
2. Selected provider and effective render plan
3. Rendered vs skipped vs blocked artifacts with reasons
4. Bundle resolution health (all referenced bundles exist, all artifacts resolvable)
"""

from __future__ import annotations

import logging

from scc_cli import config as _config_module
from scc_cli.core.bundle_resolver import (
    BundleResolutionResult,
    resolve_render_plan,
)
from scc_cli.core.enums import SeverityLevel
from scc_cli.ports.config_models import NormalizedOrgConfig

from ..types import CheckResult

logger = logging.getLogger(__name__)


def _load_raw_org_config() -> dict[str, object] | None:
    """Load raw cached org config for normalization."""
    return _config_module.load_cached_org_config()


def _get_selected_profile() -> str | None:
    """Return the selected team profile name."""
    return _config_module.get_selected_profile()


def _normalize_org_config(raw: dict[str, object]) -> NormalizedOrgConfig:
    """Normalize raw org config dict into typed model.

    Uses the NormalizedOrgConfig.from_dict() factory to avoid a static
    doctor→adapters import that would violate the architectural import
    boundary (only bootstrap.py may import adapters).
    """
    # NormalizedOrgConfig.from_dict uses importlib internally to avoid
    # the ports→adapters boundary violation
    return NormalizedOrgConfig.from_dict(dict(raw))


def check_team_context() -> CheckResult | None:
    """Check active team context and enabled bundles.

    Reports which team profile is active and what bundles are enabled.

    Returns:
        CheckResult with team/bundle info, None if no org config.
    """
    try:
        raw_org = _load_raw_org_config()
        if raw_org is None:
            return CheckResult(
                name="Team Context",
                passed=True,
                message="No org config — standalone mode, no bundles active",
                severity=SeverityLevel.INFO,
            )

        profile_name = _get_selected_profile()
        if profile_name is None:
            return CheckResult(
                name="Team Context",
                passed=True,
                message="No team profile selected",
                severity=SeverityLevel.WARNING,
            )

        org = _normalize_org_config(raw_org)
        team = org.get_profile(profile_name)
        if team is None:
            available = org.list_profile_names()
            return CheckResult(
                name="Team Context",
                passed=False,
                message=(
                    f"Selected profile '{profile_name}' not found in org config; "
                    f"available: {available}"
                ),
                fix_hint="Run 'scc team select' to pick a valid profile",
                severity=SeverityLevel.ERROR,
            )

        bundles = team.enabled_bundles
        if not bundles:
            return CheckResult(
                name="Team Context",
                passed=True,
                message=f"Profile '{profile_name}' active — no bundles enabled",
                severity=SeverityLevel.INFO,
            )

        bundle_list = ", ".join(bundles)
        return CheckResult(
            name="Team Context",
            passed=True,
            message=f"Profile '{profile_name}' — bundles: [{bundle_list}]",
        )

    except Exception as exc:
        return CheckResult(
            name="Team Context",
            passed=False,
            message=f"Unexpected error checking team context: {exc}",
            severity=SeverityLevel.ERROR,
        )


def check_bundle_resolution(provider: str = "claude") -> CheckResult | None:
    """Check bundle resolution health for the active team and provider.

    Resolves all enabled bundles against the governed-artifacts catalog
    and reports effective, skipped, and failed artifacts.

    Args:
        provider: Target provider to resolve bundles for.

    Returns:
        CheckResult with resolution summary, None if no org config/profile.
    """
    try:
        raw_org = _load_raw_org_config()
        if raw_org is None:
            return None

        profile_name = _get_selected_profile()
        if profile_name is None:
            return None

        org = _normalize_org_config(raw_org)
        team = org.get_profile(profile_name)
        if team is None or not team.enabled_bundles:
            return None

        result = resolve_render_plan(org, profile_name, provider)

        return _format_resolution_result(result, provider)

    except Exception as exc:
        return CheckResult(
            name="Bundle Resolution",
            passed=False,
            message=f"Bundle resolution failed: {exc}",
            severity=SeverityLevel.ERROR,
        )


def _format_resolution_result(
    result: BundleResolutionResult,
    provider: str,
) -> CheckResult:
    """Format a BundleResolutionResult into a doctor CheckResult."""
    total_effective = sum(len(p.effective_artifacts) for p in result.plans)
    total_skipped = sum(len(p.skipped) for p in result.plans)
    diag_count = len(result.diagnostics)

    parts: list[str] = [f"provider={provider}"]
    parts.append(f"effective={total_effective}")
    if total_skipped > 0:
        parts.append(f"skipped={total_skipped}")
    if diag_count > 0:
        parts.append(f"diagnostics={diag_count}")

    has_errors = any(
        "not found" in d.reason
        for d in result.diagnostics
    )

    if has_errors:
        detail_lines: list[str] = []
        for d in result.diagnostics:
            if "not found" in d.reason:
                detail_lines.append(f"  {d.artifact_name}: {d.reason}")
        detail = "; ".join(detail_lines).strip()
        return CheckResult(
            name="Bundle Resolution",
            passed=False,
            message=f"Resolution errors ({', '.join(parts)}): {detail}",
            fix_hint="Check governed_artifacts catalog in org config",
            severity=SeverityLevel.ERROR,
        )

    return CheckResult(
        name="Bundle Resolution",
        passed=True,
        message=f"Resolved OK ({', '.join(parts)})",
    )


def check_catalog_health() -> CheckResult | None:
    """Check that the governed-artifacts catalog is structurally sound.

    Verifies: catalog exists, bundles reference valid artifacts,
    and bindings reference valid artifacts.

    Returns:
        CheckResult, or None if no org config.
    """
    try:
        raw_org = _load_raw_org_config()
        if raw_org is None:
            return None

        org = _normalize_org_config(raw_org)
        catalog = org.governed_artifacts

        if not catalog.bundles and not catalog.artifacts and not catalog.bindings:
            return CheckResult(
                name="Artifact Catalog",
                passed=True,
                message="No governed artifacts defined",
                severity=SeverityLevel.INFO,
            )

        problems: list[str] = []

        # Check that bundles reference existing artifacts
        for bundle_id, bundle in catalog.bundles.items():
            for art_name in bundle.artifacts:
                if art_name not in catalog.artifacts:
                    problems.append(
                        f"bundle '{bundle_id}' references missing artifact '{art_name}'"
                    )

        # Check that bindings reference existing artifacts
        for art_name in catalog.bindings:
            if art_name not in catalog.artifacts:
                problems.append(
                    f"binding exists for unknown artifact '{art_name}'"
                )

        if problems:
            summary = "; ".join(problems[:3])
            suffix = f" (+{len(problems) - 3} more)" if len(problems) > 3 else ""
            return CheckResult(
                name="Artifact Catalog",
                passed=False,
                message=f"Catalog issues: {summary}{suffix}",
                fix_hint="Review governed_artifacts section in org config",
                severity=SeverityLevel.ERROR,
            )

        artifact_count = len(catalog.artifacts)
        bundle_count = len(catalog.bundles)
        return CheckResult(
            name="Artifact Catalog",
            passed=True,
            message=f"{artifact_count} artifact(s), {bundle_count} bundle(s) — all references valid",
        )

    except Exception as exc:
        return CheckResult(
            name="Artifact Catalog",
            passed=False,
            message=f"Catalog health check failed: {exc}",
            severity=SeverityLevel.ERROR,
        )


def build_artifact_diagnostics_summary(
    provider: str = "claude",
) -> dict[str, object]:
    """Build a diagnostics summary dict suitable for support bundles.

    Returns a dict with:
    - team_context: active profile and bundles
    - resolution: per-bundle effective/skipped/diagnostics
    - catalog: artifact/bundle counts and reference health

    This is the support-bundle integration point.
    """
    summary: dict[str, object] = {}

    # Team context
    raw_org = _load_raw_org_config()
    if raw_org is None:
        summary["team_context"] = {"state": "standalone", "profile": None, "bundles": []}
        summary["resolution"] = {"state": "not_applicable"}
        summary["catalog"] = {"state": "not_applicable"}
        return summary

    profile_name = _get_selected_profile()
    if profile_name is None:
        summary["team_context"] = {"state": "no_profile_selected", "profile": None, "bundles": []}
        summary["resolution"] = {"state": "not_applicable"}
        summary["catalog"] = {"state": "not_applicable"}
        return summary

    try:
        org = _normalize_org_config(raw_org)
    except Exception as exc:
        summary["team_context"] = {"state": "error", "error": str(exc)}
        summary["resolution"] = {"state": "error", "error": str(exc)}
        summary["catalog"] = {"state": "error", "error": str(exc)}
        return summary

    team = org.get_profile(profile_name)
    bundles_list = list(team.enabled_bundles) if team else []
    summary["team_context"] = {
        "state": "active",
        "profile": profile_name,
        "bundles": bundles_list,
        "profile_found": team is not None,
    }

    # Resolution
    if team is None or not team.enabled_bundles:
        summary["resolution"] = {"state": "no_bundles", "plans": []}
    else:
        try:
            result = resolve_render_plan(org, profile_name, provider)
            plans_data: list[dict[str, object]] = []
            for plan in result.plans:
                plans_data.append({
                    "bundle_id": plan.bundle_id,
                    "provider": plan.provider,
                    "effective_artifacts": list(plan.effective_artifacts),
                    "skipped": list(plan.skipped),
                    "binding_count": len(plan.bindings),
                })
            diagnostics_data: list[dict[str, str]] = [
                {"artifact": d.artifact_name, "reason": d.reason}
                for d in result.diagnostics
            ]
            summary["resolution"] = {
                "state": "resolved",
                "provider": provider,
                "plans": plans_data,
                "diagnostics": diagnostics_data,
            }
        except Exception as exc:
            summary["resolution"] = {"state": "error", "error": str(exc)}

    # Catalog health
    catalog = org.governed_artifacts
    summary["catalog"] = {
        "artifact_count": len(catalog.artifacts),
        "bundle_count": len(catalog.bundles),
        "binding_count": len(catalog.bindings),
        "artifact_names": sorted(catalog.artifacts.keys()),
        "bundle_names": sorted(catalog.bundles.keys()),
    }

    return summary
