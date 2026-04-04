"""Tests for OciSandboxRuntime adapter.

All subprocess and os.execvp calls are mocked — no Docker daemon needed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters.oci_sandbox_runtime import (
    _OCI_LABEL,
    OciSandboxRuntime,
    _container_name,
)
from scc_cli.core.constants import AGENT_NAME, SANDBOX_DATA_VOLUME
from scc_cli.core.contracts import RuntimeInfo
from scc_cli.core.errors import (
    DockerDaemonNotRunningError,
    DockerNotFoundError,
    SandboxLaunchError,
)
from scc_cli.ports.models import (
    AgentSettings,
    MountSpec,
    SandboxHandle,
    SandboxSpec,
    SandboxState,
    SandboxStatus,
)
from tests.fakes.fake_runtime_probe import FakeRuntimeProbe

# ── Fixtures ─────────────────────────────────────────────────────────────────

def _oci_capable_info(**overrides: object) -> RuntimeInfo:
    """Return a RuntimeInfo describing an OCI-capable engine without sandbox."""
    defaults: dict[str, object] = {
        "runtime_id": "docker",
        "display_name": "Docker Engine",
        "cli_name": "docker",
        "supports_oci": True,
        "supports_internal_networks": True,
        "supports_host_network": True,
        "version": "Docker version 27.5.1, build abc1234",
        "daemon_reachable": True,
        "sandbox_available": False,
        "preferred_backend": "oci",
    }
    defaults.update(overrides)
    return RuntimeInfo(**defaults)  # type: ignore[arg-type]


def _minimal_spec(**overrides: object) -> SandboxSpec:
    """Return a minimal SandboxSpec for testing."""
    defaults: dict[str, object] = {
        "image": "scc-agent-claude:latest",
        "workspace_mount": MountSpec(
            source=Path("/home/user/project"),
            target=Path("/workspace"),
        ),
        "workdir": Path("/workspace"),
    }
    defaults.update(overrides)
    return SandboxSpec(**defaults)  # type: ignore[arg-type]


@pytest.fixture()
def runtime() -> OciSandboxRuntime:
    probe = FakeRuntimeProbe(_oci_capable_info())
    return OciSandboxRuntime(probe)


# ── ensure_available ─────────────────────────────────────────────────────────

class TestEnsureAvailable:
    """Scenario coverage for ensure_available()."""

    def test_oci_capable_engine_passes(self) -> None:
        probe = FakeRuntimeProbe(_oci_capable_info())
        rt = OciSandboxRuntime(probe)
        rt.ensure_available()  # should not raise

    def test_not_installed_raises_docker_not_found(self) -> None:
        probe = FakeRuntimeProbe(
            _oci_capable_info(
                version=None,
                daemon_reachable=False,
            )
        )
        rt = OciSandboxRuntime(probe)
        with pytest.raises(DockerNotFoundError):
            rt.ensure_available()

    def test_daemon_not_running_raises(self) -> None:
        probe = FakeRuntimeProbe(
            _oci_capable_info(
                daemon_reachable=False,
                version="Docker version 27.5.1, build abc1234",
            )
        )
        rt = OciSandboxRuntime(probe)
        with pytest.raises(DockerDaemonNotRunningError):
            rt.ensure_available()

    def test_no_oci_support_raises(self) -> None:
        probe = FakeRuntimeProbe(
            _oci_capable_info(supports_oci=False)
        )
        rt = OciSandboxRuntime(probe)
        with pytest.raises(DockerNotFoundError, match="OCI containers"):
            rt.ensure_available()

    def test_sandbox_not_required(self) -> None:
        """OciSandboxRuntime should NOT check sandbox_available."""
        probe = FakeRuntimeProbe(
            _oci_capable_info(sandbox_available=False)
        )
        rt = OciSandboxRuntime(probe)
        rt.ensure_available()  # should not raise


# ── run ──────────────────────────────────────────────────────────────────────

class TestRun:
    """Verify docker create / start / exec command construction."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_basic_run_builds_correct_commands(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        container_id = "abc123def456"
        mock_run_docker.return_value = MagicMock(stdout=f"  {container_id}  \n")

        spec = _minimal_spec()
        handle = runtime.run(spec)

        # Two calls: docker create, docker start
        assert mock_run_docker.call_count == 2

        create_args = mock_run_docker.call_args_list[0]
        create_cmd: list[str] = create_args[0][0]
        assert create_cmd[0] == "create"
        assert "--name" in create_cmd
        assert spec.image in create_cmd

        start_args = mock_run_docker.call_args_list[1]
        start_cmd: list[str] = start_args[0][0]
        assert start_cmd == ["start", container_id]

        # execvp called with docker exec
        mock_execvp.assert_called_once()
        exec_argv = mock_execvp.call_args[0][1]
        assert exec_argv[0] == "docker"
        assert "exec" in exec_argv
        assert container_id in exec_argv
        assert AGENT_NAME in exec_argv
        assert "--dangerously-skip-permissions" in exec_argv

        assert handle.sandbox_id == container_id

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_workspace_mount_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        mount_str = f"{spec.workspace_mount.source}:{spec.workspace_mount.target}"
        assert mount_str in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_credential_volume_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        cred_mount = f"{SANDBOX_DATA_VOLUME}:/home/agent/.claude"
        assert cred_mount in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_env_vars_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(env={"MY_KEY": "my_val", "OTHER": "123"})
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "-e" in create_cmd
        assert "MY_KEY=my_val" in create_cmd
        assert "OTHER=123" in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_oci_label_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "--label" in create_cmd
        label_idx = create_cmd.index("--label")
        assert create_cmd[label_idx + 1] == _OCI_LABEL

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_image_consumed_from_spec(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        custom_image = "my-registry.io/custom-agent:v2"
        spec = _minimal_spec(image=custom_image)
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert custom_image in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_continue_session_flag(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(continue_session=True)
        runtime.run(spec)

        exec_argv = mock_execvp.call_args[0][1]
        assert "-c" in exec_argv

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_agent_settings_injected(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        settings = AgentSettings(
            content={"key": "value"},
            path=Path("/home/agent/.claude/settings.json"),
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        # 3 calls: create, start, cp (for settings)
        assert mock_run_docker.call_count == 3
        cp_cmd: list[str] = mock_run_docker.call_args_list[2][0][0]
        assert cp_cmd[0] == "cp"
        assert "cid123:" in cp_cmd[2]

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_workdir_in_exec(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(workdir=Path("/custom/workdir"))
        runtime.run(spec)

        exec_argv = mock_execvp.call_args[0][1]
        assert "-w" in exec_argv
        assert "/custom/workdir" in exec_argv


# ── Failure modes ────────────────────────────────────────────────────────────

class TestFailureModes:
    """Verify error handling for subprocess failures and timeouts."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_create_failure_raises_launch_error(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.side_effect = SandboxLaunchError(
            user_message="Docker command failed",
            command="docker create ...",
            stderr="name already in use",
        )
        with pytest.raises(SandboxLaunchError, match="Docker command failed"):
            runtime.run(_minimal_spec())

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_create_timeout_raises_launch_error(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="docker create", timeout=60)
        with pytest.raises(SandboxLaunchError, match="timed out"):
            runtime.run(_minimal_spec())

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_create_nonzero_exit_raises_launch_error(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="docker create", stderr="conflict"
        )
        with pytest.raises(SandboxLaunchError):
            runtime.run(_minimal_spec())


# ── list_running ─────────────────────────────────────────────────────────────

class TestListRunning:
    """Verify parsing of ``docker ps`` output."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_parses_multiple_containers(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(
            stdout="abc123\tscc-oci-aaa\ndef456\tscc-oci-bbb\n"
        )
        handles = runtime.list_running()
        assert len(handles) == 2
        assert handles[0] == SandboxHandle(sandbox_id="abc123", name="scc-oci-aaa")
        assert handles[1] == SandboxHandle(sandbox_id="def456", name="scc-oci-bbb")

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_empty_output(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="")
        assert runtime.list_running() == []

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_single_column_output(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="abc123\n")
        handles = runtime.list_running()
        assert len(handles) == 1
        assert handles[0].sandbox_id == "abc123"
        assert handles[0].name is None


# ── status ───────────────────────────────────────────────────────────────────

class TestStatus:
    """Verify docker inspect → SandboxState mapping."""

    @pytest.mark.parametrize(
        ("raw_status", "expected_state"),
        [
            ("running", SandboxState.RUNNING),
            ("created", SandboxState.CREATED),
            ("exited", SandboxState.STOPPED),
            ("dead", SandboxState.STOPPED),
            ("paused", SandboxState.RUNNING),
            ("restarting", SandboxState.RUNNING),
            ("something_else", SandboxState.UNKNOWN),
        ],
    )
    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_state_mapping(
        self,
        mock_subprocess: MagicMock,
        raw_status: str,
        expected_state: SandboxState,
        runtime: OciSandboxRuntime,
    ) -> None:
        mock_subprocess.return_value = MagicMock(
            returncode=0, stdout=f"{raw_status}\n"
        )
        handle = SandboxHandle(sandbox_id="abc123")
        result = runtime.status(handle)
        assert result.state == expected_state

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_inspect_failure_returns_unknown(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="")
        handle = SandboxHandle(sandbox_id="gone")
        assert runtime.status(handle) == SandboxStatus(state=SandboxState.UNKNOWN)

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_inspect_timeout_returns_unknown(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="docker inspect", timeout=10)
        handle = SandboxHandle(sandbox_id="slow")
        assert runtime.status(handle) == SandboxStatus(state=SandboxState.UNKNOWN)


# ── resume / stop / remove ───────────────────────────────────────────────────

class TestLifecycle:
    """Verify resume, stop, and remove delegate correctly."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_resume(self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime) -> None:
        runtime.resume(SandboxHandle(sandbox_id="cid"))
        mock_run_docker.assert_called_once_with(["start", "cid"], timeout=30)

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_stop(self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime) -> None:
        runtime.stop(SandboxHandle(sandbox_id="cid"))
        mock_run_docker.assert_called_once_with(["stop", "cid"], timeout=15)

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_remove(self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime) -> None:
        runtime.remove(SandboxHandle(sandbox_id="cid"))
        mock_run_docker.assert_called_once_with(["rm", "-f", "cid"], timeout=15)


# ── Network enforcement ──────────────────────────────────────────────────────

class TestNetworkEnforcement:
    """Verify _build_create_cmd produces correct --network flags for all modes."""

    def test_enforced_mode_adds_network_flag(self) -> None:
        """web-egress-enforced with a network name → --network <name> in command."""
        spec = _minimal_spec(network_policy="web-egress-enforced")
        cmd = OciSandboxRuntime._build_create_cmd(
            spec, "scc-oci-test", network_name="scc-egress-scc-oci-test",
        )
        assert "--network" in cmd
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "scc-egress-scc-oci-test"

    def test_locked_down_mode_adds_network_none(self) -> None:
        """locked-down-web → --network none."""
        spec = _minimal_spec(network_policy="locked-down-web")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        assert "--network" in cmd
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "none"

    def test_open_mode_no_network_flag(self) -> None:
        """open → no --network flag."""
        spec = _minimal_spec(network_policy="open")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        assert "--network" not in cmd

    def test_none_policy_no_network_flag(self) -> None:
        """None (unset) → no --network flag."""
        spec = _minimal_spec(network_policy=None)
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        assert "--network" not in cmd

    def test_enforced_mode_injects_proxy_env(self) -> None:
        """Proxy env vars appear in the create command for enforced mode."""
        spec = _minimal_spec(network_policy="web-egress-enforced")
        proxy_env = {
            "HTTP_PROXY": "http://172.18.0.2:3128",
            "HTTPS_PROXY": "http://172.18.0.2:3128",
            "NO_PROXY": "",
        }
        cmd = OciSandboxRuntime._build_create_cmd(
            spec, "scc-oci-test",
            network_name="scc-egress-scc-oci-test",
            proxy_env=proxy_env,
        )
        assert "HTTP_PROXY=http://172.18.0.2:3128" in cmd
        assert "HTTPS_PROXY=http://172.18.0.2:3128" in cmd
        assert "NO_PROXY=" in cmd


# ── Container naming ────────────────────────────────────────────────────────

class TestContainerName:
    """Verify deterministic container naming."""

    def test_deterministic(self) -> None:
        name1 = _container_name(Path("/home/user/project"))
        name2 = _container_name(Path("/home/user/project"))
        assert name1 == name2
        assert name1.startswith("scc-oci-")

    def test_different_paths_differ(self) -> None:
        assert _container_name(Path("/a")) != _container_name(Path("/b"))


# ── S02/T03 — Provider-aware exec command and credential volume mounting ─────

class TestProviderAwareExecCmd:
    """Verify _build_exec_cmd uses spec.agent_argv when present."""

    def test_build_exec_cmd_uses_agent_argv_when_present(self) -> None:
        """With agent_argv=("codex",), exec cmd uses codex, not claude."""
        spec = _minimal_spec(agent_argv=["codex"])
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert "codex" in cmd
        assert AGENT_NAME not in cmd
        assert "--dangerously-skip-permissions" not in cmd

    def test_build_exec_cmd_falls_back_to_agent_name(self) -> None:
        """Empty agent_argv uses existing AGENT_NAME + --dangerously-skip-permissions."""
        spec = _minimal_spec(agent_argv=[])
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert AGENT_NAME in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_build_exec_cmd_default_agent_argv(self) -> None:
        """Default SandboxSpec (no agent_argv given) falls back to AGENT_NAME."""
        spec = _minimal_spec()
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert AGENT_NAME in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_build_exec_cmd_continue_session_with_codex_argv(self) -> None:
        """-c appended after codex argv when continue_session=True."""
        spec = _minimal_spec(agent_argv=["codex"], continue_session=True)
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert "codex" in cmd
        assert "-c" in cmd
        # -c should be after codex
        codex_idx = cmd.index("codex")
        c_idx = cmd.index("-c")
        assert c_idx > codex_idx

    def test_build_exec_cmd_continue_session_with_default_argv(self) -> None:
        """-c appended after default AGENT_NAME argv when continue_session=True."""
        spec = _minimal_spec(continue_session=True)
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert AGENT_NAME in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "-c" in cmd


class TestProviderAwareCreateCmd:
    """Verify _build_create_cmd uses spec.data_volume and spec.config_dir."""

    def test_build_create_cmd_uses_data_volume_when_present(self) -> None:
        """With data_volume set, volume mount uses it instead of SANDBOX_DATA_VOLUME."""
        spec = _minimal_spec(data_volume="docker-codex-sandbox-data")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = "docker-codex-sandbox-data:/home/agent/.claude"
        assert mount_str in cmd
        assert SANDBOX_DATA_VOLUME not in " ".join(cmd)

    def test_build_create_cmd_uses_config_dir_when_present(self) -> None:
        """With config_dir set, mount target uses it instead of .claude."""
        spec = _minimal_spec(config_dir=".codex")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_found = any(
            "/home/agent/.codex" in arg for arg in cmd
        )
        assert mount_found

    def test_build_create_cmd_both_volume_and_config_dir(self) -> None:
        """Both data_volume and config_dir produce the expected mount."""
        spec = _minimal_spec(
            data_volume="docker-codex-sandbox-data",
            config_dir=".codex",
        )
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = "docker-codex-sandbox-data:/home/agent/.codex"
        assert mount_str in cmd

    def test_build_create_cmd_falls_back_to_defaults(self) -> None:
        """Empty data_volume and config_dir falls back to SANDBOX_DATA_VOLUME and .claude."""
        spec = _minimal_spec(data_volume="", config_dir="")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = f"{SANDBOX_DATA_VOLUME}:/home/agent/.claude"
        assert mount_str in cmd

    def test_build_create_cmd_default_spec_falls_back(self) -> None:
        """Default SandboxSpec (no volume/dir given) uses original constants."""
        spec = _minimal_spec()
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = f"{SANDBOX_DATA_VOLUME}:/home/agent/.claude"
        assert mount_str in cmd
