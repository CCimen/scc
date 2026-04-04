# S03: Typed config model adoption and strict typing cleanup

**Goal:** Land the governed-artifact/team-pack typed model hierarchy from spec-06 and convert the highest-value dict[str, Any] flows (compute_effective_config, start_session, safety_policy_loader) to use typed NormalizedOrgConfig, measurably reducing raw dict usage across the codebase.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added 6 frozen model types (ArtifactKind, ArtifactInstallIntent, GovernedArtifact, ProviderArtifactBinding, ArtifactBundle, ArtifactRenderPlan) implementing spec-06 governed artifact type hierarchy with 20 passing tests** — Create the governed-artifact type hierarchy specified in spec-06 as frozen dataclasses. These models (GovernedArtifact, ArtifactBundle, ArtifactInstallIntent, ProviderArtifactBinding, ArtifactRenderPlan, ArtifactKind) define the provider-neutral bundle architecture's type surface. They are pure data definitions with no behavioral logic.

## Steps

1. Read `specs/06-governed-artifacts.md` to confirm model names, fields, and relationships.
2. Create `src/scc_cli/core/governed_artifacts.py` with:
   - `ArtifactKind` enum: `skill`, `mcp_server`, `native_integration`, `bundle`
   - `ArtifactInstallIntent` enum: `required`, `available`, `disabled`, `request_only`
   - `GovernedArtifact` frozen dataclass: kind, name, version, publisher, pinned, provenance fields
   - `ProviderArtifactBinding` frozen dataclass: provider name, native_ref, native_config dict, transport_type
   - `ArtifactBundle` frozen dataclass: name, description, artifacts list, install_intent
   - `ArtifactRenderPlan` frozen dataclass: bundle_id, provider, bindings list, skipped list, effective_artifacts
3. Add re-exports in `src/scc_cli/core/contracts.py` so downstream code can import from either location.
4. Create `tests/test_governed_artifact_models.py` with:
   - Construction tests for each model with all fields
   - Frozen immutability assertions
   - Enum membership and value coverage tests
   - Default value tests
5. Run `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest tests/test_governed_artifact_models.py`.

## Must-Haves

- [ ] All 6 model types exist as frozen dataclasses or enums
- [ ] Models use only stdlib types (dataclasses, enum) — no pydantic dependency
- [ ] ProviderArtifactBinding is provider-specific (Claude and Codex are NOT flattened)
- [ ] ArtifactBundle carries install_intent, not raw marketplace URLs
- [ ] Re-exports added to core/contracts.py
- [ ] Unit tests pass

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest tests/test_governed_artifact_models.py -v`
- `uv run pytest --rootdir "$PWD" -q` (all 4106+ tests still pass)
  - Estimate: 45m
  - Files: src/scc_cli/core/governed_artifacts.py, src/scc_cli/core/contracts.py, tests/test_governed_artifact_models.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_governed_artifact_models.py -v && uv run pytest --rootdir "$PWD" -q
- [x] **T02: Added SafetyNetConfig, StatsConfig models and NormalizedOrgConfig.from_dict() helper, closing the known config normalization gap for security.safety_net, stats, and config_source fields** — The current NormalizedOrgConfig silently drops `security.safety_net`, `stats`, and `config_source` fields (documented in KNOWLEDGE.md as a known gap). This task extends the config model and normalizer to cover these fields, and adds a `NormalizedOrgConfig.from_dict()` convenience class method that wraps `normalize_org_config()`. The from_dict helper is critical for T03-T05 because ~50+ test files construct inline `org_config = {...}` dicts — the helper avoids massive test fixture rewrites.

## Steps

1. Read `src/scc_cli/ports/config_models.py` and `src/scc_cli/adapters/config_normalizer.py` to understand existing patterns.
2. Add to `src/scc_cli/ports/config_models.py`:
   - `SafetyNetConfig` frozen dataclass: action (str, default 'block'), rules (dict[str, Any], default empty) — mirrors SafetyPolicy but lives in the config model layer
   - `StatsConfig` frozen dataclass: enabled (bool, default False), endpoint (str | None, default None)
   - Add `safety_net: SafetyNetConfig` field to `SecurityConfig` (default=SafetyNetConfig())
   - Add `stats: StatsConfig` field to `NormalizedOrgConfig` (default=StatsConfig())
   - Add `config_source: str | None` field to `NormalizedOrgConfig` (default=None)
   - Add `@classmethod from_dict(cls, raw: dict[str, Any]) -> NormalizedOrgConfig` that calls `normalize_org_config(raw)`
3. Update `src/scc_cli/adapters/config_normalizer.py`:
   - Add `_normalize_safety_net(raw: dict[str, Any] | None) -> SafetyNetConfig`
   - Add `_normalize_stats(raw: dict[str, Any] | None) -> StatsConfig`
   - Update `_normalize_security()` to include safety_net normalization
   - Update `normalize_org_config()` to pass stats and config_source
4. Extend `tests/test_config_normalization.py` with:
   - Tests for safety_net normalization (with action, with rules, missing, invalid)
   - Tests for stats normalization
   - Tests for config_source passthrough
   - Tests for NormalizedOrgConfig.from_dict() convenience method
5. Run full verification.

## Must-Haves

- [ ] SafetyNetConfig and StatsConfig exist as frozen dataclasses
- [ ] SecurityConfig.safety_net field added with safe default
- [ ] NormalizedOrgConfig.stats and .config_source fields added
- [ ] from_dict() class method works and returns NormalizedOrgConfig
- [ ] Normalizer covers security.safety_net extraction
- [ ] D016 respected: SafetyPolicy.rules stays dict[str, Any] — SafetyNetConfig.rules also uses dict[str, Any]
- [ ] All existing config normalization tests still pass

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest tests/test_config_normalization.py -v`
- `uv run pytest --rootdir "$PWD" -q`
  - Estimate: 1h
  - Files: src/scc_cli/ports/config_models.py, src/scc_cli/adapters/config_normalizer.py, tests/test_config_normalization.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_config_normalization.py -v && uv run pytest --rootdir "$PWD" -q
