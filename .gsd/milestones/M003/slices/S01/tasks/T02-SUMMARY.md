---
id: T02
parent: S01
milestone: M003
key_files:
  - src/scc_cli/adapters/docker_sandbox_runtime.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/ui/dashboard/orchestrator.py
key_decisions:
  - DockerSandboxRuntime.__init__ accepts RuntimeProbe; bootstrap shares single probe instance between sandbox_runtime and runtime_probe fields
  - ensure_available() mirrors exact exception-raising logic of docker.check_docker_available() using RuntimeInfo fields
duration: 
verification_result: passed
completed_at: 2026-04-04T08:37:00.576Z
blocker_discovered: false
---

# T02: Replaced three docker.check_docker_available() calls with probe-backed ensure_available() in DockerSandboxRuntime, worktree start, and session resume paths

**Replaced three docker.check_docker_available() calls with probe-backed ensure_available() in DockerSandboxRuntime, worktree start, and session resume paths**

## What Happened

Added __init__(self, probe: RuntimeProbe) to DockerSandboxRuntime and rewrote ensure_available() to call self._probe.probe() and inspect the returned RuntimeInfo fields. The method raises the same four exception types (DockerNotFoundError, DockerDaemonNotRunningError, DockerVersionError, SandboxNotAvailableError) based on the same conditions as the old docker.check_docker_available() function. Updated bootstrap to share a single DockerRuntimeProbe instance between sandbox_runtime and runtime_probe. Migrated _handle_worktree_start and _handle_session_resume in the dashboard orchestrator to call adapters.sandbox_runtime.ensure_available() instead of docker.check_docker_available().

## Verification

All five verification checks passed: targeted tests (5 passed), ruff check on modified files (clean), ruff check on full codebase (clean), mypy (no issues in 244 files), full test suite (3285 passed, 23 skipped, 4 xfailed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_runtime_probe.py tests/contracts/test_sandbox_runtime_contract.py -q` | 0 | ✅ pass | 3800ms |
| 2 | `uv run ruff check src/scc_cli/adapters/docker_sandbox_runtime.py src/scc_cli/ui/dashboard/orchestrator.py src/scc_cli/bootstrap.py` | 0 | ✅ pass | 8500ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 59500ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 52600ms |
| 5 | `uv run ruff check` | 0 | ✅ pass | 3000ms |

## Deviations

Used info.version is None instead of cli_name emptiness for DockerNotFoundError detection since the probe always populates cli_name as 'docker'.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/docker_sandbox_runtime.py`
- `src/scc_cli/bootstrap.py`
- `src/scc_cli/ui/dashboard/orchestrator.py`
