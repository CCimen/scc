# SCC Maintainability Deep Dive (Post‑Refactor Review — Updated)

## Metadata
- Date: 2026-01-17
- Repo: `scc`
- Branch: `refactor/improve-maintainability`
- Scope: post‑refactor maintainability analysis
- Audience: next agent reviewing maintainability plan
- Goal: raise maintainability score from 8.5/10 to 10/10
- Status: analysis complete, implementation not started

## Feedback Integration Summary (Updated)
- Adjusted launch presenter guidance: presenters stay at the edges (CLI/UI), not as application dependencies.
- Adjusted JSON output guidance: mapping to JSON happens in command/UI layers, not inside application use cases.
- Added `presentation/json` package recommendation to centralize edge mapping.
- Chose a single error strategy: use cases return success models and raise typed `SCCError` on failure.
- Locked down `InteractionRequest` as a stable schema with characterization tests.
- Removed Logger port recommendation; use stdlib logging in application and forbid `console.print` there.
- Added architectural invariants tests (no UI/IO imports in application).
- Highlighted filesystem contract coverage as a required guardrail.
- Added conditional note for SandboxRuntime split: only split if scope grows.
- Clarified support bundle testing: in‑memory archive or temp dir ok; do not require real filesystem in tests.
- Adjusted sequence: workspace resolver unification now precedes worktree extraction.
- Added optional complexity budget guardrail (file/function size).

## Purpose
- Provide a comprehensive, handoff‑ready assessment of maintainability.
- Explain the current top blockers and how they work in code.
- Enumerate high‑value improvements with technical detail.
- Capture nice‑to‑have improvements that can be scheduled later.
- Propose a clean, sequenced plan that minimizes regressions.
- Provide acceptance criteria for a 10/10 maintainability outcome.

## How to Use This Document
- Start with Top Blockers for the biggest maintainability risks.
- Use Suggested Sequence to plan incremental, reviewable PRs.
- Use Acceptance Criteria to verify each phase is complete.
- Use Review Checklist to validate boundary and layering rules.
- Use Appendix for file references when drilling into code.

## Table of Contents
1. Evaluation Method
2. Current Architecture Snapshot
3. Maintainability Score Summary
4. Glossary
5. Design Rules and Cross‑Cutting Decisions
6. Top Blockers Overview
7. Blocker 1: Launch Flow Monolith
8. Blocker 2: Worktree Command Monolith
9. Blocker 3: Workspace Resolution Duplication
10. Blocker 4: Sessions Persistence + Formatting
11. Blocker 5: Support Bundle IO and Doctor Coupling
12. High‑Value Improvements (Beyond Blockers)
13. Guardrails and Invariants (Recommended)
14. Nice‑to‑Have Improvements
15. Suggested Sequence and Milestones
16. Implementation Tasks and Phases (Checklist)
17. Definition of 10/10 Maintainability
18. Review Checklist for Next Agent
19. Appendix: File References

## Evaluation Method
- Criterion: clear layering with consistent dependency direction.
- Criterion: modules are cohesive and single‑purpose.
- Criterion: testability without Docker/Git/network.
- Criterion: explicit boundaries between UI, application, ports, adapters.
- Criterion: minimal duplication in cross‑cutting concerns.
- Criterion: low cognitive load per module.
- Criterion: typed interfaces with stable data shapes.
- Criterion: predictable side effects (IO at edges).
- Criterion: easy onboarding for new contributors.
- Criterion: refactors are low risk due to tests and seams.

## Current Architecture Snapshot
- `scc_cli/ports/`: Protocols for runtime, git, filesystem, fetcher, clock, agent runner.
- `scc_cli/adapters/`: Docker, git, filesystem, HTTP, clock implementations.
- `scc_cli/bootstrap.py`: composition root for default adapters.
- `scc_cli/application/`: use cases for start session, settings, sync, dashboard, profiles.
- `scc_cli/commands/`: CLI entrypoints; some still orchestrate heavy logic.
- `scc_cli/ui/`: Rich/TUI rendering and interactive pickers.
- `scc_cli/services/`: workspace resolver and git detection helpers.
- `scc_cli/marketplace/`: managed state and materialization logic.
- `scc_cli/maintenance/`: tasks extracted from legacy maintenance file.
- `scc_cli/sessions.py`: session persistence and formatting.

## Maintainability Score Summary
- Current score after refactor: 8.5/10.
- Primary limiting factor: large orchestration files in commands layer.
- Secondary limiting factor: duplicated workspace detection logic.
- Third limiting factor: persistence logic with untyped dicts.
- Fourth limiting factor: application logic still consumes raw dict config.
- Fifth limiting factor: remaining command modules with heavy side effects.

## Glossary
- Application layer: use cases and orchestration without UI.
- Commands layer: CLI entrypoints and argument parsing.
- UI layer: Rich rendering and interactive prompts.
- Ports: Protocols defining adapter interfaces.
- Adapters: implementations of ports using external libraries.
- View model: data‑only output representation for UI rendering.
- InteractionRequest: data‑only structure describing a prompt/decision.
- Workspace root (WR): resolved workspace directory.
- Entry dir (ED): directory where user invoked command.
- Mount root (MR): host path mounted into container.
- Container workdir (CW): working directory inside container.

