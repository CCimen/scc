# SCC Maintainability Refactor Plan (Shareable)

## Context Snapshot (Current State)
- Hotspots: `scc/src/scc_cli/commands/launch/app.py`, `scc/src/scc_cli/ui/dashboard/orchestrator.py`, `scc/src/scc_cli/ui/settings.py`, `scc/src/scc_cli/profiles.py`, `scc/src/scc_cli/core/maintenance.py`.
- Cross-layer coupling: `scc/src/scc_cli/git.py` re-exports UI functions; `scc/src/scc_cli/cli_common.py` and `scc/src/scc_cli/json_command.py` implement parallel error paths.
- Duplicated workspace detection: `scc/src/scc_cli/services/git/core.py` vs `scc/src/scc_cli/services/workspace/resolver.py` and direct call sites in launch.
- Boundary tests exist in `scc/tests/test_import_boundaries.py` and should be extended to new layers.

## Goals (Non‑Negotiable)
- Preserve CLI/TUI behavior and JSON output schema.
- No config semantics changes (org/team/project layering, additive merges, non‑overridable blocks).
- Keep Docker sandboxes + Claude Code working exactly as today.
- Refactor incrementally with strict, reviewable steps.

## Design Rules (For Reviewers)
- UI and CLI should only call application/use cases; no business logic in UI.
- Application/use cases only depend on ports, core, services, and domain models.
- Adapters can depend on external libraries and existing modules; they should not import UI.
- Protocols should be structurally typed (PEP 544) and mypy‑checked.
- Public functions remain typed (`disallow_untyped_defs = true`).
- Use cases return data-only results/view models or interaction requests; UI owns rendering and prompts.
- Use cases must not call prompt APIs; return `InteractionRequest` (e.g., `NeedSelection`, `NeedConfirmation`) and re‑invoke with user choice.
- Avoid a general-purpose `Presenter` port; it tends to leak UI into core. If needed, keep it formatting‑only.
- No side effects at import time: no IO, environment checks, docker/git calls, or config writes at module import.

## Target Architecture (Pragmatic Ports & Adapters)
- `scc_cli/application/`: use cases and orchestration (no UI, no CLI).
- `scc_cli/ports/`: Protocols for runtime, agent, git, filesystem, fetch, clock.
- `scc_cli/adapters/`: Docker/Claude/Git/Requests/Rich implementations.
- `scc_cli/bootstrap.py`: composition root wiring adapters to use cases.
- Domain types for ports (avoid Docker‑shaped primitives):
  - `SandboxSpec`: logical image ref, workspace mount, env vars, working dir, network policy, user/group, extra mounts.
  - `SandboxHandle`: opaque identifier for a running sandbox/session.
  - `SandboxStatus`: enum-like (`CREATED`, `RUNNING`, `STOPPED`, `UNKNOWN`) + timestamps.
  - `AgentCommand`: argv list + env + working dir (no shell string).
  - `AgentSettings`: typed settings model + target write location (path + content).
- If `SandboxRuntime` grows too large, split into `SandboxProvisioner` + `SandboxSessions`.

---

## Phase 0 — Baseline & Guardrails
**Purpose:** lock behavior down so refactors can’t regress UX/JSON.

### Tasks
- [x] Audit test coverage for start/resume, JSON output envelope, marketplace sync.
- [x] Add characterization tests for:
  - JSON envelope + exit codes for both `handle_errors` and `json_command`.
  - Start workflow with workspace auto‑detection.
  - Marketplace sync “dry run” behavior.
- [x] Confirm boundary rules in `tests/test_import_boundaries.py` are aligned with new layers.

**Expected files:** `scc/tests/test_json_output*.py`, `scc/tests/test_start_*.py`, `scc/tests/test_marketplace_sync.py`.
**Risks:** under‑tested areas lead to regressions in JSON/human output.
**Exit:** tests for start/JSON/marketplace pass locally.

---

## Phase 1 — Ports + Adapters Skeleton
**Purpose:** create seams without changing call sites.

### Tasks
- [x] Add `scc_cli/ports/` Protocols:
  - `SandboxRuntime`: lifecycle using domain types (`SandboxSpec`, `SandboxHandle`, `SandboxStatus`).
  - `AgentRunner`: produces `AgentCommand`/`AgentSettings` from effective config.
  - `GitClient`, `Filesystem`, `RemoteFetcher`, `Clock`.
