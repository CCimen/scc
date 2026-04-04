# S03 Research: Typed Config Model Adoption and Strict Typing Cleanup

## Summary

S03 must land the governed-artifact/team-pack typed model hierarchy specified in specs 02, 03, and 06, and begin converting the largest `dict[str, Any]` flows in the config/launch/marketplace pipeline to use these typed models. Per D017, this is **not** generic strict-typing cleanup — the organizing principle is the provider-neutral bundle architecture.

**Depth: Targeted research.** The technology is known (Python dataclasses, existing normalizer pattern), but the governed-artifact models are entirely new to the codebase, and the `dict[str, Any]` flow touches ~32 call sites accepting raw `org_config` dicts. The scope needs careful task decomposition.

## Requirement Ownership

- **R001 (primary):** S03 must advance maintainability by replacing raw dicts in control-plane logic with typed models. D017 narrows the requirement: the typed models must follow the governed-artifact/team-pack architecture.

## Recommendation

Decompose into 5-6 tasks:

1. **Define governed-artifact core models** in `core/contracts.py` (or a new `core/governed_artifacts.py`): `GovernedArtifact`, `ArtifactBundle`, `ArtifactInstallIntent`, `ProviderArtifactBinding`, `ArtifactRenderPlan`. These are specified in spec-06 and referenced in spec-02 but **do not exist anywhere in the codebase today**. No behavioral changes — pure type definitions.

2. **Convert `compute_effective_config` from raw `org_config: dict[str, Any]` to `NormalizedOrgConfig`**. This is the single highest-value conversion: 32 call sites pass raw org-config dicts into security, delegation, MCP filtering, and effective-config computation logic. `NormalizedOrgConfig` already exists in `ports/config_models.py` and has a normalizer in `adapters/config_normalizer.py`, but it is used **only** by the `LocalConfigStore` port adapter — the compute pipeline and all its callers still bypass it and pass raw dicts. The normalizer boundary already exists; this task pushes it inward.

3. **Convert `UserConfig` alias and launch-flow config flow from raw dicts to `NormalizedUserConfig`**. The `UserConfig: TypeAlias = dict[str, Any]` in `flow_types.py` is used by `flow_interactive.py`, `flow_session.py`, and `team_settings.py`. The normalizer already exists.

4. **Type-tighten `InteractionRequest` union to preserve payload types through the wizard cast chain**. The wizard uses 23 `cast()` calls to recover prompt/view_model types. The `InteractionRequest` union collapses to `SelectRequest[object]`, losing type information. The fix is a discriminated request dispatcher pattern, not more casts.

5. **Add characterization tests for the config normalizer/compute pipeline** before and alongside the refactoring, to protect existing behavior during migration.

6. **Convert remaining `dict[str, Any]` in `personal_profiles_merge.py` and `docker/launch.py`** for safety policy, marketplace settings, and profile merge flows.

## Implementation Landscape

### What Exists

| Component | Location | Purpose | Lines |
|---|---|---|---|
| `NormalizedOrgConfig` + siblings | `ports/config_models.py` | Typed org/user/team/project config | 183 |
| Config normalizer | `adapters/config_normalizer.py` | Raw dict → typed model conversion | 225 |
| `LocalConfigStore` | `adapters/local_config_store.py` | Port impl using normalizer (only consumer today) | 42 |
| `ConfigStore` protocol | `ports/config_store.py` | Abstract config loading interface | 55 |
| `marketplace/schema.py` | `marketplace/schema.py` | Pydantic models for org config validation | 498 |
| `core/contracts.py` | `core/contracts.py` | Typed launch/runtime/network/safety contracts | ~200 |
| `EffectiveConfig` | `application/compute_effective_config.py` | Output of 3-layer merge — already typed | 775 |
| `OrganizationConfig` (pydantic) | `marketplace/schema.py` | Full Pydantic org config with validation | ~140 |

### What Does NOT Exist

