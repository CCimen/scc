"""Tests for governed-artifact doctor checks and support bundle diagnostics.

Covers:
- check_team_context: team profile and bundle reporting
- check_bundle_resolution: resolution health for active provider
- check_catalog_health: catalog structural integrity
- build_artifact_diagnostics_summary: support-bundle integration
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

from scc_cli.core.governed_artifacts import (
    ArtifactBundle,
    ArtifactInstallIntent,
    ArtifactKind,
    GovernedArtifact,
    ProviderArtifactBinding,
)
from scc_cli.doctor.checks.artifacts import (
    build_artifact_diagnostics_summary,
    check_bundle_resolution,
    check_catalog_health,
    check_team_context,
)
from scc_cli.ports.config_models import (
    GovernedArtifactsCatalog,
    NormalizedOrgConfig,
    NormalizedTeamConfig,
    OrganizationInfo,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_org_config(
    *,
    profile_name: str = "dev-team",
    bundles: tuple[str, ...] = (),
    artifacts: dict[str, GovernedArtifact] | None = None,
    catalog_bundles: dict[str, ArtifactBundle] | None = None,
    bindings: dict[str, tuple[ProviderArtifactBinding, ...]] | None = None,
) -> NormalizedOrgConfig:
    """Build a minimal NormalizedOrgConfig for testing."""
    team = NormalizedTeamConfig(name=profile_name, enabled_bundles=bundles)
    catalog = GovernedArtifactsCatalog(
        artifacts=artifacts or {},
        bundles=catalog_bundles or {},
        bindings=bindings or {},
    )
    return NormalizedOrgConfig(
        organization=OrganizationInfo(name="Test Org"),
        profiles={profile_name: team},
        governed_artifacts=catalog,
    )


def _make_raw_org(
    *,
    profile_name: str = "dev-team",
    bundles: list[str] | None = None,
    governed_artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a raw org config dict for normalization tests."""
    raw: dict[str, Any] = {
        "organization": {"name": "Test Org"},
        "profiles": {
            profile_name: {
                "description": "Test team",
            }
        },
    }
    if bundles is not None:
        raw["profiles"][profile_name]["enabled_bundles"] = bundles
    if governed_artifacts is not None:
        raw["governed_artifacts"] = governed_artifacts
    return raw


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_RAW = "scc_cli.doctor.checks.artifacts._load_raw_org_config"
_PATCH_PROFILE = "scc_cli.doctor.checks.artifacts._get_selected_profile"
_PATCH_NORMALIZE = "scc_cli.doctor.checks.artifacts._normalize_org_config"


# ═══════════════════════════════════════════════════════════════════════════════
# check_team_context
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckTeamContext:
    """Tests for check_team_context()."""

    def test_standalone_mode_when_no_org_config(self) -> None:
        """No org config → standalone info message."""
        with patch(_PATCH_RAW, return_value=None):
            result = check_team_context()

        assert result is not None
        assert result.passed is True
        assert "standalone" in result.message.lower()

    def test_no_profile_selected(self) -> None:
        """Org config present but no profile selected → warning."""
        with (
            patch(_PATCH_RAW, return_value={"organization": {"name": "X"}}),
            patch(_PATCH_PROFILE, return_value=None),
        ):
            result = check_team_context()

        assert result is not None
        assert result.passed is True
        assert "no team profile" in result.message.lower()

    def test_profile_not_found_in_org(self) -> None:
        """Selected profile doesn't exist in org → error with fix hint."""
        org = _make_org_config(profile_name="other-team")
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="missing-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_team_context()

        assert result is not None
        assert result.passed is False
        assert "not found" in result.message
        assert result.fix_hint is not None

    def test_profile_found_no_bundles(self) -> None:
        """Active profile with no bundles → info."""
        org = _make_org_config(profile_name="dev-team", bundles=())
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_team_context()

        assert result is not None
        assert result.passed is True
        assert "no bundles" in result.message.lower()

    def test_profile_with_bundles(self) -> None:
        """Active profile with bundles → lists them."""
        org = _make_org_config(
            profile_name="dev-team",
            bundles=("core-safety", "mcp-tools"),
        )
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_team_context()

        assert result is not None
        assert result.passed is True
        assert "core-safety" in result.message
        assert "mcp-tools" in result.message

    def test_handles_unexpected_exception(self) -> None:
        """Unexpected error → fail-safe error result."""
        with patch(_PATCH_RAW, side_effect=RuntimeError("boom")):
            result = check_team_context()

        assert result is not None
        assert result.passed is False
        assert "boom" in result.message


