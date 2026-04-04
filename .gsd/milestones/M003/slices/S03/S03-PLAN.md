# S03: Enforced web-egress topology and proxy ACLs

**Goal:** When `network_policy` is `web-egress-enforced`, the OCI adapter creates an internal-only Docker network, starts a Squid proxy sidecar as the sole bridge to external networks, compiles ACLs from `NetworkPolicyPlan` that deny IP literals/loopback/private/link-local/metadata endpoints by default, and attaches the agent container to the internal network with proxy env vars. When `locked-down-web`, the agent gets `--network=none`. When `open` or unset, behavior is unchanged.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added build_egress_plan() and compile_squid_acl() pure functions with 19 tests covering all three network policy modes, default deny rules, and ACL compilation ordering** — ## Description

Create the pure-logic layer that converts network policy mode + destination sets + egress rules into a `NetworkPolicyPlan`, then compiles that plan into a Squid ACL configuration string. This is the security-critical piece — ACL correctness determines whether the topology actually enforces policy. All work is pure functions with no subprocess or Docker dependency.

## Steps

1. Create `src/scc_cli/core/egress_policy.py` with two public functions:
   - `build_egress_plan(mode: NetworkPolicy, destination_sets: tuple[DestinationSet, ...] = (), egress_rules: tuple[EgressRule, ...] = ()) -> NetworkPolicyPlan` — For `OPEN`, returns a plan with `enforced_by_runtime=False` and no rules. For `WEB_EGRESS_ENFORCED`, returns a plan with default-deny rules (IP literals, loopback 127.0.0.0/8, private CIDRs 10.0.0.0/8 + 172.16.0.0/12 + 192.168.0.0/16, link-local 169.254.0.0/16, metadata 169.254.169.254) as deny rules, followed by any allow rules from `egress_rules`, with `enforced_by_runtime=True`. For `LOCKED_DOWN_WEB`, returns `enforced_by_runtime=True` with no rules and a note indicating `--network=none`.
   - `compile_squid_acl(plan: NetworkPolicyPlan) -> str` — Converts the plan's `egress_rules` into Squid ACL syntax. Uses `acl` + `http_access` directives. Deny rules use `dst` for CIDRs and `dstdomain` for hostnames. Allow rules use `dstdomain` for hostnames. Default final line: `http_access deny all`. Squid evaluates top-to-bottom first-match, so deny rules MUST come before allow rules.
2. Define private constants for the default deny targets (IP literal regex pattern, private CIDRs, link-local, metadata endpoint).
3. Create `tests/test_egress_policy.py` with comprehensive test coverage:
   - `test_open_mode_produces_no_rules` — OPEN mode returns empty rules, `enforced_by_runtime=False`.
   - `test_enforced_mode_has_default_deny_rules` — WEB_EGRESS_ENFORCED returns all default deny rules.
   - `test_locked_down_mode_has_no_rules` — LOCKED_DOWN_WEB returns `enforced_by_runtime=True`, empty rules, note about `--network=none`.
   - `test_enforced_mode_with_allow_rules` — Custom allow rules appear after default deny rules.
   - `test_enforced_mode_with_destination_sets` — Destination sets are threaded into the plan.
   - `test_compile_acl_deny_private_cidrs` — ACL output contains `acl` entries for all private CIDRs.
   - `test_compile_acl_deny_metadata` — ACL denies 169.254.169.254.
   - `test_compile_acl_allow_specific_hosts` — Allow rules produce `dstdomain` entries.
   - `test_compile_acl_deny_before_allow_ordering` — Deny `http_access` lines come before allow lines.
   - `test_compile_acl_ends_with_deny_all` — Final line is `http_access deny all`.
   - `test_compile_acl_open_mode_permits_all` — OPEN mode with no rules produces `http_access allow all`.
   - `test_compile_acl_locked_down_produces_deny_all` — LOCKED_DOWN_WEB produces only `http_access deny all`.
4. Run `uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py` and `uv run mypy src/scc_cli/core/egress_policy.py`.
5. Run `uv run pytest tests/test_egress_policy.py -q` to confirm all tests pass.

## Must-Haves