- [x] **T03: Converted compute_effective_config and 4 helpers from dict[str,Any] to NormalizedOrgConfig with backward-compatible union signatures, eliminating ~15 raw .get() navigations** — Convert the `compute_effective_config()` function and its 4 helper functions (`is_team_delegated_for_plugins`, `is_team_delegated_for_mcp`, `is_project_delegated`, `validate_stdio_server`) from accepting `org_config: dict[str, Any]` to `org_config: NormalizedOrgConfig`. This is the highest-ROI single conversion — it eliminates ~15 raw `.get()` dict navigations with typed field access across the most cross-cutting config function in the codebase.

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
  - Estimate: 2h
  - Files: src/scc_cli/application/compute_effective_config.py, src/scc_cli/application/personal_profile_policy.py, src/scc_cli/profiles.py, tests/test_compute_effective_config_characterization.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_compute_effective_config_characterization.py -v && uv run pytest --rootdir "$PWD" -q
- [ ] **T04: Convert StartSessionRequest, launch pipeline callers, and eliminate UserConfig alias** — Push the typed NormalizedOrgConfig boundary outward through the launch pipeline. Convert `StartSessionRequest.org_config` from `dict[str, Any] | None` to `NormalizedOrgConfig | None`. Eliminate the `UserConfig: TypeAlias = dict[str, Any]` alias. Update all callers that construct StartSessionRequest or call compute_effective_config with raw dicts to normalize at the call boundary.

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
  - Estimate: 1h30m
  - Files: src/scc_cli/application/start_session.py, src/scc_cli/commands/launch/flow_interactive.py, src/scc_cli/commands/launch/flow_session.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_types.py, src/scc_cli/commands/launch/render.py, src/scc_cli/commands/launch/sandbox.py, src/scc_cli/commands/launch/team_settings.py, src/scc_cli/commands/config.py, src/scc_cli/commands/config_validate.py, src/scc_cli/commands/exceptions.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
- [ ] **T05: Convert safety_policy_loader and remaining secondary dict consumers** — Convert `load_safety_policy()` and its callers from raw `dict[str, Any]` to `NormalizedOrgConfig`. Also convert remaining secondary consumers of raw org_config dicts in `personal_profile_policy.py` (the functions not yet converted in T03). Measure final dict[str, Any] reduction to confirm the slice goal is met.

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
  - Estimate: 1h
  - Files: src/scc_cli/core/safety_policy_loader.py, src/scc_cli/application/personal_profile_policy.py, src/scc_cli/doctor/checks/safety.py, src/scc_cli/application/support_bundle.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q && test $(grep -rn 'dict\[str, Any\]' src/scc_cli/ | wc -l) -lt 390
