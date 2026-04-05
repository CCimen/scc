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
SCC became a genuine multi-provider runtime. Users choose Claude or Codex via config or CLI flag (`scc provider show/set`, `scc start --provider codex`), validated against org/team policy. Provider identity flows through container naming, volume naming, session identity, machine-readable outputs (dry-run JSON, support bundle, session list). CodexAgentRunner adapter with Codex-specific image, settings, and argv. Provider-aware branding ("Sandboxed Code CLI"), doctor image check with exact build commands, and 16 coexistence proofs. 153 new tests, 4643 total, zero regressions.

### M007 — Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup (active)
S01 complete: ProviderRuntimeSpec registry replaces 5 scattered provider dicts. Settings path bug fixed (Codex no longer gets Claude's settings.json). Unknown providers fail closed with InvalidProviderError. +11 new tests, 4654 total.
S02 complete: Three Claude-named helpers renamed to provider-parameterized versions using registry. WorkContext carries provider_id with backward-compat serialization. Session list CLI shows Provider column. Sandbox records explicit provider_id='claude'. +21 new tests, 4675 total.
S03 complete: Doctor is provider-aware with --provider flag, categorized output (backend/provider/config/worktree/general), check_provider_auth() for auth readiness, and two typed provider errors (ProviderNotReadyError, ProviderImageMissingError). +43 new tests, 4718 total.
S04 complete: 9 Claude-specific constants localized from core/constants.py into 5 consumer modules. core/constants.py now holds only product-level values. profile.py documented as Claude-only. Guardrail test prevents re-introduction. +2 new tests, 4720 total.

## Next milestone order
1. ~~M001 — Provider-Neutral Launch Boundary~~ ✅
2. ~~M002 — Provider-Neutral Launch Pipeline~~ ✅
3. ~~M003 — Portable Runtime And Enforced Web Egress~~ ✅
4. ~~M004 — Cross-Agent Runtime Safety~~ ✅
5. ~~M005 — Architecture Quality, Strictness, And Hardening~~ ✅
6. ~~M006 — Provider Selection UX and End-to-End Codex Launch~~ ✅
7. **M007 — Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup** ← active (S01–S04 done, S05 remaining)

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated. Advanced through all seven milestones.

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅
- `uv run pytest --rootdir "$PWD" -q` ✅ (4720 passed, 23 skipped, 2 xfailed)
- Zero files in src/scc_cli/ exceed 1100 lines
- One file in 800–1100 zone justified (compute_effective_config.py at 852, 93% coverage)

## Known deferred items
- Wizard cast cleanup (23 casts in wizard.py/flow_interactive.py) — deferred per D018
- Legacy module coverage (docker_sandbox_runtime 30%, overall 73%) — deprioritized per D017/D021 user overrides
- Portable MCP stdio transport support — requires additional source metadata
- Live bundle registry integration — renderers write metadata references only
- Dashboard provider switching TUI feature (dashboard 'a' key)
- Container labels (scc.provider=<id>) for external tooling discovery
- Image build/push pipeline for scc-agent-codex
- Podman support on the same SandboxRuntime contracts

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
- Provider dispatch is request-scoped in `build_start_session_dependencies()`, not baked into the lru_cached DefaultAdapters singleton (D028). Shared infra stays cached; provider-specific adapters are selected per invocation.
- **ProviderRuntimeSpec** (frozen dataclass in `core/contracts.py`) is the single source of truth for provider runtime details (image ref, config dir, settings path, data volume, display name). **PROVIDER_REGISTRY** in `core/provider_registry.py` maps provider_id → spec. `get_runtime_spec()` is the fail-closed lookup — unknown providers raise `InvalidProviderError`. Replaces the 5 scattered dicts that existed in M006 (D029, D031, D034, D043).
- Unknown, forbidden, or unavailable providers fail closed in active launch logic — never silently fall back to Claude. Legacy Claude defaults are permitted only at migration/read boundaries (D032).
- AgentRunner owns settings serialization format: build_settings() produces rendered_bytes, not dict. OCI runtime writes bytes verbatim — no format assumption (D035).
- Launch argv is runner-owned via build_command(), not guessed by infrastructure. SandboxSpec.agent_argv must be populated; OCI runtime fails on empty argv (no Claude fallback).
- SCC launches Codex with --dangerously-bypass-approvals-and-sandbox inside the hardened SCC container; Codex's OS-level sandbox is redundant under SCC's container isolation (D033).
- V1 persistence model: one named volume per provider mapped to full config dir. Auth, config, and history persist between containers. SCC-managed launch config is ephemeral *in effect* because SCC deterministically writes it on every fresh launch, even when empty (D038). Auth files require strict permissions (dir 0700, files 0600, uid 1000) enforced both at image build time and at runtime via normalization (D039). Codex forces file-based auth in containers (D040). Fine-grained volume splitting deferred (D036).
- Auth readiness checking is adapter-owned via AgentProvider.auth_check() → AuthReadiness. Core never hardcodes auth file names. Future scc auth commands compose on this model (D037).
- `get_provider_display_name()` is the single source for provider-to-human-name mapping — all UI surfaces use it instead of raw provider IDs.
- Guardrail test `TestNoCloudeCodeInNonAdapterModules` prevents regression of hardcoded provider references in non-adapter code.
- provider_id is threaded through session recording, dry-run JSON, support bundle manifest, session list JSON, and container naming hash — all machine-readable outputs carry provider identity.
- check_provider_image() doctor check reports missing provider agent images with exact `docker build` fix_commands for operator recovery.
- Container naming includes provider_id in hash input to prevent Claude/Codex coexistence collisions on the same workspace.
- Session/audit helpers are provider-parameterized via registry: `get_provider_sessions_dir(provider_id)`, `get_provider_recent_sessions(provider_id)`, `get_provider_config_dir(provider_id)`. All default to `'claude'` for backward compat.
- WorkContext carries `provider_id` with backward-compatible serialization. `display_label` surfaces non-default providers only.
- Doctor checks are categorized (backend/provider/config/worktree/general) and rendered with section headers. `--provider` flag scopes checks to a specific provider's readiness.
- **core/constants.py holds only product-level values** (CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX). All Claude-specific runtime constants live in the adapter/consumer modules that use them. Guardrail test `test_no_claude_constants_in_core.py` prevents re-introduction via tokenize-based definition scanning and codebase-wide import scanning.
- **commands/profile.py is Claude provider only** — the module docstring documents intentional hardcoded `.claude/settings.local.json` references. Future provider generalization tracked separately.
