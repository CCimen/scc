---
estimated_steps: 32
estimated_files: 11
skills_used: []
---

# T04: Convert StartSessionRequest, launch pipeline callers, and eliminate UserConfig alias

Push the typed NormalizedOrgConfig boundary outward through the launch pipeline. Convert `StartSessionRequest.org_config` from `dict[str, Any] | None` to `NormalizedOrgConfig | None`. Eliminate the `UserConfig: TypeAlias = dict[str, Any]` alias. Update all callers that construct StartSessionRequest or call compute_effective_config with raw dicts to normalize at the call boundary.

## Steps

1. Change `StartSessionRequest.org_config` type in `src/scc_cli/application/start_session.py` from `dict[str, Any] | None` to `NormalizedOrgConfig | None`. Update import.
2. Update `_compute_effective_config(request)` in the same file — it currently passes `request.org_config` to `compute_effective_config()`. Since both are now typed, this should just work.
3. Find all callers that construct `StartSessionRequest(org_config=raw_dict, ...)` and add `NormalizedOrgConfig.from_dict()` at the call site:
   - `src/scc_cli/commands/launch/flow_interactive.py`
   - `src/scc_cli/commands/launch/flow_session.py`
   - `src/scc_cli/commands/launch/flow.py`
   - Test files that construct StartSessionRequest
4. Update callers of `compute_effective_config()` that still pass raw dicts:
   - `src/scc_cli/commands/config.py` (line 313)
   - `src/scc_cli/commands/config_validate.py` (line 84)
   - `src/scc_cli/commands/launch/render.py` (line 87)
   - `src/scc_cli/commands/launch/sandbox.py` (line 67)
   - `src/scc_cli/commands/exceptions.py` (line 511)
   Each of these gets `org_config` as a raw dict from somewhere upstream. Add `NormalizedOrgConfig.from_dict(org_config)` at the call boundary.
5. Eliminate `UserConfig: TypeAlias = dict[str, Any]` from `src/scc_cli/commands/launch/flow_types.py`. Replace all `UserConfig` references (flow_session.py, flow_interactive.py, team_settings.py) with `dict[str, Any]` directly or, where the value is already a NormalizedUserConfig, use that type.
6. Run full verification.

**Key constraints:**
- Push normalization to the outermost call site. Do NOT normalize mid-stack (double normalization risk from research pitfalls).
- The `UserConfig` alias is used in 3 files. Check each usage to determine if the value is truly a raw dict (from JSON load) or already a normalized config.

## Must-Haves

- [ ] StartSessionRequest.org_config is NormalizedOrgConfig | None
- [ ] UserConfig alias eliminated from flow_types.py
- [ ] All compute_effective_config callers pass NormalizedOrgConfig
- [ ] No double normalization — normalize at outermost call site only
- [ ] All existing tests pass

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest tests/test_application_start_session.py -v` (if it exists)
- `uv run pytest --rootdir "$PWD" -q`

## Inputs

- ``src/scc_cli/application/start_session.py` — StartSessionRequest to convert`
- ``src/scc_cli/application/compute_effective_config.py` — now accepts NormalizedOrgConfig (from T03)`
- ``src/scc_cli/ports/config_models.py` — NormalizedOrgConfig with from_dict (from T02)`
- ``src/scc_cli/commands/launch/flow_types.py` — UserConfig alias to eliminate`
- ``src/scc_cli/commands/launch/flow_interactive.py` — caller to update`
- ``src/scc_cli/commands/launch/flow_session.py` — caller to update`
- ``src/scc_cli/commands/launch/render.py` — caller to update`
- ``src/scc_cli/commands/launch/sandbox.py` — caller to update`
- ``src/scc_cli/commands/config.py` — caller to update`
- ``src/scc_cli/commands/config_validate.py` — caller to update`
- ``src/scc_cli/commands/exceptions.py` — caller to update`

## Expected Output

- ``src/scc_cli/application/start_session.py` — org_config typed as NormalizedOrgConfig | None`
- ``src/scc_cli/commands/launch/flow_types.py` — UserConfig alias removed`
- ``src/scc_cli/commands/launch/flow_interactive.py` — uses NormalizedOrgConfig`
- ``src/scc_cli/commands/launch/flow_session.py` — uses NormalizedOrgConfig`
- ``src/scc_cli/commands/launch/render.py` — normalizes at call boundary`
- ``src/scc_cli/commands/launch/sandbox.py` — normalizes at call boundary`
- ``src/scc_cli/commands/config.py` — normalizes at call boundary`
- ``src/scc_cli/commands/config_validate.py` — normalizes at call boundary`
- ``src/scc_cli/commands/exceptions.py` — normalizes at call boundary`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