- [ ] `build_egress_plan()` handles all three `NetworkPolicy` modes correctly
- [ ] Default deny rules cover IP literals, loopback, private CIDRs, link-local, metadata
- [ ] `compile_squid_acl()` produces valid Squid syntax with deny-before-allow ordering
- [ ] Final ACL line is always `http_access deny all` (for enforced) or `http_access allow all` (for open)
- [ ] All types are annotated; mypy clean
- [ ] 12+ unit tests covering plan builder and ACL compiler

## Verification

- `uv run pytest tests/test_egress_policy.py -q` — all tests pass
- `uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py` — clean
- `uv run mypy src/scc_cli/core/egress_policy.py` — no issues

## Negative Tests

- **Malformed inputs**: empty destination set tuple, egress rule with empty target string
- **Boundary conditions**: enforced mode with zero allow rules (only deny), OPEN mode passed through compile_squid_acl

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| NetworkPolicyPlan contract | TypeError from frozen dataclass — caught by type checker | N/A (pure function) | N/A |
| Squid ACL syntax | Invalid config crashes proxy at startup — caught by compile tests | N/A | N/A |
  - Estimate: 45m
  - Files: src/scc_cli/core/egress_policy.py, tests/test_egress_policy.py, src/scc_cli/core/contracts.py, src/scc_cli/core/enums.py
  - Verify: uv run pytest tests/test_egress_policy.py -q && uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py && uv run mypy src/scc_cli/core/egress_policy.py
- [x] **T02: Created Squid proxy sidecar image definition, NetworkTopologyManager adapter for Docker egress topology, and EgressTopologyInfo dataclass with 14 mocked subprocess tests** — ## Description

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
  - Estimate: 1h
  - Files: images/scc-egress-proxy/Dockerfile, images/scc-egress-proxy/squid.conf.template, images/scc-egress-proxy/entrypoint.sh, src/scc_cli/adapters/egress_topology.py, tests/test_egress_topology.py
  - Verify: uv run pytest tests/test_egress_topology.py -q && uv run ruff check src/scc_cli/adapters/egress_topology.py tests/test_egress_topology.py && uv run mypy src/scc_cli/adapters/egress_topology.py && test -f images/scc-egress-proxy/Dockerfile && test -f images/scc-egress-proxy/squid.conf.template && test -f images/scc-egress-proxy/entrypoint.sh
- [ ] **T03: Wire egress topology into OciSandboxRuntime and add network-enforcement guardrails** — ## Description

Integrate the egress topology layer into `OciSandboxRuntime` so that `run()` enforces network policy through actual Docker network topology. Add proxy env forwarding to the OCI path. Add guardrail tests that `_build_create_cmd` always produces the correct `--network` flag for enforced modes. Run the full test suite to confirm nothing is broken.

## Steps

1. Modify `src/scc_cli/adapters/oci_sandbox_runtime.py`:
   - Import `NetworkTopologyManager` from `egress_topology`, `build_egress_plan` and `compile_squid_acl` from `core/egress_policy`, `NetworkPolicy` from `core/enums`, `collect_proxy_env` from `core/network_policy`.
   - Add an `_topology: NetworkTopologyManager | None = None` instance attribute in `__init__`.
   - Modify `_build_create_cmd()` to accept an optional `network_name: str | None = None` parameter:
     - If `spec.network_policy == NetworkPolicy.LOCKED_DOWN_WEB.value`: add `--network none` to the create command.
     - If `network_name is not None` (i.e., enforced mode with topology set up): add `--network {network_name}` to the create command.
     - If `spec.network_policy == NetworkPolicy.WEB_EGRESS_ENFORCED.value` and topology provided proxy env: add `HTTP_PROXY` and `HTTPS_PROXY` env vars pointing at the proxy endpoint, and `NO_PROXY=""` (force everything through proxy).
     - If `spec.network_policy is None` or `NetworkPolicy.OPEN.value`: no network flags (current behavior).
   - Modify `run()` to orchestrate topology:
     - Before `docker create`: if `spec.network_policy == WEB_EGRESS_ENFORCED`, build the egress plan via `build_egress_plan()`, compile ACLs via `compile_squid_acl()`, create a `NetworkTopologyManager(session_id=container_name)`, call `setup(acl_config)` to get `EgressTopologyInfo`, store `self._topology = topology_manager`, pass `network_name=info.network_name` and proxy env to `_build_create_cmd()`.
     - After `docker create` but before `docker start`: no additional wiring needed (container is already on the internal network from `--network` flag).
     - If `spec.network_policy == LOCKED_DOWN_WEB`, pass `network_name` parameter not needed — just the `--network none` from `_build_create_cmd()`.
     - Also forward host proxy env via `collect_proxy_env()` when `WEB_EGRESS_ENFORCED` (parity with DockerSandboxRuntime).
   - Add a `_teardown_topology(self) -> None` helper that calls `self._topology.teardown()` if `self._topology` is not None. Call this in `remove()` and `stop()` methods.
