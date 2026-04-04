# M004-CONTEXT.md

# Locked decisions for M004

## Non-negotiables
- The hard baseline lives in SCC-controlled runtime wrappers, not only in provider-native hooks or plugins.
- Claude hooks and Codex-native integrations are additive UX/audit surfaces.
- First safety scope is destructive git plus explicit network tools only.
- Safety policy failures must fail closed.
- M004 may only perform local maintainability extractions in files directly touched by runtime safety work.

## Primary objective
Introduce the shared runtime safety layer that works across Claude and Codex without letting provider UX integrations become the enforcement boundary.

## Canonical references
- `CONSTITUTION.md`
- `PLAN.md`
- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/RUNTIME.md`
- `specs/05-safety-engine.md`
- `specs/07-verification-and-quality-gates.md`

## Notes
M004 depends on the runtime topology from M003 and should leave the broader repo-wide strictness, coverage, and decomposition campaign to M005.
