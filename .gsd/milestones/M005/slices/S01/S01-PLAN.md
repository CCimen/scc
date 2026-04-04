# S01: Architecture hotspot audit and decomposition plan

**Goal:** Produce a complete ranked inventory of every file over 300 lines, every architecture boundary violation, and every cross-cutting concern — then output a prioritized decomposition order with characterization test requirements for each split target.
**Demo:** After this slice, the team has a concrete, exhaustive list of all 58+ oversized files, all boundary violations, and the exact refactor order that preserves behavior.

## Tasks
- [ ] **T01: Full file inventory and hotspot ranking** — Audit every module in `src/scc_cli` for line count, function/class count, import fan-in/fan-out, and mixed-responsibility signals. Produce a ranked hotspot table covering all 58+ files over 300 lines. Group by domain: launch flow (flow.py 1665 lines), UI layer (settings 1081, orchestrator 1493, dashboard 966, wizard 931, picker 786, keys 784, git_interactive 884, chrome 590), commands layer (team 1036, config 1029, profile 715, reset 632, exceptions 685, admin 701), application layer (dashboard 1084, worktree/use_cases 1044, compute_effective_config 775, settings/use_cases 703, launch/start_wizard 914), docker layer (launch 925, credentials 743, core 620), marketplace (materialize 866, team_fetch 689, normalize 553), and other (setup 1336, personal_profiles 839, remote 491, validate 489, config 521).
  - Estimate: small
  - Files: src/scc_cli/**/*.py
  - Verify: hotspot table exists covering all files >300 lines, grouped by domain with target module count per file

- [ ] **T02: Map all architecture boundary violations** — Document every concrete violation of the intended layer separation: (1) core/ importing from marketplace/, docker/, commands/, adapters/, ui/; (2) docker/ importing from console or commands/; (3) commands/ and ui/ calling docker.* directly instead of through SandboxRuntime port; (4) circular dependencies (marketplace/sync ↔ application/sync_marketplace); (5) ports/ importing from concrete packages (doctor/, services/); (6) application/ importing docker types at module level. For each violation, document the current import, the correct dependency direction, and the fix approach.
  - Estimate: small
  - Files: src/scc_cli/core/personal_profiles.py, src/scc_cli/core/maintenance.py, src/scc_cli/docker/launch.py, src/scc_cli/commands/launch/sandbox.py, src/scc_cli/commands/admin.py, src/scc_cli/commands/worktree/container_commands.py, src/scc_cli/commands/profile.py, src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/ui/formatters.py, src/scc_cli/ui/picker.py, src/scc_cli/marketplace/sync.py, src/scc_cli/application/dashboard.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/ports/doctor_runner.py, src/scc_cli/ports/git_client.py
  - Verify: every boundary violation has a documented current→correct dependency direction and fix approach

- [ ] **T03: Add characterization tests for all high-priority split targets** — For the top 20 highest-risk modules that will be split in S02, ensure characterization tests lock current behavior. Priority: commands/launch/flow.py, ui/dashboard/orchestrator.py, application/dashboard.py, docker/launch.py, docker/credentials.py, application/worktree/use_cases.py, commands/team.py, commands/config.py, marketplace/materialize.py, core/personal_profiles.py. If tests are missing or coverage is below 50%, add focused characterization tests before any refactoring.
  - Estimate: large
  - Files: tests/**, plus all source files listed above
  - Verify: uv run pytest passes; characterization coverage exists for all top-20 split targets with at least the current public API behavior locked

- [ ] **T04: Catalog global mutable state and subprocess handling defects** — Inventory all module-level mutable state (especially docker/launch.py:41 DEFAULT_SAFETY_NET_POLICY — a public mutable dict for a security default), all subprocess.run calls without proper error handling (config.py:340, ui/git_interactive.py:869, ui/git_interactive.py:600, commands/worktree/worktree_commands.py:613), and all silent error swallowing sites (27 bare except+pass). Produce a defect list with file, line, severity, and fix approach.
  - Estimate: small
  - Files: src/scc_cli/**/*.py
  - Verify: defect list covers all mutable globals, all unhandled subprocess sites, and all silent-swallow sites with severity ratings
