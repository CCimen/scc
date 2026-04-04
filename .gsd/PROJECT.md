# Sandboxed Coding CLI (SCC)

## What the project is
SCC is a governed runtime for coding agents. It lets organizations run approved agents inside portable sandboxes with explicit policy, team-level configuration, safer defaults, and runtime-enforced controls that are explainable to security reviewers.

## What the project is not
- not a new general-purpose coding agent
- not a forever-Claude-only wrapper
- not a Docker Desktop-only product
- not a fake security story built on advisory naming
- not a proprietary skills ecosystem

## Current v1 product target
The v1 target is a clean architecture on top of `scc-sync-1.7.3` that supports Claude Code and Codex through the same provider-neutral core, portable OCI runtimes, enforced web egress, and a shared runtime safety engine.

## Strategic success condition
A security or platform team can approve SCC because its governance model, runtime enforcement, and diagnostics are understandable and inspectable, while developers can switch providers and team contexts without rebuilding their world. The implementation should also become easier to change over time, not more brittle.

## Cross-cutting engineering priority
- Maximize maintainability, clean architecture, and clean code while delivering milestones.
- Prefer smaller cohesive modules, typed seams, and composition-root boundaries over growing central orchestrators.
- When a slice touches a large or fragile file, plan the smallest safe extraction that improves testability and future changeability.
- Pair refactors with characterization or contract tests so maintainability work stays measurable.

## Milestone history

### M001 — Provider-Neutral Launch Boundary ✅
Established typed contracts (core/contracts.py), AgentProvider protocol, and provider-neutral seam for launch, runtime, network, safety, and audit planning.

### M002 — Provider-Neutral Launch Pipeline ✅
Made AgentProvider and AgentLaunchSpec part of the real launch path. Claude settings are adapter-owned. Codex is a first-class provider. Preflight validation, durable JSONL audit sink, and application-owned support-bundle converged. Launch wizard resume extracted to typed helpers.

### M003 — Portable Runtime And Enforced Web Egress ✅
Delivered portable OCI sandbox backend (no Docker Desktop dependency) with topology-enforced web egress via Squid proxy sidecar, provider destination validation, operator diagnostics, and docs truthfulness guardrails. +178 net new tests (3464 total). Key deliverables:
- RuntimeProbe protocol as canonical detection surface
- OciSandboxRuntime using docker create/start/exec
- Three-layer egress enforcement: pure policy → infrastructure adapter → runtime integration
- Provider destination registry → SandboxSpec → egress plan pipeline
- Doctor check for runtime backend, support-bundle effective egress section
- 5 docs-truthfulness guardrail tests

### M004 — Cross-Agent Runtime Safety ✅
Delivered shared safety policy and verdict engine, runtime wrapper baseline, provider-specific safety adapters, fail-closed policy loader, safety audit reader, doctor safety-policy check, and `scc support safety-audit` CLI command. +289 net new tests (3790 total across S01–S04).

### M005 — Architecture Quality, Strictness, And Hardening (active)
**S01 complete.** Established quantitative maintainability baseline (272-line audit, 153-line defect catalog) and 315 characterization + boundary tests protecting all top split targets before S02 surgery.

**S02 complete.** Decomposed all 15 HARD-FAIL/MANDATORY-SPLIT files below 800 lines, repaired 3 architecture boundary violations (application→docker, core→marketplace, docker→presentation), all 4079 tests passing. Key deliverables:
- 15 oversized modules split into ~30 focused files across all layers
- 3 boundary violations eliminated via DI, ContainerSummary boundary type, and logging replacement
- Zero HARD-FAIL files remaining in src/scc_cli/
- Patterns established: re-export residual modules, Callable DI for boundary repair, late-bound module lookup for test-patch compat, deferred imports for circular deps

**Override gate (active):** Before S03+ implementation, S03-S06 must be replanned to incorporate the governed-artifact/team-pack architecture (D-018–D-020, D017, specs/03, specs/06). Do not proceed with generic S03 strict-typing cleanup.

Remaining: S03 (governed-artifact/team-pack typed models and config flow), S04 (renderer hardening and fail-closed cleanup), S05 (critical-path coverage), S06 (guardrails/diagnostics/docs truthfulness/validation).

## Next milestone order
1. ~~M001 — Provider-Neutral Launch Boundary~~ ✅
2. ~~M002 — Provider-Neutral Launch Pipeline~~ ✅
3. ~~M003 — Portable Runtime And Enforced Web Egress~~ ✅
4. ~~M004 — Cross-Agent Runtime Safety~~ ✅
5. **M005 — Architecture Quality, Strictness, And Hardening** (active — S01 ✅, S02 ✅, S03–S06 remaining — must replan before implementation)

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated by M002/S05. Advanced by M003, M004/S01–S04, M005/S01 (baseline + characterization tests), and M005/S02 (all 15 decompositions + 3 boundary repairs complete).

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (Success: no issues found in 284 source files)
- `uv run pytest --rootdir "$PWD" -q` ✅ (4079 passed, 23 skipped, 3 xfailed, 1 xpassed)
- `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q` ✅ (315 passed)
- Zero files in src/scc_cli/ exceed 800 lines

## Key architecture invariants
- `bootstrap.py` is the sole composition root for adapter symbols consumed outside `scc_cli.adapters`.
- `AgentLaunchSpec.env` stays empty for file-based providers; provider config travels via `artifact_paths`.
- The canonical provider-adapter characterization shape is: capability metadata, clean-spec, settings-artifact, and env-is-clean.
- Adding a provider to `DefaultAdapters` still requires the same four touch points: adapter file, bootstrap wiring, fake adapters factory, and inline test constructions.
- Provider-core destination validation belongs before launch, not as a runtime surprise.
- RuntimeProbe protocol is the canonical detection surface for runtime capabilities; no consumer outside the adapter layer should call docker.check_docker_available() directly.
- Bootstrap probes runtime at construction time and selects OciSandboxRuntime or DockerSandboxRuntime based on preferred_backend.
- OciSandboxRuntime is imported only in bootstrap.py; application layer uses SandboxRuntime protocol.
- Enforced web-egress uses internal Docker network + dual-homed Squid proxy sidecar as the hard enforcement boundary (D014).
- Safety engine is provider-neutral: DefaultSafetyEngine in core orchestrates shell tokenizer + git rules + network tool rules. Fail-closed semantics.
- SafetyPolicy loader is fail-closed: any parse failure → default block policy. Uses raw org config (not NormalizedOrgConfig).
- Provider safety adapters are pure UX/audit wrappers with zero verdict logic — the engine is the single source of safety truth.
- Import boundary guard (test_import_boundaries.py) mechanically enforces layer separation via AST scanning.
- Characterization tests use mock adapters from tests/fakes/ to isolate pure application logic from infrastructure.
- Decomposed modules use re-export residuals: original module re-exports all extracted symbols, preserving backward-compatible import paths.

## Immediate next focus
- **Replan S03-S06 before implementation.** Per user override, S03-S06 must be replanned to explicitly incorporate the governed-artifact/team-pack architecture (D-018–D-020, D017, specs/03, specs/06) before any further implementation.
  - S03 must land typed GovernedArtifact/ArtifactBundle/ArtifactRenderPlan models and typed config flow
  - S04 must harden fetch/render/merge/install failure handling for the provider-native renderer pipeline
  - S06 must validate docs/diagnostics truthfulness for the team-pack model
  - One approved SCC team-pack source is canonical; team config references bundle IDs; split provider-neutral planning from provider-native renderers
