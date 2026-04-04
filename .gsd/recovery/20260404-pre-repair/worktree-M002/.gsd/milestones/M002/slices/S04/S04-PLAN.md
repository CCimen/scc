# S04: Pre-launch validation and durable audit sink

**Goal:** Enforce provider-neutral launch readiness before sandbox startup, persist canonical launch audit events durably, and make both direct launch entrypoints consume the same preflight/finalize boundary.
**Demo:** After this: TBD

## Tasks
- [ ] **T01: Add provider-neutral preflight gate and durable launch audit sink** — Build the application-owned preflight seam that validates launch readiness before sandbox startup and persists canonical launch decisions durably. Consume only `StartSessionPlan`, `AgentLaunchSpec.required_destination_sets`, and the effective network policy already present in the prepared plan; reject malformed provider metadata rather than normalizing it into permissive state.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| prepared launch plan from `prepare_start_session(...)` | raise typed `InvalidLaunchPlanError` or `LaunchPolicyBlockedError` before runtime startup | N/A | reject blank provider ids or destination-set names instead of normalizing them |
| durable audit append through `AuditEventSink` | fail closed with `LaunchAuditWriteError` and do not start the runtime | bubble sink or lock failures as launch-audit write failures | keep one canonical `AuditEvent` serializer instead of ad hoc dict writes |

## Load Profile

- **Shared resources**: one prepared launch plan, one append-only JSONL file plus lock file, and one runtime handoff boundary.
- **Per-operation cost**: constant-time validation over provider id, destination-set names, and effective network policy plus one or two audit appends around startup.
- **10x breakpoint**: correctness under repeated launches matters more than throughput; the first breakage is invalid state or duplicate/missing event writes slipping past the boundary.

## Negative Tests

- **Malformed inputs**: missing `agent_launch_spec`, blank `provider_id`, and blank required destination-set names.
- **Error paths**: `locked-down-web` with non-empty provider destination requirements and sink write failure before runtime start.
- **Boundary conditions**: standalone launch with empty required destination sets, open-network provider launch, ordered JSONL appends, and `launch.started` emission only after a sandbox handle exists.

## Steps

1. Add provider-neutral preflight validation and canonical pass/fail/start event builders in `src/scc_cli/application/launch/preflight.py` using only shared launch-plan contracts.
2. Keep `src/scc_cli/application/launch/finalize_launch.py` orchestration-only: validate first, append preflight/start events through the sink interface, and never start the sandbox after a preflight or audit-write failure.
3. Add the `AuditEventSink` port plus a local append-only JSONL adapter with locking, flush, and fsync semantics, and expose SCC-managed audit file/lock paths in `src/scc_cli/config.py`.
4. Add focused tests that pin malformed-plan rejection, blocked-policy behavior, canonical event ordering, JSONL persistence, and fail-closed sink behavior.

## Must-Haves

- [ ] Preflight validation remains provider-neutral and operates on `StartSessionPlan` / `AgentLaunchSpec`, not provider-native config shapes.
- [ ] A blocked launch fails before runtime startup and leaves behind one canonical `launch.preflight.failed` event.
- [ ] A successful launch records `launch.preflight.passed` before startup and `launch.started` only after the sandbox handle exists.
- [ ] One append-only local JSONL sink persists canonical `AuditEvent` payloads and audit persistence failures stop launch instead of degrading to best-effort logging.
  - Estimate: 90m
  - Files: src/scc_cli/application/launch/preflight.py, src/scc_cli/application/launch/finalize_launch.py, src/scc_cli/ports/audit_event_sink.py, src/scc_cli/adapters/local_audit_event_sink.py, src/scc_cli/config.py, tests/test_launch_preflight.py, tests/test_local_audit_event_sink.py
  - Verify: uv run pytest --rootdir "$PWD" ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py -q
- [ ] **T02: Adopt the shared preflight and audit seam in direct and worktree start paths** — Carry the new boundary through the real entrypoints so direct `scc start` and worktree auto-start cannot bypass provider validation or audit persistence. Keep `bootstrap.py` as the only adapter composition root, require provider plus audit wiring up front, and preserve existing dry-run plus human/JSON error behavior while making worktree auto-start team-aware.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| default adapter bundle from `bootstrap.py` | fail fast with typed launch-builder errors rather than letting entrypoints start with partial provider or audit wiring | N/A | reject partially wired dependency bundles instead of guessing defaults |
| direct `scc start` CLI boundary | surface blocked preflight through the existing human/JSON error boundary and keep runtime stopped | N/A | preserve current output contracts rather than swallowing invalid-plan or blocked-policy reasons |
| worktree auto-start team propagation | treat missing `selected_profile` propagation as a correctness bug because preflight would silently fall back to open-network semantics | N/A | preserve direct-start and worktree behavior parity for team-aware launches |

