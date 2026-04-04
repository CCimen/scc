# S01 Research: Maintainability Baseline And Refactor Queue

## Summary

S01 is a pure analysis and characterization-test slice. It produces four deliverables: a ranked hotspot inventory (T01), a boundary-repair map (T02), a robustness-debt catalog (T03), and characterization tests for top split targets (T04). No production code is restructured — only inventories and test protection are added. The codebase is well understood; all findings below are direct code measurements.

## Requirement Coverage

R001 (maintainability — validated) is the only active/validated requirement. S01 directly advances R001 by establishing the quantitative baseline that all later M005 slices depend on.

## Recommendation

**Light-to-targeted research.** The work is measurement and test-writing against known code. No new technology, no ambiguous requirements. The key risk is T04 (characterization tests) touching poorly-covered orchestration monoliths that are hard to test without heavy mocking.

---

## Implementation Landscape

### T01 — Hotspot Inventory (ranked file-size + mandatory-split set)

**Current file-size census (confirmed live):**

| Threshold | Count |
|-----------|-------|
| > 300 lines | 64 |
| > 700 lines | 22 |
| > 800 lines | 15 |
| > 1000 lines | 8 |
| > 1100 lines | 3 |

**Mandatory-split set (> 800 lines):**

| Rank | File | Lines | Domain | Layer-mixing? |
|------|------|-------|--------|---------------|
| 1 | `ui/dashboard/orchestrator.py` | 1489 | UI | Yes — subprocess, docker, git, presentation |
| 2 | `commands/launch/flow.py` | 1447 | Commands | Yes — wizard state, interaction, launch orchestration |
| 3 | `setup.py` | 1336 | Commands | Yes — setup wizard, config, git, profiles |
| 4 | `application/dashboard.py` | 1084 | Application | Yes — docker.core.ContainerInfo direct import |
| 5 | `ui/settings.py` | 1081 | UI | Moderate — large single render method |
| 6 | `application/worktree/use_cases.py` | 1044 | Application | Moderate — large switch_worktree (174 lines) |
| 7 | `commands/team.py` | 1036 | Commands | Moderate — multiple team sub-commands |
| 8 | `commands/config.py` | 1029 | Commands | Moderate — multiple config sub-commands |
| 9 | `ui/dashboard/_dashboard.py` | 966 | UI | Yes — _handle_action is 355 lines |
| 10 | `ui/wizard.py` | 931 | UI | Moderate — heavy cast usage |
| 11 | `application/launch/start_wizard.py` | 914 | Application | Moderate |
| 12 | `ui/git_interactive.py` | 884 | UI | Yes — 20+ raw subprocess.run calls |
| 13 | `docker/launch.py` | 874 | Docker | Yes — console import inverts presentation direction |
| 14 | `marketplace/materialize.py` | 866 | Marketplace | Moderate — Claude-specific concepts |
| 15 | `core/personal_profiles.py` | 839 | Core | Yes — marketplace import leaks into core |

**Hard-fail set (> 1100, must not survive M005):** ranks 1-3.

**Warning-zone additions below 800 that mix layers (include in refactor queue):**
- `ui/picker.py` (786) — large single-select picker
- `ui/keys.py` (784) — key handling
- `application/compute_effective_config.py` (775) — 401-line compute function
- `docker/credentials.py` (726) — 20+ raw subprocess calls, 5 except-Exception sites
- `commands/profile.py` (715) — profile commands
- `application/settings/use_cases.py` (715) — settings actions

**Top-10 largest functions:**

| Lines | Location | Function |
|-------|----------|----------|
| 534 | `commands/launch/flow.py` | `interactive_start` |
| 401 | `application/compute_effective_config.py` | `compute_effective_config` |
| 355 | `ui/dashboard/_dashboard.py` | `_handle_action` |
| 309 | `commands/org/update_cmd.py` | `org_update_cmd` |
| 308 | `commands/reset.py` | `reset_cmd` |
| 293 | `commands/launch/flow.py` | `start` |
| 259 | `setup.py` | `run_setup_wizard` |
| 232 | `ui/dashboard/orchestrator.py` | `run_dashboard` |
| 219 | `ui/settings.py` | `_render` |
| 216 | `docker/launch.py` | `run_sandbox` |

### T02 — Boundary-Repair Map

**Docker imports from outside adapter/runtime seams:**

| Source | Import | Violation |
|--------|--------|-----------|
| `application/dashboard.py:12` | `from scc_cli.docker.core import ContainerInfo` | Application → Docker (type import, not behind port) |
| `application/dashboard.py:661,822` | lazy `from scc_cli.docker import core as docker_core` | Application → Docker (runtime calls) |
| `ui/formatters.py:8` | docstring `from scc_cli.docker.core import ContainerInfo` | Minor (docstring only) |

