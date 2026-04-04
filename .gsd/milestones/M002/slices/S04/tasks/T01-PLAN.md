---
estimated_steps: 24
estimated_files: 7
skills_used: []
---

# T01: Add provider-neutral preflight gate and durable launch audit sink

Build the application-owned preflight seam that validates launch readiness before sandbox startup and persists canonical launch decisions durably. Consume only `StartSessionPlan`, `AgentLaunchSpec.required_destination_sets`, and the effective network policy already present in the prepared plan; reject malformed provider metadata rather than normalizing it into permissive state.

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

## Inputs

- ``src/scc_cli/application/start_session.py``
- ``src/scc_cli/core/contracts.py``
- ``src/scc_cli/core/errors.py``
- ``src/scc_cli/utils/locks.py``
- ``src/scc_cli/config.py``
- ``src/scc_cli/adapters/claude_agent_provider.py``
- ``src/scc_cli/adapters/codex_agent_provider.py``

## Expected Output

- ``src/scc_cli/application/launch/preflight.py``
- ``src/scc_cli/application/launch/finalize_launch.py``
- ``src/scc_cli/ports/audit_event_sink.py``
- ``src/scc_cli/adapters/local_audit_event_sink.py``
- ``src/scc_cli/config.py``
- ``tests/test_launch_preflight.py``
- ``tests/test_local_audit_event_sink.py``

## Verification

uv run pytest --rootdir "$PWD" ./tests/test_launch_preflight.py ./tests/test_local_audit_event_sink.py -q

## Observability Impact

Adds canonical boundary-level `launch.preflight.passed`, `launch.preflight.failed`, and `launch.started` signals plus a durable local JSONL sink at `config.LAUNCH_AUDIT_FILE`; blocked-policy reasons, sink destination, and startup-point failures become inspectable before runtime handoff.
