---
id: T09
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - tests/test_oci_sandbox_runtime.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-05T15:39:09.767Z
blocker_discovered: false
---

# T09: Added runtime permission normalization step to OCI launch path: provider config dir 0700, auth files 0600, uid 1000 ownership via docker exec after container start

**Added runtime permission normalization step to OCI launch path: provider config dir 0700, auth files 0600, uid 1000 ownership via docker exec after container start**

## What Happened

Implemented D039's runtime permission normalization. Docker named volumes retain data from prior container lifecycles, so build-time Dockerfile permissions only apply when the volume is first populated. The new normalization step runs docker exec commands after container start and before settings injection to enforce: (1) provider config directory gets chown 1000:1000 and chmod 0700, (2) known auth files get chown 1000:1000 and chmod 0600 if they exist. Implementation adds _AGENT_UID constant, _AUTH_FILES dict mapping config dir names to auth file tuples, and _normalize_provider_permissions() function with best-effort semantics. Updated 5 pre-existing tests that hardcoded _run_docker call counts.

## Verification

uv run ruff check — zero errors. uv run mypy src/scc_cli — zero issues in 293 files. uv run pytest tests/test_oci_sandbox_runtime.py -v — 64 passed. uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v — 41 passed. uv run pytest -q — 4779 passed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 3 | `uv run pytest tests/test_oci_sandbox_runtime.py -v` | 0 | ✅ pass | 5000ms |
| 4 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 1000ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 54000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `tests/test_oci_sandbox_runtime.py`