- [x] Add `scc_cli/adapters/`:
  - `docker_sandbox_runtime.py` (wraps `scc_cli/docker/*`).
  - `claude_agent_runner.py` (wraps `scc_cli/claude_adapter.py`).
  - `local_git_client.py`, `requests_fetcher.py`, `system_clock.py`.
- [x] Add minimal fakes for unit tests (e.g., `tests/fakes/fake_runtime.py`).
- [x] Add adapter contract tests (run against fakes, optionally real adapters when environment allows):
  - `tests/contracts/test_sandbox_runtime_contract.py`
  - `tests/contracts/test_agent_runner_contract.py`
  - `tests/contracts/test_git_client_contract.py`
  - `tests/contracts/test_remote_fetcher_contract.py`
  - `tests/contracts/test_clock_contract.py`
  - `tests/contracts/test_filesystem_contract.py` (atomic writes, directory creation, UTF‑8).
- [x] Extend `tests/test_import_boundaries.py` to enforce new layer rules.

**Expected files:** `scc/src/scc_cli/ports/*`, `scc/src/scc_cli/adapters/*`, `scc/tests/fakes/*`, `scc/tests/contracts/*`.
**Risks:** adapters import UI or CLI modules; Protocols drift from real adapters.
**Exit:** mypy validates Protocols; existing behavior unchanged.

---

## Phase 2 — Composition Root
**Purpose:** single wiring location, no more per‑command composition.

### Tasks
- [x] Create `scc_cli/bootstrap.py` to wire default adapters.
- [x] Route one small command through bootstrap (recommend `commands/config.py` or `commands/team.py`).
- [x] Add tests ensuring bootstrap wires defaults correctly.

**Expected files:** `scc/src/scc_cli/bootstrap.py`, touched command module.
**Risks:** dependency injection mismatches in CLI/TUI entrypoints.
**Exit:** one command uses bootstrap with no behavior change; tests green.

---

## Phase 2.5 — Shared Error Mapping (No Behavior Change)
**Purpose:** remove duplication early, reduce risk while refactoring.

### Tasks
- [x] Add `core/error_mapping.py` with:
  - `to_exit_code(exc) -> int`
  - `to_json_payload(exc) -> dict[str, Any]`
  - `to_human_message(exc) -> str`
- [x] Update `cli_common.handle_errors` and `json_command` to call the shared module without changing output.

**Expected files:** `scc/src/scc_cli/core/error_mapping.py`, `scc/src/scc_cli/cli_common.py`, `scc/src/scc_cli/json_command.py`.
**Risks:** subtle JSON/human differences if mapping changes.
**Exit:** `tests/test_json_output*` pass with identical outputs.

---

## Phase 3 — Extract ComputeEffectiveConfig
**Purpose:** isolate core config merge logic from `profiles.py`.

### Tasks
- [x] Create `scc_cli/application/compute_effective_config.py`.
- [x] Move `EffectiveConfig` + merge logic from `profiles.py` into the new module.
- [x] Keep `profiles.py` as thin wrapper for backward compatibility.
- [x] Update call sites (likely `commands/launch/app.py`, `marketplace/resolve.py`, `config.py`).
- [x] Update tests (`tests/test_profiles.py`, `tests/test_config_inheritance.py`, `tests/test_config_explain.py`).

**Expected files:** `scc/src/scc_cli/application/compute_effective_config.py`, `scc/src/scc_cli/profiles.py`.
**Risks:** subtle policy precedence changes; blocked/allowed patterns regress.
**Exit:** tests confirm identical outputs; no UI imports in application module.

---

## Phase 4 — Extract SyncMarketplace Use Case
**Purpose:** split orchestration from file/network IO.

### Tasks
- [x] Create `scc_cli/application/sync_marketplace.py` orchestrator.
- [x] Keep `marketplace/sync.py` as adapter wrapper for backwards compatibility.
- [x] Move network and filesystem dependencies behind `RemoteFetcher`/`Filesystem` ports.
- [x] Update tests (`tests/test_marketplace_sync.py`).

**Expected files:** `scc/src/scc_cli/application/sync_marketplace.py`, `scc/src/scc_cli/marketplace/sync.py`.
**Risks:** managed state drift; settings merge behavior changes.
**Exit:** sync tests pass with identical settings output.

---

