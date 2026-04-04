---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T02: Align error categories, outputs, and audit-event direction

Align SCCError categories, exit-code handling, and human/JSON output contracts around the typed direction established in T01. Introduce or tighten a shared audit event shape that network and safety work can later reuse.

## Inputs

- `Existing error/output code`
- `Spec 02`
- `M001 research findings`

## Expected Output

- `More coherent SCCError and output mapping surfaces.`
- `A shared audit-event direction visible in code and tests.`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest -k "error or exit code or json or audit"
