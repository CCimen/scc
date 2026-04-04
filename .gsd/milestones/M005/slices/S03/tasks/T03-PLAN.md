---
estimated_steps: 30
estimated_files: 4
skills_used: []
---

# T03: Convert compute_effective_config and helpers to NormalizedOrgConfig

Convert the `compute_effective_config()` function and its 4 helper functions (`is_team_delegated_for_plugins`, `is_team_delegated_for_mcp`, `is_project_delegated`, `validate_stdio_server`) from accepting `org_config: dict[str, Any]` to `org_config: NormalizedOrgConfig`. This is the highest-ROI single conversion — it eliminates ~15 raw `.get()` dict navigations with typed field access across the most cross-cutting config function in the codebase.

The 436-line characterization test file provides strong regression protection. Test fixtures that construct raw dicts should use `NormalizedOrgConfig.from_dict()` to minimize churn.

## Steps

1. Read `src/scc_cli/application/compute_effective_config.py` to identify all `org_config.get()` call sites and what fields they read.
2. Read `src/scc_cli/application/personal_profile_policy.py` — it also calls `validate_stdio_server(server_dict, org_config)` with raw dicts. It must be updated in sync or will break.
3. Change `compute_effective_config()` signature: `org_config: dict[str, Any]` → `org_config: NormalizedOrgConfig`.
4. Change `validate_stdio_server()` signature: `org_config: dict[str, Any]` → `org_config: NormalizedOrgConfig`. Update body to use `org_config.security.allow_stdio_mcp`, `org_config.security.allowed_stdio_prefixes` instead of dict access.
5. Change `is_team_delegated_for_plugins()`, `is_team_delegated_for_mcp()`, `is_project_delegated()` signatures similarly. Update body to use typed field access (`org_config.delegation.teams.allow_additional_plugins`, `org_config.profiles.get(team_name)`, etc.).
6. Update body of `compute_effective_config()` to replace all `org_config.get('security', {}).get(...)` patterns with typed field access: `org_config.security.blocked_plugins`, `org_config.defaults.enabled_plugins`, `org_config.profiles`, etc.
7. Update `src/scc_cli/application/personal_profile_policy.py` — it calls `validate_stdio_server(server_dict, org_config)`. Change its `org_config` parameter to `NormalizedOrgConfig` too, or convert at the call site.
8. Update callers that pass `org_config` directly: `src/scc_cli/profiles.py` re-exports must still work.
9. Update test fixtures in `tests/test_compute_effective_config_characterization.py` to use `NormalizedOrgConfig.from_dict({...})` wrapper around raw dict construction.
10. Run full test suite to confirm zero regressions.

**Key constraints:**
- Do NOT change callers outside this module yet (those are T04/T05 scope). If external callers pass raw dicts, they must normalize at the call boundary. For now, update the function signatures and all internal logic, plus the characterization test fixtures.
- `profiles.py` re-exports the functions — make sure the re-exported names still work.
- Do NOT touch SafetyPolicy.rules (D016: stays dict[str, Any]).

## Must-Haves

- [ ] compute_effective_config accepts NormalizedOrgConfig, not dict[str, Any]
- [ ] validate_stdio_server accepts NormalizedOrgConfig
- [ ] is_team_delegated_for_plugins, is_team_delegated_for_mcp, is_project_delegated accept NormalizedOrgConfig
- [ ] All dict .get() patterns in compute_effective_config body replaced with typed field access
- [ ] personal_profile_policy.py updated to pass NormalizedOrgConfig to validate_stdio_server
- [ ] All 436 characterization tests pass
- [ ] profiles.py re-exports still functional

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest tests/test_compute_effective_config_characterization.py -v`
- `uv run pytest --rootdir "$PWD" -q`

## Inputs

- ``src/scc_cli/application/compute_effective_config.py` — function to convert`
- ``src/scc_cli/application/personal_profile_policy.py` — calls validate_stdio_server with org_config`
- ``src/scc_cli/ports/config_models.py` — NormalizedOrgConfig with from_dict (from T02)`
- ``src/scc_cli/adapters/config_normalizer.py` — normalize_org_config (from T02)`
- ``tests/test_compute_effective_config_characterization.py` — 436-line test file to update fixtures`
- ``src/scc_cli/profiles.py` — re-exports module`

## Expected Output

- ``src/scc_cli/application/compute_effective_config.py` — all 5 functions accept NormalizedOrgConfig`
- ``src/scc_cli/application/personal_profile_policy.py` — updated to use NormalizedOrgConfig for validate_stdio_server calls`
- ``tests/test_compute_effective_config_characterization.py` — fixtures use NormalizedOrgConfig.from_dict()`
- ``src/scc_cli/profiles.py` — re-exports verified working`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_compute_effective_config_characterization.py -v && uv run pytest --rootdir "$PWD" -q
