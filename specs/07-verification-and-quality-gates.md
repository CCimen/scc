# Spec 07 — Verification And Quality Gates

## Objective
Keep architecture work safe and maintainable.

## Required gates
- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest`

## Test priorities
- characterization tests before large refactors
- contract tests for provider and runtime seams
- policy merge tests for org/team widening and project/user narrowing
- integration tests for provider-core destination validation and blocked private access
- safety tests for destructive git, explicit network tools, and fail-closed behavior

## Maintainability rules
- re-enable size and complexity guardrails after core seams stabilize
- split orchestration only after characterization coverage exists
