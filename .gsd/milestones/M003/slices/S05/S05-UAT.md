# S05: Verification, docs truthfulness, and milestone closeout — UAT

**Milestone:** M003
**Written:** 2026-04-04T11:10:24.131Z

# S05: Verification, docs truthfulness, and milestone closeout — UAT

**Milestone:** M003
**Written:** 2026-04-04

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S05 is a docs/vocabulary cleanup and guardrail slice with no runtime behavior changes. All deliverables are source edits and test files verifiable via grep and pytest.

## Preconditions

- Working directory is `scc-sync-1.7.3` with `uv sync` completed
- All S01–S04 slices are complete (NetworkPolicy enum and egress topology already landed)

## Smoke Test

Run `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` — all 5 tests should pass, confirming no stale vocabulary remains.

## Test Cases

### 1. No stale blocked_by strings in source

1. Run `grep -rn 'blocked_by=.*isolated' src/scc_cli/application/compute_effective_config.py`
2. Run `grep -rn 'blocked_by=.*unrestricted' src/scc_cli/application/compute_effective_config.py`
3. Run `grep -rn 'blocked_by=.*corp-proxy' src/scc_cli/application/compute_effective_config.py`
4. **Expected:** All three greps return no matches (exit code 1)

### 2. No stale warning strings in commands

1. Run `grep -n 'corp-proxy-only' src/scc_cli/commands/config.py`
2. **Expected:** No matches — the warning now says "web-egress-enforced"

### 3. README does not claim Docker Desktop as hard requirement

1. Run `grep 'Requires.*Docker Desktop' README.md`
2. **Expected:** No matches. The Requires line should mention "Docker (Engine, Desktop, OrbStack, or Colima)"

### 4. README example JSON uses current vocabulary

1. Run `grep '"network_policy"' README.md`
2. **Expected:** The value adjacent to `network_policy` is `"open"`, not `"unrestricted"`

### 5. README enforcement description is accurate

1. Open `README.md` and locate the enforcement scope section
2. **Expected:** Description mentions "topology-based isolation (internal Docker network + proxy sidecar)", "HTTP/HTTPS egress control", "locked-down-web applies --network=none", and "IPv4-only in v1"

### 6. Test fixtures use current vocabulary

1. Run `grep -n 'corp-proxy' tests/test_config_explain.py`
2. **Expected:** No matches — all fixtures use "web-egress-enforced"

### 7. Guardrail tests exist and pass

1. Run `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v`
2. **Expected:** 5 tests pass:
   - `test_no_stale_network_modes_in_blocked_by_strings`
   - `test_no_stale_network_modes_in_user_warnings`
   - `test_readme_no_docker_desktop_hard_requirement`
   - `test_readme_no_stale_network_mode_names`
   - `test_example_json_uses_valid_network_policy_values`

### 8. Full exit gate passes

1. Run `uv run ruff check`
2. Run `uv run mypy src/scc_cli`
3. Run `uv run pytest --rootdir "$PWD" -q`
4. **Expected:** Ruff clean, mypy 0 issues in 249 files, total test count ≥ 3464

## Edge Cases

### Stale vocabulary in comments or docstrings

1. Run `grep -rn 'corp-proxy-only\|"unrestricted"\|network_policy=isolated' src/scc_cli/ tests/`
2. **Expected:** No matches in user-facing code. Comments explaining migration history (if any) are acceptable.

### Example JSON files use valid NetworkPolicy values

1. Run `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py::test_example_json_uses_valid_network_policy_values -v`
2. **Expected:** Pass — all example JSON `network_policy` values are members of the NetworkPolicy enum

## Failure Signals

- Any of the 5 guardrail tests in `test_docs_truthfulness.py` failing
- Grep finding stale vocabulary strings in source, commands, or README
- Full pytest count dropping below 3464
- Ruff or mypy reporting new issues

## Not Proven By This UAT

- Runtime enforcement behavior (proven by S03 and S04 tests)
- Actual Squid proxy ACL compilation correctness (proven by S03 egress_policy tests)
- Provider destination resolution at launch time (proven by S04 tests)
- Documentation accuracy of features not yet implemented (e.g., future IPv6 support)

## Notes for Tester

- The word "isolated" may appear in README prose (e.g., "isolated environment", "topology-based isolation") — this is fine. The guardrail tests only flag it when used as a network_policy value (in JSON, backticks, or adjacent to `network_policy`).
- The guardrail tests import `NetworkPolicy` from `scc_cli.core.enums` to validate example JSON values, so changes to the enum will automatically be caught.
