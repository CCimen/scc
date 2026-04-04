# S05: Hardening, diagnostics, and decomposition follow-through — UAT

**Milestone:** M002
**Written:** 2026-04-03T21:45:45.582Z

# S05: Hardening, diagnostics, and decomposition follow-through — UAT

**Milestone:** M002
**Written:** 2026-04-03

## UAT Type

- UAT mode: mixed
- Why this mode is sufficient: this slice shipped both operator-facing CLI diagnostics and maintainability-only architecture changes, so the right proof is a combination of real CLI runs against a synthetic audit sink plus focused guardrail/behavior tests for the extracted support and launch seams.

## Preconditions

- Run from the M002 worktree root.
- `uv sync` has been completed for the worktree environment.
- The CLI entrypoint is available via `uv run scc`.
- For the live diagnostics checks below, create a temporary HOME with a synthetic audit sink at `~/.config/scc/audit/launch-events.jsonl` containing:
  - one successful launch event
  - one malformed line
  - one failed launch event whose metadata includes a home-directory workspace path and a failure reason

## Smoke Test

Create the synthetic audit sink and run:

`HOME="$TMP_HOME" uv run scc support launch-audit --limit 2`

The command should print `Launch audit`, show `State: available`, report the malformed record count, show the last failure, and redact the temporary home path to `~`.

## Test Cases

### 1. Human launch-audit diagnostics expose recent events and last-failure context

1. Create a temporary HOME and write a launch-audit JSONL file with three lines in this order: a passed event, a malformed line, and a failed event.
2. Run `HOME="$TMP_HOME" uv run scc support launch-audit --limit 2`.
3. Confirm the output includes:
   - `Sink: ~/.config/scc/audit/launch-events.jsonl`
   - `State: available`
   - `Malformed records in recent scan: 1`
   - `Last malformed line in recent scan: 2`
   - a `Last failure` section showing the failed event and its failure reason.
4. **Expected:** the command succeeds without showing raw home paths, shows the failure reason with `~/...` redaction, and lists the two most recent valid events in reverse chronological order.

### 2. JSON launch-audit diagnostics use the stable envelope and stay redaction-safe

1. Reuse the same temporary HOME and audit file from test case 1.
2. Run `HOME="$TMP_HOME" uv run scc support launch-audit --json --limit 2`.
3. Parse the JSON output and confirm:
   - `kind == "LaunchAudit"`
   - `status.ok == true`
   - `data.state == "available"`
   - `data.malformed_line_count == 1`
   - `data.last_malformed_line == 2`
   - `data.last_failure.event_type == "launch.preflight.failed"`
   - redacted metadata paths use `~/...` rather than the temporary HOME value.
4. **Expected:** the command returns a stable `LaunchAudit` envelope and exposes recent failure context without leaking absolute home-directory paths.

### 3. Support bundle JSON includes bounded launch-audit diagnostics on the shared application path

1. Reuse the same temporary HOME and audit file from test case 1.
2. Run `HOME="$TMP_HOME" uv run scc support bundle --json`.
3. Parse the JSON output and confirm:
   - `kind == "SupportBundle"`
   - `data.launch_audit.state == "available"`
   - `data.launch_audit.requested_limit == 5`
   - `data.launch_audit.recent_events` contains only the bounded recent events, not a raw log dump
   - `data.launch_audit.last_failure.failure_reason` matches the failed event
   - `data.doctor` is present even if `data.doctor.summary.all_ok` is false on the test machine.
4. **Expected:** support-bundle generation succeeds through the shared application implementation and includes the bounded, redacted launch-audit summary alongside the doctor section.

### 4. Settings and CLI support-bundle callers remain converged on one implementation

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q`.
2. Confirm all tests pass.
3. Inspect the test names/output if needed to confirm coverage for:
   - settings support-bundle generation
   - bounded launch-audit manifest enrichment
   - no production imports of the removed `scc_cli.support_bundle` module.
4. **Expected:** the focused suite passes, proving the CLI and settings flows share the same application-owned support-bundle path and the removed legacy helper has not returned.

### 5. Quick-resume and workspace-resume behavior remains intact after extraction

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q`.
2. Confirm all tests pass.
3. Verify the suite covers:
   - hotspot seam enforcement
   - quick-resume behavior
   - workspace-resume behavior
   - cross-team resume protection.
4. **Expected:** the extracted `wizard_resume.py` seam is enforced mechanically and the existing resume behavior remains unchanged.

## Edge Cases

### Missing audit sink stays inspectable

1. Create a temporary HOME without creating `~/.config/scc/audit/launch-events.jsonl`.
2. Run `HOME="$TMP_HOME" uv run scc support launch-audit --json --limit 2`.
3. **Expected:** the command succeeds with `data.state == "unavailable"`, zero recent events, and no crash.

### Zero-limit launch-audit request returns state without recent events

1. Create a temporary HOME with at least one valid launch-audit record.
2. Run `HOME="$TMP_HOME" uv run scc support launch-audit --json --limit 0`.
3. **Expected:** the command succeeds, reports an available sink state, and returns an empty `recent_events` list.

### Cross-team resume protection still holds after extraction

1. Run `uv run pytest --rootdir "$PWD" ./tests/test_start_cross_team_resume_prompt.py -q`.
2. **Expected:** the test passes, proving a mismatched team/workspace resume still requires the existing protection path instead of silently resuming the wrong context.

## Failure Signals

- `scc support launch-audit` crashes, omits the malformed-line counters, or shows raw absolute home paths.
- The JSON envelope kind is not `LaunchAudit` or `SupportBundle`.
- `support bundle --json` omits `launch_audit`, includes unbounded raw audit content, or stops working when doctor reports a problem.
- `tests/test_no_root_sprawl.py` fails because `src/scc_cli/support_bundle.py` or a production import of `scc_cli.support_bundle` reappears.
- `tests/test_launch_flow_hotspots.py` fails because quick-resume logic drifted back into `flow.py`.

## Requirements Proved By This UAT

- R001 — the touched launch/support hotspots were reduced into smaller seams, the shared support-bundle path is mechanically guarded, and focused plus repo-wide verification stayed green.

## Not Proven By This UAT

- Long-horizon launch-audit retention, rotation, or external aggregation.
- Live alerting on audit-sink failures or malformed-record spikes.
- Full manual TUI walkthrough of the settings screen; convergence is proved here through the shared CLI path plus focused settings tests rather than an interactive terminal session recording.

## Notes for Tester

Use a temporary HOME for the live CLI checks so the redaction behavior is obvious and no real audit/config files are touched.

If the machine’s doctor checks report environmental issues during `support bundle --json`, that does not invalidate this slice by itself. The expected behavior is that the bundle still generates and includes both the doctor output and the bounded `launch_audit` section.

Keep the current roadmap override in mind when judging follow-up ideas: after M002, the next milestone order is M003 → M004 → M005, and repo-wide cleanup belongs in M005 rather than as opportunistic spillover from this slice.
