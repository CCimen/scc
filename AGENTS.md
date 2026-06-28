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
8. Current `.gsd/milestones/*.md` files that match the active or planned milestone
9. `specs/`

## Project rules
- Treat this repository root as the implementation root.
- Historical planning docs may still mention `scc-sync-1.7.3`; in this clean workspace, read that as the current repository root unless a newer written decision says otherwise.
- In the clean workspace, the old archived dirty tree is `/Users/ccimen/dev/sccorj/scc`.
- Do not edit the archived dirty tree unless explicitly porting old WIP onto a new branch from current `main`.
- When source behavior, commands, configuration, provider support, security language, or shortcuts change, update the sibling docs repo at `../scc-cli-docs` in the same reviewable slice or explicitly document why docs are unchanged.
- Do not preserve old network mode names in core after the one-time migration.
- Do not add backward-compatibility aliases in core unless a new written decision explicitly overrides that rule.
- Do not build SCC as a new coding agent.
- Do not make Docker Desktop a required dependency.
- Do not let provider-specific details leak into core contracts.
- Do not rely on provider-native hooks, rules, or plugins as the only enforcement plane.
- Treat open Agent Skills as the only intended cross-provider portability surface.

## Execution guidance
- `.gsd/PROJECT.md` is the canonical milestone register. Files in `.gsd/milestones/`
  are supplementary planning artifacts for current or future milestones only.
- M010 is the current planning milestone for enterprise workflow readiness. Reuse or
  evolve existing owners before adding new runtime concepts.
- Prefer small, typed, contract-preserving refactors over broad rewrites.
- Add characterization tests before splitting monoliths.
- Keep provider-core destination validation in launch planning, not as a runtime surprise.
- Keep GitHub/npm/PyPI optional; they are never implicitly enabled by choosing a provider.
- When uncertain, update `.gsd/DECISIONS.md` instead of silently inventing policy.

## Code Review Graph
- Use code-review-graph first for non-trivial exploration, review context, and impact checks, then verify concrete claims in source files/tests.
- Use `rg` instead for exact symbols/strings, tiny edits, config/lock/generated files, and final file:line evidence.
- If the local CRG graph is empty or stale, fall back to `rg`, direct source reads, and tests rather than waiting on graph repair.
- Local embeddings use `ibm-granite/granite-embedding-small-english-r2`; refresh with `CRG_PARSE_EXECUTOR=thread code-review-graph build --repo .` then `code-review-graph embed --repo . --provider local --model ibm-granite/granite-embedding-small-english-r2`.

## Maintainability Review Protocol
- Review for long-term regulated-organization use: clear policy ownership, auditable behavior, deterministic tests, and explainable provider/runtime boundaries.
- Use parallel reviewers for independent concerns: architecture boundaries, oversized modules/functions, dead code/tests, provider/runtime coupling, error handling, docs drift, and performance hotspots.
- Use Claude review or the Claude peer loop for non-trivial architecture, maintainability, runtime, or readiness conclusions.
- Apply Ponytail pressure first: delete or reuse before adding; remove pre-production compatibility paths that do not protect real persisted data.
- Treat docs drift in `../scc-cli-docs` as source debt when it misstates commands, security guarantees, provider support, or configuration inheritance.
