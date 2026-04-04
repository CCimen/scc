---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T03: Stabilize the renamed network vocabulary

Run focused and full verification after the rename work, then fix any mismatches introduced by the migration so the new terminology is stable and honest across code, docs, and tests.

## Inputs

- `T02 code and docs changes`

## Expected Output

- `Passing targeted checks and full gate after terminology migration.`
- `A task summary describing any behavior-preserving fixes needed.`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest
