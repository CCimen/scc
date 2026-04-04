---
estimated_steps: 8
estimated_files: 3
skills_used: []
---

# T02: Docs and security-language truthfulness audit for team-pack model

Review and update all docs, README, examples, schemas, and error messages to:
1. Accurately describe the governed-artifact/team-pack model
2. Not claim Codex bundle parity beyond what codex_renderer implements
3. Use consistent language: 'team pack' / 'bundle' for the team-facing unit, 'governed artifact' for the policy unit
4. Show that provider surfaces are asymmetric and that's intentional
5. Update org-v1.schema.json to include governed_artifacts and enabled_bundles sections
6. Add truthfulness guardrail tests for team-pack language

This is a truthfulness pass — add only language that matches real implementation, remove or qualify claims that exceed it.

## Inputs

- `specs/06-governed-artifacts.md`
- `specs/03-provider-boundary.md`
- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/adapters/codex_renderer.py`

## Expected Output

- `tests/test_docs_truthfulness.py (extended)`
- `src/scc_cli/schemas/org-v1.schema.json (updated)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_docs_truthfulness.py -v && uv run pytest --rootdir "$PWD" -q