## Design Rules and Cross‑Cutting Decisions
- Error strategy: use cases return success models and raise typed `SCCError` on failure; commands map via `core/error_mapping` and JSON envelopes.
- Presentation mapping: JSON mapping lives only at the edges (CLI/UI); prefer a centralized `scc_cli/presentation/json/` package.
- Presenter vocabulary: presenters are edge‑only mapping helpers, not ports or application dependencies.
- Interaction requests: standardize `InteractionRequest` variants (`ConfirmRequest`, `SelectRequest`, `InputRequest`) with stable IDs/labels.
- Interaction request tests: add characterization tests to lock labels, hotkeys, and BACK semantics.
- Logging boundary: application may use stdlib `logging`; application must not call `console.print`/`typer`.
- IO boundary: application uses ports (`Filesystem`, `GitClient`, `RemoteFetcher`); avoid direct `Path.read_text`/`subprocess` in application modules.
- Naming consistency: use `SessionStore` across ports/adapters/services (avoid `SessionRepository` drift).

## Top Blockers Overview
- Blocker 1: Launch flow monolith still mixes orchestration and UI.
- Blocker 2: Worktree commands mix git, docker, IO, prompts in one file.
- Blocker 3: Workspace resolution duplicated across services and commands.
- Blocker 4: Sessions persistence layer is untyped and UI‑coupled.
- Blocker 5: Support bundle IO and doctor coupling reduce testability.

## Blocker 1: Launch Flow Monolith (`scc_cli/commands/launch/flow.py`)
### Current flow in detail — command pipeline
- `start()` is the orchestration entry for `scc start`.
- It loads user config and adapters via `get_default_adapters()`.
- It resolves session selection with `_resolve_session_selection()`.
- It validates workspace via `validate_and_resolve_workspace()`.
- It prepares workspace (worktree, deps, git safety) with `prepare_workspace()`.
- It resolves workspace team with `resolve_workspace_team()`.
- It builds `StartSessionDependencies` and `StartSessionRequest`.
- It calls `prepare_start_session()` to build plan and settings.
- It renders sync warnings and plugin enablement messages.
- It applies personal profile overlays with `_apply_personal_profile()`.
- It prints active stack summary (team, personal, workspace overrides).
- It renders worktree mount expansion info.
- It renders dry‑run output or continues to launch.
- It calls `start_session()` to start the sandbox runtime.
- It prints panels and console output directly inside the flow.
- It performs multiple JSON‑mode checks inline.
- It handles resume vs new session logic inline.

### Current flow in detail — wizard pipeline
- `interactive_start()` renders branding header and quick‑resume flow.
- It handles global Quick Resume with team filtering and toggling.
- It handles team selection or standalone mode.
- It handles workspace source selection (current, recent, team repo, custom, clone).
- It handles workspace‑scoped Quick Resume for selected workspace.
- It handles worktree creation prompts and session naming.
- It uses `pick_context_quick_resume`, `pick_team`, and `pick_workspace_source`.
- It uses `prompt_custom_workspace`, `prompt_repo_url`, and `prompt_with_layout`.
- It uses `TeamSwitchRequested` to restart the wizard loop.
- It uses `BACK` sentinel from `ui.wizard` for dashboard navigation.
- It uses `confirm_with_layout` to guard cross‑team resumes.
- It uses `print_with_layout` for several display operations.

### Why this is a blocker
- Launch flow mixes UI rendering, IO, policy decisions, and orchestration.
- The file is large and cognitively dense, slowing onboarding.
- Small changes are risky because many branches interact.
- Wizard and start pipeline share data but are not clearly separated.
- Core rules are not easily unit tested without UI mocks.
- JSON and human output handling is interleaved with control flow.
- Launch logic lacks clean side‑effect boundaries.
- Adding new start options requires editing multiple sections.

### Constraints (per feedback)
- Application layer must not depend on presenters.
- JSON mapping must live in command/UI layer.
- Application returns typed results and view models only.
- UI renders `LaunchOutput` and handles prompts.

### Desired target state
- Launch orchestration lives in application layer, not command module.
- Commands become thin wrappers around use cases.
- UI rendering becomes a pure presentation layer.
- Wizard flow becomes a state machine with explicit transitions.
- Output logic becomes view models rather than inline `console.print` calls.
- Session selection and resume logic becomes composable components.

### Proposed modularization
- Introduce `scc_cli/application/launch/` package with use cases.
- Use case: `SelectSession` (handles `--resume` and `--select`).
- Use case: `StartSessionWizard` (wizard state machine).
- Use case: `PrepareLaunchPlan` (delegates to `start_session`).
- Use case: `ApplyPersonalProfile` (pure decision + IO via ports).
- Use case: `FinalizeLaunch` (record context, call sandbox runtime).
- View model: `LaunchOutput` (info/warn/success events).
- CLI mapping: `LaunchResult -> JSON` at the command layer.
- UI mapping: `LaunchOutput -> Rich panels` in render helpers.

