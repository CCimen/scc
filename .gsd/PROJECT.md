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
Delivered portable OCI sandbox backend (no Docker Desktop dependency) with topology-enforced web egress via Squid proxy sidecar, provider destination validation, operator diagnostics, and docs truthfulness guardrails. +178 net new tests (3464 total).

### M004 — Cross-Agent Runtime Safety ✅
Delivered shared safety policy and verdict engine, runtime wrapper baseline, provider-specific safety adapters, fail-closed policy loader, safety audit reader, doctor safety-policy check, and `scc support safety-audit` CLI command. +289 net new tests (3790 total).

### M005 — Architecture Quality, Strictness, And Hardening ✅
Delivered comprehensive architecture quality: module decomposition (15 files split), typed governed-artifact model hierarchy, provider-neutral bundle resolution/rendering pipeline, 100% branch coverage on pipeline modules, D023 portable artifact rendering, and 18 truthfulness guardrail tests. Final: 4486 tests.

### M006 — Provider Selection UX and End-to-End Codex Launch ✅
SCC became a genuine multi-provider runtime. Users choose Claude or Codex via config or CLI flag (`scc provider show/set`, `scc start --provider codex`), validated against org/team policy. Provider identity flows through container naming, volume naming, session identity, machine-readable outputs (dry-run JSON, support bundle, session list). CodexAgentRunner adapter with Codex-specific image, settings, and argv. Provider-aware branding ("Sandboxed Coding CLI"), doctor image check with exact build commands, and 16 coexistence proofs. 153 new tests, 4643 total, zero regressions.

### M007 — Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup ✅
Eliminated Claude assumptions from shared/core/operator paths. ProviderRuntimeSpec replaces 5 scattered dicts. Settings serialization is provider-owned (rendered_bytes, not dict). Config layering is provider-native (Claude home-scoped, Codex workspace-scoped). Unknown providers fail closed. Auth readiness is adapter-owned via auth_check() on AgentProvider. Runtime permission normalization. Config freshness guarantee on every fresh launch. Doctor is provider-aware with --provider flag and categorized output. Core constants stripped to product-level only. 32 truthfulness guardrail tests. 166 net new tests, 4820 total.

### M008 — Cross-Flow Consistency, Reliability, and Maintainability Hardening ✅
Consolidated five duplicated launch preflight sequences into one shared module. S01: shared preflight module with typed LaunchReadiness model, flow.py and flow_interactive.py migrated, 7 structural guardrail tests. S02: auth vocabulary truthfulness (three-tier distinction), Docker Desktop removed from active paths, provider adapter dispatch consolidated via shared get_agent_provider() helper, 15 new guardrail tests. S03: 106 edge-case and regression-guard tests covering workspace persistence, resume-after-drift, setup idempotency, and error message quality. Auth bootstrap exception wrapping. Legacy Docker Desktop module documentation. 294 net new tests (5114 total), zero regressions.

## Next milestone order
1. ~~M001 — Provider-Neutral Launch Boundary~~ ✅
2. ~~M002 — Provider-Neutral Launch Pipeline~~ ✅
3. ~~M003 — Portable Runtime And Enforced Web Egress~~ ✅
4. ~~M004 — Cross-Agent Runtime Safety~~ ✅
5. ~~M005 — Architecture Quality, Strictness, And Hardening~~ ✅
6. ~~M006 — Provider Selection UX and End-to-End Codex Launch~~ ✅
7. ~~M007 — Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup~~ ✅
8. ~~M008 — Cross-Flow Consistency, Reliability, and Maintainability Hardening~~ ✅

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated. Advanced through all eight milestones.

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (303 files, 0 issues)
- `uv run pytest -q` ✅ (5114 passed, 23 skipped, 2 xfailed)
- Zero files in src/scc_cli/ exceed 1100 lines
- One file in 800–1100 zone justified (compute_effective_config.py at 852, 93% coverage)

## Known deferred items
- Wizard cast cleanup (23 casts in wizard.py/flow_interactive.py) — deferred per D018
- Legacy module coverage (docker_sandbox_runtime 30%, overall 74%) — deprioritized per D017/D021 user overrides
- Portable MCP stdio transport support — requires additional source metadata
- Live bundle registry integration — renderers write metadata references only
- Dashboard provider switching TUI feature (dashboard 'a' key)
- Container labels (scc.provider=<id>) for external tooling discovery
- Image build/push pipeline for scc-agent-codex
- Podman support on the same SandboxRuntime contracts
- `scc auth login/status/logout` commands — model supports them via auth_check()
- Fine-grained volume splitting (auth-only vs ephemeral) for enterprise data-retention (D036)
- start_claude parameter rename to start_agent in worktree_commands.py (deferred from M008/S01)
- WorkContext.provider_id threading through _record_session_and_context (deferred from M008/S01)
- orchestrator_handlers.py and worktree_commands.py full migration to shared preflight ensure_launch_ready()

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
- **Launch preflight is shared via commands/launch/preflight.py (D046):** resolve_launch_provider() → collect_launch_readiness() → ensure_launch_ready() is the canonical three-function split. Pure decision logic separated from side effects. Currently adopted by flow.py and flow_interactive.py; remaining sites (orchestrator_handlers, worktree_commands) are tracked for migration.
- Renderers return fragment dicts for caller-owned merge — they do not write shared config files (settings.local.json, .mcp.json) directly.
- **ProviderRuntimeSpec** (frozen dataclass in `core/contracts.py`) is the single source of truth for provider runtime details. **PROVIDER_REGISTRY** in `core/provider_registry.py` maps provider_id → spec.
- Unknown, forbidden, or unavailable providers fail closed in active launch logic — never silently fall back to Claude.
- **AgentRunner owns settings serialization format**: `build_settings()` produces `rendered_bytes: bytes` + `path` + `suffix`, not dict.
- **Product name is 'SCC — Sandboxed Coding CLI'** consistently across README, pyproject.toml, CLI branding, D045, and all user-facing surfaces.
- **Auth vocabulary is three-tier truthful**: 'auth cache present' (file exists), 'image available' (container image present), 'launch-ready' (both). No surface uses 'connected' or standalone 'ready' to describe partial state.
- **Docker Desktop references** are confined to docker/, adapters/, core/errors.py, and doctor/ layers only. Active user-facing commands/ paths use 'Docker' or 'container runtime'.
- **Provider adapter dispatch** uses a shared `get_agent_provider(adapters, provider_id)` helper in dependencies.py — no hardcoded per-site dispatch dicts.
- **40+ guardrail tests** across test_docs_truthfulness.py, test_auth_vocabulary_guardrail.py, test_lifecycle_inventory_consistency.py, and test_launch_preflight_guardrail.py mechanically prevent regression.
- **Auth bootstrap exception wrapping** in ensure_provider_auth: raw exceptions from bootstrap_auth() become ProviderNotReadyError with actionable guidance; already-typed ProviderNotReadyError passes through unchanged.