| Component | Required By | Notes |
|---|---|---|
| `GovernedArtifact` | spec-02, spec-06 | Approved reusable unit in SCC policy |
| `ArtifactBundle` | spec-06 | Named grouping of artifacts — team-facing unit |
| `ArtifactInstallIntent` | spec-06 | `required` / `available` / `disabled` / `request-only` |
| `ProviderArtifactBinding` | spec-06 | Provider-native rendering details |
| `ArtifactRenderPlan` | spec-06 | Per-session/per-provider materialization plan |

### The `dict[str, Any]` Flow Problem

373 total `dict[str, Any]` references in `src/scc_cli/`. Domain breakdown:

| Domain | Count | Notes |
|---|---|---|
| commands/ | 66 | Mostly `org_config: dict[str, Any]` passthrough |
| application/ | 47 | `start_session`, `compute_effective_config`, `profiles`, `personal_profile_policy` |
| core/ | 39 | `personal_profiles`, `safety_policy_loader`, `contracts.SafetyPolicy.rules` |
| marketplace/ | 36 | `render.py`, `normalize.py`, `trust.py` — heavily Claude-shaped |
| adapters/ | 40 | Normalizer + config store (already typed at boundary) |
| docker/ | 17 | `launch.py`, `sandbox.py` — safety policy + settings passthrough |
| ui/ | 10 | `wizard.py`, `picker.py` — `available_teams: list[dict[str, Any]]` |
| ports/ | 15 | Protocol definitions |

**Highest-value conversions for S03:**

1. `compute_effective_config(org_config: dict[str, Any], ...)` — called from 4+ sites, does all the policy merging
2. `StartSessionRequest.org_config: dict[str, Any]` — the launch pipeline's main config carrier
3. `UserConfig: TypeAlias = dict[str, Any]` — the launch wizard's user config type
4. `personal_profile_policy.*` functions — 4 parameters accepting raw org dicts
5. `safety_policy_loader.load_safety_policy(org_config: dict[str, Any])` — raw dict navigation for `security.safety_net`

### Two Normalization Systems

The codebase has **two separate org config normalization systems** that are not connected:

1. **`adapters/config_normalizer.py`** → produces `NormalizedOrgConfig` (frozen dataclasses in `ports/config_models.py`). Used only by `LocalConfigStore`. No pydantic dependency.

2. **`marketplace/schema.py`** → produces `OrganizationConfig` (pydantic models). Used by `sync_marketplace.py` and the marketplace compute/trust pipeline. Rich validation with field patterns, discriminated unions, and validators.

These cover overlapping but different fields. `NormalizedOrgConfig` has security, defaults, delegation, profiles, marketplaces. `OrganizationConfig` (pydantic) has all of those plus schema_version, min_cli_version, stats, safety_net, config_source, trust. Neither contains governed artifact models.

**S03 should not merge these two systems.** The normalizer produces lightweight frozen dataclasses suitable for the application layer; the pydantic models serve validation at the parsing edge. S03 should extend `ports/config_models.py` with governed artifact types and make the application-layer config flow use the frozen dataclass family.

### The Cast-Heavy Wizard Problem

`ui/wizard.py` has 12 `cast()` calls and `commands/launch/flow_interactive.py` has 11. These recover typed request/view_model payloads from the `InteractionRequest = ConfirmRequest | SelectRequest[object] | InputRequest` union. The root cause: `SelectRequest[object]` erases the generic parameter.

**Fix:** A tagged request dispatcher or per-step typed prompt models would eliminate casts. However, this is a significant refactor touching the wizard state machine, every prompt builder, and every test that mocks wizard answers. It should be task-scoped carefully.

### Boundary Between S03 and S04

D017 says S03 lands **models and typed config flow**. S04 **hardens failure handling** for the renderer pipeline. The boundary:
- S03 defines the types, converts the config compute pipeline to use them, and adds tests.
- S04 adds error handling, retry, and fail-closed behavior to the fetch/render/merge/install paths that will consume these types.
- S03 should NOT refactor the marketplace renderer — that's S04/S06 territory.

### Key Constraints

1. **KNOWLEDGE.md note:** "`NormalizedOrgConfig` strips unrecognized keys including `security.safety_net`. Code that needs raw org config fields not modeled in the normalized type must use the raw dict." — S03 must either extend `NormalizedOrgConfig` to cover safety_net or explicitly keep raw dict paths for fields not yet modeled.