### Suggested interfaces and data shapes
- `LaunchRequest` dataclass with all CLI flags.
- `LaunchContext` result object with workspace, team, session name.
- `WizardState` enum (QuickResume, TeamSelect, WorkspaceSource, WorkspacePick, etc).
- `WizardDecision` object with `next_state` and `selection`.
- `LaunchPlan` object (already exists as `StartSessionPlan`).
- `LaunchOutput` with structured messages and display variants.
- `InteractionRequest` for prompts (confirm, select, input).

### Extraction steps
- Step 1: Move `_resolve_session_selection` into application use case.
- Step 2: Move `interactive_start` into `application/launch/wizard.py`.
- Step 3: Convert prompt decisions into `InteractionRequest` objects.
- Step 4: Keep `ui/` functions as renderers of `InteractionRequest`.
- Step 5: Move `personal_profiles` application logic behind a port.
- Step 6: Add `LaunchOutput` view model for status messages.
- Step 7: Update CLI to map `LaunchResult` to JSON payloads.
- Step 8: Reduce `flow.start()` to orchestration glue.

### Test plan
- Unit tests for `SelectSession` with mocked session store.
- Unit tests for wizard state transitions without Rich UI.
- Unit tests for session selection in JSON vs human modes.
- Integration test for `scc start --dry-run` unchanged output.
- Characterization test for Quick Resume selection/resume paths.
- Test for cross‑team resume confirmation behavior.
- Test for `--standalone` and `--offline` branches.
- Test for personal profile overlay decisions in non‑interactive mode.

### Risks and mitigations
- Risk: wizard behavior changes if state handling is wrong.
- Mitigation: use characterization tests around current wizard outputs.
- Risk: interactive prompts move; prompts must retain hotkeys and labels.
- Mitigation: encode prompt labels in `InteractionRequest` objects.
- Risk: JSON output shape changes.
- Mitigation: keep JSON envelope tests as guard rails.

### Acceptance criteria
- `flow.py` reduced to thin command wrapper and controller glue.
- Wizard logic isolated into application state machine.
- No direct UI calls from application layer.
- All wizard transitions testable without UI mocks.
- JSON output tests remain stable and pass.

### Non‑goals
- Do not redesign CLI flags or output schemas.
- Do not change Quick Resume UX or keybindings.

### PR breakdown (safe increments)
- PR A: extract session selection into application use case.
- PR B: introduce wizard state machine with `InteractionRequest`.
- PR C: adopt `LaunchOutput` and move UI rendering to `render.py`.
- PR D: reduce `flow.start()` to orchestration glue.

## Blocker 2: Worktree Command Monolith (`scc_cli/commands/worktree/worktree_commands.py`)
### Current flow in detail
- `worktree_create_cmd` handles repo validation, git init, commit creation.
- It uses `Confirm` prompts and `git` helpers directly.
- It installs dependencies via `deps.auto_install_dependencies`.
- It launches Docker via `docker.run` and `docker.get_or_create_container`.
- It loads org config for policy injection when starting Claude.
- `worktree_list_cmd` loads worktrees and renders via UI.
- It builds JSON output via `_helpers.build_worktree_list_data`.
- `worktree_switch_cmd` supports `-`, `^`, and fuzzy matches.
- It handles interactive selection and branch creation prompts.
- It prints shell‑friendly output to stdout directly.
- `worktree_select_cmd` builds combined list of worktrees and branches.
- It optionally creates a worktree for a selected branch.
- `worktree_enter_cmd` spawns a new shell using subprocess.
- Worktree commands mix validation, IO, git operations, and UX.

### Why this is a blocker
- Worktree behavior spans UI, git, docker, deps, and shell operations.
- Side effects happen inline; not easily unit tested.
- Error flows are embedded and hard to reuse.
- Fuzzy matching and selection logic is duplicated across commands.
- JSON and interactive modes are interleaved in the same functions.
- Worktree commands are large and require high context to modify.

### Desired target state
- Worktree commands call application use cases only.
- Git and Docker interactions abstracted behind ports.
- Worktree selection logic reused across commands.
- JSON output and UI output handled via presenters.
- Shell output behavior isolated and locked by tests.

### Proposed modularization
- Create `scc_cli/application/worktree/` package.
- Use case: `CreateWorktree` for repo initialization and worktree creation.
- Use case: `ListWorktrees` returning typed `WorktreeSummary` list.
- Use case: `SelectWorktree` with fuzzy matching and branch creation logic.
- Use case: `SwitchWorktree` for `-`, `^`, and fuzzy lookup.
- Use case: `EnterWorktreeShell` returning `ShellCommand` data.
- Presenter: `WorktreePresenter` for JSON and table output (command layer).

