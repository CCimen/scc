# M005: Architecture Quality, Strictness, And Hardening

Canonical detailed roadmap: `.gsd/milestones/M005/M005-ROADMAP.md`

## Execution Order
Run M005 after M004. Earlier milestones may perform only narrow hygiene work inside files they already touch.

## Outcome
M005 closes the v1 architecture arc by turning the feature-complete codebase into a maintainable, typed, well-tested, and truthfully documented system with active quality guardrails.

## Success Criteria
- Mandatory hotspot set decomposed, with all modules over 1100 lines eliminated and all modules over 800 lines either reduced or explicitly justified.
- Boundary leaks repaired: no direct runtime/backend imports from core, application, commands, or UI.
- Internal config/policy/launch flow uses typed models instead of raw `dict[str, Any]`.
- Silent error swallowing, unchecked subprocess handling, mutable policy defaults, and quality `xfail`s are removed.
- Critical seams reach the roadmap coverage targets and the full quality gate is green.

## Slice Overview
| ID | Slice | Tasks | Risk | Depends | Done |
|----|-------|-------|------|---------|------|
| S01 | Maintainability baseline and refactor queue | 4 | medium | — | ⬜ |
| S02 | Decompose oversized modules and repair boundaries | 6 | high | S01 | ⬜ |
| S03 | Typed config model adoption and strict typing cleanup | 5 | high | S02 | ⬜ |
| S04 | Error handling, subprocess hardening, and fail-closed cleanup | 5 | high | S02 | ⬜ |
| S05 | Critical-path coverage elevation | 4 | high | S03,S04 | ⬜ |
| S06 | Guardrails, diagnostics, docs, and milestone validation | 4 | medium | S02,S03,S04,S05 | ⬜ |
