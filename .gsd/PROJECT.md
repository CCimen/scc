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

### M005 — Architecture Quality, Strictness, And Hardening ✅
Delivered comprehensive architecture quality improvements across 7 slices:

**S01 (Baseline):** Quantitative maintainability baseline — 272-line audit, 153-line defect catalog, 315 characterization + boundary tests.

**S02 (Decomposition):** All 15 HARD-FAIL/MANDATORY-SPLIT files decomposed below 800 lines, 3 boundary violations repaired. Zero regressions.

**S03 (Typed Models):** Governed-artifact type hierarchy (GovernedArtifact, ArtifactBundle, ArtifactRenderPlan, ProviderArtifactBinding). NormalizedOrgConfig extended. Typed config pipeline adoption.

**S04 (Pipeline):** Provider-neutral bundle resolution → ArtifactRenderPlan → provider-native renderer pipeline. Claude and Codex renderers. Fail-closed error handling. Launch pipeline integration. 126 new tests.

**S05 (Coverage):** 100% branch coverage on all three pipeline modules (bundle_resolver, claude_renderer, codex_renderer). 44 cross-provider integration tests. 191 net-new tests.

**S06 (Diagnostics):** Team-pack diagnostics in doctor/support-bundle. 4 truthfulness fixes. All guardrail xfails removed. M005 validation passed.

**S07 (D023):** Portable artifact rendering — skills and MCP servers without provider bindings now renderable by both providers. PortableArtifact type, resolver population, both renderers extended. 23 new tests.

Final state: 4486 tests passing, ruff clean, mypy clean (289 files), zero files >1100 lines.

## Next milestone order
1. ~~M001 — Provider-Neutral Launch Boundary~~ ✅
2. ~~M002 — Provider-Neutral Launch Pipeline~~ ✅
3. ~~M003 — Portable Runtime And Enforced Web Egress~~ ✅
4. ~~M004 — Cross-Agent Runtime Safety~~ ✅
5. ~~M005 — Architecture Quality, Strictness, And Hardening~~ ✅

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated. Advanced through all five milestones. M005 final state: zero files >1100 lines (from 3), one justified file in 800–1100 zone, all import boundaries enforced (31 tests), typed config models adopted, governed-artifact pipeline at 99-100% coverage, file/function size guardrails passing without xfail, 18 truthfulness tests, D023 portable artifact rendering implemented, 4486 total tests.

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (Success: no issues found in 289 source files)
- `uv run pytest --rootdir "$PWD" -q` ✅ (4486 passed, 23 skipped, 2 xfailed)
- Zero files in src/scc_cli/ exceed 1100 lines
- One file in 800–1100 zone justified (compute_effective_config.py at 852, 93% coverage)

## Known deferred items from M005
- Wizard cast cleanup (23 casts in wizard.py/flow_interactive.py) — deferred per D018
- Legacy module coverage (docker_sandbox_runtime 30%, overall 73%) — deprioritized per D017/D021 user overrides
- Portable MCP stdio transport support — requires additional source metadata
- Live bundle registry integration — renderers write metadata references only

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
- Bundle resolver is pure core — zero imports from marketplace/ or adapters/.
- Provider renderers are adapter-owned — they may import from marketplace/ for materialization helpers but planning input is always ArtifactRenderPlan.
- Renderers return fragment dicts for caller-owned merge — they do not write shared config files (settings.local.json, .mcp.json) directly.
- Provider-native surfaces are intentionally asymmetric between Claude and Codex (D019).
- .scc-managed/ subdirectories avoid collisions with user-authored files.
- Bundle pipeline in launch flow uses fail_closed=True for resolution; errors captured on StartSessionPlan, not raised.
- Doctor checks report governed-artifact health: team context, bundle resolution, and catalog health.
- 18 truthfulness guardrail tests enforce accurate docs claims about provider capabilities and architecture.
- File/function size guardrails pass without xfail — all functions under 300 lines, all files under 1100 lines.
- Portable artifacts (skills, MCP servers) without provider bindings are renderable via PortableArtifact metadata in ArtifactRenderPlan (D023).
- Only SKILL and MCP_SERVER kinds qualify as portable — NATIVE_INTEGRATION always requires provider-specific bindings.