**Core-to-marketplace leakage:**

| Source | Import | Violation |
|--------|--------|-----------|
| `core/personal_profiles.py:19` | `from scc_cli.marketplace.managed import load_managed_state` | Core → Marketplace (dependency inversion violation) |

**Presentation-to-runtime coupling:**

| Source | Import | Violation |
|--------|--------|-----------|
| `docker/launch.py:18` | `from ..console import err_line` | Docker/runtime → Presentation (console inverts direction) |

**Docker.core ↔ docker.launch cycle:**
- `docker/core.py:331`: lazy `from .launch import run` inside `start_container()` — avoided at import time but creates a runtime cycle
- `docker/launch.py:21-24`: imports `build_command`, `validate_container_filename` from `.core`

**Claude-specific shapes in marketplace pipeline:**
- `marketplace/render.py` reads/writes `.claude/settings.local.json` and `.claude/<managed-state-file>`
- `marketplace/materialize.py` validates `.claude-plugin/marketplace.json`, references "claude-plugins-official"
- `marketplace/normalize.py` defaults to `claude-plugins-official` marketplace
- `marketplace/constants.py` hardcodes `claude-plugins-official` as implicit marketplace
- `application/sync_marketplace.py` imports 7 marketplace modules directly, uses Claude-specific paths
- No Codex-native adapter/renderer exists yet

**Commands → Docker direct imports:** None found (clean).

**UI → Docker direct imports:** None beyond the docstring reference in formatters.

### T03 — Robustness-Debt Catalog

**Silent `except Exception:` sites — 87 total across 36 files:**

| File | Count | Severity |
|------|-------|----------|
| `ui/dashboard/orchestrator.py` | 11 | HIGH — silently catches across subprocess, docker, git ops |
| `application/support_bundle.py` | 8 | MEDIUM — data-gathering context |
| `application/dashboard.py` | 8 | HIGH — masks runtime failures |
| `maintenance/cache_cleanup.py` | 5 | LOW — cleanup context |
| `docker/credentials.py` | 5 | HIGH — credential ops should not silently fail |
| `application/settings/use_cases.py` | 4 | MEDIUM |
| `maintenance/repair_sessions.py` | 3 | LOW |
| `maintenance/migrations.py` | 3 | LOW |
| `doctor/checks/cache.py` | 3 | LOW — diagnostic context |
| `application/worktree/use_cases.py` | 3 | MEDIUM |
| All others (26 files) | 1-2 each | Varies |

**Unchecked subprocess usage:**
- 71 total `subprocess.run` calls across the codebase
- Only 1 uses `check=True`
- Heaviest concentrations: `ui/git_interactive.py` (20+ calls), `docker/credentials.py` (19 calls), `ui/dashboard/orchestrator.py` (5 calls)
- Many calls do not check return codes, capture stderr, or set timeouts

**Mutable module-level defaults (security-relevant):**

| File | Variable | Type | Risk |
|------|----------|------|------|
| `docker/launch.py:37` | `DEFAULT_SAFETY_NET_POLICY` | `dict[str, Any]` | HIGH — safety policy is a mutable global dict |
| `config.py:46` | `USER_CONFIG_DEFAULTS` | dict | MEDIUM — shared defaults |
| `core/destination_registry.py:17` | `PROVIDER_DESTINATION_SETS` | dict | LOW — read-only in practice |
| `core/git_safety_rules.py:153` | `BLOCK_MESSAGES` | dict | LOW |
| `core/git_safety_rules.py:207` | `_RULE_NAMES` | dict | LOW |
| `core/network_policy.py:9` | `_NETWORK_POLICY_ORDER` | dict | LOW |
| `deps.py:37` | `DETECTION_ORDER` | list | LOW |
| `deps.py:81` | `INSTALL_COMMANDS` | dict | LOW |

**Typing debt:**
- 371 `dict[str, Any]` references in `src/scc_cli`
- 46 `cast()` calls, concentrated in `commands/launch/flow.py` (14 casts, mostly `cast(str, answer.value)` / `cast(bool, answer.value)`)
- `commands/launch/flow_types.py:18` defines `UserConfig: TypeAlias = dict[str, Any]`
- `application/interaction_requests.py:139` collapses to `SelectRequest[object]` losing type info

**Existing quality xfails:**

