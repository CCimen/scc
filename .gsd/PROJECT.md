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
- Do not advance M005 ahead of M003 or M004; keep M005 as the final quality-bar milestone.
- In M003 and M004, allow only local maintainability extractions that directly enable the active slice in touched files.
- Reserve repo-wide decomposition, broad typed-config migration, guardrail restoration, xfail removal, and the larger coverage campaign for M005.

## Current milestone state
**M003: Portable Runtime And Enforced Web Egress** is in progress. S01, S02, S03, and S04 are complete. S05 (Verification, docs truthfulness, and milestone closeout) is the final remaining slice.

## Next milestone order
1. **M003 — Portable Runtime And Enforced Web Egress** (active — S05 remaining)
2. **M004 — Cross-Agent Runtime Safety**
3. **M005 — Architecture Quality, Strictness, And Hardening**

## M003 slice status
| Slice | Title | Status |
|-------|-------|--------|
| S01 | Capability-based runtime model and detection cleanup | ✅ complete |
| S02 | SCC-owned image contracts and plain OCI backend | ✅ complete |
| S03 | Enforced web-egress topology and proxy ACLs | ✅ complete |
| S04 | Policy integration, provider destination validation, and operator diagnostics | ✅ complete |
| S05 | Verification, docs truthfulness, and milestone closeout | ⬜ pending (depends: S03, S04) |

## M003/S01 outcome summary
- RuntimeProbe protocol (ports/runtime_probe.py) with a single `probe() -> RuntimeInfo` method is the new canonical detection surface.
- DockerRuntimeProbe is the sole adapter calling docker/core helpers; it never raises from probe().
- RuntimeInfo extended with version, desktop_version, daemon_reachable, sandbox_available fields (backward compatible defaults).
- DockerSandboxRuntime.ensure_available() is now probe-driven instead of calling docker.check_docker_available() directly.
- Dashboard orchestrator worktree start and session resume migrated to probe-backed detection.
- Tokenizer-based guardrail test prevents future direct check_docker_available() calls outside the adapter layer.
- Bootstrap shares one DockerRuntimeProbe instance between runtime_probe and sandbox_runtime fields.

## M003/S02 outcome summary
- OciSandboxRuntime adapter implements full SandboxRuntime protocol using docker create/start/exec (no Docker Desktop dependency).
- Frozen ImageRef dataclass with full_ref()/image_ref() roundtrip and SCC image constants (SCC_BASE_IMAGE, SCC_CLAUDE_IMAGE, SCC_CLAUDE_IMAGE_REF).
- Dockerfiles for scc-base (Ubuntu 22.04, git, curl, agent user) and scc-agent-claude (Node.js 20 LTS, Claude CLI).
- RuntimeInfo.preferred_backend field drives bootstrap backend selection: "docker-sandbox" → DockerSandboxRuntime, "oci" → OciSandboxRuntime.
- Rootless detection via docker info SecurityOptions parsing with graceful None fallback.
- start_session.py routes image selection: SCC_CLAUDE_IMAGE_REF for OCI, SANDBOX_IMAGE for Desktop.
- 34 OCI runtime tests, 23 image contract tests, 9 bootstrap/routing integration tests added.
- scc.backend=oci label convention and scc-oci-{hash} container naming for OCI containers.

## M003/S03 outcome summary
- Three-layer enforced web-egress: pure policy logic (core/egress_policy.py), infrastructure adapter (adapters/egress_topology.py), runtime integration (adapters/oci_sandbox_runtime.py).
- `build_egress_plan()` produces NetworkPolicyPlan with default deny rules for IP literals, loopback, private CIDRs, link-local, and metadata endpoints.
- `compile_squid_acl()` compiles plans into valid Squid ACL config with deny-before-allow ordering.
- NetworkTopologyManager creates internal-only Docker network, starts dual-homed Squid proxy sidecar, returns EgressTopologyInfo.
- Squid proxy sidecar image defined in images/scc-egress-proxy/ (Dockerfile, squid.conf.template, entrypoint.sh).
- OCI adapter orchestrates topology for web-egress-enforced (internal network + proxy env), uses --network=none for locked-down-web, unchanged for open.
- Topology teardown wired into both stop() and remove() with idempotent cleanup.
- 49 new tests across three test files plus guardrail preventing regression to default network.

## M003/S04 outcome summary
- Provider destination registry (`core/destination_registry.py`) maps named sets (anthropic-core, openai-core) to typed DestinationSet objects with resolve and rule-generation helpers.
- SandboxSpec.destination_sets field carries resolved sets through the launch pipeline (frozen dataclass, default empty tuple).
- `_build_sandbox_spec()` resolves provider destinations for OCI backends; OCI adapter converts to allow rules in egress plan.
- Enforced-mode preflight validates destination resolvability before launch — unknown sets raise LaunchPolicyBlockedError.
- `check_runtime_backend()` doctor check reports preferred_backend, display_name, and version via bootstrap probe.
- `effective_egress` support-bundle section includes runtime_backend, network_policy, and resolved_destination_sets with independent try/except resilience.
- 30 net new tests (3432 total suite).

## M002 outcome summary
- `AgentProvider` and `AgentLaunchSpec` are now part of the real launch path rather than planned-only seams.
- Claude-specific settings/auth behavior is adapter-owned behind `src/scc_cli/adapters/claude_settings.py` and `bootstrap.py` remains the only allowed higher-layer adapter boundary.
- Codex is a first-class provider on the same seam through `src/scc_cli/adapters/codex_agent_provider.py` with honest capability metadata.
- SCC now performs provider-neutral preflight before runtime startup and fails early on blocked or malformed launches.
- Launch/preflight decisions persist through one canonical JSONL audit sink at `~/.config/scc/audit/launch-events.jsonl`.
- Support-bundle generation now has one application-owned implementation, and launch-wizard resume behavior sits behind typed helpers with hotspot guardrails.

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated by M002/S05. Advanced by M003/S01 (RuntimeProbe protocol), M003/S02 (OCI adapter follows adapter-boundary conventions), M003/S03 (three-layer egress enforcement with 49 tests, local _run_docker to avoid cross-adapter coupling), and M003/S04 (pure destination registry, import boundary compliance for doctor checks, resilient support-bundle diagnostics).

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (Success: no issues found in 249 source files)
- `uv run pytest --rootdir "$PWD" -q` ✅ (3432 passed, 23 skipped, 4 xfailed)

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

## Immediate next focus
- S05 (Verification, docs truthfulness, and milestone closeout) is unblocked and should start next.
- S05 should verify that diagnostic surfaces match D015 requirements, confirm docs truthfulness against actual enforcement, and close out M003.