### Suggested interfaces and data shapes
- `WorktreeRequest` with workspace path and options.
- `WorktreeSelection` containing target path and display label.
- `WorktreeListResult` containing list + counts.
- `WorktreeOperationResult` with success, message, and optional data.
- `ShellCommand` object describing argv/env/cwd.

### Extraction steps
- Step 1: Create `WorktreeRepository` port to list/search worktrees.
- Step 2: Extend `GitClient` port for worktree/branch operations.
- Step 3: Move fuzzy match logic into application layer.
- Step 4: Move branch creation prompt into `InteractionRequest`.
- Step 5: Move docker launch into application `StartSession` reuse.
- Step 6: Replace direct `docker.run` in command layer.
- Step 7: Keep shell `print` only in CLI presenter.

### Test plan
- Unit tests for `SelectWorktree` fuzzy matching.
- Unit tests for `SwitchWorktree` special targets (`-`, `^`).
- Unit tests for branch creation path when no worktree exists.
- Integration test for `scc worktree list --json` unchanged shape.
- Characterization tests for error messages and hints.
- Tests for interactive vs non‑interactive prompts using fakes.

### Risks and mitigations
- Risk: shell integration output must remain identical.
- Mitigation: keep exact stdout strings and add tests.
- Risk: docker launch behavior diverges.
- Mitigation: route through `StartSession` use case.
- Risk: worktree list output formatting changes.
- Mitigation: keep `render_worktrees` and unit test outputs.

### Acceptance criteria
- `worktree_commands.py` shrinks to thin CLI wrappers.
- Worktree use cases run without actual git/docker.
- JSON output for worktree commands unchanged.
- All worktree flows testable with fakes.

### Non‑goals
- Do not change worktree CLI flags or output shapes.
- Do not change worktree shell integration semantics.

### PR breakdown (safe increments)
- PR A: add worktree ports and use case skeletons.
- PR B: migrate list + JSON output to use cases.
- PR C: migrate switch/select flows to use cases.
- PR D: migrate create/enter flows to use cases.

## Blocker 3: Workspace Resolution Duplication
### Current flow in detail
- `services/workspace/resolver.resolve_launch_context` implements Smart Start.
- It uses `git rev-parse` and `.scc.yaml` search for auto‑detection.
- It computes mount root and container workdir.
- It marks `is_suspicious` but does not prompt the user.
- `services/git/core.detect_workspace_root` does similar detection.
- It checks git and `.scc.yaml` plus `.git` fallback.
- `commands/launch/workspace.validate_and_resolve_workspace` also validates.
- It handles suspicious directory checks and WSL performance warnings.
- It mixes UI prompting with validation logic.
- Different call sites use different resolver paths.

### Why this is a blocker
- Multiple workspace resolvers increase inconsistent behavior risk.
- Suspicious directory handling is spread across modules.
- Hard to reason about precedence between git root and `.scc.yaml`.
- Auto‑detected and explicit path logic is duplicated.
- Validation is not fully testable without UI or environment.

### Desired target state
- A single, authoritative workspace resolution service.
- Workspace resolution returns structured decision and warnings.
- Interactive prompts handled by UI layer only.
- All call sites use the same workspace rules.

### Proposed modularization
- Create `scc_cli/application/workspace/` module.
- Use case: `ResolveWorkspace` returning `WorkspaceContext`.
- Use case: `ValidateWorkspace` returning warnings or requests.
- Port: `WorkspaceProbe` (git, config markers, filesystem).
- Port: `PlatformProbe` for WSL checks and performance warnings.
- Presenter: `WorkspaceWarningPresenter` for panels (edge only).

### Suggested interfaces and data shapes
- `WorkspaceContext` includes WR, ED, MR, CW.
- `WorkspaceDecision` includes `is_auto_detected` and `is_suspicious`.
- `WorkspaceWarning` list with reason, severity, suggested action.
- `WorkspaceResolutionResult` with `allow_continue` flag.
- `InteractionRequest` for `ConfirmContinue` on warnings.

### Extraction steps
- Step 1: Move `detect_workspace_root` logic into resolver.
- Step 2: Extract suspicious checks into application layer.
- Step 3: Move WSL checks into a port.
- Step 4: Ensure resolver uses ports not subprocess calls.
- Step 5: Update `validate_and_resolve_workspace` to call use case.
- Step 6: Update all callers to use `ResolveWorkspace`.

### Test plan
- Unit tests for resolution priority rules.
- Tests for `.scc.yaml` detection when git absent.
- Tests for auto‑detected suspicious behavior.
- Tests for explicit path with allow‑suspicious flag.
- Tests for WSL warning response via `InteractionRequest`.
- Tests for mount root expansion for worktrees.

### Risks and mitigations
- Risk: auto‑detection might change priority order.
- Mitigation: add characterization tests before refactor.
- Risk: path normalization changes mount root.
- Mitigation: reuse existing worktree tests.

### Acceptance criteria
- Only one resolver entry point is used in codebase.
- Workspace warnings and prompts fully testable.
- No UI operations occur inside workspace resolution logic.
- All workspace‑related tests pass unchanged.

