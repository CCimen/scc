---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: Add characterization tests for all high-priority split targets

## Inputs

- None specified.

## Expected Output

- `tests/**`
- `plus all source files listed above`

## Verification

uv run pytest passes; characterization coverage exists for all top-20 split targets with at least the current public API behavior locked