## Load Profile

- **Shared resources**: shared dependency builder, shared audit sink, fake runtime, and selected-profile config state.
- **Per-operation cost**: one prepared launch plan plus one or two audit appends per live start path.
- **10x breakpoint**: repeated blocked launches will show up as audit noise and failing tests before compute cost becomes interesting.

## Negative Tests

- **Malformed inputs**: missing `agent_provider`, missing `audit_event_sink`, and partially wired adapter bundles.
- **Error paths**: blocked preflight keeps the fake runtime at zero launches for both direct start and worktree auto-start, including JSON output mode.
- **Boundary conditions**: successful standalone starts and successful worktree auto-starts both emit the same canonical event sequence with the correct workspace path and team context.

## Steps

1. Add `src/scc_cli/commands/launch/dependencies.py` as the shared live dependency and plan builder, keeping marketplace-sync gating in one place.
2. Require provider and audit-sink wiring up front and surface missing wiring through typed errors instead of ad hoc command-layer checks.
3. Route direct `scc start` and worktree auto-start through the shared builder and `finalize_launch(...)`, deriving worktree team context from `selected_profile` so org-policy preflight stays honest.
4. Extend focused bootstrap, CLI, integration, and worktree tests so bypassing preflight, skipping audit writes, or starting the runtime after a blocked preflight becomes a failing test.

## Must-Haves

- [ ] Live dependency construction requires both `agent_provider` and `audit_event_sink` before preparing a real launch plan.
- [ ] `src/scc_cli/commands/launch/flow.py` and `src/scc_cli/commands/worktree/worktree_commands.py` both finish live starts through `finalize_launch(...)`.
- [ ] Worktree auto-start carries `selected_profile` into `StartSessionRequest.team` so provider preflight stays team-aware under locked-down policies.
- [ ] Focused tests fail loudly if either entrypoint bypasses preflight, skips audit writes, or starts the runtime after a blocked preflight.
  - Estimate: 90m
  - Files: src/scc_cli/commands/launch/dependencies.py, src/scc_cli/bootstrap.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/worktree/worktree_commands.py, tests/test_bootstrap.py, tests/test_cli.py, tests/test_integration.py, tests/test_worktree_cwd.py
  - Verify: uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q
- [ ] **T03: Build shared live launch dependency and plan helpers** — Create the shared command-layer helper that builds provider-aware and audit-aware live start dependencies and prepares live start plans once. This keeps direct-start and worktree entrypoints from reconstructing `StartSessionDependencies` inline and gives the slice one place to enforce required provider plus audit wiring before preflight ever runs.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| default adapter bundle from `bootstrap.py` | fail fast with typed launch-builder errors rather than letting entrypoints start with partial provider/audit wiring | N/A | reject partially wired dependency bundles instead of guessing defaults |
| live-plan preparation helper | preserve existing marketplace-sync gating for standalone, offline, dry-run, and team-aware launches | N/A | keep request/org-config combinations on the current sync path rather than inventing a second preparation branch |

## Load Profile

- **Shared resources**: one live dependency bundle plus one prepared start plan per launch attempt.
- **Per-operation cost**: existing plan preparation plus one provider check and one audit-sink check.
- **10x breakpoint**: drift in duplicated builder logic breaks correctness long before performance becomes interesting.

## Negative Tests

- **Malformed inputs**: missing `agent_provider`, missing `audit_event_sink`, and partially wired adapter bundles.
- **Error paths**: standalone, offline, and dry-run requests preserve current sync behavior while still using the shared helper.
- **Boundary conditions**: team-aware launch requests with org config and standalone launches without org config both prepare through the same helper.

## Steps

