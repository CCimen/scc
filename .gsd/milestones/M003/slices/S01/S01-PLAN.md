# S01: Capability-based runtime model and detection cleanup

**Goal:** Runtime selection is typed and no longer depends on name-only heuristics. A RuntimeProbe port populates RuntimeInfo from real detection, and all launch-path consumers (DockerSandboxRuntime, dashboard start/resume) use it instead of calling docker.check_docker_available() directly.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added RuntimeProbe protocol, DockerRuntimeProbe adapter, FakeRuntimeProbe fake, extended RuntimeInfo with four detection fields, wired into bootstrap, and wrote four-scenario probe tests.** — ## Description

Build the new typed runtime detection surface: a `RuntimeProbe` protocol, its Docker adapter implementation, a test fake, bootstrap wiring, and comprehensive probe tests. This is the foundation that all subsequent consumer migrations depend on.

## Steps

1. **Extend `RuntimeInfo` in `src/scc_cli/core/contracts.py`** — Add four optional fields with defaults: `version: str | None = None`, `desktop_version: str | None = None`, `daemon_reachable: bool = False`, `sandbox_available: bool = False`. These carry the detection detail that launch gating and future diagnostics need. Keep all existing fields untouched.

2. **Create `src/scc_cli/ports/runtime_probe.py`** — Define a `RuntimeProbe` Protocol with a single method `probe() -> RuntimeInfo`. Follow the existing port pattern (see `platform_probe.py` or `sandbox_runtime.py`).

3. **Create `src/scc_cli/adapters/docker_runtime_probe.py`** — Implement `DockerRuntimeProbe` that calls the existing helpers in `scc_cli.docker.core` (`_check_docker_installed`, `get_docker_version`, `get_docker_desktop_version`, `check_docker_sandbox`, and `run_command_bool(['docker', 'info'])`) to populate a full `RuntimeInfo`. For `rootless`, return `None` (unknown) — rootless detection is S02 scope. Import from `scc_cli.docker` (the package), not from `scc_cli.docker.core` directly. Handle each detection step defensively: if Docker isn't installed, return a `RuntimeInfo` with `daemon_reachable=False`, `sandbox_available=False`, etc. Do not raise exceptions from `probe()` — it returns the truthful state.

4. **Create `tests/fakes/fake_runtime_probe.py`** — A `FakeRuntimeProbe` that returns a configurable `RuntimeInfo`. Constructor takes an optional `RuntimeInfo`; defaults to a fully-capable Docker Desktop scenario.

5. **Wire into bootstrap** — In `src/scc_cli/bootstrap.py`: import `DockerRuntimeProbe` and the `RuntimeProbe` port type. Add `runtime_probe: RuntimeProbe` field to `DefaultAdapters` (after `audit_event_sink`). Construct `DockerRuntimeProbe()` in `get_default_adapters()`. In `tests/fakes/__init__.py`: import `FakeRuntimeProbe`, add it to `build_fake_adapters()` as `runtime_probe=FakeRuntimeProbe()`.

6. **Write `tests/test_runtime_probe.py`** — Test the `DockerRuntimeProbe` adapter with subprocess mocking (patch `scc_cli.docker.core` helpers). Cover at minimum:
   - Docker Desktop present: `_check_docker_installed()=True`, daemon reachable, Desktop version >= 4.50, sandbox available → `RuntimeInfo` with all capabilities true.
   - Docker Engine only: installed, daemon reachable, no Desktop version, no sandbox → `supports_oci=True`, `sandbox_available=False`, `desktop_version=None`.
   - Docker not installed: `_check_docker_installed()=False` → minimal `RuntimeInfo` with everything false/None.
   - Daemon not running: installed but `docker info` returns false → `daemon_reachable=False`.

## Must-Haves