# ═══════════════════════════════════════════════════════════════════════════════
# check_bundle_resolution
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckBundleResolution:
    """Tests for check_bundle_resolution()."""

    def test_none_when_no_org_config(self) -> None:
        """No org config → None (skip)."""
        with patch(_PATCH_RAW, return_value=None):
            assert check_bundle_resolution() is None

    def test_none_when_no_profile(self) -> None:
        """No selected profile → None."""
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value=None),
        ):
            assert check_bundle_resolution() is None

    def test_none_when_no_bundles(self) -> None:
        """Profile with empty bundles → None."""
        org = _make_org_config(profile_name="dev-team", bundles=())
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            assert check_bundle_resolution() is None

    def test_resolution_success(self) -> None:
        """Successful resolution → passed result with counts."""
        art = GovernedArtifact(
            kind=ArtifactKind.SKILL,
            name="safety-rules",
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        bundle = ArtifactBundle(
            name="core-safety",
            artifacts=("safety-rules",),
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        org = _make_org_config(
            profile_name="dev-team",
            bundles=("core-safety",),
            artifacts={"safety-rules": art},
            catalog_bundles={"core-safety": bundle},
        )

        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_bundle_resolution()

        assert result is not None
        assert result.passed is True
        assert "effective=1" in result.message

    def test_resolution_with_missing_bundle(self) -> None:
        """Bundle not in catalog → error with diagnostics."""
        org = _make_org_config(
            profile_name="dev-team",
            bundles=("nonexistent-bundle",),
            # Empty catalog — bundle won't resolve
        )

        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_bundle_resolution()

        assert result is not None
        assert result.passed is False
        assert "not found" in result.message

    def test_resolution_exception(self) -> None:
        """Resolution crash → error result."""
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(
                _PATCH_NORMALIZE,
                side_effect=RuntimeError("normalization failed"),
            ),
        ):
            result = check_bundle_resolution()

        assert result is not None
        assert result.passed is False
        assert "failed" in result.message.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# check_catalog_health
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCatalogHealth:
    """Tests for check_catalog_health()."""

    def test_none_when_no_org_config(self) -> None:
        """No org config → None."""
        with patch(_PATCH_RAW, return_value=None):
            assert check_catalog_health() is None

    def test_empty_catalog(self) -> None:
        """No artifacts or bundles → info message."""
        org = _make_org_config()
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_catalog_health()

        assert result is not None
        assert result.passed is True
        assert "no governed artifacts" in result.message.lower()

    def test_healthy_catalog(self) -> None:
        """All references valid → pass with counts."""
        art = GovernedArtifact(kind=ArtifactKind.SKILL, name="safety-rules")
        bundle = ArtifactBundle(name="core", artifacts=("safety-rules",))
        org = _make_org_config(
            artifacts={"safety-rules": art},
            catalog_bundles={"core": bundle},
        )
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_catalog_health()

        assert result is not None
        assert result.passed is True
        assert "1 artifact" in result.message
        assert "1 bundle" in result.message

    def test_bundle_references_missing_artifact(self) -> None:
        """Bundle references unknown artifact → error."""
        bundle = ArtifactBundle(name="core", artifacts=("nonexistent",))
        org = _make_org_config(catalog_bundles={"core": bundle})
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_catalog_health()

        assert result is not None
        assert result.passed is False
        assert "missing artifact" in result.message

    def test_binding_for_unknown_artifact(self) -> None:
        """Binding exists for an artifact not in catalog → error."""
        binding = ProviderArtifactBinding(provider="claude")
        org = _make_org_config(
            bindings={"ghost-artifact": (binding,)},
        )
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            result = check_catalog_health()

        assert result is not None
        assert result.passed is False
        assert "unknown artifact" in result.message

    def test_handles_exception(self) -> None:
        """Exception during check → error result."""
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_NORMALIZE, side_effect=RuntimeError("bad")),
        ):
            result = check_catalog_health()

        assert result is not None
        assert result.passed is False