1. Add or refine `build_start_session_dependencies(...)` and `prepare_live_start_plan(...)` in `src/scc_cli/commands/launch/dependencies.py` so live start paths share provider, sink, and marketplace-sync wiring.
2. Require provider and audit-sink wiring up front and surface missing wiring through typed errors instead of ad hoc command-layer checks.
3. Keep the helper command-layer owned and composition-root fed; do not add direct adapter imports to launch or worktree command modules.
4. Add focused bootstrap and command-surface coverage that fails if live dependency construction drifts from the shared helper.

## Must-Haves

- [ ] Live dependency construction requires both `agent_provider` and `audit_event_sink` before preparing a real launch plan.
- [ ] Shared helpers preserve the existing marketplace-sync gating behavior for direct launches.
- [ ] Command modules consume the same live builder instead of reconstructing `StartSessionDependencies` inline.
- [ ] Focused tests fail if composition-root wiring or shared helper behavior drifts.
  - Estimate: 45m
  - Files: src/scc_cli/commands/launch/dependencies.py, src/scc_cli/bootstrap.py, src/scc_cli/commands/launch/flow.py, tests/test_bootstrap.py, tests/test_cli.py
  - Verify: - Focused builder coverage proves provider and audit wiring are required and that direct-start preparation consumes the shared helper.
- `uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_cli.py -q`
- [ ] **T04: Route direct start and worktree auto-start through the shared launch finalizer** — Close the integration loop by forcing both live launch entrypoints to consume the shared builder and to finish through `finalize_launch(...)`. Preserve current sync, dry-run, and output behavior for direct `scc start`, propagate `selected_profile` into worktree auto-start so provider policy stays team-aware, and extend focused CLI/integration coverage so bypassing preflight or audit becomes a failing test instead of silent drift.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| direct `scc start` entrypoint | surface the preflight error through the existing CLI/JSON boundary and keep runtime stopped | N/A | preserve current human/JSON output contracts rather than swallowing the invalid-plan or blocked-policy reason |
| worktree auto-start team propagation | treat missing `selected_profile` propagation as a correctness bug because preflight would silently fall back to open-network semantics | N/A | preserve direct-start and worktree behavior parity for team-aware launches |
| shared builder plus `finalize_launch(...)` | reuse the same pass/fail boundary for both entrypoints instead of allowing one path to bypass audit or preflight | N/A | keep standalone/offline behavior intact while still reaching the shared boundary |

## Load Profile

- **Shared resources**: shared audit sink, shared dependency builder, fake runtime, and selected-profile config state.
- **Per-operation cost**: one prepared launch plan plus one or two audit appends per live start path.
- **10x breakpoint**: repeated blocked launches will show up as audit noise and failing tests before compute cost becomes interesting.

## Negative Tests

- **Malformed inputs**: standalone/offline combinations preserve current behavior while still flowing through the shared boundary when live startup is requested.
- **Error paths**: blocked preflight keeps the fake runtime at zero launches for both direct start and worktree auto-start.
- **Boundary conditions**: successful standalone starts and successful worktree auto-starts both emit the same canonical event sequence with the correct workspace path and team context.

## Steps

1. Route direct `scc start` through shared live-plan preparation and `finalize_launch(...)`, preserving current sync, dry-run, and JSON/human output behavior.
2. Route worktree auto-start through the same builder and finalizer, deriving team context from `selected_profile` so org-policy preflight and audit behavior match direct start.
3. Extend focused CLI and integration tests proving both entrypoints append canonical events, blocked launches fail before runtime start, and selected-profile propagation is preserved.
4. Finish with the focused entrypoint verification and rely on the slice-level lint/type checks for final confidence.

## Must-Haves

- [ ] `src/scc_cli/commands/launch/flow.py` and `src/scc_cli/commands/worktree/worktree_commands.py` both finish live starts through `finalize_launch(...)`.
- [ ] Worktree auto-start carries `selected_profile` into `StartSessionRequest.team` so provider preflight stays team-aware under locked-down policies.
- [ ] Success paths emit the same canonical audit events regardless of entrypoint.
- [ ] Focused tests fail loudly if either entrypoint bypasses preflight, skips audit writes, or starts the runtime after a blocked preflight.
  - Estimate: 45m
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/worktree/worktree_commands.py, tests/test_cli.py, tests/test_integration.py
  - Verify: - Focused entrypoint coverage proves both live paths use the shared builder/finalizer and preserve runtime-stopped behavior on blocked launches.
- `uv run pytest --rootdir "$PWD" ./tests/test_cli.py ./tests/test_integration.py -q`