### Non‑goals
- Do not change CLI flags or output copy.
- Do not change smart start precedence unless tests require.

### PR breakdown (safe increments)
- PR A: introduce workspace use case interfaces and tests.
- PR B: migrate detection logic to use cases.
- PR C: replace command‑layer validation with use case calls.

## Blocker 4: Sessions Persistence + Formatting (`scc_cli/sessions.py`)
### Current flow in detail
- Session records are stored in JSON under a local store.
- `list_recent` loads JSON and formats relative times.
- `record_session` and `update_session_container` write to disk.
- Sorting and filtering uses `dict[str, Any]` structures.
- Formatting logic (`format_relative_time`) lives in the same module.
- Consumers include `commands/launch/flow.py` and session commands.
- Session output is used directly in UI rendering.

### Why this is a blocker
- Persistence and formatting are mixed in one module.
- Dict‑based session structures hide schema changes.
- Hard to test without filesystem IO.
- Difficult to switch storage formats in the future.
- Reuse across modules increases coupling to storage shape.

### Desired target state
- Session persistence behind a `SessionStore` port.
- Typed `SessionRecord`/`SessionSummary` models in application layer.
- Formatting moved to a presenter or UI helper module.
- `SessionService` use case exposes list/resume/prune operations.

### Proposed modularization
- Create `scc_cli/ports/session_store.py` with minimal methods.
- Create `scc_cli/adapters/session_store_json.py` for current storage.
- Create `scc_cli/application/sessions.py` with typed models.
- Move relative‑time formatting into `ui/time_format.py`.
- Update command modules to use `SessionService` outputs.

### Suggested interfaces and data shapes
- `SessionRecord` dataclass with typed fields.
- `SessionSummary` dataclass for list views.
- `SessionFilter` object with `team`, `all_teams`, `limit`.
- `SessionListResult` with list + count + timestamps.
- `SessionUpdateResult` with success status and message.

### Extraction steps
- Step 1: Create `SessionStore` port and JSON adapter.
- Step 2: Create `SessionService` use case for list and record.
- Step 3: Move `format_relative_time` into UI helper.
- Step 4: Update command modules to use `SessionService`.
- Step 5: Remove dict‑based manipulation in commands.

### Test plan
- Unit tests for `SessionService.list_recent` using fake store.
- Unit tests for `SessionService.record_session` update path.
- Unit tests for relative‑time formatting helper.
- Integration tests for `scc sessions` output unchanged.
- Tests for `session prune` logic with fake data.

### Risks and mitigations
- Risk: session storage format changes break existing sessions.
- Mitigation: keep adapter backwards compatible and add migration test.
- Risk: UI output changes due to new models.
- Mitigation: lock output via characterization tests.

### Acceptance criteria
- Session storage encapsulated behind a port.
- Command modules do not read JSON session files directly.
- Session list and resume flows remain behavior‑identical.

### Non‑goals
- Do not alter session storage file format.
- Do not change CLI output or flags.

### PR breakdown (safe increments)
- PR A: add session store port + adapter + unit tests.
- PR B: migrate list and record flows to use case.
- PR C: swap UI formatting to shared helper.

## Blocker 5: Support Bundle IO + Doctor Coupling
### Current flow in detail
- `support_bundle.py` performs IO directly with `Path` and `zipfile`.
- It reads config and org config via `config.load_user_config` and `load_cached_org_config`.
- It calls `doctor.run_doctor` to collect diagnostic data.
- It builds JSON manifest and writes ZIP file.
- `commands/support.py` mixes output selection and bundle creation.
- JSON output uses `build_envelope` in command layer.

### Why this is a blocker
- IO‑heavy code sits in one module with hidden dependencies.
- No port for filesystem or clock makes tests harder.
- Command module cannot be reused for other UIs.
- Doctor coupling makes bundle generation harder to isolate.
- Redaction logic is not easily tested without IO.

### Desired target state
- Support bundle generation is a use case with explicit dependencies.
- Filesystem and clock are ports for deterministic tests.
- Doctor data injected through a `DoctorRunner` port.
- Command layer only handles output formatting and CLI flags.

### Proposed modularization
- Create `scc_cli/application/support_bundle.py` use case.
- Port: `DoctorRunner` for `run_doctor` result.
- Port: `ArchiveWriter` (zip writer) for output packaging.
- Use case returns `SupportBundleData` with redaction options.
- Command wraps `SupportBundleData` into JSON envelope.

### Suggested interfaces and data shapes
- `SupportBundleRequest` (redact flags, workspace path, output path).
- `SupportBundleData` (system info, config, doctor results).
- `SupportBundleResult` (manifest data + optional zip path).
- `DoctorResult` interface with typed status details.

### Extraction steps
- Step 1: Move `build_bundle_data` into application use case.
- Step 2: Introduce `DoctorRunner` and `Filesystem` dependencies.
- Step 3: Add `ArchiveWriter` adapter around `zipfile`.
- Step 4: Update `support_bundle_cmd` to call use case.
- Step 5: Add unit tests for redaction and bundle assembly.

