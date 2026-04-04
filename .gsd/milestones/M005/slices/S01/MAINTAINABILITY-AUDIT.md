# Maintainability Audit — SCC CLI (`scc-sync-1.7.3`)

Generated from live codebase scans on 2026-04-04.
Total source: 61,089 lines across `src/scc_cli/`.

---

## Section 1 — Ranked Hotspot Inventory

### 1.1 Files > 300 Lines (63 files)

| Rank | File | Lines | Domain | Split Tag | Layer-Mixing |
|------|------|-------|--------|-----------|--------------|
| 1 | `ui/dashboard/orchestrator.py` | 1489 | ui | HARD-FAIL | Yes — imports application |
| 2 | `commands/launch/flow.py` | 1447 | commands | HARD-FAIL | No |
| 3 | `setup.py` | 1336 | other | HARD-FAIL | No |
| 4 | `application/dashboard.py` | 1084 | application | MANDATORY-SPLIT | Yes — imports runtime, services |
| 5 | `ui/settings.py` | 1081 | ui | MANDATORY-SPLIT | Yes — imports application, infrastructure |
| 6 | `application/worktree/use_cases.py` | 1044 | application | MANDATORY-SPLIT | Yes — imports infrastructure, services |
| 7 | `commands/team.py` | 1036 | commands | MANDATORY-SPLIT | No |
| 8 | `commands/config.py` | 1029 | commands | MANDATORY-SPLIT | Yes — imports infrastructure |
| 9 | `ui/dashboard/_dashboard.py` | 966 | ui | MANDATORY-SPLIT | Yes — imports application |
| 10 | `ui/wizard.py` | 931 | ui | MANDATORY-SPLIT | Yes — imports application, services |
| 11 | `application/launch/start_wizard.py` | 914 | application | MANDATORY-SPLIT | No |
| 12 | `ui/git_interactive.py` | 884 | ui | MANDATORY-SPLIT | No |
| 13 | `docker/launch.py` | 874 | docker | MANDATORY-SPLIT | No |
| 14 | `marketplace/materialize.py` | 866 | marketplace | MANDATORY-SPLIT | No |
| 15 | `core/personal_profiles.py` | 839 | core | MANDATORY-SPLIT | Yes — imports marketplace |
| 16 | `ui/picker.py` | 786 | ui | — | No |
| 17 | `ui/keys.py` | 784 | ui | — | No |
| 18 | `application/compute_effective_config.py` | 775 | application | — | No |
| 19 | `docker/credentials.py` | 726 | docker | — | No |
| 20 | `commands/profile.py` | 715 | commands | — | No |
| 21 | `application/settings/use_cases.py` | 715 | application | — | Yes — imports infrastructure |
| 22 | `commands/admin.py` | 701 | commands | — | No |
| 23 | `commands/worktree/worktree_commands.py` | 696 | commands | — | No |
| 24 | `marketplace/team_fetch.py` | 689 | marketplace | — | No |
| 25 | `update.py` | 688 | other | — | No |
| 26 | `commands/exceptions.py` | 685 | commands | — | No |
| 27 | `commands/reset.py` | 632 | commands | — | No |
| 28 | `docker/core.py` | 593 | docker | — | No |
| 29 | `ui/chrome.py` | 590 | ui | — | No |
| 30 | `console.py` | 562 | other | — | No |
| 31 | `services/git/worktree.py` | 556 | services | — | No |
| 32 | `marketplace/normalize.py` | 553 | marketplace | — | No |
| 33 | `config.py` | 541 | other | — | No |
| 34 | `core/git_safety_rules.py` | 527 | core | — | No |
| 35 | `adapters/claude_settings.py` | 508 | adapters | — | Yes — imports application |
| 36 | `marketplace/schema.py` | 498 | marketplace | — | No |
| 37 | `remote.py` | 491 | other | — | Yes — imports infrastructure |
| 38 | `validate.py` | 489 | other | — | Yes — imports marketplace |
| 39 | `source_resolver.py` | 470 | other | — | No |
| 40 | `ui/formatters.py` | 460 | ui | — | Yes — imports runtime |
| 41 | `ui/list_screen.py` | 437 | ui | — | No |
| 42 | `models/plugin_audit.py` | 434 | models | — | No |
| 43 | `marketplace/resolve.py` | 430 | marketplace | — | No |
| 44 | `core/errors.py` | 399 | core | — | No |
| 45 | `contexts.py` | 394 | other | — | No |
| 46 | `commands/worktree/container_commands.py` | 385 | commands | — | No |
| 47 | `stats.py` | 378 | other | — | No |
| 48 | `utils/ttl.py` | 376 | utils | — | No |
| 49 | `adapters/oci_sandbox_runtime.py` | 353 | adapters | — | No |
| 50 | `application/support_bundle.py` | 351 | application | — | Yes — imports infrastructure |
| 51 | `ui/gate.py` | 350 | ui | — | No |
| 52 | `platform.py` | 350 | other | — | No |
| 53 | `theme.py` | 348 | other | — | No |
| 54 | `commands/worktree/session_commands.py` | 344 | commands | — | No |
| 55 | `commands/org/update_cmd.py` | 330 | commands | — | No |
| 56 | `cli.py` | 324 | other | — | No |
| 57 | `application/start_session.py` | 322 | application | — | No |
| 58 | `commands/support.py` | 321 | commands | — | No |
| 59 | `commands/launch/wizard_resume.py` | 321 | commands | — | No |
| 60 | `marketplace/compute.py` | 316 | marketplace | — | No |
| 61 | `commands/launch/render.py` | 315 | commands | — | No |
| 62 | `marketplace/render.py` | 314 | marketplace | — | No |
| 63 | `commands/launch/workspace.py` | 309 | commands | — | No |

