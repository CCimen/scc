---
id: S05
parent: M002
milestone: M002
provides:
  - Bounded redaction-safe launch-audit diagnostics via `scc support launch-audit` and support-bundle manifests.
  - One application-owned support-bundle implementation shared by the CLI and settings flows.
  - Typed quick-resume and workspace-resume helpers plus hotspot guardrails for the launch wizard.
requires:
  - slice: S02
    provides: Claude-specific adapter cleanup so support and launch hardening could stay provider-neutral.
  - slice: S03
    provides: A second real provider on the shared seam, which the new diagnostics surface now reports without Claude-shaped assumptions.
  - slice: S04
    provides: The durable launch-audit JSONL sink and shared finalize/preflight launch boundary that S05 exposes and hardens.
affects:
  - M002 milestone validation
  - M003 planning
  - M004 planning
  - M005 quality-bar planning
key_files:
  - src/scc_cli/application/launch/audit_log.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/commands/support.py
  - src/scc_cli/application/settings/use_cases.py
  - src/scc_cli/ui/settings.py
  - src/scc_cli/commands/launch/wizard_resume.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_types.py
  - tests/test_launch_audit_support.py
  - tests/test_support_bundle.py
  - tests/test_application_settings.py
  - tests/test_no_root_sprawl.py
  - tests/test_launch_flow_hotspots.py
  - tests/test_start_wizard_quick_resume_flow.py
  - tests/test_start_wizard_workspace_quick_resume.py
  - tests/test_start_cross_team_resume_prompt.py
  - README.md
key_decisions:
  - D008: expose the durable launch audit through one application-owned reader and keep support-bundle generation on a single application path.
  - D009: keep quick-resume and workspace-resume orchestration in `src/scc_cli/commands/launch/wizard_resume.py` behind explicit typed context and hotspot guardrails.
  - D010: validate R001 after S05 because the touched hotspots were reduced, the support path converged, and repo-wide lint/type/test gates passed.
patterns_established:
  - Use bounded redaction-safe readers over append-only diagnostic files instead of inventing parallel persistence formats.
  - Keep support/diagnostic generation application-owned so CLI and TUI callers share one real implementation.
  - When touching a large orchestrator, extract one behavior slice into typed helpers and pin the seam with characterization plus hotspot guardrail tests.
observability_surfaces:
  - `scc support launch-audit` in human and JSON modes
  - support bundle `launch_audit` manifest section
  - durable local JSONL sink at `~/.config/scc/audit/launch-events.jsonl`
  - hotspot/root-sprawl guardrail tests for architectural drift
drill_down_paths:
  - .gsd/milestones/M002/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T21:45:45.582Z
blocker_discovered: false
---

# S05: Hardening, diagnostics, and decomposition follow-through

**S05 made the provider-neutral launch path inspectable and easier to change by shipping bounded launch-audit diagnostics, converging support-bundle ownership on one application path, and extracting the launch-wizard resume hotspot behind typed helpers and guardrails.**

## What Happened

S04 left SCC with a durable launch-audit sink but no operator-facing way to inspect it without opening raw JSONL by hand. S05 closed that gap by adding an application-level audit reader that tails the configured sink, tolerates malformed lines, redacts home-directory paths, and powers both the new `scc support launch-audit` command and the support-bundle manifest. The command now exposes recent events, malformed-record counts, and last-failure context in both human and stable JSON-envelope forms, while support bundles include a bounded `launch_audit` section instead of copying raw unbounded log contents.

The slice also removed the duplicated support-bundle implementation split between the legacy top-level helper and the newer application use case. CLI bundle generation, settings-screen bundle generation, default-path calculation, manifest assembly, and archive writing now converge on `src/scc_cli/application/support_bundle.py`. The legacy `src/scc_cli/support_bundle.py` path was removed instead of preserved as a compatibility shim, and root-sprawl/import-boundary tests now fail if that duplicate path returns.

Finally, S05 reduced the biggest remaining launch-flow hotspot inside `interactive_start`. Quick-resume and workspace-resume orchestration moved into `src/scc_cli/commands/launch/wizard_resume.py`, using explicit typed context/result helpers instead of large nested closures over mutable state. The existing `--team` over `selected_profile` precedence, back/cancel/team-switch behavior, and cross-team resume protections stayed intact under focused characterization tests, and a new hotspot guardrail now enforces that the seam stays extracted.

