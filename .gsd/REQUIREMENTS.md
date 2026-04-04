# Requirements

This file is the explicit capability and coverage contract for the project.

## Validated

### R001 — SCC changes must improve maintainability by keeping touched areas cohesive, testable, and easier to change, especially when work crosses oversized or high-churn files.
- Class: non-functional
- Status: validated
- Description: SCC changes must improve maintainability by keeping touched areas cohesive, testable, and easier to change, especially when work crosses oversized or high-churn files.
- Why it matters: Maintainability directly drives testability, consistency, and the long-term cost and safety of future provider/runtime changes.
- Source: user-feedback
- Primary owning slice: architecture
- Supporting slices: M002/S03, M002/S05
- Validation: Proof from M005: Zero files >1100 lines (from 3 at 1665/1493/1336), 15 MANDATORY-SPLIT files decomposed, 3 boundary violations repaired, 31 import boundary tests pass, typed governed-artifact model hierarchy adopted, provider-neutral bundle pipeline with 100% branch coverage (resolver + both renderers), D023 portable artifact rendering implemented, file/function size guardrails pass without xfail, 18 truthfulness tests, 4486 total tests passing. Exit gate: `uv run ruff check` (0 errors), `uv run mypy src/scc_cli` (289 files, 0 issues), `uv run pytest --rootdir "$PWD" -q` (4486 passed, 23 skipped, 2 xfailed).
- Notes: Validated by M002/S05, substantially strengthened by M005. M005 delivered: module decomposition (S02), typed config models (S03), governed-artifact pipeline (S04), 100% pipeline coverage (S05), diagnostics/truthfulness/guardrails (S06), D023 portable artifact rendering (S07). Wizard cast cleanup deferred (D018). Legacy module coverage targets deferred per D017/D021 user overrides directing work toward team-pack architecture.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | non-functional | validated | architecture | M002/S03, M002/S05 | Proof from M005: Zero files >1100 lines (from 3 at 1665/1493/1336), 15 MANDATORY-SPLIT files decomposed, 3 boundary violations repaired, 31 import boundary tests pass, typed governed-artifact model hierarchy adopted, provider-neutral bundle pipeline with 100% branch coverage (resolver + both renderers), D023 portable artifact rendering implemented, file/function size guardrails pass without xfail, 18 truthfulness tests, 4486 total tests passing. Exit gate: `uv run ruff check` (0 errors), `uv run mypy src/scc_cli` (289 files, 0 issues), `uv run pytest --rootdir "$PWD" -q` (4486 passed, 23 skipped, 2 xfailed). |

## Coverage Summary

- Active requirements: 0
- Mapped to slices: 0
- Validated: 1 (R001)
- Unmapped active requirements: 0
