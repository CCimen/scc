# M003/S01 — Research: Capability-based runtime model and detection cleanup

**Date:** 2026-04-04

## Summary

S01's job is to replace the current name-based, Docker-Desktop-only runtime detection in `docker/core.py` with a typed, capability-probed `RuntimeInfo` model that downstream slices (S02–S04) can rely on for portable OCI backend decisions. Today every call site assumes Docker Desktop: `check_docker_available()` gates on Desktop version ≥ 4.50 and `docker sandbox` CLI presence, and the `DockerSandboxRuntime` adapter hard-codes `docker sandbox run` invocations. The `RuntimeInfo` dataclass already exists in `core/contracts.py` (from M001) but has **zero consumers** — it is constructed only in a single test (`test_core_contracts.py`). This slice must make `RuntimeInfo` the canonical runtime-identity type, populate it from real probing, and route all "is the runtime available / what can it do?" questions through it rather than through scattered `check_docker_*` calls.

The work is high risk because nearly every launch path (CLI start, dashboard start, dashboard resume, worktree auto-start, doctor checks) independently calls Docker detection helpers. A premature change that breaks one path will surface as a launch failure. The approach must be incremental: add a typed runtime probe behind the existing `SandboxRuntime` port, write characterization tests against current detection behavior, then migrate callers one seam at a time while keeping the old helpers alive until all consumers are moved.

## Recommendation

1. **Add a `RuntimeProbe` port** in `src/scc_cli/ports/runtime_probe.py` with a single method `probe() -> RuntimeInfo` that returns the canonical runtime identity and capabilities.
2. **Implement `DockerRuntimeProbe` adapter** in `src/scc_cli/adapters/docker_runtime_probe.py` that replaces the scattered detection logic from `docker/core.py` (`_check_docker_installed`, `check_docker_available`, `check_docker_sandbox`, `get_docker_version`, `get_docker_desktop_version`) with a single coherent probe that fills `RuntimeInfo` fields: `runtime_id`, `cli_name`, `supports_oci`, `supports_internal_networks`, `supports_host_network`, `rootless`.
3. **Wire the probe through `bootstrap.py`** so it is available to the composition root and test fakes.
4. **Update `DockerSandboxRuntime.ensure_available()`** to accept/use a `RuntimeInfo` instead of calling `docker.check_docker_available()` directly.
5. **Migrate the two dashboard `check_docker_available()` call sites** and the **four doctor environment checks** to consume `RuntimeInfo` from the probe, preserving existing UX messaging.
6. **Write characterization tests** that pin current detection behavior (version parsing, sandbox check, daemon check) before any extraction, using subprocess mocking.
7. **Add a focused guardrail test** (`test_runtime_detection_hotspots.py`) that scans `src/scc_cli` for raw `docker.check_docker_available()` calls outside the adapter layer, preventing regression.

This is a **targeted research** — the work uses established patterns already in the codebase (port/adapter protocol, bootstrap wiring, characterization tests) but touches multiple consumer sites with non-trivial integration surfaces.

## Implementation Landscape

### Key Files

- `src/scc_cli/core/contracts.py` — Already defines `RuntimeInfo` (lines 73–93). The dataclass is complete for S01 purposes. No changes needed to the type itself unless probing reveals a missing field (e.g., `version: str | None`). Consider adding `version` to capture the detected engine version string for diagnostics.
- `src/scc_cli/docker/core.py` (593 lines) — Contains **all** current runtime detection: `_check_docker_installed()`, `check_docker_available()`, `check_docker_sandbox()`, `get_docker_version()`, `get_docker_desktop_version()`. These are the heuristics S01 must absorb into a typed probe. The functions will stay alive during S01 as internal helpers but should no longer be the public detection surface.
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — The only `SandboxRuntime` implementation. Its `ensure_available()` calls `docker.check_docker_available()` directly. S01 should make it consume `RuntimeInfo` instead.
- `src/scc_cli/ports/sandbox_runtime.py` — The `SandboxRuntime` protocol. `ensure_available()` takes no arguments today. S01 may either: (a) keep this signature and have the adapter hold a probe reference, or (b) add a `runtime_info()` method. Option (a) is less disruptive.
- `src/scc_cli/bootstrap.py` — Composition root. Must add `RuntimeProbe` field to `DefaultAdapters`, wire `DockerRuntimeProbe`, and pass it to `DockerSandboxRuntime` or make it independently available.
- `src/scc_cli/ui/dashboard/orchestrator.py` (1489 lines) — Two direct `docker.check_docker_available()` calls at lines 514 and 650 (dashboard start and resume flows). These must be migrated to the probe or the `SandboxRuntime.ensure_available()` path.
- `src/scc_cli/doctor/checks/environment.py` — Four doctor checks (`check_docker`, `check_docker_desktop`, `check_docker_sandbox`, `check_docker_running`) each independently call Docker detection helpers. These are diagnostic-only but should also route through the typed probe for consistency.
- `src/scc_cli/commands/launch/sandbox.py` — Legacy launch path. Does not call `check_docker_available()` itself (that happens upstream), but imports `docker` directly for `get_or_create_container` and `run`. S02 scope, not S01.
- `tests/test_docker_core.py` (1041 lines) — Extensive tests for current detection behavior. These are the characterization baseline. New tests should complement, not replace them.
- `tests/fakes/fake_sandbox_runtime.py` — Test fake for `SandboxRuntime`. Needs a parallel `FakeRuntimeProbe` in `tests/fakes/`.
- `tests/fakes/__init__.py` — Factory for `build_fake_adapters()`. Must add `FakeRuntimeProbe`.

