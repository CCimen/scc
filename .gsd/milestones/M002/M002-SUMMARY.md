---
id: M002
title: "Provider-Neutral Launch Adoption"
status: complete
completed_at: 2026-04-03T22:20:41.477Z
key_decisions:
  - Keep provider launch data in typed provider-neutral contracts and represent each provider as a small `AgentProvider` adapter behind `bootstrap.py` rather than widening shared orchestration.
  - Validate provider-core destination requirements before runtime startup and persist launch/preflight decisions through one canonical `AuditEvent` JSONL sink reused by every live launch entrypoint.
  - Expose launch diagnostics and support bundles through one application-owned path, and reduce launch-flow hotspots with typed helper extraction plus guardrail tests instead of broad framework rewrites.
  - Keep post-M002 milestone order as M003 → M004 → M005 and limit M003/M004 maintainability work to local enabling extractions, reserving broader hardening for M005.
key_files:
  - src/scc_cli/application/start_session.py
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/adapters/claude_settings.py
  - src/scc_cli/application/launch/preflight.py
  - src/scc_cli/adapters/local_audit_event_sink.py
  - src/scc_cli/application/launch/finalize_launch.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/application/launch/audit_log.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/commands/support.py
  - src/scc_cli/commands/launch/wizard_resume.py
  - src/scc_cli/commands/launch/flow.py
  - tests/test_launch_preflight.py
  - tests/test_launch_audit_support.py
  - tests/test_support_bundle.py
  - tests/test_launch_flow_hotspots.py
lessons_learned:
  - The provider seam only stays honest if every live launch path shares the same dependency builder and `finalize_launch(...)` boundary; parallel start paths drift quickly.
  - For file-configured providers, `artifact_paths` are the stable seam and `AgentLaunchSpec.env` should stay clean; pushing provider settings into env vars would leak encoding details into core contracts.
  - Durable operator diagnostics work better as a bounded redaction-safe reader over the canonical audit sink than as a second persistence format or raw log dump.
  - Milestone closeout should re-run the exact exit gate from the active worktree and record a validation artifact from that live proof, not rely on older green slice summaries.
---

# M002: Provider-Neutral Launch Adoption

**Provider-neutral launch planning is now live for Claude and Codex, with pre-launch validation, a durable audit sink, bounded operator diagnostics, and a restored green exit gate in the active worktree.**

## What Happened

M002 turned the typed seams introduced in M001 into the real launch path and then hardened the result until the worktree could close on current evidence instead of intention. S01 made `AgentProvider` and `AgentLaunchSpec` live by routing start-session planning through a provider-owned launch seam while keeping contracts provider-neutral. S02 completed the Claude-side cleanup by moving settings/auth translation behind adapter-owned modules and preserving `bootstrap.py` as the only higher-layer adapter boundary. S03 proved the seam was real rather than Claude-shaped by adding Codex as a second first-class provider with the same characterization pattern and without widening shared contracts. S04 then added the missing operational backbone: provider-neutral preflight that fails before runtime startup when provider-core destinations are unavailable or policy-blocked, plus one durable `AuditEvent` JSONL sink reused by every live launch path. S05 made that new behavior inspectable and easier to maintain by exposing bounded redaction-safe launch-audit diagnostics, converging support-bundle generation on one application-owned implementation, and extracting the launch-wizard resume hotspot behind typed helpers and guardrail tests. S06 stayed narrow and did the milestone-closeout work correctly: it reran the exact repo gate from the active worktree, confirmed the milestone still passed on live code, and rendered the validation artifact with verdict `pass`. Across the milestone, the project moved from Claude-shaped orchestration toward a provider-neutral launch core that is easier to inspect, easier to extend, and mechanically guarded by focused contract, integration, and hotspot tests.

## Success Criteria Results

- **Live provider-neutral launch seam:** Met. S01 moved the real launch path through `AgentProvider.prepare_launch(...)` and `prepare_start_session()` now produces typed `AgentLaunchSpec` data. Evidence: S01 verification passed in `tests/test_application_start_session.py`, `tests/test_bootstrap.py`, and `tests/test_core_contracts.py`.
- **Claude-specific behavior stays adapter-owned:** Met. S02 moved Claude settings/auth handling into `src/scc_cli/adapters/claude_settings.py`, removed the package-root shim, and preserved the bootstrap-only adapter import boundary. Evidence: `tests/test_import_boundaries.py`, `tests/test_no_root_sprawl.py`, and `tests/test_claude_agent_provider.py` all passed.
- **Codex is first-class on the same seam:** Met. S03 added `src/scc_cli/adapters/codex_agent_provider.py` with honest capability metadata and the canonical four-test characterization suite. Evidence: `tests/test_codex_agent_provider.py` plus bootstrap/start-session/CLI/integration coverage passed.
- **Provider-core validation fails before runtime startup:** Met. S04 introduced provider-neutral preflight over launch-plan readiness, required destination sets, and effective network policy. Evidence: `src/scc_cli/application/launch/preflight.py`, typed preflight/audit failures, and the focused S04 verification suite plus repo gate passed.
- **One durable structured audit sink exists:** Met. S04 added `AuditEventSink` and `LocalAuditEventSink` with canonical JSONL persistence at `~/.config/scc/audit/launch-events.jsonl`; S05 then surfaced the sink through `scc support launch-audit` and support bundles. Evidence: S04 and S05 slice verification plus CLI smoke checks passed.
- **Milestone exit gate restored in the active worktree:** Met. S06 reran `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q` from the active M002 worktree and recorded `verdict: pass` in `.gsd/milestones/M002/M002-VALIDATION.md`.

## Definition of Done Results

- **All roadmap slices complete:** Met. S01-S06 are complete and each has a rendered summary and UAT/plan artifacts under `.gsd/milestones/M002/slices/`.
- **Milestone produced actual code changes:** Met. `git diff --stat HEAD $(git merge-base HEAD main) -- ':!.gsd/'` shows substantial non-`.gsd/` code deltas across launch, adapter, support, and test files.
- **Cross-slice integration works as one system:** Met. S02 and S03 both consume the S01 seam; S04 reuses that seam for preflight/audit; S05 reuses the S04 audit sink instead of inventing a second diagnostics path; S06 revalidated the assembled result without reopening implementation scope.
- **Verification contract is green on current code:** Met. The active-worktree gate passed in S06/T01 and the milestone validation artifact exists with `verdict: pass`.
- **No unresolved closeout mismatch remains between roadmap, slice outputs, requirements, and decisions:** Met. `M002-VALIDATION.md` records a pass verdict and explicitly notes alignment between the roadmap, R001, and D010/D011.

## Requirement Outcomes

- **R001 — maintainability in touched high-churn areas:** `active` → `validated` during M002/S05, and that result still holds at closeout. Evidence: support-bundle logic converged on one application-owned path, launch-wizard resume branches moved into typed helpers, hotspot/root-sprawl guardrails were added, and the focused maintainability suites plus repo-wide `ruff`, `mypy`, and `pytest` gates all passed. `.gsd/REQUIREMENTS.md` already records this validated state.
- No additional requirement state transitions were needed during milestone completion.

## Deviations

None beyond the slice-level deviations already recorded in S01-S03; milestone closeout used the delivered scope and did not reopen implementation work.

## Follow-ups

Start M003 next and keep milestone sequencing `M003 -> M004 -> M005`. In M003 and M004, limit maintainability work to local extractions that directly enable the active slice. Consider launch-audit retention or rotation in M005 if incident review needs more than the bounded recent tail.
