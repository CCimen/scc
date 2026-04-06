---
id: T03
parent: S02
milestone: M008-g7jk8d
key_files:
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/commands/launch/provider_choice.py
  - src/scc_cli/setup.py
  - tests/test_docs_truthfulness.py
key_decisions:
  - Shared get_agent_provider() helper in dependencies.py replaces hardcoded dicts in provider_choice.py and setup.py
  - init.py template confirmed correct per D045; guardrail test added
duration: 
verification_result: passed
completed_at: 2026-04-06T13:16:25.736Z
blocker_discovered: false
---

# T03: Consolidated provider adapter dispatch into shared get_agent_provider() helper; verified init template branding and added 3 guardrail tests

**Consolidated provider adapter dispatch into shared get_agent_provider() helper; verified init template branding and added 3 guardrail tests**

## What Happened

Extracted get_agent_provider(adapters, provider_id) in dependencies.py as a single dispatch surface that maps provider_id → AgentProvider using the existing _PROVIDER_DISPATCH table. Replaced the hardcoded adapters_by_provider dict in provider_choice.py:collect_provider_readiness() and the provider_map dict in setup.py:_run_provider_onboarding() with calls to the shared helper. Verified init.py:generate_template_content() already uses "Sandboxed Coding CLI" per D045. Added 3 guardrail tests to test_docs_truthfulness.py: one verifying the init template branding, and two preventing re-introduction of hardcoded dispatch dicts in provider_choice.py and setup.py.

## Verification

All 5008 tests pass (0 failures, 23 skipped, 2 xfailed). Ruff check clean. Mypy clean on all modified files. All 45 targeted tests (test_docs_truthfulness.py + test_start_provider_choice.py) pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_docs_truthfulness.py tests/test_start_provider_choice.py -v` | 0 | ✅ pass | 8700ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 6500ms |
| 3 | `uv run mypy src/scc_cli/commands/launch/provider_choice.py src/scc_cli/setup.py src/scc_cli/commands/launch/dependencies.py` | 0 | ✅ pass | 2400ms |
| 4 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 66300ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/commands/launch/provider_choice.py`
- `src/scc_cli/setup.py`
- `tests/test_docs_truthfulness.py`
