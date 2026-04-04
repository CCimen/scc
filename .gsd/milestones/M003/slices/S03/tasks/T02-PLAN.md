---
estimated_steps: 62
estimated_files: 5
skills_used: []
---

# T02: Create proxy sidecar image and NetworkTopologyManager adapter with mocked tests

## Description

Build the Docker network topology management layer: a Squid-based proxy sidecar image definition and a `NetworkTopologyManager` class that creates internal Docker networks, starts/stops the proxy sidecar, and cleans up idempotently. All Docker subprocess calls are mocked in tests.

## Steps

1. Create `images/scc-egress-proxy/Dockerfile`:
   - Base: `alpine:3.19`
   - Install `squid` package
   - Copy `squid.conf.template` to `/etc/squid/squid.conf.template`
   - Create a startup script that copies the template to `squid.conf` (allowing runtime config injection via environment or volume mount) and runs `squid -N` (foreground mode)
   - Expose port 3128 (Squid default)
   - HEALTHCHECK: `squid -k check` or `wget -q --spider http://localhost:3128` with 5s interval
2. Create `images/scc-egress-proxy/squid.conf.template`:
   - Include a marker comment `# SCC_ACL_RULES_START` / `# SCC_ACL_RULES_END` where compiled ACL rules will be injected
   - Default ports: `acl SSL_ports port 443`, `acl Safe_ports port 80 443`
   - `http_access deny !Safe_ports`, `http_access deny CONNECT !SSL_ports`
   - Logging to stdout: `access_log stdio:/dev/stdout`
   - Cache disabled: `cache deny all`
   - Listen on `0.0.0.0:3128`
3. Create `images/scc-egress-proxy/entrypoint.sh`:
   - If `/etc/squid/acl-rules.conf` exists (volume-mounted by topology manager), include it in the config
   - Otherwise, use the template as-is (default deny all)
   - Start squid in foreground: `exec squid -N -f /etc/squid/squid.conf`
4. Create `src/scc_cli/adapters/egress_topology.py` with class `NetworkTopologyManager`:
   - `__init__(self, session_id: str)` — session_id used for naming (network: `scc-egress-{session_id}`, proxy container: `scc-proxy-{session_id}`)
   - `setup(self, acl_config: str) -> EgressTopologyInfo` — (a) Create internal network: `docker network create --internal scc-egress-{session_id}`. (b) Write `acl_config` to a temp file. (c) Start proxy container: `docker run -d --name scc-proxy-{session_id} --network scc-egress-{session_id} --label scc.egress-proxy=true -v {tempfile}:/etc/squid/acl-rules.conf:ro -p 0:3128 scc-egress-proxy:latest`. (d) Connect proxy to default bridge network: `docker network connect bridge scc-proxy-{session_id}`. (e) Get proxy internal IP: `docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' scc-proxy-{session_id}` (use the IP from the internal network, not bridge). (f) Return `EgressTopologyInfo(network_name=..., proxy_container=..., proxy_endpoint=http://{ip}:3128)`.
   - `teardown(self) -> None` — Idempotent: `docker rm -f scc-proxy-{session_id}` (ignore errors), `docker network rm scc-egress-{session_id}` (ignore errors).
5. Define `EgressTopologyInfo` as a frozen dataclass in the same module: `network_name: str`, `proxy_container_name: str`, `proxy_endpoint: str`.
6. Use `_run_docker` helper from `oci_sandbox_runtime.py` — OR define a local equivalent. Decision: import the existing `_run_docker` or extract it to a shared location. Since `_run_docker` is module-private in oci_sandbox_runtime.py, create a minimal `_run_docker` in egress_topology.py following the same pattern (consistent error handling via SandboxLaunchError). Do NOT import from oci_sandbox_runtime to avoid coupling.
7. Create `tests/test_egress_topology.py` with mocked subprocess tests:
   - `test_setup_creates_internal_network` — asserts `docker network create --internal` is called
   - `test_setup_starts_proxy_container` — asserts `docker run` with correct image, labels, volume mount
   - `test_setup_connects_proxy_to_bridge` — asserts `docker network connect bridge` is called
   - `test_setup_returns_topology_info` — returned info has correct network name, proxy container name, and proxy endpoint with internal IP
   - `test_teardown_removes_proxy_and_network` — asserts `docker rm -f` and `docker network rm` are called
   - `test_teardown_idempotent_on_missing_resources` — teardown succeeds even if rm/network rm fail (CalledProcessError ignored)
   - `test_setup_failure_on_network_create_raises` — SandboxLaunchError when network create fails
   - `test_setup_failure_on_proxy_start_triggers_cleanup` — if proxy start fails, teardown is still called for the network