**Summary:** 3 files exceed 1100 lines (HARD-FAIL), 12 files exceed 800 lines (MANDATORY-SPLIT), 63 files total exceed 300 lines.

### 1.2 Top-25 Largest Functions (AST analysis)

| Rank | Function | File | Start Line | Lines |
|------|----------|------|------------|-------|
| 1 | `interactive_start` | `commands/launch/flow.py` | L786 | 534 |
| 2 | `compute_effective_config` | `application/compute_effective_config.py` | L375 | 401 |
| 3 | `Dashboard._handle_action` | `ui/dashboard/_dashboard.py` | L612 | 355 |
| 4 | `reset_cmd` | `commands/reset.py` | L325 | 308 |
| 5 | `start` | `commands/launch/flow.py` | L486 | 293 |
| 6 | `run_setup_wizard` | `setup.py` | L936 | 259 |
| 7 | `run_dashboard` | `ui/dashboard/orchestrator.py` | L65 | 232 |
| 8 | `SettingsScreen._render` | `ui/settings.py` | L839 | 219 |
| 9 | `run_sandbox` | `docker/launch.py` | L304 | 216 |
| 10 | `_resolve_session_selection` | `commands/launch/flow.py` | L114 | 212 |
| 11 | `team_validate` | `commands/team.py` | L744 | 198 |
| 12 | `render_start_wizard_prompt` | `ui/wizard.py` | L198 | 192 |
| 13 | `_copy_credentials_from_container` | `docker/credentials.py` | L126 | 183 |
| 14 | `_handle_profile_menu` | `ui/dashboard/orchestrator.py` | L1191 | 180 |
| 15 | `switch_worktree` | `application/worktree/use_cases.py` | L475 | 174 |
| 16 | `load_status_tab_data` | `application/dashboard.py` | L649 | 169 |
| 17 | `_config_validate` | `commands/config.py` | L549 | 166 |
| 18 | `unblock_cmd` | `commands/exceptions.py` | L522 | 164 |
| 19 | `team_info` | `commands/team.py` | L590 | 149 |
| 20 | `cleanup_worktree` | `ui/git_interactive.py` | L473 | 147 |
| 21 | `_run_single_select_picker` | `ui/picker.py` | L506 | 140 |
| 22 | `_run_quick_resume_picker` | `ui/picker.py` | L648 | 139 |
| 23 | `_handle_session_resume` | `ui/dashboard/orchestrator.py` | L592 | 136 |
| 24 | `team_switch` | `commands/team.py` | L444 | 136 |
| 25 | `worktree_create_cmd` | `commands/worktree/worktree_commands.py` | L128 | 134 |

**Summary:** 5 functions exceed 250 lines — these are the highest-priority decomposition targets. The top function (`interactive_start`) at 534 lines is larger than many entire modules.

