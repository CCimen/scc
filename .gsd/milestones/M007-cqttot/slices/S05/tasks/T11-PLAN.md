---
estimated_steps: 7
estimated_files: 2
skills_used: []
---

# T11: Persistence model tests: config freshness transitions

Add targeted tests proving the persistence model works across session transitions: governed->standalone launch, team A->team B, settings->no-settings. Verify config freshness is deterministic and not reliant on fresh container creation alone.

Steps:
1. Identify the right test surface for persistence transitions
2. Write tests for governed->standalone (stale team config cleared)
3. Write tests for teamA->teamB (new team config replaces old)
4. Write tests for settings->no-settings (empty/default config written)
5. Run full test suite

## Inputs

- `D038, D042 decision text`
- `current test infrastructure`

## Expected Output

- `Transition tests for persistence model`

## Verification

uv run pytest tests/adapters/test_oci_sandbox_runtime.py tests/commands/launch/ -v && uv run ruff check