2. **`SafetyPolicy.rules: dict[str, Any]`** — D016 explicitly decided to keep this as `dict[str, Any]` in M004. S03 should not change it.

3. **No dual team configs** — D017 requires bundle IDs, not raw marketplace URLs, in team config. The models should carry `enabled_bundles` not `enabled_plugins`.

4. **Asymmetric provider surfaces** — `ProviderArtifactBinding` must NOT flatten Claude and Codex into one plugin contract. Each binding variant should be provider-specific.

5. **The marketplace pipeline stays Claude-shaped for now.** S03 introduces the types; the actual provider-neutral renderer migration is a larger effort for future work or S06.

## Natural Task Seams

### Task 1: Governed Artifact Core Models (~150 lines)
- **Files:** `core/governed_artifacts.py` (new), `core/contracts.py` (re-export only)
- **Delivers:** `GovernedArtifact`, `ArtifactBundle`, `ArtifactInstallIntent`, `ProviderArtifactBinding`, `ArtifactRenderPlan`, `ArtifactKind`
- **Tests:** Unit tests for construction, serialization, and enum coverage
- **Risk:** Low — pure type definitions with no behavioral change
- **Verifies:** `uv run mypy src/scc_cli`, `uv run pytest`

### Task 2: Extend NormalizedOrgConfig + Normalizer for Missing Fields (~200 lines changed)
- **Files:** `ports/config_models.py`, `adapters/config_normalizer.py`
- **Delivers:** `SafetyNetConfig`, `StatsConfig`, `FederationConfig` fields on `NormalizedOrgConfig`, updated normalizer
- **Why:** Current normalizer silently drops `security.safety_net`, `stats`, and `config_source`. Adding these removes the KNOWLEDGE.md escape hatch for raw dict access.
- **Risk:** Medium — must not break existing `NormalizedOrgConfig` consumers
- **Tests:** Extend `tests/test_config_normalization.py`

### Task 3: Convert compute_effective_config to NormalizedOrgConfig (~400 lines changed)
- **Files:** `application/compute_effective_config.py`, callers (5-8 files)
- **Delivers:** `compute_effective_config(org_config: NormalizedOrgConfig, ...)` signature, updated callers
- **Why:** This is the highest-ROI single conversion — eliminates ~15 `org_config.get()` dict navigations with typed field access
- **Risk:** High — touches the most cross-cutting config flow. Characterization tests exist (436 lines in `test_compute_effective_config_characterization.py`) but callers need coordinated updates.
- **Prerequisite:** Task 2 (normalizer covers all fields compute_effective_config reads)
- **Tests:** All existing characterization tests must pass unchanged

### Task 4: Convert launch pipeline org_config carriers (~200 lines changed)
- **Files:** `application/start_session.py`, `commands/launch/flow.py`, `commands/launch/flow_session.py`, `commands/launch/render.py`, `flow_types.py`
- **Delivers:** `StartSessionRequest.org_config: NormalizedOrgConfig | None`, `UserConfig` alias eliminated
- **Why:** The launch pipeline is the main consumer of raw org dicts after compute_effective_config
- **Risk:** Medium — tests for launch flow exist but mock at different levels
- **Prerequisite:** Task 3

### Task 5: Convert personal_profiles and safety_policy_loader (~150 lines changed)
- **Files:** `core/personal_profiles_merge.py`, `core/personal_profiles.py`, `core/safety_policy_loader.py`, `application/personal_profile_policy.py`
- **Delivers:** Functions accept typed models instead of raw dicts for org_config, settings, and MCP
- **Why:** These are secondary dict consumers that feed into the launch pipeline
- **Risk:** Medium — profile merge logic is complex and poorly covered

### Task 6 (stretch): Type-safe wizard prompt dispatch
- **Files:** `ui/wizard.py`, `application/interaction_requests.py`, `application/launch/start_wizard.py`
- **Delivers:** Discriminated prompt types replacing `cast()` recovery pattern
- **Why:** Eliminates 23 casts, but this is a significant refactor
- **Risk:** High — touches the wizard state machine and all wizard tests
- **Note:** May be deferred if budget is tight; the cast pattern works, it's just type-unsafe

