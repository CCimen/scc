---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T04: Final milestone validation and completion

1. Run the full M005 verification gate: ruff check + mypy + pyright + pytest --cov --cov-branch
2. Verify all M005 exit criteria from M005-CONTEXT.md:
   - All modules over 1100 lines reduced below threshold
   - All modules over 800 lines split or justified
   - Direct runtime/backend imports from core/app/commands/UI removed
   - Internal config/policy logic uses typed models
   - Silent failure swallowing removed from maintained paths
   - File/function size tests pass without xfail
   - Docs and diagnostics are truthful
3. Write VALIDATION.md with evidence for each criterion
4. Complete the milestone

## Inputs

- `.gsd/milestones/M005/M005-CONTEXT.md`
- `.gsd/milestones/M005/M005-ROADMAP.md`

## Expected Output

- `.gsd/milestones/M005/VALIDATION.md`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
