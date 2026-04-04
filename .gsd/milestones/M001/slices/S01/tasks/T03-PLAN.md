---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T03: Confirm and tighten canonical-root guidance

Confirm that active references, milestone artifacts, and execution guidance all point to scc-sync-1.7.3 as the implementation root, with the dirty scc tree treated as archival/rollback evidence only. Tighten any stale local guidance discovered during the inventory.

## Inputs

- `T01 inventory findings`
- `Existing root guidance files`

## Expected Output

- `Canonical-root references aligned for active M001 work.`
- `A task summary describing any guidance/doc adjustments made.`

## Verification

rg -n "scc-sync-1.7.3|dirty `scc` tree|archival|rollback evidence" . --glob 'AGENTS.md' --glob '.gsd/**' --glob 'README.md' --glob 'PLAN.md'