This slice stayed within the active overrides: the extractions were local to touched support and launch files and directly enabled the active slice. It did not pull repo-wide decomposition or broad guardrail cleanup forward from M005, and the next milestone order remains M003 → M004 → M005.

## Verification

Verified the three slice-plan command sets and then re-ran the repo-wide gates in the active worktree:

- `uv run pytest --rootdir "$PWD" ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q`
- `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q`
- `uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q`
- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest --rootdir "$PWD" -q`

Also verified the new diagnostics surface through the real CLI entrypoint using a synthetic audit sink under a temporary HOME:

- `uv run scc support launch-audit --limit 2` showed `State: available`, surfaced `Malformed records in recent scan: 1`, reported the last failure, and redacted home paths to `~`.
- `uv run scc support launch-audit --json --limit 2` returned a stable `kind: LaunchAudit` envelope with redacted metadata and failure context.
- `uv run scc support bundle --json` returned a `SupportBundle` envelope whose manifest included a bounded `launch_audit` section on the shared application path.

## Requirements Advanced

- R001 — Removed duplicated support-bundle logic, extracted typed resume helpers out of `interactive_start`, and added hotspot/root-sprawl guardrails around the touched launch and support seams.

## Requirements Validated

- R001 — Repo-wide `ruff`, `mypy`, and `pytest` passed after the support-path convergence and wizard extraction landed, and the new focused guardrail suites prove the touched high-churn areas are now smaller, more cohesive, and mechanically protected against regression.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

The launch-audit reader only reports on a bounded recent scan window, not the full file history. That keeps the command cheap on large logs, but older malformed lines or failures can age out of the surface.

The support-bundle command’s top-level success means manifest generation succeeded, not that every embedded health check is green. Operators still need to inspect `doctor.summary` and `launch_audit` content inside the manifest.

## Follow-ups

Keep milestone order M003 → M004 → M005 after M002. Any further decomposition work in M003-M004 should remain local to the files being actively changed; broad guardrail restoration, repo-wide decomposition, and larger quality-bar work stay reserved for M005.

Consider log rotation or longer-horizon aggregation for the durable launch-audit sink in M005 if operators need more than the bounded recent tail during incident review.

## Files Created/Modified

- `src/scc_cli/application/launch/audit_log.py` — Added the bounded redaction-safe reader for recent launch-audit diagnostics.
- `src/scc_cli/application/support_bundle.py` — Became the single application-owned support-bundle path, including default-path calculation and launch-audit manifest enrichment.
- `src/scc_cli/commands/support.py` — Added `scc support launch-audit` and routed support-bundle behavior through the shared application implementation.
- `src/scc_cli/presentation/json/launch_audit_json.py` — Added the stable `LaunchAudit` JSON envelope mapping.
- `src/scc_cli/application/settings/use_cases.py` — Routed settings-screen support-bundle generation through the shared application use case.
- `src/scc_cli/ui/settings.py` — Switched the settings UI to the shared default support-bundle path helper.
- `src/scc_cli/commands/launch/wizard_resume.py` — Extracted quick-resume and workspace-resume orchestration behind typed helpers.
- `src/scc_cli/commands/launch/flow.py` — Delegated resume branches to the extracted helper module instead of inline closures.
- `src/scc_cli/commands/launch/flow_types.py` — Added typed resume context/result aliases that make the new seam explicit.
- `README.md` — Documented the new launch-audit inspection surface and troubleshooting path.
- `tests/test_launch_audit_support.py` — Pinned missing-file, malformed-line, redaction, and JSON-envelope behavior for the new diagnostics surface.
- `tests/test_support_bundle.py` — Proved bounded launch-audit manifest enrichment and the single-path application ownership.
- `tests/test_application_settings.py` — Proved settings actions call the shared support-bundle implementation.
- `tests/test_no_root_sprawl.py` — Prevents reintroduction of the removed legacy support-bundle module.
- `tests/test_launch_flow_hotspots.py` — Mechanically guards the extracted launch-wizard seam.
- `tests/test_start_wizard_quick_resume_flow.py` — Preserves quick-resume behavior after extraction.
- `tests/test_start_wizard_workspace_quick_resume.py` — Preserves workspace-resume behavior after extraction.
- `tests/test_start_cross_team_resume_prompt.py` — Preserves cross-team resume protections after extraction.
