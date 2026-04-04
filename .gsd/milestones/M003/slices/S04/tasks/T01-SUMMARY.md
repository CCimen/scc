---
id: T01
parent: S04
milestone: M003
key_files:
  - src/scc_cli/core/destination_registry.py
  - tests/test_destination_registry.py
key_decisions:
  - Registry uses plain dict[str, DestinationSet] for trivial extensibility
  - destination_sets_to_allow_rules helper co-located in registry module
duration: 
verification_result: passed
completed_at: 2026-04-04T10:15:32.814Z
blocker_discovered: false
---

# T01: Added provider destination registry with anthropic-core/openai-core sets, resolve/rule-generation helpers, and 17 unit tests

**Added provider destination registry with anthropic-core/openai-core sets, resolve/rule-generation helpers, and 17 unit tests**

## What Happened

Created src/scc_cli/core/destination_registry.py — a pure module defining PROVIDER_DESTINATION_SETS with anthropic-core and openai-core DestinationSet entries. Exposed resolve_destination_sets(names) for name-to-object lookup (raises ValueError for unknowns) and destination_sets_to_allow_rules(sets) for converting sets to EgressRule allow tuples. Created tests/test_destination_registry.py with 17 tests across registry contents, resolution (happy path, ordering, empty, errors), and rule generation (single/multi host, combined sets, target matching, type checks, reason format).

## Verification

All three verification commands pass: pytest (17/17 tests), mypy (no issues), ruff check (all passed after auto-fixing I001 import sort in test file).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q` | 0 | ✅ pass | 750ms |
| 2 | `uv run mypy src/scc_cli/core/destination_registry.py` | 0 | ✅ pass | 3000ms |
| 3 | `uv run ruff check src/scc_cli/core/destination_registry.py tests/test_destination_registry.py` | 0 | ✅ pass | 500ms |

## Deviations

Ruff import-sort auto-fix applied to test file (I001) — cosmetic only.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/destination_registry.py`
- `tests/test_destination_registry.py`
