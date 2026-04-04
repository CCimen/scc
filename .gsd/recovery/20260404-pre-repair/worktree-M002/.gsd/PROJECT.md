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
**M002: Provider-Neutral Launch Adoption** is complete. The live launch path now goes through provider-neutral contracts for Claude and Codex, provider-core requirements are validated before runtime startup, launch/preflight events persist to one durable audit sink, and the active worktree exit gate is green.

## Next milestone order
After M002, the next milestones remain:
1. **M003 — Portable Runtime And Enforced Web Egress**
2. **M004 — Cross-Agent Runtime Safety**
3. **M005 — Architecture Quality, Strictness, And Hardening**

Register or confirm M003 and M004 from `PLAN.md` before beginning M005.

## M002 outcome summary
- `AgentProvider` and `AgentLaunchSpec` are now part of the real launch path rather than planned-only seams.
- Claude-specific settings/auth behavior is adapter-owned behind `src/scc_cli/adapters/claude_settings.py` and `bootstrap.py` remains the only allowed higher-layer adapter boundary.
- Codex is a first-class provider on the same seam through `src/scc_cli/adapters/codex_agent_provider.py` with honest capability metadata.
- SCC now performs provider-neutral preflight before runtime startup and fails early on blocked or malformed launches.
- Launch/preflight decisions persist through one canonical JSONL audit sink at `~/.config/scc/audit/launch-events.jsonl`.
- Operators can inspect recent launch diagnostics through `scc support launch-audit`, and support bundles include a bounded redacted `launch_audit` section.
- Support-bundle generation now has one application-owned implementation, and launch-wizard resume behavior sits behind typed helpers with hotspot guardrails.
- The milestone closeout gate was rerun from the active M002 worktree and passed cleanly: `ruff`, `mypy`, `pytest`, and validation artifact presence.

## Milestone M002 slice status
| Slice | Title | Status |
|-------|-------|--------|
| S01 | Live launch-path adoption of AgentProvider and AgentLaunchSpec | ✅ complete |
| S02 | Claude adapter extraction and cleanup | ✅ complete |
| S03 | Codex adapter as a first-class provider on the same seam | ✅ complete |
| S04 | Pre-launch validation and durable audit sink | ✅ complete |
| S05 | Hardening, diagnostics, and decomposition follow-through | ✅ complete |
| S06 | Restore milestone-exit contract gate | ✅ complete |

## Current verification baseline
- `uv run pytest --rootdir "$PWD" ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q` ✅ (`25 passed`)
- `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q` ✅ (`27 passed`)
- `uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q` ✅ (`12 passed`)
- `uv run ruff check` ✅
- `uv run mypy src/scc_cli` ✅ (`Success: no issues found in 242 source files`)
- `uv run pytest --rootdir "$PWD" -q` ✅ (`3281 passed, 23 skipped, 4 xfailed`)
- `test -f .gsd/milestones/M002/M002-VALIDATION.md && rg -n "pass|needs-attention|needs-remediation" .gsd/milestones/M002/M002-VALIDATION.md` ✅ (`verdict: pass`)
- `test -f .gsd/milestones/M002/M002-SUMMARY.md` ✅
- Live diagnostic smoke checks ✅
  - `HOME="$TMP_HOME" uv run scc support launch-audit --limit 2`
  - `HOME="$TMP_HOME" uv run scc support launch-audit --json --limit 2`
  - `HOME="$TMP_HOME" uv run scc support bundle --json`

## Requirement status
- **R001: maintainability in touched high-churn areas** — ✅ validated by M002/S05 and reaffirmed at milestone closeout by the restored M002 exit gate.

## Key architecture invariants
- `bootstrap.py` is the sole composition root for adapter symbols consumed outside `scc_cli.adapters`.
- `AgentLaunchSpec.env` stays empty for file-based providers; provider config travels via `artifact_paths`.
- The canonical provider-adapter characterization shape is: capability metadata, clean-spec, settings-artifact, and env-is-clean.
- Adding a provider to `DefaultAdapters` still requires the same four touch points: adapter file, bootstrap wiring, fake adapters factory, and inline test constructions.
- Provider-core destination validation belongs before launch, not as a runtime surprise.
- Live launch entrypoints should build dependencies through shared command-layer helpers and finish through `finalize_launch(...)` so preflight and audit behavior cannot drift between `scc start` and worktree auto-start.
- Support-bundle behavior extends from `src/scc_cli/application/support_bundle.py`; higher layers call into it rather than reintroducing parallel helpers.
- `scc support launch-audit` and the support-bundle `launch_audit` section are the authoritative operator-facing views of the durable launch-audit sink.

## Immediate next focus
- Reassess the roadmap with M002 complete.
- Confirm or register M003 and M004 from `PLAN.md`.
- Start M003 next: portable runtime and enforced web egress.
- Keep maintainability work in M003 local to the files that active runtime/egress slices touch.
