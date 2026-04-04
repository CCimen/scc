# M001: Baseline Freeze And Typed Foundation

## Vision
Establish scc-sync-1.7.3 as the only active implementation root, migrate SCC to truthful network vocabulary, lock current fragile behavior with characterization tests, and define the typed control-plane contracts needed for later provider/runtime work without provider leakage or fake enforcement claims.

## Slice Overview
| ID | Slice | Risk | Depends | Done | After this |
|----|-------|------|---------|------|------------|
| S01 | Baseline truth and implementation-root freeze | high | — | ✅ | After this slice, the repo has an explicit M001 execution baseline: active root confirmed, working-tree state inventoried, and the standard verification gate recorded. |
| S02 | Truthful network vocabulary migration | high | S01 | ✅ | After this slice, active M001 code/docs/tests speak in truthful network terms instead of unrestricted/corp-proxy-only/isolated. |
| S03 | Characterization tests for fragile current behavior | medium | S01, S02 | ✅ | After this slice, launch/resume, config inheritance, and safety behavior are locked by tests so later refactors can move safely. |
| S04 | Typed control-plane contracts and shared error-audit seams | high | S03 | ✅ | After this slice, the codebase has explicit typed contracts for the control-plane direction and aligned error/audit seams, with specs and decisions updated to match. |