### Build Order

1. **Characterization tests first** — Pin the current `check_docker_available()` decision tree behavior with focused tests that mock subprocess calls. This is the safety net for all subsequent extraction.
2. **`RuntimeProbe` port + `DockerRuntimeProbe` adapter** — New typed probe that encapsulates detection. Prove it returns correct `RuntimeInfo` for Docker Desktop present, Docker Engine only, Docker missing, and daemon-not-running scenarios.
3. **Bootstrap wiring** — Add `RuntimeProbe` field to `DefaultAdapters`, `FakeRuntimeProbe` to test fakes.
4. **`DockerSandboxRuntime` migration** — Make `ensure_available()` use the probe. This is the first real consumer and proves the seam works.
5. **Dashboard + doctor migration** — Move the remaining `check_docker_available()` consumers to the probe path.
6. **Guardrail test** — Scan for stale raw detection calls outside the adapter layer.

### Verification Approach

- `uv run pytest tests/test_docker_core.py -q` — existing detection tests still pass (characterization).
- `uv run pytest tests/contracts/test_sandbox_runtime_contract.py -q` — runtime contract still satisfied.
- New tests: `uv run pytest tests/test_runtime_probe.py -q` — probe adapter returns correct `RuntimeInfo` shapes for each scenario.
- `uv run pytest tests/test_runtime_detection_hotspots.py -q` — guardrail confirms no stale detection calls leak outside the adapter.
- `uv run ruff check` — no import or style violations.
- `uv run mypy src/scc_cli` — all new code fully typed.
- `uv run pytest --rootdir "$PWD" -q` — full suite green.

## Constraints

- **M003 context rule**: Only local maintainability extractions that directly enable the slice are in scope. Do not refactor the entire `docker/` package or migrate all Docker subprocess calls. S01 scope is detection/identity, not container lifecycle.
- **D006 (Runtime strategy)**: Portable OCI first, Docker Desktop optional. The probe must handle Docker Engine without Docker Desktop as a first-class case — `docker sandbox` missing should not be a fatal error; it just means `supports_sandbox_cli = false` (or similar).
- **D004 (No backward compat aliases in core)**: New `RuntimeProbe` port replaces the old surface. Callers migrate; old helpers become adapter-internal, not long-term public API.
- **KNOWLEDGE rule**: When touching an oversized or high-churn file (`docker/core.py` at 593 lines, `orchestrator.py` at 1489 lines), leave behind a smaller seam or helper. The probe extraction satisfies this for `docker/core.py`. Dashboard callers should route through a typed boundary, not import `docker` directly.
- **bootstrap.py import boundary**: Application and command layers must not import from `scc_cli.adapters.*` or `scc_cli.docker.*` directly for detection. The probe should be consumed via the composition root or via the `SandboxRuntime` port.

## Common Pitfalls

- **Splitting detection too eagerly** — Trying to make `docker/core.py` empty of detection helpers in S01 would break the many internal callers (`build_command`, `list_scc_containers`, etc.) that still need `docker` primitives. Keep the helpers alive internally; the public detection surface moves to the probe.
- **Adding `RuntimeInfo` to `SandboxRuntime.run()` signature** — This would break every caller and test. Instead, let the adapter hold a reference to the probe and query it in `ensure_available()`. Keep the `run(spec)` signature stable.
- **Dashboard orchestrator inline dependency construction** — Lines 530–540 and 665–675 build `StartSessionDependencies` inline instead of using the shared `build_start_session_dependencies` from `dependencies.py`. S01 should not fix this (that's S04/S05 scope) but should be aware when migrating the `check_docker_available()` calls — the probe must be accessible without refactoring the inline construction.
- **`tests/fakes/__init__.py` construction sites** — Any new field on `DefaultAdapters` must also appear in `build_fake_adapters()` with a `None` or fake default. Missing this causes silent test breakage.
- **`RuntimeInfo.rootless` detection** — Detecting rootless mode is non-trivial (`docker info --format '{{.SecurityOptions}}'` or checking cgroup paths). For S01, returning `rootless=None` (unknown) is honest. Rootless detection can land in S02 where it matters for volume mount semantics.

## Open Risks

- **Docker Desktop version probing may differ across OS** — `docker desktop version` CLI is macOS-only in some Docker Desktop releases. The current `get_docker_desktop_version()` has fallback logic; the probe must preserve this without assuming a single OS.
- **`docker info` timeout on slow daemon startup** — Current code uses a 5-second timeout. Under heavy load or on WSL2, this can intermittently fail. The probe should surface this as a `RuntimeInfo` with degraded fields rather than throwing, so callers can provide useful diagnostics.
- **Dashboard inline `docker.check_docker_available()` calls** — The orchestrator builds its own `StartSessionDependencies` without going through the shared builder. Migrating these two call sites without touching the inline construction is possible (just replace the docker call with a probe call passed in or resolved from adapters) but requires care to not widen the change surface.

## Sources

- Existing `RuntimeInfo` contract: `src/scc_cli/core/contracts.py:73–93`
- Current detection heuristics: `src/scc_cli/docker/core.py:52–113`
- Spec 04 runtime targets: `specs/04-runtime-and-egress.md`
- M003 milestone roadmap: `.gsd/milestones/M003/M003-ROADMAP.md`
