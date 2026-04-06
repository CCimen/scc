"""Docker network topology manager for enforced web-egress.

Creates an internal-only Docker network, starts a Squid proxy sidecar
as the sole bridge to external networks, and tears everything down
idempotently.

Topology::

    ┌──────────────┐   internal-only    ┌───────────────┐   bridge
    │ agent        │ ─────────────────▶ │ scc-proxy     │ ──────────▶ Internet
    │ container    │   scc-egress-{id}  │ (Squid 3128)  │   (default)
    └──────────────┘                    └───────────────┘

The agent container is attached **only** to the internal network and
reaches the outside world exclusively through the proxy.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from scc_cli.core.errors import SandboxLaunchError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROXY_IMAGE = "scc-egress-proxy:latest"
_PROXY_PORT = 3128
_PROXY_LABEL = "scc.egress-proxy=true"

_CREATE_TIMEOUT = 30
_RUN_TIMEOUT = 60
_INSPECT_TIMEOUT = 10
_DEFAULT_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EgressTopologyInfo:
    """Result of a successful topology setup.

    Attributes:
        network_name: Internal-only Docker network name.
        proxy_container_name: Name of the running Squid proxy sidecar.
        proxy_endpoint: ``http://<internal-ip>:3128`` reachable from the
            internal network.
    """

    network_name: str
    proxy_container_name: str
    proxy_endpoint: str


# ---------------------------------------------------------------------------
# Docker subprocess helper (local copy — intentionally decoupled from
# oci_sandbox_runtime._run_docker to avoid cross-adapter imports)
# ---------------------------------------------------------------------------


def _run_docker(
    args: list[str],
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a ``docker`` subprocess with standard error handling.

    Raises:
        SandboxLaunchError: on non-zero exit or timeout.
    """
    cmd = ["docker", *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxLaunchError(
            user_message=f"Docker command timed out after {timeout}s",
            command=" ".join(cmd),
            stderr=str(exc),
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SandboxLaunchError(
            user_message="Docker command failed",
            command=" ".join(cmd),
            stderr=exc.stderr or "",
        ) from exc


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class NetworkTopologyManager:
    """Manages Docker network topology for enforced web-egress sessions.

    Each session gets an internal-only Docker network and a Squid proxy
    sidecar that is dual-homed (internal + bridge).  The agent container
    is later attached to the internal network with ``http_proxy`` /
    ``https_proxy`` environment variables pointing at the sidecar.
    """

    def __init__(self, session_id: str) -> None:
        self._session_id = session_id
        self._network_name = f"scc-egress-{session_id}"
        self._proxy_name = f"scc-proxy-{session_id}"
        self._acl_tmpfile: Path | None = None

    # -- public ------------------------------------------------------------

    def setup(self, acl_config: str) -> EgressTopologyInfo:
        """Create the internal network, start the proxy, return topology info.

        On failure at any stage, already-created resources are cleaned up
        before the ``SandboxLaunchError`` propagates.
        """
        # 1. Create internal-only network
        _run_docker(
            ["network", "create", "--internal", self._network_name],
            timeout=_CREATE_TIMEOUT,
        )

        try:
            # 2. Write ACL config to a temp file for volume mount
            acl_file = self._write_acl_file(acl_config)

            # 3. Start proxy container on the internal network
            _run_docker(
                [
                    "run",
                    "-d",
                    "--name",
                    self._proxy_name,
                    "--network",
                    self._network_name,
                    "--label",
                    _PROXY_LABEL,
                    "-v",
                    f"{acl_file}:/etc/squid/acl-rules.conf:ro",
                    _PROXY_IMAGE,
                ],
                timeout=_RUN_TIMEOUT,
            )

            # 4. Connect proxy to the default bridge (dual-homed)
            _run_docker(
                ["network", "connect", "bridge", self._proxy_name],
                timeout=_DEFAULT_TIMEOUT,
            )

            # 5. Get proxy IP on the *internal* network
            proxy_ip = self._get_proxy_internal_ip()

            return EgressTopologyInfo(
                network_name=self._network_name,
                proxy_container_name=self._proxy_name,
                proxy_endpoint=f"http://{proxy_ip}:{_PROXY_PORT}",
            )
        except Exception:
            # Any failure after network creation → clean up what we created
            self.teardown()
            raise

    def teardown(self) -> None:
        """Idempotently remove the proxy container and internal network.

        Errors from ``docker rm`` / ``docker network rm`` are silently
        ignored so teardown can be called unconditionally.
        """
        # Remove proxy container (ignore errors — may not exist)
        try:
            _run_docker(
                ["rm", "-f", self._proxy_name],
                timeout=_DEFAULT_TIMEOUT,
                check=False,
            )
        except SandboxLaunchError:
            pass  # timeout during teardown — best-effort

        # Remove internal network (ignore errors — may not exist)
        try:
            _run_docker(
                ["network", "rm", self._network_name],
                timeout=_DEFAULT_TIMEOUT,
                check=False,
            )
        except SandboxLaunchError:
            pass  # timeout during teardown — best-effort

        # Clean up ACL temp file if we created one
        if self._acl_tmpfile is not None:
            self._acl_tmpfile.unlink(missing_ok=True)
            self._acl_tmpfile = None

    # -- private -----------------------------------------------------------

    def _write_acl_file(self, acl_config: str) -> Path:
        """Write *acl_config* to a named temp file and return its path."""
        fd, path_str = tempfile.mkstemp(prefix="scc-acl-", suffix=".conf")
        path = Path(path_str)
        try:
            path.write_text(acl_config)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            # Close the OS-level file descriptor (write_text opens its own)
            import os

            os.close(fd)
        self._acl_tmpfile = path
        return path

    def _get_proxy_internal_ip(self) -> str:
        """Inspect the proxy container and return its IP on the internal network.

        Raises:
            SandboxLaunchError: if the IP cannot be determined.
        """
        result = _run_docker(
            [
                "inspect",
                "--format",
                f"{{{{.NetworkSettings.Networks.{self._network_name}.IPAddress}}}}",
                self._proxy_name,
            ],
            timeout=_INSPECT_TIMEOUT,
        )
        ip_addr = result.stdout.strip()
        if not ip_addr:
            raise SandboxLaunchError(
                user_message="Could not determine proxy internal IP address",
                command=f"docker inspect {self._proxy_name}",
                stderr="Empty IP address returned for internal network",
            )
        return ip_addr