### Test plan
- Unit tests for redaction of secret keys.
- Unit tests for path redaction when enabled.
- Unit tests for doctor failure handling.
- Integration test for JSON output envelope unchanged.
- Use either in‑memory archive or temp dir for ZIP assertions.

### Risks and mitigations
- Risk: manifest schema drift.
- Mitigation: keep JSON tests in `tests/test_support_bundle.py`.
- Risk: performance regressions.
- Mitigation: keep existing zip writer implementation.

### Acceptance criteria
- Support bundle generation testable without real filesystem.
- Command layer only handles CLI flags and output routing.
- Doctor integration is injected and mockable.

### Non‑goals
- Do not change the bundle schema or redaction rules.
- Do not change CLI flags or JSON envelope structure.

### PR breakdown (safe increments)
- PR A: introduce use case and ports with tests.
- PR B: migrate command layer to use case.

## High‑Value Improvements (Beyond Blockers)
### HV1: Centralize edge JSON mapping (`scc_cli/presentation/json/`)
- Problem: JSON mapping is scattered across commands.
- Approach: add `presentation/json/` with `launch_json.py`, `worktree_json.py`, `sessions_json.py`, `support_json.py`.
- Benefit: one place to evolve JSON schemas and avoid drift.
- Guardrail: commands import mapping helpers; application never does.

### HV2: Typed org config models
- Problem: `application/profiles.py` and `compute_effective_config.py` use `dict[str, Any]`.
- Why it matters: schema drift and hidden invariants increase risk.
- Approach: introduce minimal normalized typed models (not full schema).
- Step 1: define `NormalizedOrgConfig` and `NormalizedTeamConfig`.
- Step 2: parse/validate once at config load edges.
- Step 3: replace raw dicts in application layer.
- Guardrail: avoid “typed model explosion” by modeling only what is used.

### HV3: Dashboard session view models
- Problem: `application/dashboard.py` uses `dict[str, Any]` sessions.
- Approach: reuse `SessionSummary` from sessions use case.
- Benefit: reduces duplicate session parsing and key access.
- Guardrail: keep UI output unchanged.

### HV4: Managed marketplace state fully ported
- Problem: optional filesystem port with fallback to direct `Path` IO.
- Approach: always pass `Filesystem` dependency.
- Benefit: deterministic tests and consistent behavior.
- Guardrail: preserve existing file format.

### HV5: Dependency installation port
- Problem: direct calls to `deps.auto_install_dependencies` in commands.
- Approach: create `DependencyInstaller` port with minimal interface.
- Benefit: improved testability and clearer boundaries.
- Guardrail: do not over‑model package managers.

### HV6: Sandbox runtime lifecycle split (conditional)
- Problem: `SandboxRuntime` may grow to include multiple unrelated responsibilities.
- Approach: split into `SandboxProvisioner` and `SandboxSessions` only if needed.
- Benefit: clearer responsibilities when interface grows.
- Guardrail: do not split unless interface expansion demands it.

### HV7: Cross‑module time formatting
- Problem: time formatting duplicated in wizard and sessions.
- Approach: create shared `ui/time_format.py` helper.
- Benefit: consistent output and simpler tests.
- Guardrail: keep output strings identical.

### HV8: Logging boundary (no Logger port)
- Problem: application sometimes prints directly or relies on UI.
- Approach: allow stdlib logging in application, forbid `console.print` there.
- Benefit: simple boundary without extra abstraction.
- Guardrail: rely on `caplog` for tests, no custom Logger port.

### HV9: Marketplace resolve side effects
- Problem: resolution and merging logic are intertwined.
- Approach: split algorithmic functions from IO functions.
- Benefit: simpler unit tests and fewer side‑effects.
- Guardrail: keep outputs identical and use characterization tests.

### HV10: Optional dependency import discipline
- Problem: optional imports can leak into non‑adapter modules.
- Approach: enforce that heavy libs import only in adapters.
- Benefit: reduces import‑time side effects and improves testability.
- Guardrail: update boundary tests if needed.

## Guardrails and Invariants (Recommended)
### G1: Filesystem contract coverage
- Ensure `tests/contracts/test_filesystem_contract.py` covers atomic writes, mkdirp, UTF‑8, and round‑trip reads.
- Expand if new filesystem behavior is introduced.

### G2: Architectural invariants tests
- Enforce application layer cannot import `rich`, `typer`, `subprocess`, `docker`, `requests`, or `zipfile`.
- Enforce application layer avoids `Path.read_text`/`write_text` and `print`.
- Prefer a small AST‑based pytest test to keep it fast.

### G3: InteractionRequest schema tests
- Add tests asserting prompt labels, hotkeys, and BACK semantics remain stable.
- Ensure wizard flows reuse shared request types.

### G4: Complexity budget (optional)
- Set maximum file size / function size guardrails for commands modules.
- Start with a manual checklist; automate later if needed.

