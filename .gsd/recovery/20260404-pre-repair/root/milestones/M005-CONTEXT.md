# M005: Architecture Quality, Strictness, And Hardening

Canonical detailed context: `.gsd/milestones/M005/M005-CONTEXT.md`

## Why This Milestone Exists
M005 is the final quality-bar milestone for the current v1 arc. It exists to turn the feature-complete codebase into something that is actually safe to evolve: decomposed where needed, typed internally, well-tested on critical seams, explicit in its failure behavior, and truthful in its diagnostics.

## Sequencing Rule
Run M005 after M004. Do not move the full milestone ahead of M003 or M004. Those milestones still reshape runtime, egress, and safety surfaces, so early broad hardening would create avoidable churn.

## Scope
In scope:
- decomposition of hotspot modules
- architecture boundary repair
- typed config/policy/launch flow
- strict typing cleanup
- error and subprocess hardening
- critical-path coverage
- guardrail restoration
- diagnostics/docs truthfulness

Out of scope:
- new providers
- new policy surfaces
- new safety command families
- unrelated feature work

## Current Planning Baseline
- 58 Python files exceed 300 lines; 15 exceed 800; 3 exceed 1100.
- `commands/launch/flow.py`, `ui/dashboard/orchestrator.py`, and `setup.py` are the largest hotspot modules.
- The repo still contains heavy raw-dict and cast usage in launch/config/marketplace/UI flows.
- Critical coverage gaps remain in runtime, docker, error-mapping, and dashboard/settings surfaces.
- Direct runtime/backend imports still leak into core, application, command, and UI layers.

## Delivery Rule
M005 must fix real maintainability problems, not perform cosmetic churn. Split by responsibility, strengthen types when touching a module, add tests before deep surgery, and remove `xfail` by fixing the underlying defect.
