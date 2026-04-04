---
id: T01
parent: S01
milestone: M003
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/runtime_probe.py
  - src/scc_cli/adapters/docker_runtime_probe.py
  - tests/fakes/fake_runtime_probe.py
  - tests/fakes/__init__.py
  - src/scc_cli/bootstrap.py
  - tests/test_runtime_probe.py
key_decisions:
  - RuntimeProbe.runtime_probe field added as Optional (None default) on DefaultAdapters for incremental adoption
  - Test patches target adapter module namespace rather than scc_cli.docker.core definition site
duration: 
verification_result: passed
completed_at: 2026-04-04T08:22:23.258Z
blocker_discovered: false
---

# T01: Added RuntimeProbe protocol, DockerRuntimeProbe adapter, FakeRuntimeProbe fake, extended RuntimeInfo with four detection fields, wired into bootstrap, and wrote four-scenario probe tests.

**Added RuntimeProbe protocol, DockerRuntimeProbe adapter, FakeRuntimeProbe fake, extended RuntimeInfo with four detection fields, wired into bootstrap, and wrote four-scenario probe tests.**

## What Happened

Extended RuntimeInfo in contracts.py with four new optional fields (version, desktop_version, daemon_reachable, sandbox_available) with defaults preserving backward compatibility. Created RuntimeProbe protocol in ports/runtime_probe.py with a single probe() -> RuntimeInfo method. Implemented DockerRuntimeProbe adapter that calls existing scc_cli.docker helpers defensively — never raises from probe(), returns truthful state across three early-exit paths (not installed, daemon unreachable, full detection). Created FakeRuntimeProbe test fake defaulting to a fully-capable Docker Desktop scenario. Wired runtime_probe into DefaultAdapters and build_fake_adapters(). Wrote tests/test_runtime_probe.py covering four scenarios: Desktop present, Engine only, not installed, daemon not running.

## Verification

All four verification commands pass: pytest (15 passed, 0 failed), ruff check on new files (clean), ruff check full codebase (clean), mypy src/scc_cli (no issues in 244 files).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py -q` | 0 | ✅ pass | 4100ms |
| 2 | `uv run ruff check src/scc_cli/ports/runtime_probe.py src/scc_cli/adapters/docker_runtime_probe.py tests/fakes/fake_runtime_probe.py tests/test_runtime_probe.py` | 0 | ✅ pass | 4100ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 10000ms |
| 4 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 10000ms |

## Deviations

Initial test patches targeted scc_cli.docker.core but needed to target scc_cli.adapters.docker_runtime_probe instead due to Python mock scoping with re-exported names. Standard mock targeting fix, not a plan deviation.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/runtime_probe.py`
- `src/scc_cli/adapters/docker_runtime_probe.py`
- `tests/fakes/fake_runtime_probe.py`
- `tests/fakes/__init__.py`
- `src/scc_cli/bootstrap.py`
- `tests/test_runtime_probe.py`
