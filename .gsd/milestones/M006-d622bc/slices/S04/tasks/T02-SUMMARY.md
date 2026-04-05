---
id: T02
parent: S04
milestone: M006-d622bc
key_files:
  - src/scc_cli/commands/launch/render.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/presentation/json/sessions_json.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/ports/models.py
  - src/scc_cli/application/start_session.py
  - tests/test_provider_machine_readable.py
key_decisions:
  - _container_name uses provider_id:workspace as hash input when non-empty, preserving backward compat for empty provider_id
  - Support bundle resolves provider_id via config.get_selected_provider() at manifest build time with try/except safety
  - SandboxSpec.provider_id defaults to empty string (not None) for hash-input consistency
duration: 
verification_result: passed
completed_at: 2026-04-05T01:08:52.159Z
blocker_discovered: false
---

# T02: Added provider_id to dry-run JSON, support bundle manifest, session list JSON, and provider-aware container naming to SandboxSpec and OCI runtime

**Added provider_id to dry-run JSON, support bundle manifest, session list JSON, and provider-aware container naming to SandboxSpec and OCI runtime**

## What Happened

Implemented two D028 deliverables across seven source files: (1) provider_id now appears in dry-run JSON output, support bundle manifest, and session list JSON envelope; (2) _container_name() in OCI runtime hashes provider_id:workspace to produce different container names per provider, preventing coexistence collisions. SandboxSpec gained a provider_id field populated by _build_sandbox_spec() from the provider adapter's capability profile. All changes are backward compatible — empty provider_id preserves the original hash, and new keyword parameters default to None.

## Verification

18/18 task-specific tests pass. Ruff and mypy clean on all 6 source files. Full regression suite: 4617 passed, 0 failures. Slice-level checks (test_session_provider_id, ruff, mypy on session files) all pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_machine_readable.py -v --no-cov` | 0 | ✅ pass | 6400ms |
| 2 | `uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` | 0 | ✅ pass | 4700ms |
| 3 | `uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` | 0 | ✅ pass | 4700ms |
| 4 | `uv run pytest --rootdir "$PWD" -q --no-cov` | 0 | ✅ pass | 63300ms |
| 5 | `uv run pytest tests/test_session_provider_id.py -v --no-cov` | 0 | ✅ pass | 4700ms |
| 6 | `uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` | 0 | ✅ pass | 4700ms |
| 7 | `uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` | 0 | ✅ pass | 4700ms |

## Deviations

Renamed local variable provider_id to resolved_pid in _build_sandbox_spec() to avoid shadowing; added non-OCI branch provider resolution that wasn't in the plan but was needed for consistency.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/render.py`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/presentation/json/sessions_json.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/ports/models.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_provider_machine_readable.py`
