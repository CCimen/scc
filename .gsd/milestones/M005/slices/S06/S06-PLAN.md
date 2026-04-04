# S06: Guardrails, diagnostics, ruff cleanup, and final truthfulness pass

**Goal:** Re-enable CI guardrails for complexity and file size, remove all transitional ruff ignores, verify diagnostics expose true system state, and ensure docs/security claims match implemented behavior exactly.
**Demo:** After this slice, CI enforces complexity/size limits with zero xfail, all transitional ruff ignores are removed, diagnostics truthfully report system state, and docs make no overclaims.

## Tasks
- [ ] **T01: Re-enable complexity and file-size guardrails** — Remove all `xfail` markers from complexity and size checks. Configure Ruff pylint rules for function/module complexity limits (PLR0912 max-branches, PLR0911 max-returns, PLR0915 max-statements). Set and enforce maximum file line counts. Ensure all guardrails pass on the decomposed codebase.
  - Estimate: small
  - Files: pyproject.toml, pyrightconfig.json, tests/test_guardrails*.py
  - Verify: uv run ruff check && uv run pytest; no xfail on size/complexity tests

- [ ] **T02: Remove all transitional ruff ignores** — Remove every M005 transitional ignore from pyproject.toml [tool.ruff.lint] ignore list (PLC0415, PLR0912, PLW1510, B904, PLR0911, PLR0915, RET505, SIM102, RUF022, SIM108, SIM105, PTH123, and all ~30 other transitional ignores). Fix any remaining violations that surface. The final ruff config should only ignore rules with permanent justification (E501, PLR0913, PLR2004).
  - Estimate: medium
  - Files: pyproject.toml, src/scc_cli/**/*.py
  - Verify: uv run ruff check passes with only permanent ignores remaining in pyproject.toml

- [ ] **T03: Verify and improve operator diagnostics** — Review the `doctor` module and diagnostic commands to ensure they accurately expose the effective provider, runtime backend, network mode, safety posture, and policy source. Fix any misleading or missing information. Verify that the system can explain its own state clearly to an operator.
  - Estimate: small
  - Files: src/scc_cli/doctor/*.py, src/scc_cli/commands/config.py, src/scc_cli/commands/admin.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T04: Final docs and security-language truthfulness review** — Review README, examples, and any user-facing docs to ensure security claims, enforcement descriptions, and mode explanations match implemented behavior exactly. Fix any overclaims. Verify that PEP 8 style is followed consistently throughout. Run the full exit gate one final time.
  - Estimate: small
  - Files: README.md, examples/*.json, src/scc_cli/schemas/org-v1.schema.json
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pyright src/scc_cli && uv run pytest --cov --cov-branch; manual review of docs
