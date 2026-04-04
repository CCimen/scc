# M005: Architecture Quality, Strictness, And Hardening

## Execution Order
M005 is the final quality-bar milestone for the current v1 arc and should run after M004 completes. M002-M004 may perform narrow maintainability extractions only when they directly enable active feature work in touched files. They should not pull the full cross-cutting M005 cleanup forward.

## Vision
Turn the completed v1 feature set into a highly maintainable, strongly typed, well-tested, and robust codebase that is easy to understand, modify, and extend without reintroducing provider leakage, architectural drift, or misleading operational behavior.

## Current Audit Baseline
- 58 Python files exceed 300 lines; 23 exceed 700, 15 exceed 800, 8 exceed 1000, and 3 exceed 1100.
- The highest-risk large-file clusters are in `commands/`, `ui/`, `application/`, `marketplace/`, `docker/`, and `core/`.
- The repo still contains 368 `dict[str, Any]` references and 49 `cast()` calls, concentrated in config, launch, marketplace, and UI interaction flows.
- There are 36 `except Exception:` sites, multiple unchecked `subprocess.run(...)` paths, and mutable module-level defaults such as `DEFAULT_SAFETY_NET_POLICY`.
- Quality guardrails are not yet trustworthy because existing `xfail`s still mask file-size, function-size, and test-isolation failures.
- Current coverage gaps remain severe in high-risk modules: `adapters/docker_sandbox_runtime.py` 22%, `docker/launch.py` 54%, `core/error_mapping.py` 74%, `ui/settings.py` 0%, `ui/dashboard/orchestrator.py` 6%, `commands/reset.py` 7%, `commands/profile.py` 9%, `docker/credentials.py` 8%.

## Success Criteria
- Every module currently above 1100 lines is decomposed below the hard guardrail threshold.
- Every module currently above 800 lines is either decomposed below 800 lines or explicitly retained with single-responsibility justification in milestone validation.
- The top-20 mandatory split targets are decomposed or retired into smaller cohesive modules with clear ownership.
- Internal control-plane, launch-planning, and policy-merging flows stop accepting or returning raw `dict[str, Any]`; raw dictionaries remain only at parsing, serialization, or presentation boundaries.
- The generic interaction pipeline no longer depends on widespread `cast(answer.value, ...)` patterns in launch and wizard flows.
- Direct runtime/backend imports from core, application, commands, and UI are removed or isolated behind explicit ports/adapters.
- Silent error swallowing, mutable global defaults, and unchecked subprocess execution are eliminated from maintained production paths.
- File-size and function-size guardrails pass without `xfail`, and transitional Ruff/mypy relaxations are removed or reduced to narrow documented exceptions.
- Critical seams achieve meaningful high coverage: `docker_sandbox_runtime.py` at least 90%, `docker/launch.py` at least 80%, policy/planning/error/audit paths 95-100%, and overall coverage above 80%.
- Docs and diagnostics remain truthful about provider, runtime, network, safety, and enforcement posture.
- Exit gate passes: `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pyright src/scc_cli`, and `uv run pytest --cov --cov-branch`.

## Slice Overview
| ID | Slice | Tasks | Risk | Depends | Done | After this |
|----|-------|-------|------|---------|------|------------|
| S01 | Maintainability baseline and refactor queue | 4 | medium | — | ⬜ | Hotspots, mandatory split targets, boundary leaks, guardrail gaps, and characterization-test needs are ranked and explicit. |
| S02 | Decompose oversized modules and repair boundaries | 6 | high | S01 | ⬜ | Mandatory split targets are decomposed by domain, and cross-layer leaks/cycles are removed. |
| S03 | Typed config model adoption and strict typing cleanup | 5 | high | S02 | ⬜ | Internal config/policy flow is typed, interaction flows are generic end-to-end, and transitional typing relaxations are removed. |
| S04 | Error handling, subprocess hardening, and fail-closed cleanup | 5 | high | S02 | ⬜ | Silent failures are removed, subprocess handling is explicit, mutable defaults are frozen, and error surfaces align across CLI/JSON/audit. |
| S05 | Critical-path coverage elevation | 4 | high | S03,S04 | ⬜ | High-risk runtime, planning, and error paths have durable coverage with meaningful assertions. |
| S06 | Guardrails, diagnostics, docs, and milestone validation | 4 | medium | S02,S03,S04,S05 | ⬜ | Guardrails are live, docs are truthful, the full gate is green, and the milestone closes with no quality `xfail`s. |

## Slice Detail

### S01 — Maintainability Baseline And Refactor Queue
1. `T01` Produce a ranked hotspot inventory for all Python files over 300 lines, with a mandatory split set covering every file above 800 lines plus any smaller file that mixes layers or workflows.
2. `T02` Record the boundary-repair map: direct `docker` imports outside adapter/runtime seams, core-to-marketplace leakage, presentation/runtime coupling, and import cycles such as `docker.core <-> docker.launch`.
3. `T03` Catalog robustness debt: silent `except Exception` sites, unchecked subprocess calls, mutable module globals/defaults, sentinel-return error paths, and existing `xfail` quality tests.
4. `T04` Add or refresh characterization tests for the top split targets before deeper surgery, especially `commands/launch/flow.py`, `ui/dashboard/orchestrator.py`, `docker/launch.py`, and policy/config hotspots.