## Nice‑to‑Have Improvements
### N1: UI wizard cleanup
- Extract list‑item creation helpers for wizard screens.
- Add unit tests for list item ordering and labels.
- Keep keybind hints unchanged.

### N2: Launch render consolidation
- Group launch render helpers under a presenter module.
- Keep `render.py` limited to `LaunchOutput` rendering.
- Reduce scattered `console.print` calls.

### N3: Shared error panel wrappers
- Centralize repeated “warning panel” patterns.
- Reduce duplication and inconsistent styling.

### N4: Session prune use case
- Move prune logic from `session_commands.py` to use case.
- Provide a result summary for UI and JSON output.

### N5: Worktree helper expansion
- Expand `_helpers.py` for shared formatting and filtering.
- Add unit tests for new helpers.

### N6: Support bundle redaction utils
- Extract `redact_secrets` and `redact_paths` to utilities.
- Add unit tests for redaction logic.

### N7: Git safety logic boundary
- Extract git safety prompts into a use case.
- Use `InteractionRequest` for confirm prompts.

### N8: Replace magic strings for team filters
- Replace `__all__` sentinel strings with enum/constants.
- Reduce accidental misuse in filters.

### N9: Config store port
- Add `ConfigStore` port for user/org config access.
- Reduce direct calls to `config.load_user_config` in commands.

### N10: Environment access helper
- Add small helper or port for `os.environ` lookups.
- Improve testability for environment‑dependent logic.

### N11: Marketplace cache maintenance
- Add use case for cache cleanup with explicit result objects.
- Reduce IO in command layer.

### N12: Minimal docs updates
- Update internal docs for new use cases and ports.
- Keep documentation co‑located with modules.

## Suggested Sequence and Milestones (Updated Order)
### Phase 0: Guardrails and cross‑cutting decisions
- Define and document the error strategy (use cases raise typed `SCCError`).
- Define stable `InteractionRequest` schema and add characterization tests.
- Add `scc_cli/presentation/json/` mapping helpers for JSON outputs.
- Add architectural invariants tests (no UI/IO imports in application).
- Confirm filesystem contract coverage (atomic writes, mkdirp, UTF‑8).
- Optional: define a complexity budget for command modules.

### Phase 1: Sessions store + view models
- Add `SessionStore` port and JSON adapter.
- Add `SessionRecord` and `SessionSummary` models.
- Add `SessionService` use case.
- Update session commands and dashboard to use models.
- Add unit tests for service and formatting.
- Success: session commands are thin wrappers.

### Phase 2: Workspace resolver unification
- Create `application/workspace` resolver and validator.
- Merge `detect_workspace_root` logic into resolver.
- Replace command validation with use case output.
- Add characterization tests for precedence rules.
- Success: all workspace resolution flows use one entry point.

### Phase 3: Worktree use cases
- Introduce `application/worktree` use cases.
- Add ports for git worktree operations and dependency install.
- Migrate `list` and `switch` flows first.
- Migrate `create`, `select`, and `enter` flows next.
- Add characterization tests for shell output.
- Success: worktree commands are thin wrappers.

### Phase 4: Launch flow split
- Introduce wizard state machine with `InteractionRequest`.
- Extract session selection and resume logic into use case.
- Move personal profile decisions into application use case.
- Move output messages into `LaunchOutput` view model.
- Keep JSON mapping in command layer.
- Success: `flow.py` becomes orchestration glue.

### Phase 5: Support bundle use case
- Add `support_bundle` use case + ports.
- Add archive writer adapter.
- Update support command to call use case.
- Add unit tests with in‑memory or temp‑dir archive checks.
- Success: no IO in command layer beyond output.

### Phase 6: Typed config models
- Add normalized typed config models.
- Parse and validate at config load edges.
- Replace dict‑based access in application layer.
- Add tests for model validation and mapping.
- Success: fewer `dict[str, Any]` in use cases.

### Phase 7: Cleanup and polish
- Consolidate time formatting.
- Replace magic strings with enums/constants.
- Add small refactor helpers and docs.
- Update boundary tests if new layers appear.
- Success: only edge modules print; core is pure.

## Implementation Tasks and Phases (Checklist)
### Phase 0 — Guardrails and Cross‑Cutting Decisions
- [x] Boundary tests enforce application/adapters separation.
- [x] Contract tests exist for runtime/git/agent/remote/clock/filesystem.
- [x] Characterization tests cover JSON/start/marketplace flows.
- [ ] Add `scc_cli/presentation/json/` mapping helpers and route command JSON through them.
- [ ] Decide and document the error strategy (use cases raise typed `SCCError`).
- [ ] Define `InteractionRequest` schema (Confirm/Select/Input).
- [ ] Add InteractionRequest characterization tests (labels/back behavior).
- [ ] Add architectural invariants tests for application imports and IO.
- [ ] Optional: add complexity budget checks (file/function size).

