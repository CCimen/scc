---
id: T01
parent: S04
milestone: M002
key_files:
  - src/scc_cli/application/launch/preflight.py
  - src/scc_cli/application/launch/finalize_launch.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/ports/audit_event_sink.py
  - src/scc_cli/adapters/local_audit_event_sink.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/config.py
  - tests/test_launch_preflight.py
  - tests/test_local_audit_event_sink.py
key_decisions:
  - Reused the canonical AuditEvent contract as the only persisted payload and wrote it to a local append-only JSONL sink guarded by a file lock.
  - Kept finalize_launch orchestration-only by moving provider-neutral validation and event construction into a dedicated preflight module.
  - Used a narrow legacy fallback only when neither the provider launch spec nor the audit sink seam is wired, so T01 stays compatible while T02 finishes live-path adoption.
duration: 
verification_result: passed
completed_at: 2026-04-03T20:02:34.168Z
blocker_discovered: false
---

# T01: Added provider-neutral launch preflight validation and a durable local AuditEvent JSONL sink, then gated finalize_launch on that seam with focused coverage for pass, block, and sink-failure paths.

**Added provider-neutral launch preflight validation and a durable local AuditEvent JSONL sink, then gated finalize_launch on that seam with focused coverage for pass, block, and sink-failure paths.**

## What Happened

I added a new application-level preflight module that validates provider-owned AgentLaunchSpec data before runtime startup, rejects malformed launch metadata, and blocks provider-required destination sets under locked-down-web without introducing provider-specific fields. I introduced a small AuditEventSink port plus a LocalAuditEventSink adapter that persists canonical AuditEvent records as append-only JSONL in SCC-managed local storage behind a file lock. I extended StartSessionDependencies with the new sink and updated finalize_launch to emit launch.preflight.passed, launch.preflight.failed, and launch.started events through that sink, failing closed on audit persistence errors before sandbox_runtime.run(...). I also added focused tests for malformed plans, blocked launches, standalone launches with no required destination sets, sink write failures, JSON serialization, and append behavior, then confirmed the broader slice checks and full repo gate remained green.

## Verification

Focused verification passed with `uv run pytest ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py -q`, `uv run ruff check`, and `uv run mypy src/scc_cli`. Slice-level verification also passed with `uv run pytest ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q`. The broader gate also passed with `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py -q` | 0 | ✅ pass | 7364ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 35ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8890ms |
| 4 | `uv run pytest ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q` | 0 | ✅ pass | 7791ms |
| 5 | `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q` | 0 | ✅ pass | 38860ms |

## Deviations

Kept one narrow compatibility bridge in `finalize_launch()`: when neither `agent_launch_spec` nor `audit_event_sink` is wired yet, it preserves the legacy direct handoff to `start_session()` so the current tree stays green until T02 threads the shared dependency builder through the live CLI and worktree start paths. Once the seam is in use, the boundary is fail-closed.

## Known Issues

None. T02 still needs to route all live start paths through the shared dependency builder so the new seam is always present, but that is planned follow-up work rather than an unexpected issue.

## Files Created/Modified

- `src/scc_cli/application/launch/preflight.py`
- `src/scc_cli/application/launch/finalize_launch.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/ports/audit_event_sink.py`
- `src/scc_cli/adapters/local_audit_event_sink.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/config.py`
- `tests/test_launch_preflight.py`
- `tests/test_local_audit_event_sink.py`
