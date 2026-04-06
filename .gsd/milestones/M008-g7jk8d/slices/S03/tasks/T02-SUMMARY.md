---
id: T02
parent: S03
milestone: M008-g7jk8d
key_files:
  - tests/test_resume_after_drift.py
  - src/scc_cli/commands/launch/auth_bootstrap.py
key_decisions:
  - Wrap unexpected bootstrap_auth exceptions in ensure_provider_auth (shared entry point) rather than per-adapter
  - ProviderNotReadyError from bootstrap_auth passes through unchanged to avoid double-wrapping
duration: 
verification_result: passed
completed_at: 2026-04-06T13:42:08.892Z
blocker_discovered: false
---

# T02: Added 22 resume-after-drift edge case tests and auth bootstrap exception wrapping in ensure_provider_auth

**Added 22 resume-after-drift edge case tests and auth bootstrap exception wrapping in ensure_provider_auth**

## What Happened

Created tests/test_resume_after_drift.py with 22 tests across 7 classes covering all task-plan scenarios: resume with deleted auth volume stays on codex provider; resume with removed image triggers auto-build or fails with build command; explicit --provider overrides resume provider; provider blocked by team policy raises ProviderNotAllowedError; legacy session with None provider_id falls through to auto-single/global preference; explicit --provider with missing auth in non-interactive raises with actionable guidance; auth bootstrap exceptions (OSError, FileNotFoundError, TimeoutExpired) are wrapped in ProviderNotReadyError. Added try/except in ensure_provider_auth to wrap raw bootstrap_auth failures while letting ProviderNotReadyError pass through unchanged.

## Verification

uv run pytest tests/test_resume_after_drift.py -v → 22 passed. uv run ruff check → clean. uv run mypy src/scc_cli → clean. uv run pytest -q → 5047 passed, 23 skipped, 2 xfailed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_resume_after_drift.py -v` | 0 | ✅ pass | 5400ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 3200ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5900ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 64300ms |

## Deviations

Used MagicMock for NormalizedOrgConfig in allowed-providers tests because config normalizer doesn't carry allowed_providers from raw dict. Patched provider_image module directly for image-missing tests.

## Known Issues

None.

## Files Created/Modified

- `tests/test_resume_after_drift.py`
- `src/scc_cli/commands/launch/auth_bootstrap.py`