# ═══════════════════════════════════════════════════════════════════════════════
# build_artifact_diagnostics_summary (support bundle)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildArtifactDiagnosticsSummary:
    """Tests for support-bundle artifact diagnostics."""

    def test_standalone_mode(self) -> None:
        """No org config → standalone summary."""
        with patch(_PATCH_RAW, return_value=None):
            summary = build_artifact_diagnostics_summary()

        assert summary["team_context"]["state"] == "standalone"  # type: ignore[index]
        assert summary["resolution"]["state"] == "not_applicable"  # type: ignore[index]

    def test_no_profile_selected(self) -> None:
        """Org config but no profile → no_profile_selected."""
        with (
            patch(_PATCH_RAW, return_value={"organization": {"name": "X"}}),
            patch(_PATCH_PROFILE, return_value=None),
        ):
            summary = build_artifact_diagnostics_summary()

        assert summary["team_context"]["state"] == "no_profile_selected"  # type: ignore[index]

    def test_active_profile_with_resolved_bundles(self) -> None:
        """Full resolution scenario."""
        art = GovernedArtifact(
            kind=ArtifactKind.SKILL,
            name="safety-rules",
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        bundle = ArtifactBundle(
            name="core-safety",
            artifacts=("safety-rules",),
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        org = _make_org_config(
            profile_name="dev-team",
            bundles=("core-safety",),
            artifacts={"safety-rules": art},
            catalog_bundles={"core-safety": bundle},
        )
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            summary = build_artifact_diagnostics_summary()

        ctx = summary["team_context"]
        assert ctx["state"] == "active"  # type: ignore[index]
        assert ctx["profile"] == "dev-team"  # type: ignore[index]
        assert "core-safety" in ctx["bundles"]  # type: ignore[index,operator]

        res = summary["resolution"]
        assert res["state"] == "resolved"  # type: ignore[index]
        assert len(res["plans"]) == 1  # type: ignore[index,arg-type]
        plan = res["plans"][0]  # type: ignore[index]
        assert plan["effective_artifacts"] == ["safety-rules"]

        cat = summary["catalog"]
        assert cat["artifact_count"] == 1  # type: ignore[index]
        assert cat["bundle_count"] == 1  # type: ignore[index]

    def test_normalization_failure(self) -> None:
        """Normalization error → error state in all sections."""
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, side_effect=RuntimeError("parse error")),
        ):
            summary = build_artifact_diagnostics_summary()

        assert summary["team_context"]["state"] == "error"  # type: ignore[index]
        assert summary["resolution"]["state"] == "error"  # type: ignore[index]

    def test_profile_not_found_still_reports(self) -> None:
        """Selected profile missing from org → context reports it."""
        org = _make_org_config(profile_name="other-team")
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="missing-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            summary = build_artifact_diagnostics_summary()

        ctx = summary["team_context"]
        assert ctx["state"] == "active"  # type: ignore[index]
        assert ctx["profile_found"] is False  # type: ignore[index]

    def test_resolution_with_skipped_artifacts(self) -> None:
        """Resolution that skips disabled artifacts → diagnostics populated."""
        disabled_art = GovernedArtifact(
            kind=ArtifactKind.SKILL,
            name="deprecated-tool",
            install_intent=ArtifactInstallIntent.DISABLED,
        )
        active_art = GovernedArtifact(
            kind=ArtifactKind.SKILL,
            name="active-tool",
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        bundle = ArtifactBundle(
            name="mixed-bundle",
            artifacts=("active-tool", "deprecated-tool"),
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        org = _make_org_config(
            profile_name="dev-team",
            bundles=("mixed-bundle",),
            artifacts={
                "active-tool": active_art,
                "deprecated-tool": disabled_art,
            },
            catalog_bundles={"mixed-bundle": bundle},
        )
        with (
            patch(_PATCH_RAW, return_value={"profiles": {}}),
            patch(_PATCH_PROFILE, return_value="dev-team"),
            patch(_PATCH_NORMALIZE, return_value=org),
        ):
            summary = build_artifact_diagnostics_summary()

        res = summary["resolution"]
        assert res["state"] == "resolved"  # type: ignore[index]
        plans = res["plans"]  # type: ignore[index]
        assert len(plans) == 1  # type: ignore[arg-type]
        assert "deprecated-tool" in plans[0]["skipped"]  # type: ignore[index]
        assert "active-tool" in plans[0]["effective_artifacts"]  # type: ignore[index]


# ═══════════════════════════════════════════════════════════════════════════════
# Integration with run_all_checks
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunAllChecksIntegration:
    """Verify artifact checks are registered in run_all_checks."""

    def test_artifact_checks_are_registered(self) -> None:
        """Confirm the check names appear in run_all_checks output."""
        from scc_cli.doctor.checks import run_all_checks
        from scc_cli.doctor.types import CheckResult

        # Patch everything to isolate from real environment
        with ExitStack() as stack:
            mock_git = stack.enter_context(patch("scc_cli.doctor.checks.environment.check_git"))
            mock_docker = stack.enter_context(
                patch("scc_cli.doctor.checks.environment.check_docker")
            )
            mock_dd = stack.enter_context(
                patch("scc_cli.doctor.checks.environment.check_docker_desktop")
            )
            mock_ds = stack.enter_context(
                patch("scc_cli.doctor.checks.environment.check_docker_sandbox")
            )
            mock_dr = stack.enter_context(
                patch("scc_cli.doctor.checks.environment.check_docker_running")
            )
            mock_wsl = stack.enter_context(patch("scc_cli.doctor.checks.environment.check_wsl2"))
            mock_rb = stack.enter_context(
                patch("scc_cli.doctor.checks.environment.check_runtime_backend")
            )
            mock_cd = stack.enter_context(
                patch("scc_cli.doctor.checks.config.check_config_directory")
            )
            mock_ucv = stack.enter_context(
                patch("scc_cli.doctor.checks.config.check_user_config_valid")
            )
            stack.enter_context(
                patch(
                    "scc_cli.doctor.checks.worktree.check_git_version_for_worktrees",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch("scc_cli.doctor.checks.worktree.check_worktree_health", return_value=None)
            )
            stack.enter_context(
                patch(
                    "scc_cli.doctor.checks.worktree.check_worktree_branch_conflicts",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch(
                    "scc_cli.doctor.checks.organization.check_org_config_reachable",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch(
                    "scc_cli.doctor.checks.organization.check_marketplace_auth_available",
                    return_value=None,
                )
            )
            stack.enter_context(
                patch(
                    "scc_cli.doctor.checks.organization.check_credential_injection",
                    return_value=None,
                )
            )
            mock_cache = stack.enter_context(
                patch("scc_cli.doctor.checks.cache.check_cache_readable")
            )
            stack.enter_context(
                patch("scc_cli.doctor.checks.cache.check_cache_ttl_status", return_value=None)
            )
            mock_exc = stack.enter_context(
                patch("scc_cli.doctor.checks.cache.check_exception_stores")
            )
            mock_sp = stack.enter_context(patch("scc_cli.doctor.checks.safety.check_safety_policy"))
            stack.enter_context(
                patch(_PATCH_RAW, return_value={"organization": {"name": "Test"}, "profiles": {}})
            )
            stack.enter_context(patch(_PATCH_PROFILE, return_value="dev-team"))
            stub = CheckResult(name="stub", passed=True, message="ok")
            mock_git.return_value = stub
            mock_docker.return_value = stub
            mock_dd.return_value = stub
            mock_ds.return_value = stub
            mock_dr.return_value = stub
            mock_wsl.return_value = (stub, False)
            mock_rb.return_value = stub
            mock_cd.return_value = stub
            mock_ucv.return_value = stub
            mock_cache.return_value = stub
            mock_exc.return_value = stub
            mock_sp.return_value = stub

            results = run_all_checks()

        names = [r.name for r in results]
        assert "Team Context" in names
