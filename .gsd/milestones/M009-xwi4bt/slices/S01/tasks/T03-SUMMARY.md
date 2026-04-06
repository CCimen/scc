---
id: T03
parent: S01
milestone: M009-xwi4bt
key_files:
  - src/scc_cli/commands/launch/auth_bootstrap.py
  - src/scc_cli/commands/launch/preflight.py
  - tests/test_auth_vocabulary_guardrail.py
key_decisions:
  - Keep auth_bootstrap.py as deprecated redirect rather than deleting, since test files exercise the old ensure_provider_auth signature
  - Add optional provider parameter to _ensure_auth for redirect compatibility
duration: 
verification_result: passed
completed_at: 2026-04-06T16:54:57.641Z
blocker_discovered: false
---

# T03: Reduced auth_bootstrap.py to a deprecated redirect delegating to preflight._ensure_auth, making _ensure_auth the single canonical location for all auth messaging

**Reduced auth_bootstrap.py to a deprecated redirect delegating to preflight._ensure_auth, making _ensure_auth the single canonical location for all auth messaging**

## What Happened

Verified ensure_provider_auth has zero callers in non-test source code. Replaced auth_bootstrap.py with a thin deprecated redirect that preserves the old signature for test compatibility, builds a minimal LaunchReadiness, and delegates to preflight._ensure_auth with the provider passed directly. Added optional provider parameter to _ensure_auth to support the redirect without adapter dispatch table mismatches. Updated vocabulary guardrail test to check preflight.py as the canonical auth messaging location.

## Verification

ruff check clean, mypy clean (303 source files), pytest 5117 passed / 23 skipped / 2 xfailed. Targeted tests (auth_vocabulary_guardrail, error_message_quality, resume_after_drift, launch_preflight) all 131 passed. grep confirms no non-test callers of ensure_provider_auth and no non-test imports from auth_bootstrap module.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 63000ms |
| 4 | `grep -rn 'from.*auth_bootstrap' src/scc_cli/ | grep -v __pycache__` | 0 | ✅ pass | 100ms |

## Deviations

Added optional provider parameter to _ensure_auth — necessary because test mocks set deps.agent_provider directly rather than using the adapter dispatch table. The parameter defaults to None so existing callers are unaffected.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/auth_bootstrap.py`
- `src/scc_cli/commands/launch/preflight.py`
- `tests/test_auth_vocabulary_guardrail.py`
