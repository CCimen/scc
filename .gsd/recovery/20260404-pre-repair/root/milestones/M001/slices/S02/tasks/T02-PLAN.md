---
estimated_steps: 1
estimated_files: 8
skills_used: []
---

# T02: Migrate active surfaces to truthful network names

Update active M001 target surfaces from legacy network terms to the truthful vocabulary. Preserve actual behavior, remove planned compatibility aliases from core-target surfaces, and keep any non-network English uses of 'isolated' untouched when they do not name the network mode.

## Inputs

- `T01 inventory`
- `CONSTITUTION.md`
- `PLAN.md`

## Expected Output

- `Core enums/schema/docs/tests aligned to open, web-egress-enforced, and locked-down-web where in scope.`
- `No stale legacy mode names left in active M001 target surfaces.`

## Verification

rg -n "unrestricted|corp-proxy-only|isolated" src tests examples README.md && uv run ruff check && uv run mypy src/scc_cli