## What To Build First

**Task 1 (models) → Task 2 (extend normalizer) → Task 3 (compute pipeline) → Task 4 (launch pipeline) → Task 5 (secondary consumers).** Task 6 is stretch.

Task 1 is safe and unblocks nothing else (the models exist independently). Tasks 2-5 form a dependency chain. Task 3 is the riskiest because it touches the most-consumed function. Existing characterization tests (436 lines) provide good regression protection for Task 3.

## Verification

### Always-on gate (every task)
```bash
uv run ruff check
uv run mypy src/scc_cli
uv run pyright src/scc_cli
uv run pytest --cov --cov-branch
```

### Task-specific checks
- Task 1: `uv run pytest tests/test_governed_artifact_models.py` (new)
- Task 2: `uv run pytest tests/test_config_normalization.py`
- Task 3: `uv run pytest tests/test_compute_effective_config_characterization.py`
- Task 4: `uv run pytest tests/test_application_start_session.py`
- Task 5: `uv run pytest tests/test_personal_profiles*.py`

### Slice-level success criteria
- All governed artifact models from spec-06 exist as frozen dataclasses
- `compute_effective_config` accepts `NormalizedOrgConfig` not `dict[str, Any]`
- `StartSessionRequest.org_config` is typed, not raw dict
- `UserConfig: TypeAlias = dict[str, Any]` is eliminated
- Total `dict[str, Any]` count in `src/scc_cli/` decreases measurably (target: reduce from 373 to <320)
- No new `# type: ignore` or `cast()` calls added (net reduction expected)
- All 4106 existing tests pass
- `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pyright src/scc_cli` all clean

## Pitfalls

1. **Double normalization risk.** Many call sites call `config.load_user_config()` (returns raw dict) and pass it deep into the stack. Converting mid-stack means some callers normalize, then pass to functions that re-normalize. The conversion must be pushed to the outermost call site, not sprinkled through the chain.

2. **KNOWLEDGE.md safety_net gap.** The normalizer currently strips `security.safety_net`. If Task 2 doesn't add it, Task 3 will fail because `load_safety_policy()` reads `org_config.get("security", {}).get("safety_net", {})`. Task 2 must add this field before Task 3 can proceed.

3. **The marketplace Pydantic vs dataclass boundary.** `sync_marketplace.py` uses `OrganizationConfig` (pydantic). `compute_effective_config` would use `NormalizedOrgConfig` (dataclass). These represent the same data differently. S03 must not try to unify them — the marketplace pipeline owns its own pydantic-validated edge.

4. **Test fixtures pass raw dicts.** ~50+ test files construct `org_config = {"security": {...}, "profiles": {...}}` inline. Converting `compute_effective_config` to typed input means either (a) updating all test fixtures to construct `NormalizedOrgConfig`, or (b) providing a convenience `NormalizedOrgConfig.from_dict()` helper that wraps the normalizer. Option (b) is preferred to avoid massive test churn.

5. **Circular import potential.** `core/contracts.py` already imports from `core/enums.py`. Adding governed artifact models that reference each other must stay within `core/` to avoid circular dependency with `ports/` or `application/`.

## Skill Discovery

No external skills needed. This is internal Python dataclass/typing work using established patterns already in the codebase (frozen dataclasses, config normalizer, protocol-based ports). The relevant existing skills are already applied:
- `karpathy-guidelines` — surgical changes, verify before and after
- `writing-clearly-and-concisely` — for docstrings on new models

## Sources

- `specs/02-control-plane-and-types.md` — required model list
- `specs/03-provider-boundary.md` — provider boundary rules
- `specs/06-governed-artifacts.md` — full governed artifact specification with example YAML
- D017 — scoping override: S03 must land governed artifact models, not generic typing cleanup
- D016 — `SafetyPolicy.rules` stays `dict[str, Any]`
- KNOWLEDGE.md — `NormalizedOrgConfig` strips safety_net (must be fixed)
