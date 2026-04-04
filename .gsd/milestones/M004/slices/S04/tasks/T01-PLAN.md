---
estimated_steps: 51
estimated_files: 6
skills_used: []
---

# T01: Host-side typed policy loader, doctor safety check, and tests

Create `core/safety_policy_loader.py` with `load_safety_policy(org_config: dict[str, Any] | None) -> SafetyPolicy` that extracts safety policy from org config dicts and returns a typed `SafetyPolicy`. Fail-closed: any parse error → default `SafetyPolicy(action="block")`. Create `doctor/checks/safety.py` with `check_safety_policy() -> CheckResult` that probes org config availability and policy validity through `bootstrap.get_default_adapters()`. Register the new check in `doctor/checks/__init__.py` and `doctor/core.py`. Write comprehensive tests and a guardrail preventing core→docker imports.

## Steps

1. Create `src/scc_cli/core/safety_policy_loader.py`:
   - Define `VALID_SAFETY_NET_ACTIONS = frozenset({"block", "warn", "allow"})`
   - Implement `load_safety_policy(org_config: dict[str, Any] | None) -> SafetyPolicy`
   - Extract `security.safety_net` from org config dict
   - Validate `action` field: if missing or not in valid set → `"block"` (fail-closed)
   - Pass remaining keys as `rules` dict
   - Return `SafetyPolicy(action=action, rules=rules, source="org.security.safety_net")`
   - On any exception or if org_config is None → return default `SafetyPolicy(action="block")`
   - Do NOT import from `scc_cli.docker.launch` — duplicate the ~10 lines of validation logic

2. Create `src/scc_cli/doctor/checks/safety.py`:
   - Implement `check_safety_policy() -> CheckResult`
   - Try loading org config via `bootstrap.get_default_adapters()` → `adapters.config_store`
   - If no org config: return WARNING CheckResult ("No org config found, using default block policy")
   - If org config lacks `security.safety_net`: return WARNING ("No safety_net section in org config")
   - If action is invalid: return ERROR with fix hint
   - If valid: return PASS with the effective action
   - Wrap the whole check in try/except → return ERROR on any unexpected failure

3. Register the check in `doctor/checks/__init__.py`:
   - Import `check_safety_policy` from `.safety`
   - Add to `run_all_checks()` after the cache checks section
   - Add to `__all__`

4. Register the check in `doctor/core.py`:
   - Import `check_safety_policy` from `.checks`
   - Call it in `run_doctor()` and append to `result.checks`

5. Create `tests/test_safety_policy_loader.py` with tests:
   - `test_none_org_config_returns_default_block` — None → SafetyPolicy(action="block")
   - `test_empty_dict_returns_default_block` — {} → block
   - `test_missing_security_key_returns_default_block`
   - `test_missing_safety_net_key_returns_default_block`
   - `test_valid_block_action_passthrough`
   - `test_valid_warn_action_passthrough`
   - `test_valid_allow_action_passthrough`
   - `test_invalid_action_falls_back_to_block`
   - `test_rules_extracted_from_policy`
   - `test_non_dict_org_config_returns_default_block` — e.g. string or list input
   - `test_no_import_from_docker_launch` — guardrail: tokenize `safety_policy_loader.py`, assert no NAME token `docker` in import statements

6. Create `tests/test_safety_doctor_check.py` with tests:
   - `test_check_passes_with_valid_org_config` — mock config_store to return org config with valid safety_net
   - `test_check_warns_when_no_org_config` — mock config_store returning None
   - `test_check_warns_when_no_safety_net_section`
   - `test_check_errors_on_malformed_org_config` — mock config_store raising exception

## Must-Haves

- [ ] `load_safety_policy()` returns `SafetyPolicy` (never raw dict, never None)
- [ ] Fail-closed: any parse failure → default block policy
- [ ] No imports from `scc_cli.docker.launch` in `safety_policy_loader.py`
- [ ] Doctor check goes through `bootstrap.get_default_adapters()` per KNOWLEDGE.md rule
- [ ] All tests in `test_safety_policy_loader.py` and `test_safety_doctor_check.py` pass
- [ ] `uv run ruff check` clean
- [ ] `uv run mypy src/scc_cli` clean

## Inputs

- ``src/scc_cli/core/contracts.py` — SafetyPolicy dataclass definition`
- ``src/scc_cli/doctor/types.py` — CheckResult dataclass definition`
- ``src/scc_cli/doctor/checks/__init__.py` — existing check registration pattern`
- ``src/scc_cli/doctor/core.py` — existing run_doctor() wiring pattern`
- ``src/scc_cli/bootstrap.py` — get_default_adapters() for doctor check access`
- ``src/scc_cli/docker/launch.py` — reference for validation logic to duplicate (do NOT import)`

## Expected Output

- ``src/scc_cli/core/safety_policy_loader.py` — typed policy loader module`
- ``src/scc_cli/doctor/checks/safety.py` — doctor safety-policy check`
- ``src/scc_cli/doctor/checks/__init__.py` — updated with safety check registration`
- ``src/scc_cli/doctor/core.py` — updated with safety check call`
- ``tests/test_safety_policy_loader.py` — policy loader tests + import guardrail`
- ``tests/test_safety_doctor_check.py` — doctor safety check tests`

## Verification

uv run pytest tests/test_safety_policy_loader.py tests/test_safety_doctor_check.py -v && uv run ruff check && uv run mypy src/scc_cli && grep -r 'from scc_cli.docker' src/scc_cli/core/safety_policy_loader.py; test $? -eq 1
