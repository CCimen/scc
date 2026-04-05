---
id: T03
parent: S04
milestone: M007-cqttot
key_files:
  - tests/test_no_claude_constants_in_core.py
  - tests/test_oci_sandbox_runtime.py
key_decisions:
  - Used tokenize-based scanning for constant definitions (per KNOWLEDGE.md) and simple string matching for import-line scanning
duration: 
verification_result: passed
completed_at: 2026-04-05T14:01:46.484Z
blocker_discovered: false
---

# T03: Added guardrail test preventing Claude-specific constants in core/constants.py; fixed ruff I001 import-sorting violation in test_oci_sandbox_runtime.py

**Added guardrail test preventing Claude-specific constants in core/constants.py; fixed ruff I001 import-sorting violation in test_oci_sandbox_runtime.py**

## What Happened

Created tests/test_no_claude_constants_in_core.py with two tests: (1) tokenize-based scan of core/constants.py for Claude-specific NAME tokens, (2) codebase-wide scan for imports of Claude constants from core.constants. Also fixed a pre-existing ruff I001 violation in test_oci_sandbox_runtime.py caused by T02's import restructuring.

## Verification

All four verification gates pass: ruff check (0 errors), mypy on core/constants.py (no issues), guardrail test (2/2 passed), full pytest suite (4720 passed, 23 skipped, 2 xfailed). rg scan confirms zero Claude-constant imports from core.constants.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3400ms |
| 2 | `uv run mypy src/scc_cli/core/constants.py` | 0 | ✅ pass | 45400ms |
| 3 | `uv run pytest tests/test_no_claude_constants_in_core.py -v` | 0 | ✅ pass | 12600ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 50800ms |

## Deviations

Fixed pre-existing ruff I001 violation in tests/test_oci_sandbox_runtime.py that was introduced by T02's import changes — not in the task plan but required for the ruff check gate.

## Known Issues

None.

## Files Created/Modified

- `tests/test_no_claude_constants_in_core.py`
- `tests/test_oci_sandbox_runtime.py`
