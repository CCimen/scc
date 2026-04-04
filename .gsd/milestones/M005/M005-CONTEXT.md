# M005 Context: Architecture Quality, Strictness, And Hardening

## Milestone Intent
M005 exists to convert the feature-complete v1 state into a codebase that is excellent to maintain: smaller modules, sharper boundaries, stricter types, better tests on critical seams, clearer error handling, and truthful operational diagnostics.

This is not optional cleanup. It is the milestone that determines whether SCC remains easy to evolve as an enterprise-quality governed runtime or degrades into large-file orchestration, weak contracts, and fragile behavior.

## Milestone Sequencing
M005 should run after M004 completes.

Reason:
- M003 still reshapes runtime and enforced-egress architecture.
- M004 still reshapes shared safety surfaces and provider UX integration paths.
- A full M005 pass before those milestones would create expensive churn because launch, runtime, docker, and safety modules would be decomposed and typed once, then reopened and restructured again.

Allowed before M005:
- characterization tests added in active milestone work
- small helper extractions inside files already being changed
- local type tightening that directly enables the active slice
- removal of obviously unsafe behavior in code already under modification

Not allowed before M005:
- repo-wide decomposition campaigns
- cross-domain quality sweeps
- guardrail-restoration work that spans unrelated launch/runtime/safety modules
- broad refactors whose main purpose is code hygiene rather than milestone delivery

## Why This Is The Right Final Milestone
Previous milestones establish the clean architecture, provider-neutral launch boundary, portable runtime direction, enforced web-egress direction, and shared safety engine. M005 is where the codebase must be made worthy of those ideas: the architecture should be obvious in the code, types should be trustworthy, error behavior should be deterministic, and quality guardrails should be mechanically enforced.

## What Previous Milestones Already Gave You
- `scc-sync-1.7.3` is the only active implementation root.
- Truthful network vocabulary is live.
- Typed seams already exist in parts of the codebase.
- Provider-neutral launch architecture is being adopted in M002.
- Runtime and safety direction are already fixed by plan/spec.
- Characterization and contract tests exist, but they are not yet sufficient to protect every hotspot.

## Locked Product Decisions For M005
These are already decided and should not be reopened:
- SCC is a governed runtime for coding agents, not a new coding agent.
- V1 scope is Claude Code plus Codex only.
- Hard enforcement belongs in SCC-controlled runtime layers.
- Open Agent Skills are the only intended shared portability surface.
- Provider-native hooks, rules, plugins, marketplaces, and config layouts remain adapter-owned.
- Plugins are distribution/render units, not the canonical cross-provider policy object.
- No backward-compatibility aliases for pre-M001 terminology belong in core.
- M005 is the post-M004 quality-bar milestone, not an earlier substitute for M003 or M004.

## Specific Decision For Team-Pack Work
If GSD reaches the team-pack or governed-artifact refactor in M005, it should implement it here rather than trying to squeeze it into the remaining M004 safety slices.

Reason:
- the current issue is primarily control-plane shape, renderer decomposition, typed config adoption, and adapter-boundary cleanup
- those are M005 concerns
- M004 should only make current capability and safety posture truthful

The desired M005 implementation target is one approved team-pack source that SCC can project into:
- Claude-native plugin and adjacent native surfaces
- Codex-native plugin plus separate rules/hooks/config/instruction surfaces

without requiring a second team policy document.

## In Scope
- Decomposition of large or mixed-responsibility files into smaller cohesive modules
- Architecture boundary repair and cycle removal
- Typed internal config/policy/launch models
- Removal of cast-heavy interaction flows and broad `Any` propagation
- Robust error handling, subprocess hardening, and fail-closed cleanup
- Risk-based coverage increases on critical runtime/planning/error paths
- Re-enabled size, complexity, and isolation guardrails
- Truthful diagnostics/docs review
- PEP 8 style enforcement throughout

## Out Of Scope
- New provider support
- New network-policy surface area
- New safety command families
- New product features unrelated to maintainability/robustness
- Enterprise control-plane hosting, SSO, central audit export
- Arbitrary line-count churn on modules that are already cohesive and low-risk

## Current Audit Baseline
These observations come from the current local repository state and should be treated as the planning baseline for M005:

### Size And Decomposition Pressure
- 58 Python files exceed 300 lines.
- 23 exceed 700 lines.
- 15 exceed 800 lines.
- 8 exceed 1000 lines.
- 3 exceed 1100 lines.