## Phase 5 — Launch Workflow
**Purpose:** orchestration without UI/CLI leakage.

### Tasks
- [x] Add `StartSession` use case that composes:
  - resolve workspace (use `services/workspace/resolver.py`).
  - compute effective config.
  - sync marketplace.
  - render agent settings.
  - run sandbox via `SandboxRuntime`.
- [x] Update `commands/launch/app.py` to call the use case.
- [x] Remove duplicate workspace detection in launch; rely on `resolve_launch_context`.
- [x] Ensure JSON output mode still uses same envelopes/exit codes.

**Expected files:** `scc/src/scc_cli/application/start_session.py`, `scc/src/scc_cli/commands/launch/app.py`.
**Risks:** regression in resume/select flows; JSON output divergence.
**Exit:** `tests/test_start_*` and `tests/test_json_output*` pass.

---

## Phase 6 — Dashboard Refactor
**Purpose:** make UI thin + testable.

### Tasks
- [x] Introduce `DashboardViewModel` and action handlers in `application/`.
- [x] Move flow logic out of `ui/dashboard/orchestrator.py` into application layer.
- [x] Ensure Rich rendering only consumes view models.
- [x] Add unit tests for state transitions (no Rich imports).

**Expected files:** `scc/src/scc_cli/application/dashboard.py`, `scc/src/scc_cli/ui/dashboard/orchestrator.py`.
**Risks:** UI regressions in shortcuts/flows.
**Exit:** `tests/test_ui_*` green with no behavior changes.

---

## Phase 6.5 — Settings Refactor
**Purpose:** keep settings maintainable and remove UI logic coupling.

### Tasks
- [x] Create `application/settings/` use cases:
  - `load_settings_state(ctx) -> SettingsViewModel`
  - `apply_settings_change(request) -> Result`
  - `validate_settings(request) -> ValidationResult`
- [x] Refactor `ui/settings.py` to render + route input + call use cases.
- [x] Extract config writes and prompt loops into application layer functions.
- [x] Add unit tests for “change X -> writes Y” using fake filesystem/config store.

**Expected files:** `scc/src/scc_cli/application/settings/*`, `scc/src/scc_cli/ui/settings.py`.
**Risks:** settings UX regressions; config write edge cases.
**Exit:** settings tests pass; `ui/settings.py` is significantly thinner.

---

## Phase 7 — Facades + Error Handling Unification
**Purpose:** remove cross‑layer coupling, unify JSON/human errors.

### Tasks
- [x] Remove UI re‑exports from `scc_cli/git.py`.
- [x] Update call sites to import UI helpers directly from `scc_cli/ui/*`.
- [x] Consolidate `cli_common.handle_errors` and `json_command` onto shared mapping (from Phase 2.5).
- [x] Add tests for JSON envelope consistency.

**Expected files:** `scc/src/scc_cli/git.py`, `scc/src/scc_cli/cli_common.py`, `scc/src/scc_cli/json_command.py`.
**Risks:** CLI/JSON drift or missing imports.
**Exit:** `tests/test_json_output*` green and boundary tests pass.

---

## Phase 7.5 — Maintenance Refactor
**Purpose:** turn `core/maintenance.py` into cohesive modules and testable tasks.

### Tasks
- [x] Split `core/maintenance.py` into `maintenance/` package:
  - `maintenance/cache_cleanup.py`
  - `maintenance/repair_sessions.py`
  - `maintenance/migrations.py`
  - `maintenance/health_checks.py`
- [x] Define a task registry (`name`, `description`, preconditions, `run(ctx) -> Result`).
- [x] Add tests per task with fake filesystem/session store.

**Expected files:** `scc/src/scc_cli/maintenance/*`, `scc/src/scc_cli/core/maintenance.py` (thin wrapper or removed).
**Risks:** missed task wiring; task side effects change.
**Exit:** maintenance tasks covered by unit tests; file size reduced.

---

## Phase 8 — Docs / ADR
**Purpose:** codify architecture for future agents.

### Tasks
- [x] Add ADR describing `SandboxRuntime` vs `AgentRunner` split.
- [x] Update `architecture-report.md` with new layering and module map.

**Expected files:** `scc/architecture-report.md`, ADR location agreed by team.
**Risks:** stale docs if skipped.
**Exit:** docs updated, no tests needed.

---

