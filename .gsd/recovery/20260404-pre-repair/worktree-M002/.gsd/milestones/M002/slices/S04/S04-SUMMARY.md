---
id: S04
parent: M002
milestone: M002
provides:
  - A provider-neutral preflight gate that validates `AgentLaunchSpec` metadata and blocks provider-required destination sets under incompatible network policy before runtime startup.
  - A durable local `AuditEvent` JSONL sink, wired through `bootstrap.py`, that records launch preflight pass/fail and launch-start events with canonical structured payloads.
  - One shared live launch dependency/preparation path reused by both direct `scc start` and worktree auto-start, including correct team-context propagation into preflight and audit behavior.
requires:
  - slice: S01
    provides: The live `AgentProvider` / `AgentLaunchSpec` seam and shared finalize-launch boundary that S04 could turn into an honest preflight gate.
  - slice: S02
    provides: Claude-side provider-owned launch metadata and the composition-root discipline that kept adapter details out of command and application layers while audit wiring was added.
  - slice: S03
    provides: A second real provider with required destination semantics (`openai-core`) proving the preflight logic had to stay provider-neutral rather than Claude-shaped.
affects:
  - S05
key_files:
  - src/scc_cli/application/launch/preflight.py
  - src/scc_cli/ports/audit_event_sink.py
  - src/scc_cli/adapters/local_audit_event_sink.py
  - src/scc_cli/application/launch/finalize_launch.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - tests/test_launch_preflight.py
  - tests/test_local_audit_event_sink.py
  - tests/test_cli.py
  - tests/test_integration.py
key_decisions:
  - Reuse `AuditEvent` as the only persisted payload family and record launch/preflight decisions in an append-only local JSONL sink guarded by a file lock.
  - Keep `finalize_launch(...)` orchestration-only by moving provider-neutral validation and audit-event construction into a dedicated preflight module.
  - Route both direct `scc start` and worktree auto-start through the shared `commands/launch/dependencies.py` builder and the same `finalize_launch(...)` boundary so preflight, audit persistence, and team-context behavior cannot drift between entrypoints.
patterns_established:
  - (none)
observability_surfaces:
  - Durable local launch audit sink at `~/.config/scc/audit/launch-events.jsonl` with companion lock file `~/.config/scc/audit/launch-events.lock`.
  - Canonical structured event types `launch.preflight.passed`, `launch.preflight.failed`, and `launch.started` persisted through `AuditEvent`.
  - Typed preflight/audit startup failures (`LaunchPolicyBlockedError`, `LaunchAuditWriteError`, `LaunchAuditUnavailableError`) that surface through SCC’s existing human and JSON error boundary before runtime start.
drill_down_paths:
  - .gsd/milestones/M002/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T20:33:31.655Z
blocker_discovered: false
---

# S04: Pre-launch validation and durable audit sink

**SCC now fails malformed or policy-blocked launches before runtime startup and records canonical preflight/start audit events through one durable JSONL sink shared by direct start and worktree auto-start.**

## What Happened

T01 introduced a provider-neutral launch-preflight seam that validates the prepared `AgentLaunchSpec` before runtime startup. The new `evaluate_launch_preflight(...)` logic checks that provider identity and required destination metadata are structurally valid, uses the effective network policy from the prepared sandbox plan, and blocks provider-required destination sets when the launch would run under `locked-down-web`. Instead of inventing a second payload schema, the slice reused the canonical `AuditEvent` contract for `launch.preflight.passed`, `launch.preflight.failed`, and `launch.started`, surfaced through a small `AuditEventSink` port and a default `LocalAuditEventSink` adapter that writes append-only JSONL records behind a file lock.

`finalize_launch(...)` now behaves as the honest launch boundary for the live path: it emits a failed preflight event before re-raising a policy or launch-plan error, emits a passed preflight event before runtime handoff, and emits a launch-started event after sandbox startup. If audit persistence fails, SCC raises a typed `LaunchAuditWriteError` that names the sink destination and stops before runtime startup, preserving the slice’s fail-closed requirement.

T02 then carried that seam all the way through the real entrypoints. `bootstrap.py` remains the only adapter composition root and now exposes the durable audit sink beside the provider wiring. `src/scc_cli/commands/launch/dependencies.py` centralizes shared live dependency construction and plan preparation, so both direct `scc start` and worktree auto-start use the same provider-aware dependency bundle. Worktree auto-start now derives `team` from `selected_profile`, prepares the same start-session plan as direct start, and finishes through `finalize_launch(...)` rather than bypassing preflight and audit by calling `start_session(...)` directly.

The slice outcome is the first durable, provider-neutral launch audit path in SCC. Provider requirements are now checked before runtime startup instead of surfacing as a runtime surprise, every live launch path records canonical structured events through one sink, and the touched launch code became more maintainable by extracting a preflight module, an audit-sink port/adapter, and a shared command-layer dependency builder instead of growing the central orchestrators further.

