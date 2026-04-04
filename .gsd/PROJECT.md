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
- Do not advance M005 ahead of M004; keep M005 as the final quality-bar milestone.
- In M004, allow only local maintainability extractions that directly enable the active slice in touched files.
- Reserve repo-wide decomposition, broad typed-config migration, guardrail restoration, xfail removal, and the larger coverage campaign for M005.

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

### M004 — Cross-Agent Runtime Safety (in progress)
**S01 complete.** Delivered shared safety policy and verdict engine: shell tokenizer, git safety rules, network tool rules lifted from plugin into core with typed SafetyVerdict returns, orchestrated by DefaultSafetyEngine with fail-closed semantics, wired into bootstrap. +166 net new tests (3630 total).

Key S01 deliverables:
- CommandFamily enum (DESTRUCTIVE_GIT, NETWORK_TOOL)
- Shell tokenizer in core (5 public functions, pure stdlib)
- Git safety rules with typed SafetyVerdict returns (all plugin analyzers lifted)
- Network tool rules detecting 6 tools (curl, wget, ssh, scp, sftp, rsync)
- DefaultSafetyEngine with fail-closed policy semantics
- SafetyEngine protocol port
- FakeSafetyEngine for downstream tests
- Boundary guardrail preventing plugin/provider imports in core safety modules

Remaining slices: S02 (runtime wrapper baseline), S03 (Claude/Codex UX/audit adapters), S04 (fail-closed loading, audit surfaces, diagnostics), S05 (verification, docs, closeout).

## Next milestone order
1. ~~M001 — Provider-Neutral Launch Boundary~~ ✅
2. ~~M002 — Provider-Neutral Launch Pipeline~~ ✅
3. ~~M003 — Portable Runtime And Enforced Web Egress~~ ✅
4. **M004 — Cross-Agent Runtime Safety** (active — S01 ✅, S02–S05 remaining)
5. **M005 — Architecture Quality, Strictness, And Hardening**

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated by M002/S05. Advanced by M003 across all 5 slices and by M004/S01 (safety logic decomposed into focused core modules).

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (Success: no issues found in 254 source files)
- `uv run pytest --rootdir "$PWD" -q` ✅ (3630 passed, 23 skipped, 4 xfailed)

## Key architecture invariants
- `bootstrap.py` is the sole composition root for adapter symbols consumed outside `scc_cli.adapters`.
- `AgentLaunchSpec.env` stays empty for file-based providers; provider config travels via `artifact_paths`.
- The canonical provider-adapter characterization shape is: capability metadata, clean-spec, settings-artifact, and env-is-clean.
- Adding a provider to `DefaultAdapters` still requires the same four touch points: adapter file, bootstrap wiring, fake adapters factory, and inline test constructions.
- Provider-core destination validation belongs before launch, not as a runtime surprise.
- RuntimeProbe protocol is the canonical detection surface for runtime capabilities; no consumer outside the adapter layer should call docker.check_docker_available() directly.
- DockerSandboxRuntime accepts a RuntimeProbe in __init__; ensure_available() inspects RuntimeInfo fields.
- Bootstrap probes runtime at construction time and selects OciSandboxRuntime or DockerSandboxRuntime based on preferred_backend.
- OciSandboxRuntime is imported only in bootstrap.py; application layer uses SandboxRuntime protocol.
- Image routing is backend-aware: SCC_CLAUDE_IMAGE_REF for OCI, SANDBOX_IMAGE for Docker Desktop.
- Enforced web-egress uses internal Docker network + dual-homed Squid proxy sidecar as the hard enforcement boundary (D014).
- Egress policy logic is pure (core/egress_policy.py), infrastructure is adapter-owned (adapters/egress_topology.py), orchestration stays in OciSandboxRuntime.
- Enterprise egress model (D-007, D015): web-egress-enforced is the normal cloud-provider enterprise mode; locked-down-web is intentional no-web posture. Org owns baseline mode, hard deny overlays, named destination sets, and delegation. Teams widen within delegated bounds only. Project/user narrow only. One active team context per session — no implicit multi-team union. Topology + proxy policy are the hard control; wrappers are defense-in-depth, UX, and audit. Diagnostics must show active team context, effective destination sets, runtime backend, network mode, and blocked reasons.
- Provider destination sets flow through: registry resolve → SandboxSpec.destination_sets → OCI adapter allow rules → egress plan. Enforced-mode preflight validates resolvability before launch.
- Doctor checks access runtime probes via bootstrap.get_default_adapters(), never direct adapter imports.
- Support-bundle sections use independent try/except per data source for partial-failure resilience.
- Docs-truthfulness guardrail tests prevent stale network-mode vocabulary from reappearing in source, tests, or docs.
- Safety engine is provider-neutral: DefaultSafetyEngine in core orchestrates shell tokenizer + git rules + network tool rules. SafetyEngine protocol in ports. Fail-closed semantics (missing policy keys → rule enabled). Boundary guardrail prevents plugin/provider imports in core safety modules.
- M004 runtime wrapper scope is exactly 7 tools: git, curl, wget, ssh, scp, sftp, rsync (D017). No package managers, cloud CLIs, kubectl, terraform, or broad command families.
- Runtime wrappers are defense-in-depth, early UX, and audit only — never the primary enforcement plane for network isolation. Topology + proxy policy (D014) are the hard control.
- Provider-native integrations in M004 are adapter-owned and additive only; they relay but never override shared engine verdicts.
- One active team context per session/workspace in safety diagnostics and surfaces — no implicit union of team access (extends D015).

## Immediate next focus
- M004/S02: Runtime wrapper baseline in `scc-base` — depends on S01's safety engine and protocol.
