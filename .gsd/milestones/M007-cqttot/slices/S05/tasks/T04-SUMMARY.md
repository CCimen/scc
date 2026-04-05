---
id: T04
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/adapters/codex_agent_runner.py
  - tests/test_codex_agent_runner.py
key_decisions:
  - D033 implemented as-written — bypass flag is a positional argv element owned by the runner
duration: 
verification_result: passed
completed_at: 2026-04-05T14:50:54.797Z
blocker_discovered: false
---

# T04: CodexAgentRunner now launches `codex --dangerously-bypass-approvals-and-sandbox`, deferring OS-level sandbox to SCC's container isolation per D033

**CodexAgentRunner now launches `codex --dangerously-bypass-approvals-and-sandbox`, deferring OS-level sandbox to SCC's container isolation per D033**

## What Happened

Updated CodexAgentRunner.build_command() to include --dangerously-bypass-approvals-and-sandbox in the argv. The flag is runner-owned — it lives in the adapter, not in ProviderRuntimeSpec or any core contract. This mirrors the Claude pattern where --dangerously-skip-permissions defers host-level enforcement to SCC's container boundary. Updated existing test and added dedicated D033 test.

## Verification

uv run pytest tests/test_codex_agent_runner.py -v — 7 passed. uv run ruff check — clean. uv run mypy — clean. uv run pytest -q — 4741 passed, 0 failed. Slice-level truthfulness/branding tests — 41 passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_codex_agent_runner.py -v` | 0 | ✅ pass | 5300ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 5300ms |
| 3 | `uv run mypy src/scc_cli/adapters/codex_agent_runner.py` | 0 | ✅ pass | 5200ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 50100ms |
| 5 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 5600ms |

## Deviations

Test file at tests/test_codex_agent_runner.py not tests/adapters/test_codex_agent_runner.py — minor path mismatch from plan.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_runner.py`
- `tests/test_codex_agent_runner.py`
