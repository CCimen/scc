---
estimated_steps: 28
estimated_files: 1
skills_used: []
---

# T02: Add guardrail tests preventing vocabulary and truthfulness regression

## Description

Creates `tests/test_docs_truthfulness.py` with guardrail tests that scan source, tests, and docs for stale network-mode vocabulary and Constitution violations. These tests prevent regression — if anyone reintroduces old names or Docker Desktop hard-dependency claims, the test suite will catch it.

Follow the established scanning pattern from `tests/test_runtime_detection_hotspots.py` (tokenize-based for code scanning). For string-literal and README scanning, regex is appropriate since we're matching content, not Python identifiers.

## Steps

1. Create `tests/test_docs_truthfulness.py` with these tests:

   a. `test_no_stale_network_modes_in_blocked_by_strings` — Scan all `.py` files in `src/scc_cli/` for `blocked_by=` string arguments containing old network mode names (`unrestricted`, `corp-proxy-only`, `corp-proxy`, `isolated`). Use `ast` module or regex over file content to find string literals in `blocked_by=` kwargs. Must not match non-network uses of "isolated" (e.g. "isolated feature development").

   b. `test_no_stale_network_modes_in_user_warnings` — Scan `src/scc_cli/commands/` for warning/error strings containing old network mode names. Use regex targeting string literals that also mention `network_policy` or `proxy` context.

   c. `test_readme_no_docker_desktop_hard_requirement` — Read `README.md` and assert it does NOT contain a line matching `Requires.*Docker Desktop` without also mentioning alternatives (Engine, OrbStack, Colima).

   d. `test_readme_no_stale_network_mode_names` — Scan `README.md` for old network mode names used as values: `"unrestricted"`, `"corp-proxy-only"`, `"isolated"` in network_policy context. The word "isolated" in prose ("isolated feature", "isolated environment") is fine — only match it as a network_policy value (e.g. in JSON, in backticks, or adjacent to network_policy).

   e. `test_example_json_uses_valid_network_policy_values` — Scan all `examples/*.json` files, find `"network_policy"` values, and assert each is a valid member of the NetworkPolicy enum (`open`, `web-egress-enforced`, `locked-down-web`).

2. Import `NetworkPolicy` from `scc_cli.core.network_policy` (or wherever it's defined) to validate enum membership in test (e).

3. Run the new tests to confirm they pass against the T01-fixed codebase.

4. Run the full test suite as the milestone exit gate: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q`. Confirm test count is ≥3464 (3459 baseline + ≥5 new).

## Must-Haves

- [ ] `tests/test_docs_truthfulness.py` exists with ≥5 test functions
- [ ] Tests scan source for stale `blocked_by` strings
- [ ] Tests scan commands for stale warning strings
- [ ] Tests verify README has no Docker Desktop hard requirement
- [ ] Tests verify README has no stale network mode names
- [ ] Tests verify example JSON files use valid NetworkPolicy values
- [ ] All new tests pass
- [ ] Full exit gate passes: ruff + mypy + pytest
- [ ] Test count ≥3464

## Verification

- `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` — all ≥5 tests pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite passes, count ≥3464

## Inputs

- ``src/scc_cli/application/compute_effective_config.py` — T01 output: blocked_by strings should now use locked-down-web`
- ``src/scc_cli/commands/config.py` — T01 output: warning string should now use web-egress-enforced`
- ``README.md` — T01 output: Docker requirement and enforcement scope should be updated`
- ``examples/*.json` — existing example files with network_policy values (already correct)`
- ``tests/test_runtime_detection_hotspots.py` — reference pattern for tokenize-based source scanning`

## Expected Output

- ``tests/test_docs_truthfulness.py` — new guardrail test file with ≥5 tests preventing vocabulary and truthfulness regression`

## Verification

uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