---

## Section 2 — Boundary-Repair Map

### 2.1 Docker Imports Outside docker/ and adapters/

| Source File:Line | Import Target | Violation Type | Severity |
|------------------|---------------|----------------|----------|
| `application/dashboard.py:12` | `scc_cli.docker.core.ContainerInfo` | App-layer → runtime type | MEDIUM |
| `application/dashboard.py:661` | `scc_cli.docker.core` (lazy) | App-layer → runtime module | HIGH |
| `application/dashboard.py:822` | `scc_cli.docker.core` (lazy) | App-layer → runtime module | HIGH |
| `ui/formatters.py:8` | `scc_cli.docker.core.ContainerInfo` (docstring) | Presentation → runtime type | LOW |

### 2.2 Core-to-Marketplace Leakage

| Source File:Line | Import Target | Violation Type | Severity |
|------------------|---------------|----------------|----------|
| `core/personal_profiles.py:19` | `scc_cli.marketplace.managed.load_managed_state` | Core → marketplace dependency inversion | HIGH |

This is the single most architecturally significant violation: the core layer depends on a higher-level marketplace module, breaking the dependency rule.

### 2.3 Presentation-to-Runtime Coupling

| Source File:Line | Import Target | Violation Type | Severity |
|------------------|---------------|----------------|----------|
| `docker/launch.py:18` | `..console.err_line` | Runtime → presentation helper | MEDIUM |

### 2.4 Claude-Specific Shapes in Marketplace Pipeline

| Category | Files | Count | Notes |
|----------|-------|-------|-------|
| Adapter modules (expected) | `adapters/claude_settings.py`, `adapters/claude_agent_provider.py`, `adapters/claude_agent_runner.py`, `adapters/claude_safety_adapter.py` | 4 | Properly placed |
| Bootstrap wiring | `bootstrap.py` | 1 | Imports all Claude adapters; acceptable as composition root |
| UI/branding references | `ui/branding.py`, `ui/git_interactive.py`, `ui/dashboard/orchestrator.py` | 3 | Hardcoded "Claude" strings in display text |
| Session management | `sessions.py` | 1 | Claude Code-specific session directory discovery |
| Docker credential paths | `docker/credentials.py` | 1 | Hardcoded `.claude.json`, `.claude/` paths (~20 references) |

**Key finding:** `docker/credentials.py` has ~20 hardcoded references to `.claude.json` and `/home/agent/.claude/` paths. This is the primary Claude-specific coupling in the runtime layer and blocks multi-agent support.

### 2.5 Import Cycle Assessment

| Suspected Cycle | Actual Finding |
|-----------------|----------------|
| `docker.core` ↔ `docker.launch` | **No cycle detected** — `docker.launch` does not import `docker.core` at module level |
| `commands/` → `application/` → `commands/` | **No cycle detected** — `application/` does not import from `commands/` |
| `adapters/claude_settings` → `application` | **Violation found** — adapter imports from application layer (upward dependency) |

### 2.6 Layer-Mixing Summary (files > 800 lines)

Of the 15 files tagged MANDATORY-SPLIT or HARD-FAIL, **8 have cross-layer imports:**

| File | Own Layer | Imports From |
|------|-----------|--------------|
| `ui/dashboard/orchestrator.py` | presentation | application |
| `application/dashboard.py` | application | runtime, services |
| `ui/settings.py` | presentation | application, infrastructure |
| `application/worktree/use_cases.py` | application | infrastructure, services |
| `commands/config.py` | presentation | infrastructure |
| `ui/dashboard/_dashboard.py` | presentation | application |
| `ui/wizard.py` | presentation | application, services |
| `core/personal_profiles.py` | core | marketplace |

---

## Section 3 — Robustness-Debt Catalog

### 3.1 Broad `except Exception` Sites

**Total: 87 sites** across the codebase.

