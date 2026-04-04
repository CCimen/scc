"""Tests for DockerRuntimeProbe adapter.

Covers four detection scenarios by patching the helpers where
the adapter module imported them.
"""

from __future__ import annotations

from unittest.mock import patch

from scc_cli.adapters.docker_runtime_probe import DockerRuntimeProbe

# Patch targets: the names as imported into the adapter module.
_MOD = "scc_cli.adapters.docker_runtime_probe"


class TestDockerRuntimeProbeDesktopPresent:
    """Docker Desktop present: all capabilities available."""

    @patch(f"{_MOD}._check_docker_installed", return_value=True)
    @patch(f"{_MOD}.get_docker_version", return_value="Docker version 27.5.1, build abc1234")
    @patch(f"{_MOD}.run_command_bool", return_value=True)
    @patch(f"{_MOD}.run_command", return_value="[name=seccomp,name=rootless]")
    @patch(f"{_MOD}.get_docker_desktop_version", return_value="4.50.0")
    @patch(f"{_MOD}.check_docker_sandbox", return_value=True)
    def test_full_desktop_capabilities(
        self,
        _mock_sandbox: object,
        _mock_desktop: object,
        _mock_run_cmd: object,
        _mock_daemon: object,
        _mock_version: object,
        _mock_installed: object,
    ) -> None:
        probe = DockerRuntimeProbe()
        info = probe.probe()

        assert info.runtime_id == "docker"
        assert info.display_name == "Docker Desktop"
        assert info.cli_name == "docker"
        assert info.supports_oci is True
        assert info.supports_internal_networks is True
        assert info.supports_host_network is True
        assert info.version == "Docker version 27.5.1, build abc1234"
        assert info.desktop_version == "4.50.0"
        assert info.daemon_reachable is True
        assert info.sandbox_available is True
        assert info.rootless is True
        assert info.preferred_backend == "docker-sandbox"


class TestDockerRuntimeProbeEngineOnly:
    """Docker Engine only: no Desktop, no sandbox."""

    @patch(f"{_MOD}._check_docker_installed", return_value=True)
    @patch(f"{_MOD}.get_docker_version", return_value="Docker version 24.0.7, build afdd53b")
    @patch(f"{_MOD}.run_command_bool", return_value=True)
    @patch(f"{_MOD}.run_command", return_value="[name=seccomp,name=cgroupns]")
    @patch(f"{_MOD}.get_docker_desktop_version", return_value=None)
    @patch(f"{_MOD}.check_docker_sandbox", return_value=False)
    def test_engine_only(
        self,
        _mock_sandbox: object,
        _mock_desktop: object,
        _mock_run_cmd: object,
        _mock_daemon: object,
        _mock_version: object,
        _mock_installed: object,
    ) -> None:
        probe = DockerRuntimeProbe()
        info = probe.probe()

        assert info.runtime_id == "docker"
        assert info.display_name == "Docker Engine"
        assert info.supports_oci is True
        assert info.desktop_version is None
        assert info.daemon_reachable is True
        assert info.sandbox_available is False
        assert info.rootless is False
        assert info.preferred_backend == "oci"


class TestDockerRuntimeProbeNotInstalled:
    """Docker not installed: everything false/None."""

    @patch(f"{_MOD}._check_docker_installed", return_value=False)
    def test_not_installed(self, _mock_installed: object) -> None:
        probe = DockerRuntimeProbe()
        info = probe.probe()

        assert info.runtime_id == "docker"
        assert info.display_name == "Docker (not installed)"
        assert info.supports_oci is False
        assert info.supports_internal_networks is False
        assert info.supports_host_network is False
        assert info.version is None
        assert info.desktop_version is None
        assert info.daemon_reachable is False
        assert info.sandbox_available is False
        assert info.preferred_backend is None


class TestDockerRuntimeProbeDaemonNotRunning:
    """Docker installed but daemon not running."""

    @patch(f"{_MOD}._check_docker_installed", return_value=True)
    @patch(f"{_MOD}.get_docker_version", return_value="Docker version 27.5.1, build abc1234")
    @patch(f"{_MOD}.run_command_bool", return_value=False)
    def test_daemon_not_running(
        self,
        _mock_daemon: object,
        _mock_version: object,
        _mock_installed: object,
    ) -> None:
        probe = DockerRuntimeProbe()
        info = probe.probe()

        assert info.runtime_id == "docker"
        assert info.display_name == "Docker (daemon not running)"
        assert info.supports_oci is True
        assert info.supports_internal_networks is False
        assert info.supports_host_network is False
        assert info.version == "Docker version 27.5.1, build abc1234"
        assert info.daemon_reachable is False
        assert info.sandbox_available is False
        assert info.preferred_backend is None


class TestDockerRuntimeProbeRootlessDetectionFailure:
    """Rootless detection fails gracefully when run_command raises."""

    @patch(f"{_MOD}._check_docker_installed", return_value=True)
    @patch(f"{_MOD}.get_docker_version", return_value="Docker version 24.0.7, build afdd53b")
    @patch(f"{_MOD}.run_command_bool", return_value=True)
    @patch(f"{_MOD}.run_command", side_effect=OSError("docker info failed"))
    @patch(f"{_MOD}.get_docker_desktop_version", return_value=None)
    @patch(f"{_MOD}.check_docker_sandbox", return_value=False)
    def test_rootless_detection_failure_returns_none(
        self,
        _mock_sandbox: object,
        _mock_desktop: object,
        _mock_run_cmd: object,
        _mock_daemon: object,
        _mock_version: object,
        _mock_installed: object,
    ) -> None:
        probe = DockerRuntimeProbe()
        info = probe.probe()

        assert info.rootless is None
        assert info.daemon_reachable is True
        assert info.preferred_backend == "oci"
