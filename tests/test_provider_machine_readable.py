"""Tests for machine-readable provider_id outputs and provider-aware container naming.

Covers: build_dry_run_data, build_session_list_data, _container_name,
SandboxSpec.provider_id, and support bundle manifest provider_id.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


class TestBuildDryRunDataProviderId:
    """build_dry_run_data includes provider_id in output dict."""

    def test_with_provider_id(self, tmp_path: Path) -> None:
        from scc_cli.commands.launch.render import build_dry_run_data

        result = build_dry_run_data(
            workspace_path=tmp_path,
            team=None,
            org_config=None,
            project_config=None,
            provider_id="claude",
        )
        assert result["provider_id"] == "claude"

    def test_with_codex_provider_id(self, tmp_path: Path) -> None:
        from scc_cli.commands.launch.render import build_dry_run_data

        result = build_dry_run_data(
            workspace_path=tmp_path,
            team=None,
            org_config=None,
            project_config=None,
            provider_id="codex",
        )
        assert result["provider_id"] == "codex"

    def test_without_provider_id(self, tmp_path: Path) -> None:
        from scc_cli.commands.launch.render import build_dry_run_data

        result = build_dry_run_data(
            workspace_path=tmp_path,
            team=None,
            org_config=None,
            project_config=None,
        )
        assert result["provider_id"] is None


class TestBuildSessionListDataProviderId:
    """build_session_list_data includes provider_id."""

    def test_with_provider_id(self) -> None:
        from scc_cli.presentation.json.sessions_json import build_session_list_data

        result = build_session_list_data([], team="my-team", provider_id="claude")
        assert result["provider_id"] == "claude"
        assert result["team"] == "my-team"
        assert result["count"] == 0

    def test_without_provider_id(self) -> None:
        from scc_cli.presentation.json.sessions_json import build_session_list_data

        result = build_session_list_data([{"id": "1"}], team="t")
        assert result["provider_id"] is None
        assert result["count"] == 1

    def test_with_codex_provider_id(self) -> None:
        from scc_cli.presentation.json.sessions_json import build_session_list_data

        result = build_session_list_data([], provider_id="codex")
        assert result["provider_id"] == "codex"


class TestContainerNameProviderAware:
    """_container_name includes provider_id in hash, producing different names per provider."""

    def test_different_names_for_different_providers(self, tmp_path: Path) -> None:
        from scc_cli.adapters.oci_sandbox_runtime import _container_name

        name_claude = _container_name(tmp_path, "claude")
        name_codex = _container_name(tmp_path, "codex")
        assert name_claude != name_codex

    def test_empty_provider_id_backward_compat(self, tmp_path: Path) -> None:
        """Empty provider_id hashes just the workspace path (backward compat)."""
        from scc_cli.adapters.oci_sandbox_runtime import _container_name

        expected_digest = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:12]
        expected = f"scc-oci-{expected_digest}"
        assert _container_name(tmp_path) == expected
        assert _container_name(tmp_path, "") == expected

    def test_provider_id_changes_hash(self, tmp_path: Path) -> None:
        from scc_cli.adapters.oci_sandbox_runtime import _container_name

        name_default = _container_name(tmp_path)
        name_with_provider = _container_name(tmp_path, "claude")
        assert name_default != name_with_provider

    def test_deterministic(self, tmp_path: Path) -> None:
        from scc_cli.adapters.oci_sandbox_runtime import _container_name

        assert _container_name(tmp_path, "claude") == _container_name(tmp_path, "claude")

    def test_hash_format(self, tmp_path: Path) -> None:
        from scc_cli.adapters.oci_sandbox_runtime import _container_name

        name = _container_name(tmp_path, "codex")
        assert name.startswith("scc-oci-")
        assert len(name) == len("scc-oci-") + 12


class TestSandboxSpecProviderId:
    """SandboxSpec gains provider_id field."""

    def test_default_empty(self) -> None:
        from scc_cli.ports.models import MountSpec, SandboxSpec

        spec = SandboxSpec(
            image="test:latest",
            workspace_mount=MountSpec(source=Path("/ws"), target=Path("/ws")),
            workdir=Path("/ws"),
        )
        assert spec.provider_id == ""

    def test_explicit_provider_id(self) -> None:
        from scc_cli.ports.models import MountSpec, SandboxSpec

        spec = SandboxSpec(
            image="test:latest",
            workspace_mount=MountSpec(source=Path("/ws"), target=Path("/ws")),
            workdir=Path("/ws"),
            provider_id="codex",
        )
        assert spec.provider_id == "codex"


class TestSupportBundleManifestProviderId:
    """Support bundle manifest includes provider_id."""

    def test_provider_id_in_manifest(self, tmp_path: Path) -> None:
        from scc_cli.application.support_bundle import (
            SupportBundleDependencies,
            SupportBundleRequest,
            build_support_bundle_manifest,
        )

        mock_fs = MagicMock()
        mock_fs.exists.return_value = False

        mock_clock = MagicMock()
        mock_clock.now.return_value = MagicMock(isoformat=lambda: "2025-01-01T00:00:00")

        mock_doctor = MagicMock()
        mock_doctor.run.side_effect = Exception("skip")

        mock_archive = MagicMock()

        deps = SupportBundleDependencies(
            filesystem=mock_fs,
            clock=mock_clock,
            doctor_runner=mock_doctor,
            archive_writer=mock_archive,
        )

        request = SupportBundleRequest(
            output_path=tmp_path / "bundle.zip",
            redact_paths=False,
            workspace_path=tmp_path,
        )

        with patch(
            "scc_cli.application.support_bundle.config.get_selected_provider",
            return_value="claude",
        ):
            manifest = build_support_bundle_manifest(request, dependencies=deps)

        assert "provider_id" in manifest
        assert manifest["provider_id"] == "claude"

    def test_provider_id_none_when_unset(self, tmp_path: Path) -> None:
        from scc_cli.application.support_bundle import (
            SupportBundleDependencies,
            SupportBundleRequest,
            build_support_bundle_manifest,
        )

        mock_fs = MagicMock()
        mock_fs.exists.return_value = False

        mock_clock = MagicMock()
        mock_clock.now.return_value = MagicMock(isoformat=lambda: "2025-01-01T00:00:00")

        mock_doctor = MagicMock()
        mock_doctor.run.side_effect = Exception("skip")

        mock_archive = MagicMock()

        deps = SupportBundleDependencies(
            filesystem=mock_fs,
            clock=mock_clock,
            doctor_runner=mock_doctor,
            archive_writer=mock_archive,
        )

        request = SupportBundleRequest(
            output_path=tmp_path / "bundle.zip",
            redact_paths=False,
            workspace_path=tmp_path,
        )

        with patch(
            "scc_cli.application.support_bundle.config.get_selected_provider",
            return_value=None,
        ):
            manifest = build_support_bundle_manifest(request, dependencies=deps)

        assert manifest["provider_id"] is None


class TestBuildSandboxSpecPopulatesProviderId:
    """_build_sandbox_spec populates provider_id from the provider adapter."""

    def _make_resolver_result(self) -> Any:
        from scc_cli.core.workspace import ResolverResult

        return ResolverResult(
            workspace_root=Path("/ws"),
            mount_root=Path("/ws"),
            entry_dir=Path("/ws"),
            container_workdir="/ws",
            is_auto_detected=False,
            is_suspicious=False,
        )

    def test_oci_backend_with_provider(self) -> None:
        from scc_cli.application.start_session import StartSessionRequest, _build_sandbox_spec
        from scc_cli.core.contracts import RuntimeInfo

        mock_provider = MagicMock()
        mock_provider.capability_profile.return_value = MagicMock(
            provider_id="codex",
            required_destination_set="codex-api",
        )

        request = StartSessionRequest(
            workspace_path=Path("/ws"),
            workspace_arg="/ws",
            entry_dir=Path("/ws"),
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=False,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="codex",
        )

        runtime_info = RuntimeInfo(
            runtime_id="docker",
            display_name="Docker",
            cli_name="docker",
            supports_oci=True,
            supports_internal_networks=True,
            supports_host_network=True,
            preferred_backend="oci",
        )

        with patch(
            "scc_cli.application.start_session.resolve_destination_sets",
            return_value=(),
        ):
            spec = _build_sandbox_spec(
                request=request,
                resolver_result=self._make_resolver_result(),
                effective_config=None,
                agent_settings=None,
                runtime_info=runtime_info,
                agent_provider=mock_provider,
            )

        assert spec is not None
        assert spec.provider_id == "codex"

    def test_non_oci_backend_with_provider(self) -> None:
        from scc_cli.application.start_session import StartSessionRequest, _build_sandbox_spec

        mock_provider = MagicMock()
        mock_provider.capability_profile.return_value = MagicMock(
            provider_id="claude",
            required_destination_set=None,
        )

        request = StartSessionRequest(
            workspace_path=Path("/ws"),
            workspace_arg="/ws",
            entry_dir=Path("/ws"),
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=False,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )

        spec = _build_sandbox_spec(
            request=request,
            resolver_result=self._make_resolver_result(),
            effective_config=None,
            agent_settings=None,
            runtime_info=None,
            agent_provider=mock_provider,
        )

        assert spec is not None
        assert spec.provider_id == "claude"

    def test_no_provider_defaults_empty(self) -> None:
        from scc_cli.application.start_session import StartSessionRequest, _build_sandbox_spec

        request = StartSessionRequest(
            workspace_path=Path("/ws"),
            workspace_arg="/ws",
            entry_dir=Path("/ws"),
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=False,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
        )

        spec = _build_sandbox_spec(
            request=request,
            resolver_result=self._make_resolver_result(),
            effective_config=None,
            agent_settings=None,
        )

        assert spec is not None
        assert spec.provider_id == ""