## PR Size & Step Discipline
- Each PR should change one layer boundary or one use‑case extraction.
- Each PR must include tests proving no behavior change.
- Keep diffs reviewable (prefer <500 LOC net change unless a file split demands more).

---

## Execution Requirements (Per Change)
- TDD: write tests (characterization/unit) before refactors or behavior changes.
- Validate each change set with: `uv run ruff check`, `uv run ruff format`, `uv run mypy src/scc_cli`, `uv run pytest`.

---

## Implementation Principles (Non‑Negotiable)
1. Behavior preservation is the #1 feature. Add characterization tests before refactors.
2. One direction of dependencies:
   - `ui/` and `commands/` may depend on `application/`.
   - `application/` may depend on `ports/`, `services/`, `core/`, and domain models.
   - `adapters/` may depend on external libs and legacy modules.
   - `application/` must not import `ui/` or `commands/` (boundary tests enforce this).
3. Functional core, imperative shell: compute plans/results; adapters perform IO.
4. Ports must be minimal and domain‑shaped; avoid “god ports.”
5. No UI prompts from core; use `InteractionRequest` objects instead.
6. Make illegal states unrepresentable; prefer dataclasses/models to dicts.
7. Add tests before moving code; use characterization tests for JSON/config/marketplace flows.
8. No side effects at import time.
9. Keep compatibility shims thin and temporary.

---

## Coding Style, Comments, Docstrings
### Style
- Use ruff format consistently; no manual formatting debates.
- Prefer `pathlib` for paths; keep filesystem boundary logic in adapters/FS port.

### Typing
- All new application/ports code must be fully typed.
- Avoid `Any` in core/application except for narrowly scoped JSON payloads.
- Use specific type ignores (`# type: ignore[<code>]`) with short reason.

### Comments
- Comments must explain “why,” not “what.”
- Focus comments on config merge invariants, security blocks, delegation rules, workspace trust gating, marketplace merge rules, and JSON/exit code mapping.

### Docstrings
- Required for public functions/classes in `application/` and `ports/`.
- Describe invariants, inputs/outputs in domain terms, and side‑effect boundaries.
- Use a consistent docstring style (Google or reST) and stick to it.

---

## Validation Checklist (Each Phase)
- `uv run ruff check`
- `uv run ruff format`
- `uv run mypy src/scc_cli`
- `uv run pytest` (focused subset per phase, then full suite pre‑merge)

---

## Definition of Done (10/10 Maintainability)
### Architecture & Boundaries
- [x] Application layer has zero imports from `ui/` and `commands/` (enforced by tests).
- [x] Adapters have zero imports from `ui/` (enforced by tests).
- [x] Entry points compose dependencies via `bootstrap.py` only.

### Hotspot Reduction
- [x] `commands/launch/app.py` becomes a thin orchestration shell.
- [x] Dashboard orchestrator becomes thin; state transitions unit-testable.
- [x] `profiles.py` reduced to compatibility wrapper; policy logic extracted.
- [x] `ui/settings.py` and `core/maintenance.py` no longer mega-files.

### Testability
- [x] Use cases have unit coverage without Docker/Git/network.
- [x] Adapter contract tests exist for runtime/git/agent/filesystem ports.
- [x] Characterization tests lock JSON envelopes + exit codes + key outputs.

### Typing & Tooling
- [x] Protocols are mypy-checked and used by use cases.
- [x] New modules keep typed public interfaces.
- [x] CI gates run ruff + mypy + pytest.


---

## Suggested Review Checklist (For Another Agent)
- Confirm new application modules have no UI imports.
- Confirm adapters do not import CLI modules.
- Confirm Protocols match actual adapter signatures.
- Confirm JSON output unchanged for both `handle_errors` and `json_command`.
- Confirm workspace detection only uses `resolve_launch_context`.
- Confirm `claude_adapter.py` remains the only Claude format knowledge source.
- Confirm adapter contract tests exist and run against fakes.
- Confirm settings and maintenance refactors reduce file size and responsibility.

---

## Phase Execution Checklist (Per Phase)
1. Add/confirm characterization tests first.
2. Implement the smallest seam (port/dataclass) enabling extraction.
3. Move logic into application/use case module.
4. Keep old module as thin wrapper if needed; update call sites incrementally.
5. Run ruff check/format, mypy, focused pytest subset, then full suite pre‑merge.
6. Ensure boundary tests still enforce dependency rules.
