---
id: T01
parent: S02
milestone: M003
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/adapters/docker_runtime_probe.py
  - tests/test_runtime_probe.py
  - tests/fakes/fake_runtime_probe.py
key_decisions:
  - preferred_backend uses literal strings 'docker-sandbox' and 'oci' rather than an enum, matching task plan contract
  - Rootless detection uses broad Exception catch for graceful fallback
duration: 
verification_result: passed
completed_at: 2026-04-04T09:01:32.043Z
blocker_discovered: false
---

# T01: Add preferred_backend field to RuntimeInfo and rootless detection to DockerRuntimeProbe with five test scenarios

**Add preferred_backend field to RuntimeInfo and rootless detection to DockerRuntimeProbe with five test scenarios**

## What Happened

Added `preferred_backend: str | None = None` to RuntimeInfo in contracts.py. Updated DockerRuntimeProbe.probe() to detect rootless mode via `docker info --format '{{.SecurityOptions}}'` with graceful None fallback, and to compute preferred_backend: "docker-sandbox" when sandbox is available, "oci" when daemon is reachable without sandbox, None otherwise. Updated all four existing test classes with new field assertions and added TestDockerRuntimeProbeRootlessDetectionFailure for the graceful fallback path.

## Verification

Ran targeted pytest (16 passed), mypy (no issues), ruff check (all passed), and full pytest suite (3287 passed, 23 skipped, 4 xfailed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q` | 0 | ✅ pass | 7600ms |
| 2 | `uv run mypy src/scc_cli/core/contracts.py src/scc_cli/adapters/docker_runtime_probe.py` | 0 | ✅ pass | 3800ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 56200ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 55100ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `tests/test_runtime_probe.py`
- `tests/fakes/fake_runtime_probe.py`