8. Run lint, mypy, and tests.

## Must-Haves

- [ ] `images/scc-egress-proxy/Dockerfile` with Alpine + Squid + healthcheck
- [ ] `images/scc-egress-proxy/squid.conf.template` with ACL injection markers and safe defaults
- [ ] `images/scc-egress-proxy/entrypoint.sh` with ACL include logic
- [ ] `NetworkTopologyManager.setup()` creates network, starts proxy on dual networks, returns info
- [ ] `NetworkTopologyManager.teardown()` is idempotent
- [ ] `EgressTopologyInfo` dataclass with network_name, proxy_container_name, proxy_endpoint
- [ ] 8+ mocked subprocess tests
- [ ] mypy clean, ruff clean

## Verification

- `uv run pytest tests/test_egress_topology.py -q` — all tests pass
- `uv run ruff check src/scc_cli/adapters/egress_topology.py tests/test_egress_topology.py` — clean
- `uv run mypy src/scc_cli/adapters/egress_topology.py` — no issues
- `test -f images/scc-egress-proxy/Dockerfile && test -f images/scc-egress-proxy/squid.conf.template && test -f images/scc-egress-proxy/entrypoint.sh` — image files exist

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| docker network create | SandboxLaunchError with stderr | SandboxLaunchError (timeout) | N/A |
| docker run (proxy) | SandboxLaunchError; cleanup triggered for network | SandboxLaunchError (timeout); cleanup triggered | N/A |
| docker inspect (proxy IP) | SandboxLaunchError; full cleanup triggered | SandboxLaunchError (timeout) | Parse failure → SandboxLaunchError |
| docker rm/network rm (teardown) | Silently ignored (idempotent) | Silently ignored | N/A |

## Observability Impact

- Signals added: `scc.egress-proxy=true` Docker label on proxy containers for filtering
- How a future agent inspects this: `docker ps --filter label=scc.egress-proxy` lists proxies; `docker network ls --filter name=scc-egress-` lists egress networks
- Failure state exposed: SandboxLaunchError includes failing command + stderr

## Inputs

- ``src/scc_cli/core/egress_policy.py` — compile_squid_acl() output used as acl_config input to setup()`
- ``src/scc_cli/core/contracts.py` — NetworkPolicyPlan dataclass consumed by the topology manager`
- ``src/scc_cli/core/errors.py` — SandboxLaunchError for consistent error handling`
- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — reference for _run_docker pattern (do not import, replicate locally)`

## Expected Output

- ``images/scc-egress-proxy/Dockerfile` — Alpine + Squid proxy sidecar image`
- ``images/scc-egress-proxy/squid.conf.template` — Squid config with ACL injection markers`
- ``images/scc-egress-proxy/entrypoint.sh` — startup script with ACL include logic`
- ``src/scc_cli/adapters/egress_topology.py` — NetworkTopologyManager class + EgressTopologyInfo dataclass`
- ``tests/test_egress_topology.py` — 8+ mocked subprocess tests for topology lifecycle`

## Verification

uv run pytest tests/test_egress_topology.py -q && uv run ruff check src/scc_cli/adapters/egress_topology.py tests/test_egress_topology.py && uv run mypy src/scc_cli/adapters/egress_topology.py && test -f images/scc-egress-proxy/Dockerfile && test -f images/scc-egress-proxy/squid.conf.template && test -f images/scc-egress-proxy/entrypoint.sh
