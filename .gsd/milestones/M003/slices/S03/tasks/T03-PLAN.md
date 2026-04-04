---
estimated_steps: 59
estimated_files: 3
skills_used: []
---

# T03: Wire egress topology into OciSandboxRuntime and add network-enforcement guardrails

## Description

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

## Inputs

- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — existing OciSandboxRuntime with _build_create_cmd, _build_exec_cmd, run, stop, remove methods`
- ``src/scc_cli/adapters/egress_topology.py` — NetworkTopologyManager.setup(acl_config) -> EgressTopologyInfo, teardown()`
- ``src/scc_cli/core/egress_policy.py` — build_egress_plan() and compile_squid_acl() functions`
- ``src/scc_cli/core/enums.py` — NetworkPolicy.WEB_EGRESS_ENFORCED, LOCKED_DOWN_WEB, OPEN values`
- ``src/scc_cli/core/network_policy.py` — collect_proxy_env() for host proxy forwarding`
- ``tests/test_oci_sandbox_runtime.py` — existing 34 tests that must continue passing`

## Expected Output

- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — modified with network policy enforcement in _build_create_cmd and topology orchestration in run()`
- ``tests/test_oci_sandbox_runtime.py` — extended with TestNetworkEnforcement class (4+ tests)`
- ``tests/test_oci_egress_integration.py` — new integration test file with 5+ tests including guardrail`

## Verification

uv run pytest tests/test_oci_sandbox_runtime.py tests/test_oci_egress_integration.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
