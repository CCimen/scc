---
id: T12
parent: S05
milestone: M007-cqttot
key_files:
  - tests/test_docs_truthfulness.py
  - .gsd/DECISIONS.md
key_decisions:
  - Updated D-001 from 'Sandboxed Coding CLI' to 'Sandboxed Code CLI' per D030
duration: 
verification_result: passed
completed_at: 2026-04-05T15:55:14.397Z
blocker_discovered: false
---

# T12: Added 10 decision-reconciliation guardrail tests (D033/D035/D037/D040/D041) and corrected D-001 product identity to 'Sandboxed Code CLI'; full suite passes at 4820 tests

**Added 10 decision-reconciliation guardrail tests (D033/D035/D037/D040/D041) and corrected D-001 product identity to 'Sandboxed Code CLI'; full suite passes at 4820 tests**

## What Happened

Added targeted truthfulness tests verifying each M007/S05 reconciliation decision is implemented in code: D033 (Codex bypass flag in runner), D035 (AgentSettings rendered_bytes, no json.dumps in OCI runtime), D037 (auth_check on AgentProvider protocol and both adapters), D040 (file-based auth store in Codex config), D041 (workspace-scoped Codex settings, home-scoped Claude settings), and D-001/D030 consistency (pyproject.toml provider-neutral). Also corrected D-001 heading in DECISIONS.md from 'Sandboxed Coding CLI' to 'Sandboxed Code CLI' per D030.

## Verification

All gate commands pass: ruff check (zero errors), mypy src/scc_cli (zero issues, 293 files), pytest -q (4820 passed, 0 failed, threshold ≥4750). Slice-level: pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v (50/50 pass).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 5000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5000ms |
| 3 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 5000ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass (4820 passed >= 4750) | 65000ms |

## Deviations

Updated D-001 in DECISIONS.md to correct 'Sandboxed Coding CLI' to 'Sandboxed Code CLI' — documentation consistency issue found during reconciliation.

## Known Issues

None.

## Files Created/Modified

- `tests/test_docs_truthfulness.py`
- `.gsd/DECISIONS.md`