| Test file | xfail reason | What it masks |
|-----------|-------------|---------------|
| `test_file_sizes.py:157` | "commands/launch/app.py exceeds limit" | File-size guardrail is not enforced |
| `test_function_sizes.py:170` | "Known large functions exceed guardrail" | Function-size guardrail is not enforced |
| `test_ui_integration.py:441` | "Test isolation issue" | Dashboard test fails in full suite |
| `test_ui_integration.py:462` | "Test isolation issue" | Start test fails in full suite |

### T04 — Characterization-Test Needs

**Existing test coverage for top split targets:**

| File | Lines | Existing tests | Test count | Coverage gap |
|------|-------|----------------|------------|-------------|
| `commands/launch/flow.py` | 1447 | `test_launch_flow_hotspots.py` | 5 | SEVERE — only guardrail tests, no behavioral coverage |
| `ui/dashboard/orchestrator.py` | 1489 | `test_application_dashboard.py` | 9 | SEVERE — 6% coverage per context doc |
| `application/dashboard.py` | 1084 | `test_application_dashboard.py` | 9 (shared) | Moderate |
| `docker/launch.py` | 874 | `test_docker.py`, `test_docker_core.py` | 13+91 | Moderate — 54% per context doc |
| `ui/wizard.py` | 931 | `test_ui_wizard.py` | 59 | Reasonable |
| `marketplace/materialize.py` | 866 | `test_marketplace_materialize.py` | 34 | Reasonable |
| `core/personal_profiles.py` | 839 | `test_personal_profiles.py` | 7 | NEEDS MORE |
| `application/compute_effective_config.py` | 775 | `test_effective_config.py` | 28 | Moderate |

**Priority characterization-test targets for T04 (must add before S02 surgery):**
1. `commands/launch/flow.py` — `interactive_start` (534 lines) and `start` (293 lines) need behavioral characterization. Current tests are only AST-level guardrails.
2. `ui/dashboard/orchestrator.py` — `run_dashboard` (232 lines) and dashboard action handlers. Only 6% coverage. Heavily mocked interactions needed.
3. `docker/launch.py` — `run_sandbox` (216 lines). 54% coverage. Needs failure-branch and safety-policy injection tests.
4. `core/personal_profiles.py` — only 7 tests for 839-line module. Needs profile CRUD and marketplace-state interaction characterization.

**Existing test infrastructure:**
- `tests/conftest.py` provides `temp_dir`, `temp_git_repo`, and `build_fake_adapters`
- `tests/fakes/` has fake adapters for agent_provider, safety_engine, sandbox_runtime, agent_runner, safety_adapter, runtime_probe
- `tests/contracts/` has contract tests for remote_fetcher, filesystem, git_client, clock, agent_runner, sandbox_runtime
- Architecture invariant tests exist in `test_architecture_invariants.py` (forbids UI/command imports and direct IO in application layer)

---

## Natural Seams For Task Decomposition

T01-T03 are pure analysis tasks that produce markdown artifacts — they can be parallelized. T04 (characterization tests) depends on T01's identification of which files are mandatory split targets and should run last.

**T01** — Run the file-size census script, produce a ranked inventory file, tag each file's domain cluster and layer-mixing status. Output: a `.gsd/milestones/M005/slices/S01/HOTSPOT-INVENTORY.md`.

**T02** — Grep-based analysis of import violations, produce the boundary-repair map. Output: a boundary-repair section in the research or a standalone artifact.

**T03** — Catalog `except Exception`, unchecked subprocess, mutable globals, xfails. Output: a robustness-debt section.

**T04** — Write characterization tests for the top-4 split targets before S02 surgery. This is the only task that writes `.py` files to `tests/`. Priority targets: `commands/launch/flow.py`, `ui/dashboard/orchestrator.py`, `docker/launch.py`, `core/personal_profiles.py`. Must verify with `uv run pytest` and `uv run mypy src/scc_cli`.

## Risks And Watchouts

1. **T04 mocking depth**: The orchestrator and launch flow are deeply coupled to docker, git, marketplace, and interactive UI. Characterization tests will need heavy patching. Use the existing `tests/fakes/` infrastructure where possible.
2. **xfail promotion timing**: The xfails should NOT be removed in S01 — only cataloged. Removal belongs in S06.
3. **Scope creep**: S01 must not start refactoring. It only measures and protects. Any fix temptation should be noted as a finding for S02-S06.
4. **File-count drift**: The numbers here are current as of this scan. If M003/M004 work lands between now and S01 execution, re-run the census.

## Verification

- T01-T03: Artifacts exist and contain all mandatory data points
- T04: `uv run pytest` passes (all new characterization tests green), `uv run mypy src/scc_cli` passes, `uv run ruff check` passes
- No production code changes — only test files and GSD artifacts
