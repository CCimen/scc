# M001-CONTEXT.md

# Locked decisions for M001

## Non-negotiables
- No long-term backward compatibility in core after the one-time migration.
- No Docker Desktop dependency in the architecture.
- No provider-specific logic in core contracts.
- No fake use of “isolated” language.
- No widening of effective egress outside org policy and delegated team policy.

## Primary objective
Create the cleanest possible foundation for later runtime and provider work. Do not rush into Podman, Pi, OpenCode, or enterprise dashboards before the baseline and typed architecture are sound.

## Canonical references
- `CONSTITUTION.md`
- `PLAN.md`
- `.gsd/REQUIREMENTS.md`
- `specs/01-repo-baseline-and-migration.md`
- `specs/02-control-plane-and-types.md`
- `specs/03-provider-boundary.md`
- `specs/07-verification-and-quality-gates.md`

## Notes
This milestone is intentionally quality-first. It should reduce ambiguity, provider leakage, and orchestration risk before any major feature expansion.
