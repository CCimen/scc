---
estimated_steps: 10
estimated_files: 2
skills_used: []
---

# T12: Final truthfulness validation: decisions vs code reconciliation

Verify that D033, D035, D037, D040, D041 are reflected in code and tests. Expand truthfulness guardrail tests to cover reconciliation items. Ensure README, docs, and UI naming are consistent with 'SCC — Sandboxed Code CLI'. Run milestone exit gate.

Steps:
1. Add truthfulness tests validating each reconciliation decision is implemented
2. Verify D033: Codex launch argv includes bypass flag
3. Verify D035: AgentSettings uses rendered_bytes, OCI runtime no json.dumps
4. Verify D037: AgentProvider has auth_check method
5. Verify D040: Codex config includes file-based auth store
6. Verify D041: Codex settings path is workspace-scoped
7. Run full test suite as exit gate
8. Verify test count >= 4750

## Inputs

- `All D029-D043 decisions`
- `All reconciliation task outputs`

## Expected Output

- `Expanded truthfulness tests`
- `Full suite green`
- `Milestone exit gate passes`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