Largest hotspots:
1. `src/scc_cli/commands/launch/flow.py` — 1665
2. `src/scc_cli/ui/dashboard/orchestrator.py` — 1493
3. `src/scc_cli/setup.py` — 1336
4. `src/scc_cli/application/dashboard.py` — 1084
5. `src/scc_cli/ui/settings.py` — 1081
6. `src/scc_cli/application/worktree/use_cases.py` — 1044
7. `src/scc_cli/commands/team.py` — 1036
8. `src/scc_cli/commands/config.py` — 1029
9. `src/scc_cli/ui/dashboard/_dashboard.py` — 966
10. `src/scc_cli/ui/wizard.py` — 931
11. `src/scc_cli/docker/launch.py` — 925
12. `src/scc_cli/application/launch/start_wizard.py` — 914
13. `src/scc_cli/ui/git_interactive.py` — 884
14. `src/scc_cli/marketplace/materialize.py` — 866
15. `src/scc_cli/core/personal_profiles.py` — 839
16. `src/scc_cli/ui/picker.py` — 786
17. `src/scc_cli/ui/keys.py` — 784
18. `src/scc_cli/application/compute_effective_config.py` — 775
19. `src/scc_cli/docker/credentials.py` — 743
20. `src/scc_cli/commands/profile.py` — 715

Domain concentration:
- `commands/`: 13 files above 300 lines, 8849 total lines
- `ui/`: 11 files above 300 lines, 8762 total lines
- `application/`: 6 files above 300 lines, 4827 total lines
- `marketplace/`: 7 files above 300 lines, 3666 total lines
- `docker/`: 3 files above 300 lines, 2288 total lines
- `core/`: 2 files above 300 lines, 1174 total lines

### Typing Pressure
- 368 `dict[str, Any]` references remain in `src/scc_cli`.
- 49 `cast()` calls remain in `src/scc_cli`.
- `commands/launch/flow_types.py` still defines `UserConfig: TypeAlias = dict[str, Any]`.
- `application/interaction_requests.py` is only partially generic because `InteractionRequest` still collapses selection payloads to `SelectRequest[object]`.
- Typed config models already exist in `ports/config_models.py`, so M005 should prefer adoption and expansion over inventing a second model family.

### Reliability And Error-Handling Pressure
- 36 `except Exception:` sites remain in `src/scc_cli`.
- Existing unchecked subprocess usage appears in git, profile, dashboard, doctor, and worktree flows.
- `docker/launch.py` exposes mutable module-level defaults, including `DEFAULT_SAFETY_NET_POLICY`.
- Quality `xfail`s still exist in `tests/test_file_sizes.py`, `tests/test_function_sizes.py`, and `tests/test_ui_integration.py`.

### Coverage Pressure
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — 22%
- `src/scc_cli/docker/launch.py` — 54%
- `src/scc_cli/core/error_mapping.py` — 74%
- `src/scc_cli/ui/settings.py` — 0%
- `src/scc_cli/ui/dashboard/orchestrator.py` — 6%
- `src/scc_cli/commands/reset.py` — 7%
- `src/scc_cli/commands/profile.py` — 9%
- `src/scc_cli/docker/credentials.py` — 8%

### Architecture Boundary Pressure
Current repo evidence shows these concrete boundary problems:
- `core/personal_profiles.py` imports marketplace-managed state and reaches into `docker.launch`.
- `application/dashboard.py` imports `docker.core.ContainerInfo`.
- `ui/dashboard/orchestrator.py`, `commands/admin.py`, `commands/profile.py`, and `commands/worktree/container_commands.py` call runtime/docker modules directly.
- `docker/launch.py` imports `console`, which inverts runtime-to-presentation direction.
- `docker.core` and `docker.launch` still form a direct import cycle.
- `marketplace/materialize.py`, `marketplace/render.py`, and `application/sync_marketplace.py` are still anchored to Claude-native concepts such as `settings.local.json`, `.claude-plugin/marketplace.json`, and `claude-plugins-official`, even though the product goal is one governed artifact model that renders to both Claude and Codex.
- There is not yet one explicit adapter-owned model for Codex plugins, Codex rules, Codex hooks, and provider-native instruction files, which risks future drift if new support is bolted onto the current Claude-shaped pipeline.
- Claude and Codex plugin surfaces are intentionally asymmetric. M005 should not "solve" this by inventing a fake shared plugin format in core; it should make the provider-neutral bundle plan explicit and keep native projection logic inside adapters.
- The developer-facing UX should remain close to the old SCC model: choose a team and get one team package. The code-facing architecture should achieve that by rendering from one approved team-pack source, not by making Claude marketplace shape the canonical config model.

## Canonical References To Load First
Read these before planning any M005 slice work:
1. `CONSTITUTION.md`
2. `PLAN.md`
3. `.gsd/PROJECT.md`
4. `.gsd/REQUIREMENTS.md`
5. `.gsd/DECISIONS.md`
6. `.gsd/KNOWLEDGE.md`
7. `.gsd/RUNTIME.md`
8. `specs/02-control-plane-and-types.md`
9. `specs/03-provider-boundary.md`
10. `specs/04-runtime-and-egress.md`
11. `specs/05-safety-engine.md`
12. `specs/07-verification-and-quality-gates.md`

