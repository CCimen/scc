# S04: Pre-launch validation and durable audit sink — UAT

**Milestone:** M002
**Written:** 2026-04-03T20:33:31.655Z

# S04: Pre-launch validation and durable audit sink — UAT

**Milestone:** M002
**Written:** 2026-04-03

## UAT Type

- UAT mode: command-driven and artifact-driven.
- Why this mode is sufficient: this slice changes the launch boundary, durable audit persistence, and live CLI entrypoint wiring. The most truthful proof is the focused launch/preflight/audit tests plus the repo gate that exercises both direct start and worktree auto-start on the same seam.

## Preconditions

- Run from the M002 worktree root.
- Dependencies are synced (`uv sync`).
- Pin pytest to the worktree with `--rootdir "$PWD"`; this avoids false path-resolution failures from the synced repo root when verifying worktree-local files.

## Test Cases

### 1. Malformed provider launch metadata is rejected before runtime start

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_launch_preflight.py -q -k "missing_agent_launch_spec or blank_provider_identity or blank_required_destination_name"`.
2. Confirm the selected tests pass.
3. **Expected:** SCC rejects a missing `agent_launch_spec`, a blank provider identity, and blank required-destination metadata as typed preflight errors before any runtime launch occurs.

### 2. Allowed launches emit canonical preflight-passed and launch-started audit events

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_launch_preflight.py -q -k "allowed_launch"`.
2. **Expected:** the test passes and proves `finalize_launch(...)` emits `launch.preflight.passed` followed by `launch.started`, includes `provider_id` and `network_policy` in metadata, and records the sandbox id only after runtime handoff succeeds.

### 3. Locked-down launches fail before runtime and still leave a durable failed-preflight record

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_launch_preflight.py -q -k "blocks_locked_down_provider_launch_before_runtime_start"`.
2. **Expected:** the test passes; runtime call count stays `0`, only `launch.preflight.failed` is recorded, and the failure references `locked-down-web` instead of surfacing later as a runtime surprise.

### 4. Audit sink serialization and append behavior are canonical and durable

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_local_audit_event_sink.py -q`.
2. **Expected:** `3 passed`; serialized records use canonical JSON with ISO timestamps and severity strings, two successive appends produce two JSONL lines, and the sink reports its destination path correctly.

### 5. Direct `scc start` uses the shared preflight/audit builder in both success and block paths

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_cli.py -q -k "appends_canonical_launch_audit_events or returns_json_error_when_preflight_blocks_runtime"`.
2. **Expected:** the allowed-start case records `launch.preflight.passed` then `launch.started`; the blocked case returns a JSON error through SCC’s normal error boundary, leaves no runtime running, and records only `launch.preflight.failed`.

### 6. Worktree auto-start reuses the same finalize-launch seam and team-context propagation

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_integration.py -q -k "worktree_auto_start_appends_shared_audit_events or worktree_auto_start_blocks_before_runtime_when_preflight_fails"`.
2. **Expected:** the passing case records the same canonical audit events for the worktree path; the failing case blocks before runtime startup and records only the failed-preflight event, proving worktree auto-start no longer bypasses the shared boundary.

### 7. Composition-root wiring and full repository verification remain green

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_worktree_cwd.py -q`.
2. Run `uv run ruff check`.
3. Run `uv run mypy src/scc_cli`.
4. Run `uv run pytest --rootdir "$PWD" --tb=short -q`.
5. **Expected:** bootstrap wiring requires both provider and audit sink, worktree cwd behavior stays correct, lint passes, mypy succeeds, and the full suite stays green (`3273 passed, 23 skipped, 4 xfailed` in the verified run).

## Edge Cases

- A standalone launch with no required destination sets remains allowed and still records safe audit metadata.
- A sink write failure blocks launch before runtime start instead of silently dropping audit coverage.
- Worktree auto-start derives `team` from `selected_profile`, so org-policy preflight stays aligned with direct start.

## Failure Signals

- `tests/test_launch_preflight.py` fails on malformed metadata handling, incorrect policy blocking, missing failed-preflight records, or accidental runtime startup on blocked paths.
- `tests/test_local_audit_event_sink.py` fails on non-canonical JSON, lost appends, or incorrect destination reporting.
- `tests/test_cli.py` or `tests/test_integration.py` fail if either live entrypoint bypasses the shared dependency builder or `finalize_launch(...)`.
- `ruff`, `mypy`, or the full pytest gate fail if the new seams broke typing, wiring, or broader runtime behavior.

## Not Proven By This UAT

- Remote/export audit delivery beyond the local JSONL sink.
- Retention/rotation behavior for the audit file.
- A richer end-user audit-inspection UX beyond the stored event stream and existing SCC error output.