### S02 — Decompose Oversized Modules And Repair Boundaries
1. `T01` Split the launch-flow cluster: `commands/launch/flow.py`, `commands/launch/render.py`, `commands/launch/sandbox.py`, `application/launch/start_wizard.py`, and adjacent wizard helpers.
2. `T02` Split the dashboard/settings UI cluster: `ui/dashboard/orchestrator.py`, `ui/dashboard/_dashboard.py`, `ui/settings.py`, `ui/wizard.py`, `ui/git_interactive.py`, `ui/picker.py`, and `ui/keys.py`.
3. `T03` Split the commands cluster: `commands/team.py`, `commands/config.py`, `commands/profile.py`, `commands/reset.py`, `commands/admin.py`, and worktree command surfaces.
4. `T04` Split the application/control-plane cluster: `application/dashboard.py`, `application/worktree/use_cases.py`, `application/compute_effective_config.py`, `application/settings/use_cases.py`, and nearby orchestration helpers.
5. `T05` Split the marketplace/profile/config cluster: `marketplace/materialize.py`, `marketplace/team_fetch.py`, `marketplace/resolve.py`, `application/sync_marketplace.py`, `core/personal_profiles.py`, and `setup.py`.
6. `T06` Repair architecture boundaries as part of the splits: remove direct runtime/backend imports from core/application/commands/UI, break import cycles, and move provider/runtime-specific logic behind explicit ports/adapters.

### S03 — Typed Config Model Adoption And Strict Typing Cleanup
1. `T01` Adopt typed internal config models as the default control-plane shape for org, project, user, team, session, marketplace, and MCP data; raw dictionaries remain edge-only.
2. `T02` Eliminate raw-dict launch/config aliases such as `UserConfig: TypeAlias = dict[str, Any]` from launch, config, setup, validation, and policy-merging paths.
3. `T03` Make the interaction request/response flow generic end-to-end so launch and wizard code stop relying on repeated `cast(answer.value, ...)` recovery.
4. `T04` Remove transitional mypy relaxations, redundant casts, and broad `Any` flow in touched modules while keeping any remaining exceptions explicit and documented.
5. `T05` Centralize typed serialization boundaries so JSON envelopes and adapter persistence do not leak raw-dict shapes back into application logic.

### S04 — Error Handling, Subprocess Hardening, And Fail-Closed Cleanup
1. `T01` Remove silent error swallowing and replace sentinel-return fallbacks with explicit exceptions or result objects that callers must handle.
2. `T02` Harden subprocess usage through shared helpers or checked wrappers: return-code checking, stderr propagation, timeout policy, and domain-specific error mapping.
3. `T03` Freeze mutable module-level defaults and security-relevant globals, including safety-policy defaults and other shared mutable dictionaries.
4. `T04` Align exception taxonomy and rendering so CLI, JSON, and audit/event outputs remain category-stable and truthful.
5. `T05` Audit fail-closed behavior for policy, safety, runtime detection, and provider validation paths; ambiguous state must not degrade into permissive behavior.

### S05 — Critical-Path Coverage Elevation
1. `T01` Raise `adapters/docker_sandbox_runtime.py` coverage to at least 90% with port-level and adapter-level tests.
2. `T02` Raise `docker/launch.py` to at least 80% and `docker/credentials.py` materially upward with tests for resume, reuse, cleanup, safety-policy injection, and failure branches.
3. `T03` Push policy/planning/error/audit seams to 95-100% meaningful coverage: config merge, launch planning, provider validation, error mapping, and audit routing.
4. `T04` Extract decision-heavy logic out of poorly covered UI/command orchestrators where needed so coverage is earned through testable modules, not line-chasing snapshot glue.

### S06 — Guardrails, Diagnostics, Docs, And Milestone Validation
1. `T01` Remove quality `xfail`s from file-size, function-size, and isolation tests by fixing the underlying defects and making guardrails enforceable again.
2. `T02` Remove transitional Ruff ignore categories and reduce mypy overrides to narrow intentional cases, ideally tests only.
3. `T03` Run a final truthfulness pass on docs, JSON/human diagnostics, and operator-facing wording about provider, runtime, network, safety, and enforcement.
4. `T04` Validate the milestone against the success criteria with a before/after hotspot summary, an unresolved-risk register, and the full green verification gate.

## Parallelism
Inside M005, S03 and S04 can run in parallel after S02 because they focus on different failure modes. M005 itself should not run in parallel with M003 or M004 because those milestones still reshape the same launch/runtime/safety surfaces.