### Phase 1 — Sessions store + view models
- [ ] Introduce `SessionStore` port and JSON adapter.
- [ ] Add `SessionRecord` and `SessionSummary` models.
- [ ] Implement `SessionService` use case.
- [ ] Update session commands and dashboard to use models.
- [ ] Add unit tests for list/record/prune flows.
- [ ] Move relative‑time formatting to `ui/time_format.py`.

### Phase 2 — Workspace resolver unification
- [ ] Create `application/workspace` resolver + validator.
- [ ] Merge `detect_workspace_root` logic into resolver.
- [ ] Replace command validation with use case outputs.
- [ ] Add characterization tests for resolution precedence.
- [ ] Add tests for suspicious/WSL warnings via `InteractionRequest`.

### Phase 3 — Worktree use cases
- [ ] Add `application/worktree` package with use cases.
- [ ] Extend `GitClient` for worktree/branch queries.
- [ ] Implement `SelectWorktree` fuzzy match logic.
- [ ] Implement `SwitchWorktree` and `EnterWorktreeShell` (return `ShellCommand`).
- [ ] Migrate list/select/switch/create/enter commands to use cases.
- [ ] Add characterization tests for shell output.

### Phase 4 — Launch flow split
- [ ] Build wizard state machine with `InteractionRequest`.
- [ ] Extract session selection/resume into use case.
- [ ] Move personal profile decisions into application use case.
- [ ] Create `LaunchOutput` view model and UI renderer.
- [ ] Map `LaunchResult` to JSON via presentation helpers.
- [ ] Reduce `flow.py` to orchestration glue.

### Phase 5 — Support bundle use case
- [ ] Add support bundle use case with `DoctorRunner` and `ArchiveWriter`.
- [ ] Move redaction logic into testable helpers.
- [ ] Update support command to use use case.
- [ ] Add unit tests with in‑memory or temp‑dir archive checks.

### Phase 6 — Typed config models
- [ ] Define normalized typed config models used by use cases.
- [ ] Parse/validate at config load edges.
- [ ] Replace dict access in application layer.
- [ ] Add validation and mapping tests.

### Phase 7 — Cleanup and polish
- [ ] Consolidate time formatting in `ui/time_format.py`.
- [ ] Replace magic strings with enums/constants.
- [ ] Add config store port for user/org config access.
- [ ] Expand guardrails if new layers appear.
- [ ] Update docs for new modules and ports.

## Definition of 10/10 Maintainability
- Commands are thin wrappers with no business logic.
- Application use cases are fully testable with fakes.
- IO happens only in adapters or UI/CLI edges.
- Workspace resolution has one authoritative implementation.
- Sessions persistence is typed and port‑based.
- Worktree flows are use‑case driven and deterministic.
- Launch wizard is a state machine with explicit transitions.
- InteractionRequest schema is stable and tested.
- JSON mapping is centralized in `presentation/json` and stays at the edges.
- Error strategy is consistent (use cases raise typed `SCCError`).
- Architectural invariants tests prevent UI/IO imports in application.
- Filesystem contract tests enforce atomic writes and UTF‑8.
- Logging uses stdlib logging only in application.
- Tests cover key behavior and prevent regressions.

## Review Checklist for Next Agent
- Verify no application modules import `ui/` or `commands/`.
- Verify application modules avoid `rich`, `typer`, `subprocess`, and direct `Path.read_text`.
- Verify adapters remain the only place for external libraries.
- Verify `bootstrap.py` is the only place composing adapters.
- Verify JSON mapping uses `presentation/json` helpers and stays at edges.
- Verify InteractionRequest schema is reused and tested for labels/BACK semantics.
- Verify error strategy is consistent (use cases raise `SCCError`).
- Verify filesystem contract tests cover atomic writes and UTF‑8.
- Verify new use cases have unit tests with fakes.
- Verify JSON output matches prior envelopes.
- Verify interactive flows preserve key bindings and labels.
- Verify warnings and prompts preserve exact text when expected.
- Verify new ports are mypy‑checked and used consistently.
- Verify command modules are thin wrappers.

## Appendix: File References
- `scc_cli/commands/launch/flow.py`
- `scc_cli/commands/launch/workspace.py`
- `scc_cli/services/workspace/resolver.py`
- `scc_cli/services/git/core.py`
- `scc_cli/commands/worktree/worktree_commands.py`
- `scc_cli/commands/worktree/session_commands.py`
- `scc_cli/sessions.py`
- `scc_cli/support_bundle.py`
- `scc_cli/commands/support.py`
- `scc_cli/application/start_session.py`
- `scc_cli/application/dashboard.py`
- `scc_cli/application/profiles.py`
- `scc_cli/application/compute_effective_config.py`
- `scc_cli/marketplace/managed.py`
- `scc_cli/commands/launch/render.py`
- `scc_cli/ui/wizard.py`
- `scc_cli/ui/dashboard/orchestrator.py`
- `scc_cli/bootstrap.py`
- `scc_cli/ports/`
- `scc_cli/adapters/`
