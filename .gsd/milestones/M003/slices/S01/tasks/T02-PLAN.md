---
estimated_steps: 29
estimated_files: 3
skills_used: []
---

# T02: Migrate DockerSandboxRuntime and dashboard orchestrator to use RuntimeProbe

## Description

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

## Inputs

- `src/scc_cli/adapters/docker_sandbox_runtime.py`
- `src/scc_cli/bootstrap.py`
- `src/scc_cli/ui/dashboard/orchestrator.py`
- `src/scc_cli/ports/runtime_probe.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/docker/core.py`

## Expected Output

- `src/scc_cli/adapters/docker_sandbox_runtime.py`
- `src/scc_cli/bootstrap.py`
- `src/scc_cli/ui/dashboard/orchestrator.py`

## Verification

uv run pytest tests/test_docker_core.py tests/contracts/test_sandbox_runtime_contract.py tests/test_runtime_probe.py -q && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
