# M003-CONTEXT.md

# Locked decisions for M003

## Non-negotiables
- No Docker Desktop dependency.
- No provider-specific runtime logic in core contracts.
- Enforced web egress must be hard enforcement through SCC-controlled topology and proxy policy.
- Host networking is forbidden in enforced modes.
- IP literals, loopback, private, link-local, and metadata destinations are denied by default.
- Org and delegated team policy are the only scopes allowed to widen effective egress in v1.
- Project and user scopes may narrow only.
- Every session/workspace runs under one active team context; SCC must not implicitly union multiple team allowlists.
- M003 may only perform local maintainability extractions in files directly touched by runtime and egress work.

## Primary objective
Build the portable runtime and enforced web-egress layer that makes SCC's network claims technically truthful for Claude and Codex without reopening the broader M005 hardening sweep. The operator model should stay simple: teams choose approved destination sets, users switch context when they move between teams, and local scopes can only make access stricter.

## Canonical references
- `CONSTITUTION.md`
- `PLAN.md`
- `.gsd/PROJECT.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/DECISIONS.md`
- `.gsd/KNOWLEDGE.md`
- `.gsd/RUNTIME.md`
- `specs/04-runtime-and-egress.md`
- `specs/07-verification-and-quality-gates.md`

## Notes
M003 comes before M004 and M005. It should tighten runtime portability and network enforcement while preserving the provider-neutral launch seam established in M002.
