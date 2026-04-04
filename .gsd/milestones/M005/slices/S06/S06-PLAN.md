# S06: Guardrails, diagnostics, docs, and milestone validation

**Goal:** Re-enable CI guardrails for complexity and file size, remove all transitional ruff ignores, verify diagnostics expose true system state, and ensure docs/security claims match implemented behavior exactly.
**Demo:** After this: TBD

## Tasks
- [ ] **T01: Re-enable complexity and file-size guardrails** — 
  - Files: pyproject.toml, pyrightconfig.json, tests/test_guardrails*.py
  - Verify: uv run ruff check && uv run pytest; no xfail on size/complexity tests
- [ ] **T02: Remove all transitional ruff ignores** — 
  - Files: pyproject.toml, src/scc_cli/**/*.py
  - Verify: uv run ruff check passes with only permanent ignores remaining in pyproject.toml
- [ ] **T03: Verify and improve operator diagnostics** — 
  - Files: src/scc_cli/doctor/*.py, src/scc_cli/commands/config.py, src/scc_cli/commands/admin.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T04: Final docs and security-language truthfulness review** — 
  - Files: README.md, examples/*.json, src/scc_cli/schemas/org-v1.schema.json
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pyright src/scc_cli && uv run pytest --cov --cov-branch; manual review of docs
