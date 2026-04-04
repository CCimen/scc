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
**M003: Portable Runtime And Enforced Web Egress** is in progress. S01 (capability-based runtime model and detection cleanup) is complete.

## Next milestone order
1. **M003 — Portable Runtime And Enforced Web Egress** (active)
2. **M004 — Cross-Agent Runtime Safety**
3. **M005 — Architecture Quality, Strictness, And Hardening**

## M003 slice status
| Slice | Title | Status |
|-------|-------|--------|
| S01 | Capability-based runtime model and detection cleanup | ✅ complete |
| S02 | SCC-owned image contracts and plain OCI backend | ⬜ pending (depends: S01) |
| S03 | Enforced web-egress topology and proxy ACLs | ⬜ pending (depends: S01, S02) |
| S04 | Policy integration, provider destination validation, and operator diagnostics | ⬜ pending (depends: S02, S03) |
| S05 | Verification, docs truthfulness, and milestone closeout | ⬜ pending (depends: S03, S04) |

## M003/S01 outcome summary
- RuntimeProbe protocol (ports/runtime_probe.py) with a single `probe() -> RuntimeInfo` method is the new canonical detection surface.
- DockerRuntimeProbe is the sole adapter calling docker/core helpers; it never raises from probe().
- RuntimeInfo extended with version, desktop_version, daemon_reachable, sandbox_available fields (backward compatible defaults).
- DockerSandboxRuntime.ensure_available() is now probe-driven instead of calling docker.check_docker_available() directly.
- Dashboard orchestrator worktree start and session resume migrated to probe-backed detection.
- Tokenizer-based guardrail test prevents future direct check_docker_available() calls outside the adapter layer.
- Bootstrap shares one DockerRuntimeProbe instance between runtime_probe and sandbox_runtime fields.

## M002 outcome summary
- `AgentProvider` and `AgentLaunchSpec` are now part of the real launch path rather than planned-only seams.
- Claude-specific settings/auth behavior is adapter-owned behind `src/scc_cli/adapters/claude_settings.py` and `bootstrap.py` remains the only allowed higher-layer adapter boundary.
- Codex is a first-class provider on the same seam through `src/scc_cli/adapters/codex_agent_provider.py` with honest capability metadata.
- SCC now performs provider-neutral preflight before runtime startup and fails early on blocked or malformed launches.
- Launch/preflight decisions persist through one canonical JSONL audit sink at `~/.config/scc/audit/launch-events.jsonl`.
- Support-bundle generation now has one application-owned implementation, and launch-wizard resume behavior sits behind typed helpers with hotspot guardrails.

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated by M002/S05. Advanced by M003/S01 (RuntimeProbe protocol reduces detection sprawl).

## Current verification baseline
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (Success: no issues found in 244 source files)
- `uv run pytest --rootdir "$PWD" -q` ✅ (3286 passed, 23 skipped, 4 xfailed)

## Key architecture invariants
- `bootstrap.py` is the sole composition root for adapter symbols consumed outside `scc_cli.adapters`.
- `AgentLaunchSpec.env` stays empty for file-based providers; provider config travels via `artifact_paths`.
- The canonical provider-adapter characterization shape is: capability metadata, clean-spec, settings-artifact, and env-is-clean.
- Adding a provider to `DefaultAdapters` still requires the same four touch points: adapter file, bootstrap wiring, fake adapters factory, and inline test constructions.
- Provider-core destination validation belongs before launch, not as a runtime surprise.
- RuntimeProbe protocol is the canonical detection surface for runtime capabilities; no consumer outside the adapter layer should call docker.check_docker_available() directly.
- DockerSandboxRuntime accepts a RuntimeProbe in __init__; ensure_available() inspects RuntimeInfo fields.

## Immediate next focus
- Reassess the M003 roadmap with S01 complete.
- S02 (SCC-owned image contracts and plain OCI backend) is unblocked and should start next.
- S02 will extend RuntimeProbe/RuntimeInfo with rootless detection and OCI backend selection.