### Operational Readiness
- **Health signal:** successful launches append canonical `launch.preflight.passed` and `launch.started` records to the durable sink, and both direct start and worktree auto-start are covered by focused CLI/integration tests.
- **Failure signal:** blocked launches emit `launch.preflight.failed` and never call the sandbox runtime; audit path failures raise `LaunchAuditWriteError`/`LaunchAuditUnavailableError` before startup and identify the sink destination.
- **Recovery procedure:** restore write access or free space for `~/.config/scc/audit/`, or fix the selected team/network policy mismatch, then rerun the launch. Because failures happen before runtime startup, there is no partial sandbox to clean up for these cases.
- **Monitoring gaps:** the sink is durable but still local-only; there is no built-in rotation, export pipeline, or dedicated health/status command for launch audit storage yet.

## Verification

- `uv run pytest --rootdir "$PWD" ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py -q` → passed (`11 passed`).
- `uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q` → passed (`73 passed`).
- `uv run ruff check` → passed.
- `uv run mypy src/scc_cli` → passed (`Success: no issues found in 240 source files`).
- `uv run pytest --rootdir "$PWD" --tb=short -q` → passed (`3273 passed, 23 skipped, 4 xfailed`).
- Focused assertions in the verified tests confirm all required slice behaviors: malformed plans fail early, locked-down provider launches stop before runtime startup, audit sink write failures fail closed, direct start emits canonical audit events, and worktree auto-start reuses the same preflight/audit seam.

## Requirements Advanced

- R001 — S04 advanced R001 by extracting preflight validation, audit persistence, and live dependency wiring into small typed modules (`preflight.py`, `audit_event_sink.py`, `local_audit_event_sink.py`, and `commands/launch/dependencies.py`) instead of further inflating `finalize_launch.py`, `flow.py`, or worktree command orchestration; it paired those seams with focused contract/CLI/integration tests plus green lint/type/full-suite verification.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 expanded the planned dependency-builder extraction slightly by centralizing shared live-plan preparation and sync gating in `src/scc_cli/commands/launch/dependencies.py`, which reduced duplicated command-layer wiring more than a constructor-only helper would have. Slice verification was also pinned with `--rootdir "$PWD"` so pytest stayed rooted in the worktree; this preserved the intent of the planned checks while avoiding false path-resolution failures against worktree-local tests.

## Known Limitations

The durable sink is local-only for now: SCC writes canonical JSONL records under `~/.config/scc/audit/launch-events.jsonl`, but there is not yet a remote/export sink, retention policy, or rotation strategy. Audit persistence is intentionally fail-closed, so filesystem permission or disk-space problems block launch until the sink path is healthy again. This slice also proves shared entrypoint behavior and boundary semantics, not a broader audit-analysis UX.

## Follow-ups

S05 should build on this slice by adding better diagnostics around the audit sink, considering retention/rotation or export strategies for `launch-events.jsonl`, and continuing decomposition work in remaining high-churn launch orchestration modules without bypassing the shared `finalize_launch(...)` boundary.

## Files Created/Modified

- `src/scc_cli/application/launch/preflight.py` — Added provider-neutral preflight validation and canonical audit-event builders for pass/fail/start launch decisions.
- `src/scc_cli/ports/audit_event_sink.py` — Added the durable audit sink port used by launch orchestration without importing adapter details.
- `src/scc_cli/adapters/local_audit_event_sink.py` — Added the local append-only JSONL audit sink with file locking, fsync, and canonical `AuditEvent` serialization.
- `src/scc_cli/application/launch/finalize_launch.py` — Gated runtime startup on preflight success and durable audit writes while keeping launch finalization orchestration-only.
- `src/scc_cli/config.py` — Exposed durable audit storage paths under SCC-managed local config storage.
- `src/scc_cli/commands/launch/dependencies.py` — Centralized live launch dependency and plan preparation so both start entrypoints reuse the same provider and audit wiring.
- `src/scc_cli/bootstrap.py` — Wired `LocalAuditEventSink()` into `DefaultAdapters` while preserving `bootstrap.py` as the only adapter composition root.
- `src/scc_cli/commands/launch/flow.py` — Switched direct `scc start` flow to the shared dependency/preflight/audit builder.
- `src/scc_cli/commands/worktree/worktree_commands.py` — Switched worktree auto-start to derive team context from `selected_profile` and finish through the shared finalize-launch boundary.
- `tests/test_launch_preflight.py` — Covered malformed plans, blocked launches, allowed launches, sink-write failures, and audit-sink availability requirements.
- `tests/test_local_audit_event_sink.py` — Covered canonical JSON serialization, append-only JSONL writes, and sink destination reporting.
- `tests/test_bootstrap.py` — Covered composition-root audit sink wiring plus shared dependency-builder requirements.
- `tests/test_cli.py` — Covered direct-start audit emission and JSON-mode blocked-preflight behavior.
- `tests/test_integration.py` — Covered worktree auto-start reuse of the shared preflight/audit seam for both pass and block paths.
- `.gsd/KNOWLEDGE.md` — Updated the worktree-local pytest guidance to pin `--rootdir "$PWD"` for reliable verification in `.gsd/worktrees/*`.
- `.gsd/PROJECT.md` — Refreshed the project status document to reflect S04 completion and the remaining S05 focus.