Then inspect the highest-risk code surfaces first:
- `src/scc_cli/commands/launch/`
- `src/scc_cli/ui/dashboard/`
- `src/scc_cli/application/`
- `src/scc_cli/docker/`
- `src/scc_cli/marketplace/`
- `src/scc_cli/core/personal_profiles.py`
- `src/scc_cli/setup.py`

## Architectural Rules

### 1. Decompose by responsibility, not only by line count
Line count is a signal, not the goal. M005 should absolutely split the current mandatory hotspot set, but it should not perform arbitrary churn on cohesive low-risk modules just to hit cosmetic numbers.

### 2. Mandatory split rule
Any module above 800 lines or mixing multiple architectural layers is a mandatory split candidate. Modules above 1100 lines must not survive M005 unchanged.

### 3. Raw dictionaries stop at the edges
Parsing, persistence, JSON envelopes, and presentation serializers may still use raw dictionaries. Control-plane, application, and launch-planning logic must use typed models.

### 4. No direct runtime/backend calls from core, application, commands, or UI
Those layers may depend on ports, services, and use cases. They should not reach straight into `docker.*` or equivalent runtime modules.

### 5. Generic interaction flows replace cast-heavy recovery
The fix for repeated `cast(answer.value, ...)` is not more casts. It is a typed request/answer path that preserves payload type information across the application/UI boundary.

### 6. Test before deep surgery
Before splitting a fragile or poorly covered module, add characterization or contract tests that protect current behavior.

### 7. Fail closed on policy, safety, and runtime validity
If policy is unreadable, runtime capability is ambiguous, provider requirements cannot be validated, or safety configuration is invalid, the system must block or error clearly rather than continue permissively.

### 8. Remove `xfail` by fixing reality
Guardrail and isolation tests should not remain permanently xfailed. M005 should fix the code or the test design so the guardrail becomes trustworthy again.

### 9. Prefer explicit outcomes over sentinel values
If callers need to distinguish success, refusal, and failure, represent that explicitly. Do not print a warning and return a value that looks successful.

## GSD Auto-Mode Task Shaping Guidance
Because GSD dispatches fresh sessions per task, every task plan in M005 should be explicit enough to stand alone:

### Required for every task
- exact files to read first
- exact files allowed to change
- exact verification commands to run
- architectural boundary constraints that must remain true
- a short must-have list with mechanically checkable outcomes

### Preferred task size
- one context-window-sized unit
- usually 2-5 write files
- avoid mixing decomposition, strict typing, coverage, and docs cleanup in one task unless the change is genuinely tiny

### Good M005 task shapes
- extract one launch-flow helper cluster and add characterization tests
- convert one config sub-pipeline from raw dicts to typed models
- harden one subprocess-heavy module behind a checked wrapper
- raise coverage for one adapter/runtime seam with focused tests

### Bad M005 task shapes
- "refactor commands layer"
- "fix typing across the repo"
- "raise coverage everywhere"
- "clean up dashboard and settings and worktree"

## Verification Expectations

### Always-on gate
- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pyright src/scc_cli`
- `uv run pytest --cov --cov-branch`

### Slice-specific expectations
- S01 must leave behind inventories and test protection for promoted hotspots.
- S02 must keep decomposition changes behavior-safe with targeted tests.
- S03 must remove typing relaxations rather than adding new ignores.
- S04 must test failure branches, not just success paths.
- S05 must improve meaningful assertions on decision branches, not inflate coverage with trivial wrapper tests.
- S06 must eliminate `xfail` and prove guardrails are active in CI.

## Milestone Exit Contract
M005 is not complete until all of the following are true:
- all modules over 1100 lines are reduced below the hard guardrail threshold
- every module currently above 800 lines is split below 800 lines or explicitly justified as cohesive and low-risk
- the top-20 hotspot list is no longer dominated by orchestration monoliths
- direct runtime/backend imports from core, application, commands, and UI are removed or isolated behind ports/adapters
- internal config/policy/launch logic no longer traffics in raw `dict[str, Any]`
- cast-heavy interaction flow recovery is removed from launch and wizard paths
- silent failure swallowing and unchecked subprocess behavior are removed from maintained production paths
- file/function size and isolation tests pass without `xfail`
- critical runtime/planning/error/audit seams meet the coverage targets in the roadmap
- docs and diagnostics are truthful
- `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pyright src/scc_cli`, and `uv run pytest --cov --cov-branch` all pass

## Hand-Off Note
If M003 or M004 discovers a hotspot that must be partially decomposed early, keep the change local to the active milestone and note the remaining work for M005. Do not silently convert a feature milestone into a broad quality sweep.
