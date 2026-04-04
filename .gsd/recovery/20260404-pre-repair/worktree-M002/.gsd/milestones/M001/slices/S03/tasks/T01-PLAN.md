---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Characterize current Claude launch and resume behavior

Inspect existing launch and resume coverage, then add characterization tests for the current Claude launch/resume paths that M001 intends to preserve through later refactors. Focus on behavior that operators depend on, not incidental implementation details.

## Inputs

- `Existing launch tests`
- `PLAN.md milestone test plan`

## Expected Output

- `New or tightened characterization tests for Claude launch/resume behavior.`
- `Evidence that current launch/resume behavior is preserved.`

## Verification

uv run pytest -k "launch or resume or start"