- [ ] `RuntimeInfo` extended with 4 new optional fields, existing fields untouched.
- [ ] `RuntimeProbe` protocol in ports with `probe() -> RuntimeInfo`.
- [ ] `DockerRuntimeProbe` adapter calls existing `docker/core.py` helpers, never raises from `probe()`.
- [ ] `FakeRuntimeProbe` in test fakes with configurable return.
- [ ] `DefaultAdapters` and `build_fake_adapters()` include `runtime_probe` field.
- [ ] `tests/test_runtime_probe.py` covers 4 scenarios and all pass.

## Verification

- `uv run pytest tests/test_runtime_probe.py -q` — all probe tests pass.
- `uv run pytest tests/test_core_contracts.py -q` — existing contract tests still pass (RuntimeInfo backward compatible).
- `uv run ruff check src/scc_cli/ports/runtime_probe.py src/scc_cli/adapters/docker_runtime_probe.py tests/fakes/fake_runtime_probe.py tests/test_runtime_probe.py` — clean.
- `uv run mypy src/scc_cli` — no type errors.
  - Estimate: 1.5h
  - Files: src/scc_cli/core/contracts.py, src/scc_cli/ports/runtime_probe.py, src/scc_cli/adapters/docker_runtime_probe.py, tests/fakes/fake_runtime_probe.py, tests/fakes/__init__.py, src/scc_cli/bootstrap.py, tests/test_runtime_probe.py
  - Verify: uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q && uv run ruff check && uv run mypy src/scc_cli
- [x] **T02: Replaced three docker.check_docker_available() calls with probe-backed ensure_available() in DockerSandboxRuntime, worktree start, and session resume paths** — ## Description

Replace the three `docker.check_docker_available()` calls in launch-path code with probe-based detection. This is the consumer migration that makes RuntimeProbe the canonical detection surface for launch decisions.

## Steps

1. **Inject RuntimeProbe into DockerSandboxRuntime** — Add a `__init__` method to `DockerSandboxRuntime` that accepts a `RuntimeProbe` parameter and stores it as `self._probe`. Update `ensure_available()` to call `self._probe.probe()`, inspect the returned `RuntimeInfo`, and raise the same exception types as `docker.check_docker_available()` based on the info fields:
   - If `not info.daemon_reachable` and `info.cli_name` is empty/version is None → `DockerNotFoundError()`
   - If `not info.daemon_reachable` → `DockerDaemonNotRunningError()`
   - If `info.desktop_version` is set and below `MIN_DOCKER_VERSION` → `DockerVersionError(current_version=info.desktop_version)`
   - If `not info.sandbox_available` → `SandboxNotAvailableError()`
   Import error types from `scc_cli.core.errors`.

2. **Update bootstrap wiring** — In `get_default_adapters()`, construct `DockerRuntimeProbe()` first (or reuse the one being assigned to `runtime_probe`), then pass it to `DockerSandboxRuntime(probe)`. Ensure the same probe instance is used for both.

3. **Migrate dashboard orchestrator worktree start (line ~514)** — In `_start_worktree_session` in `src/scc_cli/ui/dashboard/orchestrator.py`: move `adapters = get_default_adapters()` before the Docker check `Status` block. Replace `docker.check_docker_available()` with `adapters.sandbox_runtime.ensure_available()`. Remove the `docker` import from this function if it was only used for detection (check other uses of `docker` in the same function first — if `docker` is still used for other purposes, keep the import).

4. **Migrate dashboard orchestrator resume (line ~650)** — In `_resume_session_dashboard`: same pattern — move adapters retrieval up, replace `docker.check_docker_available()` with `adapters.sandbox_runtime.ensure_available()`. Preserve the existing `try/except` error handling around the call.

5. **Verify no behavior change** — The same exceptions are raised in the same scenarios. The error messages and exit codes are unchanged. The dashboard UX is identical.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| docker CLI subprocess (via probe) | Returns RuntimeInfo with degraded fields | Probe returns `daemon_reachable=False` | Version parsing returns (0,0,0), probe still returns valid RuntimeInfo |