| Severity | Count | Locations |
|----------|-------|-----------|
| HIGH | 11 | `docker/credentials.py` (5), `docker/launch.py` (implicit via `commands/launch/flow.py:874,1445`), `core/safety_policy_loader.py` (1), `adapters/egress_topology.py` (2), `adapters/docker_runtime_probe.py` (1) |
| MEDIUM | 28 | `application/settings/use_cases.py` (4), `application/dashboard.py` (8), `application/worktree/use_cases.py` (3), `application/sync_marketplace.py` (1), `commands/org/update_cmd.py` (2), `commands/launch/flow.py` (2), `commands/reset.py` (1), `commands/team.py` (1), `marketplace/materialize.py` (1), `marketplace/team_fetch.py` (2), `cli_common.py` (1), `json_command.py` (1), `contexts.py` (1) |
| LOW | 48 | `maintenance/*` (16), `doctor/*` (5), `ui/*` (12), `update.py` (2), `utils/*` (3), `application/support_bundle.py` (8), `adapters/local_filesystem.py` (1), `core/personal_profiles.py` (1) |

**Highest-risk sites:** The 5 in `docker/credentials.py` handle credential copying/symlinking where silent failures can leave containers in broken auth states. The 2 in `adapters/egress_topology.py` handle network setup where silent failures can leave containers without egress isolation.

### 3.2 Unchecked `subprocess.run` Calls

**Total: 71 calls** across the codebase.

| Category | Count | Notes |
|----------|-------|-------|
| With `check=True` | 1 | Only `ui/dashboard/orchestrator.py:1162` |
| With stderr capture (`capture_output`/`stderr=`) | 2 | Most calls ignore failure output |
| With `timeout=` | 1 | Only `ui/git_interactive.py:635` |
| No check, no capture (riskiest) | 68 | Silent failures, no timeout protection |

**Highest-risk files by subprocess density:**
- `docker/credentials.py` — 21 calls, all unchecked, credential operations
- `ui/git_interactive.py` — 12 calls, mostly unchecked, git operations
- `docker/launch.py` — 8 calls, unchecked, container lifecycle
- `services/git/worktree.py` — 7 calls, unchecked, git worktree management

### 3.3 Mutable Module-Level Defaults

| Identifier | File | Type | Mutability Risk |
|------------|------|------|-----------------|
| `DEFAULT_KEY_MAP` | `ui/keys.py:578` | `dict` built by function | MEDIUM — called once but stored as mutable dict |
| `DETECTION_ORDER` | `deps.py:37` | `list[tuple]` | LOW — tuple-of-tuples but list is mutable |
| `INSTALL_COMMANDS` | `deps.py:81` | `dict` | LOW — read-only in practice |
| `DEFAULT_SAFETY_NET_POLICY` | `docker/launch.py:37` | `dict[str, Any]` | HIGH — mutable dict used as default return |
| `USER_CONFIG_DEFAULTS` | `config.py:46` | `dict` | MEDIUM — defensively deep-copied at use site |
| `_DEFAULT_DENY_TARGETS` | `core/egress_policy.py:42` | `tuple[tuple]` | SAFE — immutable |
| `DEFAULT_MARKETPLACE_REPO` | `core/constants.py:69` | `str` | SAFE — immutable |
| `BLOCK_MESSAGES` | `core/git_safety_rules.py:153` | `dict[str, str]` | LOW — read-only in practice |
| `_RULE_NAMES` | `core/git_safety_rules.py:207` | `dict[str, str]` | LOW — read-only in practice |
| `_DEFAULT_POLICY` | `core/safety_policy_loader.py:20` | `SafetyPolicy` | MEDIUM — dataclass, returned as default |
| `_NETWORK_POLICY_ORDER` | `core/network_policy.py:9` | `dict` | LOW — read-only lookup |
| `DEFAULT_ORG_CONFIG_TTL_SECONDS` | `marketplace/constants.py:84` | `Final[int]` | SAFE — Final annotation |

**Key risk:** `DEFAULT_SAFETY_NET_POLICY` in `docker/launch.py` is a plain mutable `dict[str, Any]` that is returned directly. Any caller mutating the return value mutates the global.

### 3.4 Typing Debt

| Pattern | Count |
|---------|-------|
| `dict[str, Any]` references | 371 |
| `cast()` calls | 46 |
| `TypeAlias = dict[str, Any]` | 1 (`commands/launch/flow_types.py:18`) |

**371 `dict[str, Any]` references** represent the single largest typing-debt category. Many of these are configuration objects that should be typed dataclasses or TypedDicts.

### 3.5 Existing Quality xfails

