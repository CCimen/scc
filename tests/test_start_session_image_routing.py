"""Tests for _build_sandbox_spec image routing based on runtime info."""

from __future__ import annotations

from pathlib import Path

from scc_cli.application.start_session import _SANDBOX_IMAGE as SANDBOX_IMAGE
from scc_cli.application.start_session import StartSessionRequest, _build_sandbox_spec
from scc_cli.core.contracts import RuntimeInfo
from scc_cli.core.image_contracts import SCC_CLAUDE_IMAGE_REF
from scc_cli.core.workspace import ResolverResult


def _make_runtime_info(preferred_backend: str) -> RuntimeInfo:
    return RuntimeInfo(
        runtime_id="docker",
        display_name="Docker",
        cli_name="docker",
        supports_oci=True,
        supports_internal_networks=True,
        supports_host_network=True,
        daemon_reachable=True,
        sandbox_available=True,
        preferred_backend=preferred_backend,
    )


def _make_request(dry_run: bool = False) -> StartSessionRequest:
    return StartSessionRequest(
        workspace_path=Path("/tmp/test-workspace"),
        workspace_arg=None,
        entry_dir=Path("/tmp/test-workspace"),
        team=None,
        session_name=None,
        resume=False,
        fresh=False,
        offline=False,
        standalone=False,
        dry_run=dry_run,
        allow_suspicious=False,
        org_config=None,
    )


def _make_resolver_result() -> ResolverResult:
    return ResolverResult(
        workspace_root=Path("/tmp/test-workspace"),
        entry_dir=Path("/tmp/test-workspace"),
        mount_root=Path("/tmp/test-workspace"),
        container_workdir="/tmp/test-workspace",
        is_auto_detected=False,
        is_suspicious=False,
    )


class TestBuildSandboxSpecImageRouting:
    """Verify _build_sandbox_spec selects the correct image based on runtime_info."""

    def test_oci_backend_uses_scc_image(self) -> None:
        """OCI backend routes to SCC_CLAUDE_IMAGE_REF."""
        info = _make_runtime_info("oci")
        spec = _build_sandbox_spec(
            request=_make_request(),
            resolver_result=_make_resolver_result(),
            effective_config=None,
            agent_settings=None,
            runtime_info=info,
        )
        assert spec is not None
        assert spec.image == SCC_CLAUDE_IMAGE_REF

    def test_docker_sandbox_backend_uses_default_image(self) -> None:
        """Docker-sandbox backend uses the Docker Desktop sandbox template image."""
        info = _make_runtime_info("docker-sandbox")
        spec = _build_sandbox_spec(
            request=_make_request(),
            resolver_result=_make_resolver_result(),
            effective_config=None,
            agent_settings=None,
            runtime_info=info,
        )
        assert spec is not None
        assert spec.image == SANDBOX_IMAGE

    def test_none_runtime_info_uses_default_image(self) -> None:
        """When runtime_info is None, falls back to SANDBOX_IMAGE."""
        spec = _build_sandbox_spec(
            request=_make_request(),
            resolver_result=_make_resolver_result(),
            effective_config=None,
            agent_settings=None,
            runtime_info=None,
        )
        assert spec is not None
        assert spec.image == SANDBOX_IMAGE

    def test_no_runtime_info_kwarg_uses_default_image(self) -> None:
        """When runtime_info is not passed at all, defaults to SANDBOX_IMAGE."""
        spec = _build_sandbox_spec(
            request=_make_request(),
            resolver_result=_make_resolver_result(),
            effective_config=None,
            agent_settings=None,
        )
        assert spec is not None
        assert spec.image == SANDBOX_IMAGE

    def test_dry_run_returns_none(self) -> None:
        """Dry-run returns None regardless of runtime_info."""
        info = _make_runtime_info("oci")
        spec = _build_sandbox_spec(
            request=_make_request(dry_run=True),
            resolver_result=_make_resolver_result(),
            effective_config=None,
            agent_settings=None,
            runtime_info=info,
        )
        assert spec is None
