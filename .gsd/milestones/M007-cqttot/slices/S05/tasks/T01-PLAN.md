---
estimated_steps: 22
estimated_files: 3
skills_used: []
---

# T01: Updated README title to 'SCC - Sandboxed Code CLI', made pyproject.toml provider-neutral, added 5 M007 truthfulness guardrail tests

Fix the product name in README.md and pyproject.toml per D030, then add ~5 truthfulness guardrail tests to test_docs_truthfulness.py covering M007 deliverables.

## Steps

1. Edit `README.md` line 1: change `SCC - Sandboxed Claude CLI` to `SCC - Sandboxed Code CLI`.
2. Edit `pyproject.toml` line 8 description: change `Run Claude Code in Docker sandboxes with team configs and git worktree support` to `Run AI coding agents in Docker sandboxes with team configs and git worktree support`.
3. Add an M007 section to `tests/test_docs_truthfulness.py` with these guardrail tests:
   - `test_readme_title_says_sandboxed_code_cli` — asserts README line 1 contains 'Sandboxed Code CLI', not 'Sandboxed Claude CLI' or 'Sandboxed Coding CLI'
   - `test_provider_runtime_spec_exists_in_core` — asserts `core/provider_registry.py` exists and contains `PROVIDER_REGISTRY` and `ProviderRuntimeSpec` is defined in `core/contracts.py`
   - `test_fail_closed_dispatch_error_exists` — asserts `core/errors.py` defines `InvalidProviderError`
   - `test_doctor_check_provider_auth_exists` — asserts `doctor/checks/environment.py` defines `check_provider_auth`
   - `test_core_constants_no_claude_specifics` — asserts `core/constants.py` does NOT contain claude-specific runtime constants (SANDBOX_IMAGE, AGENT_NAME, DATA_VOLUME etc). This complements the existing `test_no_claude_constants_in_core.py` guardrail but lives in the truthfulness test file for documentation continuity.
4. Run `uv run ruff check README.md tests/test_docs_truthfulness.py` — must pass.
5. Run `uv run pytest tests/test_docs_truthfulness.py -v` — all tests including new ones must pass.
6. Run `uv run pytest -q` — full suite must pass with zero regressions vs 4745 baseline.

## Must-Haves

- [ ] README title is 'SCC - Sandboxed Code CLI'
- [ ] pyproject.toml description is provider-neutral
- [ ] 5 new truthfulness tests in test_docs_truthfulness.py covering M007 deliverables
- [ ] Full test suite passes

## Verification

- `uv run ruff check` — zero errors
- `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` — all pass
- `uv run pytest -q` — >= 4750 passed, 0 failed

## Inputs

- ``README.md` — line 1 contains stale 'Sandboxed Claude CLI' product name`
- ``pyproject.toml` — line 8 contains Claude-specific description`
- ``tests/test_docs_truthfulness.py` — existing 18 truthfulness tests covering M003-M005; append M007 section`
- ``src/scc_cli/core/provider_registry.py` — M007/S01 deliverable, must exist (read-only verification target)`
- ``src/scc_cli/core/contracts.py` — contains ProviderRuntimeSpec (read-only verification target)`
- ``src/scc_cli/core/errors.py` — contains InvalidProviderError (read-only verification target)`
- ``src/scc_cli/doctor/checks/environment.py` — contains check_provider_auth (read-only verification target)`
- ``src/scc_cli/core/constants.py` — must NOT contain Claude-specific constants (read-only verification target)`

## Expected Output

- ``README.md` — title line updated to 'SCC - Sandboxed Code CLI'`
- ``pyproject.toml` — description updated to provider-neutral text`
- ``tests/test_docs_truthfulness.py` — ~5 new M007 truthfulness guardrail tests appended`

## Verification

uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v && uv run ruff check && uv run pytest -q
