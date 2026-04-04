---
estimated_steps: 20
estimated_files: 4
skills_used: []
---

# T05: Convert safety_policy_loader and remaining secondary dict consumers

Convert `load_safety_policy()` and its callers from raw `dict[str, Any]` to `NormalizedOrgConfig`. Also convert remaining secondary consumers of raw org_config dicts in `personal_profile_policy.py` (the functions not yet converted in T03). Measure final dict[str, Any] reduction to confirm the slice goal is met.

## Steps

1. Convert `load_safety_policy(org_config: dict[str, Any] | None)` in `src/scc_cli/core/safety_policy_loader.py` to accept `NormalizedOrgConfig | None`. Update body to use `org_config.security.safety_net.action` and `org_config.security.safety_net.rules` (the SafetyNetConfig added in T02) instead of `org_config.get('security', {}).get('safety_net', {})`.
2. Update callers of `load_safety_policy`:
   - `src/scc_cli/doctor/checks/safety.py` (line 70) — passes `raw_org` dict. Add `NormalizedOrgConfig.from_dict()` at call site.
   - `src/scc_cli/application/support_bundle.py` (line 296) — passes `raw_org_config`. Normalize at call site.
3. Review `src/scc_cli/application/personal_profile_policy.py` for remaining `org_config: dict[str, Any]` parameters not already converted in T03. Convert function signatures `filter_personal_settings()` and `filter_personal_mcp()` to accept NormalizedOrgConfig. Update their callers.
4. Run `grep -c 'dict\[str, Any\]' src/scc_cli/**/*.py | ...` to measure final count. Target: < 390 (down from 443).
5. Run full verification.

## Must-Haves

- [ ] load_safety_policy accepts NormalizedOrgConfig | None
- [ ] All callers of load_safety_policy updated to normalize at boundary
- [ ] personal_profile_policy functions accept NormalizedOrgConfig where they previously took raw dicts
- [ ] dict[str, Any] count in src/scc_cli/ < 390 (measured and reported)
- [ ] All 4106+ tests pass

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest --rootdir "$PWD" -q`
- `grep -rn 'dict\[str, Any\]' src/scc_cli/ | wc -l` reports < 390

## Inputs

- ``src/scc_cli/core/safety_policy_loader.py` — function to convert`
- ``src/scc_cli/ports/config_models.py` — NormalizedOrgConfig with SafetyNetConfig (from T02)`
- ``src/scc_cli/application/personal_profile_policy.py` — partially converted in T03, finish here`
- ``src/scc_cli/doctor/checks/safety.py` — caller to update`
- ``src/scc_cli/application/support_bundle.py` — caller to update`

## Expected Output

- ``src/scc_cli/core/safety_policy_loader.py` — accepts NormalizedOrgConfig | None`
- ``src/scc_cli/application/personal_profile_policy.py` — all org_config params are NormalizedOrgConfig`
- ``src/scc_cli/doctor/checks/safety.py` — normalizes at call boundary`
- ``src/scc_cli/application/support_bundle.py` — normalizes at call boundary`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q && test $(grep -rn 'dict\[str, Any\]' src/scc_cli/ | wc -l) -lt 390
