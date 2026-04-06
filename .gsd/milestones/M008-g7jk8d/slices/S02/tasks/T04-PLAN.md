---
estimated_steps: 7
estimated_files: 1
skills_used: []
---

# T04: Slice verification gate

Run full verification:
1. ruff check on all touched files
2. mypy on all touched source files
3. Focused pytest on guardrail, truthfulness, lifecycle, and provider choice tests
4. Full pytest suite (>= 4820 with zero regressions)
5. Verify via rg that no active user-facing string in commands/ contains 'Docker Desktop'
6. Verify branding consistency: rg 'Sandboxed Cod' src/scc_cli/ should show only 'Sandboxed Coding CLI'

## Inputs

- None specified.

## Expected Output

- Update the implementation and proof artifacts needed for this task.

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
