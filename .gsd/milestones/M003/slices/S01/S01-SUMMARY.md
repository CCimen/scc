---
id: S01
parent: M003
milestone: M003
provides:
  - RuntimeProbe protocol (ports/runtime_probe.py) with probe() -> RuntimeInfo
  - RuntimeInfo extended with version, desktop_version, daemon_reachable, sandbox_available fields
  - DockerRuntimeProbe adapter as the canonical Docker detection surface
  - FakeRuntimeProbe for test scenarios
  - DockerSandboxRuntime.ensure_available() now probe-driven
  - Guardrail preventing direct check_docker_available() outside adapter layer
requires:
  []
affects:
  - S02
  - S03
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/runtime_probe.py
  - src/scc_cli/adapters/docker_runtime_probe.py
  - src/scc_cli/adapters/docker_sandbox_runtime.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/ui/dashboard/orchestrator.py
  - tests/test_runtime_probe.py
  - tests/test_runtime_detection_hotspots.py
  - tests/fakes/fake_runtime_probe.py
  - tests/fakes/__init__.py
key_decisions:
  - D012: RuntimeProbe protocol as the canonical detection surface — probe() -> RuntimeInfo, DockerRuntimeProbe as sole adapter, bootstrap shares single probe instance, tokenizer guardrail prevents regression
  - RuntimeProbe.runtime_probe field added as Optional (None default) on DefaultAdapters for incremental adoption
  - DockerSandboxRuntime.__init__ accepts RuntimeProbe; ensure_available() mirrors exact exception-raising logic using RuntimeInfo fields
  - Used Python tokenizer instead of regex for guardrail source scanning to correctly distinguish code references from string/comment mentions
patterns_established:
  - RuntimeProbe protocol pattern: single probe() method returning a typed RuntimeInfo dataclass with defensive error handling (never raises)
  - Guardrail test using Python tokenize module for detecting code-level references to deprecated call sites while excluding definitions, re-exports, and adapter wrappers
  - Shared probe instance pattern in bootstrap: construct once, pass to both the runtime_probe field and DockerSandboxRuntime constructor
observability_surfaces:
  - none — detection is synchronous and results flow through RuntimeInfo fields; no new logs, endpoints, or persisted state added in this slice
drill_down_paths:
  - .gsd/milestones/M003/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T08:46:01.165Z
blocker_discovered: false
---

# S01: Capability-based runtime model and detection cleanup

**Runtime detection is now typed: a RuntimeProbe protocol populates RuntimeInfo from real Docker state, all launch-path consumers use it instead of calling docker.check_docker_available() directly, and a tokenizer-based guardrail prevents regression.**

## What Happened

This slice replaced the scattered docker.check_docker_available() detection calls with a single typed detection surface.

**T01** established the foundation: extended RuntimeInfo with four optional detection fields (version, desktop_version, daemon_reachable, sandbox_available), created the RuntimeProbe protocol in ports/ with a single probe() -> RuntimeInfo method, implemented DockerRuntimeProbe as the adapter that calls existing docker/core helpers defensively (never raises from probe()), added FakeRuntimeProbe for tests, wired runtime_probe into DefaultAdapters and build_fake_adapters(), and wrote four-scenario probe tests covering Docker Desktop present, Engine only, not installed, and daemon not running.

**T02** migrated the three consumer call sites: added __init__(probe: RuntimeProbe) to DockerSandboxRuntime and rewrote ensure_available() to inspect RuntimeInfo fields and raise the same four exception types as before; updated bootstrap to share a single probe instance between sandbox_runtime and runtime_probe; migrated _handle_worktree_start and _handle_session_resume in the dashboard orchestrator to call adapters.sandbox_runtime.ensure_available() instead of docker.check_docker_available(). The error behavior is semantically identical — same exceptions, same conditions.

**T03** added a tokenizer-based guardrail test that scans src/scc_cli/ for code-level references to check_docker_available outside three allowed files (the definition, re-export, and adapter), preventing future regression. Used Python's tokenize module instead of regex to correctly distinguish NAME tokens from docstring/comment mentions. Final full-suite run: 3286 passed, 23 skipped, 4 xfailed.

## Verification

All slice-level verification gates pass:

1. **Targeted tests** — `uv run pytest tests/test_runtime_probe.py tests/test_core_contracts.py tests/test_runtime_detection_hotspots.py tests/contracts/test_sandbox_runtime_contract.py -q` → 17 passed
2. **Ruff lint** — `uv run ruff check` → All checks passed
3. **Mypy** — `uv run mypy src/scc_cli` → Success: no issues found in 244 source files
4. **Full suite** — `uv run pytest --rootdir "$PWD" -q` → 3286 passed, 23 skipped, 4 xfailed

## Requirements Advanced

- R001 — Replaced scattered docker.check_docker_available() heuristics with a single typed RuntimeProbe protocol behind the adapter boundary, improving testability and maintainability of runtime detection. Added tokenizer guardrail to prevent regression.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Two minor deviations from the original plan:
1. T01: Test patches target the adapter module namespace (scc_cli.adapters.docker_runtime_probe) rather than the definition site (scc_cli.docker.core) due to Python mock scoping with re-exported names. Standard practice, no behavior change.
2. T02: Used `info.version is None` instead of cli_name emptiness for DockerNotFoundError detection since the probe always populates cli_name as 'docker'. Semantically equivalent.
3. T03: Switched from regex-based detection to tokenize-based scanning after the initial regex approach incorrectly flagged a docstring mention in docker_sandbox_runtime.py as a violation.

## Known Limitations

- RuntimeInfo.rootless returns None (unknown) — rootless detection is S02 scope.
- RuntimeProbe field on DefaultAdapters uses Optional with None default for incremental adoption safety; downstream code should handle the None case until all consumers migrate.

## Follow-ups

- S02 needs to extend RuntimeProbe/RuntimeInfo with rootless detection and OCI backend selection.
- S03 depends on RuntimeInfo.sandbox_available for egress topology decisions.

## Files Created/Modified

- `src/scc_cli/core/contracts.py` — Extended RuntimeInfo with four optional detection fields: version, desktop_version, daemon_reachable, sandbox_available
- `src/scc_cli/ports/runtime_probe.py` — New file: RuntimeProbe protocol with probe() -> RuntimeInfo
- `src/scc_cli/adapters/docker_runtime_probe.py` — New file: DockerRuntimeProbe adapter calling docker/core helpers defensively
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — Added __init__(probe: RuntimeProbe), rewrote ensure_available() to use probe-backed RuntimeInfo
- `src/scc_cli/bootstrap.py` — Wired shared DockerRuntimeProbe instance into both runtime_probe and sandbox_runtime fields
- `src/scc_cli/ui/dashboard/orchestrator.py` — Migrated _handle_worktree_start and _handle_session_resume from docker.check_docker_available() to adapters.sandbox_runtime.ensure_available()
- `tests/test_runtime_probe.py` — New file: four-scenario probe tests (Desktop, Engine only, not installed, daemon down)
- `tests/test_runtime_detection_hotspots.py` — New file: tokenizer-based guardrail preventing stale check_docker_available() calls
- `tests/fakes/fake_runtime_probe.py` — New file: FakeRuntimeProbe with configurable RuntimeInfo return
- `tests/fakes/__init__.py` — Added FakeRuntimeProbe to build_fake_adapters()