| Test File | Marker | What It Masks |
|-----------|--------|---------------|
| `tests/test_ui_integration.py:441` | `@pytest.mark.xfail` | `test_cli_shows_dashboard_when_no_workspace_detected` — test isolation issue, passes individually |
| `tests/test_ui_integration.py:462` | `@pytest.mark.xfail` | `test_cli_invokes_start_when_workspace_detected` — test isolation issue, passes individually |
| `tests/test_file_sizes.py:157` | `@pytest.mark.xfail` | `commands/launch/app.py` exceeds file size limit — awaiting refactor |
| `tests/test_function_sizes.py:170` | `@pytest.mark.xfail` | Known large functions exceed guardrail (launch flow and org/reset commands) |

---

## Priority Queue for S02–S06

The following ranked list combines all three audit categories into a unified action queue, ordered by impact × risk.

| Priority | Item | Category | Severity | Target Slice | Rationale |
|----------|------|----------|----------|--------------|-----------|
| 1 | Split `commands/launch/flow.py` (1447 lines, top function 534 lines) | Hotspot | HARD-FAIL | S02 | Largest command file; `interactive_start` alone is 534 lines |
| 2 | Split `ui/dashboard/orchestrator.py` (1489 lines) | Hotspot | HARD-FAIL | S02 | Largest file in codebase; 11 `except Exception` sites |
| 3 | Split `setup.py` (1336 lines) | Hotspot | HARD-FAIL | S02 | Third-largest; `run_setup_wizard` is 259 lines |
| 4 | Fix `application/dashboard.py` boundary leak (imports docker.core) | Boundary | HIGH | S03 | Application layer directly calls runtime Docker API |
| 5 | Fix `core/personal_profiles.py` marketplace dependency inversion | Boundary | HIGH | S03 | Core depends on marketplace — breaks dependency direction |
| 6 | Harden `docker/credentials.py` subprocess calls (21 unchecked) | Robustness | HIGH | S04 | Credential ops with no error checking or timeouts |
| 7 | Split `application/dashboard.py` (1084 lines, layer-mixed) | Hotspot | MANDATORY-SPLIT | S02 | Cross-layer imports compound the size problem |
| 8 | Split `commands/team.py` (1036 lines, 3 large functions) | Hotspot | MANDATORY-SPLIT | S02 | Three functions > 130 lines each |
| 9 | Decompose `compute_effective_config` (401-line function) | Hotspot | MANDATORY-SPLIT | S02 | Second-largest function; pure logic, highly decomposable |
| 10 | Harden `docker/launch.py` subprocess calls (8 unchecked) | Robustness | HIGH | S04 | Container lifecycle with silent failures |
| 11 | Fix `DEFAULT_SAFETY_NET_POLICY` mutable global | Robustness | HIGH | S04 | Returned directly; caller mutation corrupts global state |
| 12 | Split `ui/settings.py` (1081 lines, layer-mixed) | Hotspot | MANDATORY-SPLIT | S02 | Imports from application and infrastructure layers |
| 13 | Split `application/worktree/use_cases.py` (1044 lines) | Hotspot | MANDATORY-SPLIT | S02 | `switch_worktree` at 174 lines; cross-layer imports |
| 14 | Fix `adapters/claude_settings.py` upward dependency | Boundary | MEDIUM | S03 | Adapter imports from application layer |
| 15 | Harden `docker/credentials.py` `except Exception` sites (5 HIGH) | Robustness | HIGH | S04 | Silent credential failures leave containers broken |
| 16 | Extract `docker/credentials.py` Claude-specific paths | Boundary | MEDIUM | S03 | ~20 hardcoded `.claude` references block multi-agent |
| 17 | Add timeouts to all 71 subprocess.run calls | Robustness | MEDIUM | S04 | Only 1 of 71 calls has a timeout |
| 18 | Replace `dict[str, Any]` with typed structures (371 sites) | Typing | MEDIUM | S05 | Start with config/launch/settings hot paths |
| 19 | Resolve 4 xfail markers in test suite | Quality | LOW | S06 | 2 test isolation issues; 2 awaiting refactor |
| 20 | Fix `docker/launch.py` console import (runtime → presentation) | Boundary | MEDIUM | S03 | Runtime imports presentation helper |
