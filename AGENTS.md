# AGENTS.md

## Read this first
Before planning or changing code, read these files in this order:

1. `CONSTITUTION.md`
2. `PLAN.md`
3. `.gsd/PROJECT.md`
4. `.gsd/REQUIREMENTS.md`
5. `.gsd/DECISIONS.md`
6. `.gsd/KNOWLEDGE.md`
7. `.gsd/RUNTIME.md`
8. `.gsd/milestones/M001-ROADMAP.md`
9. `.gsd/milestones/M001-CONTEXT.md`
10. `.gsd/milestones/M001-RESEARCH.md`
11. `specs/`

## Project rules
- Treat `scc-sync-1.7.3` as the only implementation root.
- Do not work in the archived dirty `scc` tree.
- Do not preserve old network mode names in core after the one-time migration.
- Do not add backward-compatibility aliases in core unless a new written decision explicitly overrides that rule.
- Do not build SCC as a new coding agent.
- Do not make Docker Desktop a required dependency.
- Do not let provider-specific details leak into core contracts.
- Do not rely on provider-native hooks, rules, or plugins as the only enforcement plane.
- Treat open Agent Skills as the only intended cross-provider portability surface.

## Execution guidance
- M001 is the only active milestone until it is complete.
- Prefer small, typed, contract-preserving refactors over broad rewrites.
- Add characterization tests before splitting monoliths.
- Keep provider-core destination validation in launch planning, not as a runtime surprise.
- Keep GitHub/npm/PyPI optional; they are never implicitly enabled by choosing a provider.
- When uncertain, update `.gsd/DECISIONS.md` instead of silently inventing policy.
