---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T03: Consolidate provider adapter dispatch, preserve branding, and verify init template

Provider adapter dispatch:
1. In provider_choice.py collect_provider_readiness(): the hardcoded adapters_by_provider dict maps provider_id to adapter fields. Extract into a shared helper or reuse the _PROVIDER_DISPATCH pattern from dependencies.py.
2. In setup.py _run_provider_onboarding(): same hardcoded provider_map. Use the shared helper.
3. The goal: one dispatch surface for 'which adapter field is the AgentProvider for provider X' — consumed by dependencies.py, provider_choice.py, and setup.py.

Branding:
4. Verify init.py .scc.yaml template uses 'Sandboxed Coding CLI' per D045 (NOT 'Sandboxed Code CLI'). If it says 'Sandboxed Code CLI', that is the old D030 wording and must be corrected to match D045.
5. Add/update guardrail test verifying .scc.yaml template matches D045 product name.

Note: the live codebase already shows 'Sandboxed Coding CLI' in init.py line 73 — verify it's correct and add the test.

## Inputs

- `src/scc_cli/commands/launch/dependencies.py`

## Expected Output

- `src/scc_cli/commands/launch/provider_choice.py`
- `src/scc_cli/setup.py`
- `src/scc_cli/commands/init.py`
- `tests/test_docs_truthfulness.py`

## Verification

uv run pytest tests/test_docs_truthfulness.py tests/test_start_provider_choice.py -v && uv run ruff check && uv run mypy src/scc_cli/commands/launch/provider_choice.py src/scc_cli/setup.py
