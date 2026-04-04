---
id: T01
parent: S01
milestone: M004
key_files:
  - src/scc_cli/core/enums.py
  - src/scc_cli/core/shell_tokenizer.py
  - src/scc_cli/ports/safety_engine.py
  - tests/test_shell_tokenizer.py
key_decisions:
  - Copied shell tokenizer verbatim from plugin to preserve battle-tested parsing logic
duration: 
verification_result: passed
completed_at: 2026-04-04T11:34:36.222Z
blocker_discovered: false
---

# T01: Added CommandFamily enum, lifted shell tokenizer from plugin into core, and defined SafetyEngine protocol port

**Added CommandFamily enum, lifted shell tokenizer from plugin into core, and defined SafetyEngine protocol port**

## What Happened

Extended enums.py with CommandFamily(str, Enum) containing DESTRUCTIVE_GIT and NETWORK_TOOL members. Created shell_tokenizer.py in core by copying the full module from the scc-safety-net plugin — pure stdlib, 5 public functions. Created SafetyEngine Protocol in ports/safety_engine.py with a single evaluate(command, policy) -> SafetyVerdict method. Adapted all 44 plugin tests to use the new import path; all pass unchanged.

## Verification

Ran mypy on all 3 source files (no issues), ruff check (all passed), and pytest on test_shell_tokenizer.py (44 passed in 0.80s).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run mypy src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py` | 0 | ✅ pass | 3000ms |
| 2 | `uv run ruff check src/scc_cli/core/enums.py src/scc_cli/core/shell_tokenizer.py src/scc_cli/ports/safety_engine.py` | 0 | ✅ pass | 1000ms |
| 3 | `uv run pytest tests/test_shell_tokenizer.py -v` | 0 | ✅ pass | 800ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/enums.py`
- `src/scc_cli/core/shell_tokenizer.py`
- `src/scc_cli/ports/safety_engine.py`
- `tests/test_shell_tokenizer.py`
