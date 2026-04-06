"""Tests for bootstrap backend selection based on runtime probe results."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scc_cli.adapters.docker_sandbox_runtime import DockerSandboxRuntime
from scc_cli.adapters.oci_sandbox_runtime import OciSandboxRuntime
from scc_cli.bootstrap import get_default_adapters
from scc_cli.core.contracts import RuntimeInfo


def _make_runtime_info(preferred_backend: str, sandbox_available: bool = True) -> RuntimeInfo:
    return RuntimeInfo(
        runtime_id="docker",
        display_name="Docker",
        cli_name="docker",
        supports_oci=True,
        supports_internal_networks=True,
        supports_host_network=True,
        daemon_reachable=True,
        sandbox_available=sandbox_available,
        preferred_backend=preferred_backend,
    )


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Clear lru_cache before each test so probe results take effect."""
    get_default_adapters.cache_clear()


class TestBootstrapBackendSelection:
    """Verify bootstrap selects the correct sandbox runtime from probe results."""

    @patch("scc_cli.bootstrap.DockerRuntimeProbe")
    def test_oci_backend_produces_oci_runtime(self, mock_probe_cls: object) -> None:
        """When probe returns preferred_backend='oci', bootstrap wires OciSandboxRuntime."""
        info = _make_runtime_info("oci", sandbox_available=False)
        mock_probe_cls.return_value.probe.return_value = info  # type: ignore[union-attr]

        adapters = get_default_adapters()

        assert isinstance(adapters.sandbox_runtime, OciSandboxRuntime)

    @patch("scc_cli.bootstrap.DockerRuntimeProbe")
    def test_docker_sandbox_backend_produces_docker_runtime(self, mock_probe_cls: object) -> None:
        """When probe returns preferred_backend='docker-sandbox', bootstrap wires DockerSandboxRuntime."""
        info = _make_runtime_info("docker-sandbox", sandbox_available=True)
        mock_probe_cls.return_value.probe.return_value = info  # type: ignore[union-attr]

        adapters = get_default_adapters()

        assert isinstance(adapters.sandbox_runtime, DockerSandboxRuntime)

    @patch("scc_cli.bootstrap.DockerRuntimeProbe")
    def test_none_backend_defaults_to_docker_runtime(self, mock_probe_cls: object) -> None:
        """When preferred_backend is None (unknown), bootstrap defaults to DockerSandboxRuntime."""
        info = RuntimeInfo(
            runtime_id="docker",
            display_name="Docker",
            cli_name="docker",
            supports_oci=True,
            supports_internal_networks=True,
            supports_host_network=True,
            daemon_reachable=True,
            sandbox_available=True,
            preferred_backend=None,
        )
        mock_probe_cls.return_value.probe.return_value = info  # type: ignore[union-attr]

        adapters = get_default_adapters()

        assert isinstance(adapters.sandbox_runtime, DockerSandboxRuntime)

    @patch("scc_cli.bootstrap.DockerRuntimeProbe")
    def test_probe_is_passed_to_oci_runtime(self, mock_probe_cls: object) -> None:
        """OciSandboxRuntime receives the same probe instance used for probing."""
        info = _make_runtime_info("oci")
        mock_instance = mock_probe_cls.return_value
        mock_instance.probe.return_value = info

        adapters = get_default_adapters()

        assert isinstance(adapters.sandbox_runtime, OciSandboxRuntime)
        # The runtime probe should be the same probe instance
        assert adapters.runtime_probe is mock_instance
