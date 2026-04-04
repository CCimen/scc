---
id: T02
parent: S05
milestone: M004
key_files:
  - tests/test_docs_truthfulness.py
key_decisions:
  - Extended existing test_docs_truthfulness.py rather than creating a separate file — keeps all truthfulness guardrails co-located
  - File-existence tests for core safety modules and adapters provide structural guardrails beyond code behavior tests
duration: 
verification_result: passed
completed_at: 2026-04-04T13:36:01.469Z
blocker_discovered: false
---

# T02: Added 5 safety truthfulness guardrail tests and passed the full M004 exit gate (3795 tests, ruff clean, mypy clean).

**Added 5 safety truthfulness guardrail tests and passed the full M004 exit gate (3795 tests, ruff clean, mypy clean).**

## What Happened

Extended `tests/test_docs_truthfulness.py` with 5 M004-specific guardrail tests:

1. **test_readme_mentions_safety_audit_command** — Verifies README contains 'safety-audit', ensuring the S04-delivered `scc support safety-audit` command stays documented.

2. **test_readme_describes_core_safety_engine** — Verifies README mentions 'safety engine' or 'runtime safety' as a core capability. Per Constitution §9, the SCC-owned safety engine must not be attributed solely to the plugin.

3. **test_readme_enforcement_scope_mentions_runtime_wrappers** — Verifies README describes runtime wrappers as defense-in-depth and mentions the covered network tools (curl, wget, ssh). Prevents future edits from removing the M004 enforcement scope documentation.

4. **test_safety_engine_core_files_exist** — Verifies all 5 core safety modules exist on disk: safety_engine.py, shell_tokenizer.py, git_safety_rules.py, network_tool_rules.py, safety_policy_loader.py. Guards against accidental deletion of M004/S01+S04 deliverables.

5. **test_safety_adapter_files_exist** — Verifies both provider safety adapter files exist: claude_safety_adapter.py, codex_safety_adapter.py. Guards against accidental deletion of M004/S03 deliverables.

Full exit gate results:
- `uv run ruff check` — All checks passed
- `uv run mypy src/scc_cli` — Success: no issues found in 261 source files
- `uv run pytest --rootdir "$PWD" -q` — 3795 passed, 23 skipped, 4 xfailed (+5 net new from 3790 S04 baseline)

## Verification

All three exit gates passed: ruff clean, mypy clean (261 files), pytest 3795 passed. All 10 truthfulness guardrail tests pass (5 M003 + 5 M004).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 15000ms |
| 3 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 62090ms |
| 4 | `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` | 0 | ✅ pass (10/10 tests) | 1170ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `tests/test_docs_truthfulness.py`