## Must-Haves

- [ ] `DockerSandboxRuntime.__init__` accepts `RuntimeProbe` parameter.
- [ ] `ensure_available()` uses probe, raises same exception types as before.
- [ ] Dashboard orchestrator line ~514 uses `adapters.sandbox_runtime.ensure_available()`.
- [ ] Dashboard orchestrator line ~650 uses `adapters.sandbox_runtime.ensure_available()`.
- [ ] All existing tests in `test_docker_core.py` and `test_sandbox_runtime_contract.py` still pass.

## Verification

- `uv run pytest tests/test_docker_core.py tests/contracts/test_sandbox_runtime_contract.py -q` — existing tests pass.
- `uv run pytest tests/test_runtime_probe.py -q` — probe tests still pass.
- `uv run ruff check src/scc_cli/adapters/docker_sandbox_runtime.py src/scc_cli/ui/dashboard/orchestrator.py src/scc_cli/bootstrap.py` — clean.
- `uv run mypy src/scc_cli` — no type errors.
- `uv run pytest --rootdir "$PWD" -q` — full suite green.
  - Estimate: 1h
  - Files: src/scc_cli/adapters/docker_sandbox_runtime.py, src/scc_cli/bootstrap.py, src/scc_cli/ui/dashboard/orchestrator.py
  - Verify: uv run pytest tests/test_docker_core.py tests/contracts/test_sandbox_runtime_contract.py tests/test_runtime_probe.py -q && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
- [ ] **T03: Add guardrail test preventing stale detection calls and run full verification** — ## Description

Add a guardrail test that scans `src/scc_cli/` for direct `docker.check_docker_available()` calls outside the adapter layer, preventing future regression. Then run the full lint/type/test suite to confirm S01 is green.

## Steps

1. **Create `tests/test_runtime_detection_hotspots.py`** — Write a test that uses `pathlib` and text scanning to find `check_docker_available()` calls in `src/scc_cli/`. The test should:
   - Scan all `.py` files under `src/scc_cli/` recursively.
   - Find lines containing `check_docker_available` (as a function call or import).
   - Exclude allowed locations: `src/scc_cli/docker/core.py` (definition), `src/scc_cli/docker/__init__.py` (re-export), `src/scc_cli/adapters/docker_runtime_probe.py` (the adapter that wraps it).
   - Assert no other files contain the call. If violations are found, the error message should list the file and line number.
   - Follow the pattern established by `tests/test_launch_flow_hotspots.py` and `tests/test_no_root_sprawl.py` if they exist.

2. **Run full verification suite** — Execute all verification commands:
   - `uv run ruff check` — no lint violations across entire repo.
   - `uv run mypy src/scc_cli` — all code typed.
   - `uv run pytest --rootdir "$PWD" -q` — full suite green including the new guardrail.

3. **Verify the guardrail catches violations** — Temporarily add a `check_docker_available` reference in a test to confirm the guardrail would catch it, then remove it. (Or simply verify the test logic by reading it carefully.)

## Must-Haves

- [ ] `tests/test_runtime_detection_hotspots.py` exists and passes.
- [ ] Guardrail correctly excludes `docker/core.py`, `docker/__init__.py`, and `adapters/docker_runtime_probe.py`.
- [ ] `uv run ruff check` passes.
- [ ] `uv run mypy src/scc_cli` passes.
- [ ] `uv run pytest --rootdir "$PWD" -q` passes (full suite).

## Verification

- `uv run pytest tests/test_runtime_detection_hotspots.py -q` — guardrail passes.
- `uv run ruff check` — clean.
- `uv run mypy src/scc_cli` — clean.
- `uv run pytest --rootdir "$PWD" -q` — full suite green.
  - Estimate: 30m
  - Files: tests/test_runtime_detection_hotspots.py
  - Verify: uv run pytest tests/test_runtime_detection_hotspots.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