2. Update `tests/test_oci_sandbox_runtime.py`:
   - Add new test class `TestNetworkEnforcement`:
     - `test_enforced_mode_adds_network_flag` — when `spec.network_policy='web-egress-enforced'`, `_build_create_cmd` output contains `--network` with the internal network name.
     - `test_locked_down_mode_adds_network_none` — when `spec.network_policy='locked-down-web'`, `_build_create_cmd` output contains `--network none`.
     - `test_open_mode_no_network_flag` — when `spec.network_policy='open'` or None, `_build_create_cmd` output does NOT contain `--network`.
     - `test_enforced_mode_injects_proxy_env` — proxy env vars (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`) appear in the create command env.
3. Create `tests/test_oci_egress_integration.py` with integration-level tests (still mocked subprocess):
   - `test_run_enforced_sets_up_topology_before_create` — Mock `NetworkTopologyManager.setup`, verify it's called before `docker create`.
   - `test_run_enforced_passes_network_to_create` — Verify `docker create` args contain `--network scc-egress-*`.
   - `test_run_locked_down_skips_topology` — `NetworkTopologyManager` is NOT instantiated for `locked-down-web`.
   - `test_remove_tears_down_topology` — When topology was set up, `remove()` calls `teardown()`.
   - `test_run_open_mode_unchanged` — No topology setup, no network flags.
4. Add a guardrail test in `tests/test_oci_egress_integration.py`:
   - `test_enforced_mode_never_produces_default_network` — For `web-egress-enforced`, `_build_create_cmd` must NOT produce a command without an explicit `--network` flag (prevents regression to default bridge).
5. Run full verification:
   - `uv run ruff check` — all clean
   - `uv run mypy src/scc_cli` — no issues
   - `uv run pytest --rootdir "$PWD" -q` — full suite passes

## Must-Haves

- [ ] `_build_create_cmd()` respects all three network policy modes
- [ ] `run()` sets up egress topology for `web-egress-enforced`
- [ ] `run()` uses `--network none` for `locked-down-web`
- [ ] `run()` does nothing for `open`/unset (backward compatible)
- [ ] Proxy env vars injected for enforced mode
- [ ] Topology teardown wired into `remove()` and `stop()`
- [ ] Guardrail test prevents regression to default network for enforced mode
- [ ] Full test suite passes

## Verification

- `uv run pytest tests/test_oci_sandbox_runtime.py tests/test_oci_egress_integration.py -q` — all tests pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite passes

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| NetworkTopologyManager.setup() | SandboxLaunchError propagates to caller | SandboxLaunchError (timeout) | N/A |
| NetworkTopologyManager.teardown() | Silently ignored (idempotent) | Silently ignored | N/A |
| compile_squid_acl() | Invalid config → proxy fails at startup → agent can't reach network | N/A (pure function) | N/A |

## Observability Impact

- Signals added: OCI adapter now creates labeled Docker networks and proxy containers discoverable via standard docker commands
- How a future agent inspects this: `docker network ls --filter name=scc-egress-` and `docker ps --filter label=scc.egress-proxy` reveal topology state
- Failure state exposed: SandboxLaunchError from topology setup includes the specific Docker command that failed and its stderr
  - Estimate: 1h
  - Files: src/scc_cli/adapters/oci_sandbox_runtime.py, tests/test_oci_sandbox_runtime.py, tests/test_oci_egress_integration.py
  - Verify: uv run pytest tests/test_oci_sandbox_runtime.py tests/test_oci_egress_integration.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
