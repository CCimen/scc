---
estimated_steps: 11
estimated_files: 2
skills_used: []
---

# T02: Resume-after-drift edge cases and auth bootstrap failure handling

**Resume-after-drift tests:**
1. Session exists with provider_id='codex', but Codex auth volume was deleted → resume triggers auth bootstrap (not silent switch to Claude)
2. Session exists with provider_id='codex', but Codex image was removed → resume triggers image auto-build in interactive mode, fails with build command in non-interactive
3. Session exists with provider_id='codex', explicit --provider claude → CLI flag overrides resume provider (intentional switch)
4. Session exists with provider_id='codex', codex no longer in allowed_providers → ProviderNotAllowedError
5. Session exists with provider_id=None (legacy) → falls back to claude at read boundary per D032
6. Explicit --provider codex with missing auth in non-interactive mode → typed error with actionable guidance, NOT a prompt or silent switch

**Auth bootstrap callback failure:**
7. Test: Codex auth bootstrap_auth() raises because browser callback port is unavailable → SCC catches and produces a clean ProviderNotReadyError with guidance ('run scc start interactively to complete browser sign-in'), not a raw socket/server error.
8. If the current code doesn't handle this, add a try/except in ensure_provider_auth or in the Codex adapter's bootstrap_auth() to wrap the failure.

All tests go through the shared preflight module from S01.

## Inputs

- `src/scc_cli/commands/launch/preflight.py`
- `src/scc_cli/adapters/codex_agent_provider.py`

## Expected Output

- `tests/test_resume_after_drift.py`

## Verification

uv run pytest tests/test_resume_after_drift.py -v
