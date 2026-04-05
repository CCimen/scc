---
estimated_steps: 19
estimated_files: 1
skills_used: []
---

# T03: Add guardrail test and run full-suite verification

## Description

Add a guardrail test that prevents Claude-specific runtime constants from being re-added to core/constants.py. Verify the entire codebase has zero Claude-constant imports from core/constants.py. Run the full test suite.

The guardrail test follows the established pattern in tests/test_provider_branding.py (TestNoCloudeCodeInNonAdapterModules) — it scans source and fails on violations.

## Steps

1. Create `tests/test_no_claude_constants_in_core.py` with:
   - A test class `TestNoCloudeSpecificConstantsInCore` that reads `src/scc_cli/core/constants.py` and asserts none of the known Claude-specific constant names are defined there
   - Known Claude constant names to check: `AGENT_NAME`, `SANDBOX_IMAGE`, `AGENT_CONFIG_DIR`, `SANDBOX_DATA_VOLUME`, `SANDBOX_DATA_MOUNT`, `CREDENTIAL_PATHS`, `OAUTH_CREDENTIAL_KEY`, `DEFAULT_MARKETPLACE_REPO`
   - Use Python's `tokenize` module (per KNOWLEDGE.md guidance) to scan for NAME tokens matching these constants, avoiding false positives from comments or strings
   - A second test `test_no_claude_constant_imports_from_core` that scans all .py files under `src/scc_cli/` for `from.*core.constants import` lines containing any of the Claude-specific constant names
   - Both tests should produce actionable error messages listing the exact file and line

2. Verify the guardrail test passes: `uv run pytest tests/test_no_claude_constants_in_core.py -v`

3. Run rg scan to confirm zero Claude-constant imports from core.constants across the codebase: `rg 'from.*core\.constants import.*(AGENT_NAME|SANDBOX_IMAGE|SANDBOX_DATA_VOLUME|SANDBOX_DATA_MOUNT|OAUTH_CREDENTIAL_KEY|AGENT_CONFIG_DIR|CREDENTIAL_PATHS|DEFAULT_MARKETPLACE_REPO)' src/scc_cli/`

4. Run full suite: `uv run pytest -q` — must pass with zero regressions

5. Run `uv run ruff check` and `uv run mypy src/scc_cli/core/constants.py` for final lint/type check

## Must-Haves

- [ ] Guardrail test exists and passes
- [ ] Guardrail test would fail if a Claude constant were re-added to core/constants.py (verify by temporarily adding one)
- [ ] Full test suite passes with zero regressions
- [ ] Zero Claude-constant imports from core.constants in src/scc_cli/

## Inputs

- ``src/scc_cli/core/constants.py` — the cleaned constants file from T01`
- ``tests/test_provider_branding.py` — reference pattern for guardrail tests`

## Expected Output

- ``tests/test_no_claude_constants_in_core.py` — guardrail test preventing Claude-specific constants in core/constants.py`

## Verification

uv run pytest tests/test_no_claude_constants_in_core.py -v && uv run pytest -q && uv run ruff check tests/test_no_claude_constants_in_core.py
