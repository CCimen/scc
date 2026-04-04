---
id: T01
parent: S05
milestone: M004
key_files:
  - README.md
key_decisions:
  - Positioned safety engine as 'built-in' core capability with plugin as 'additional coverage' — truthful without overstating
  - Runtime wrappers described as 'defense-in-depth' per Constitution §9 and OVERRIDES.md — topology+proxy remain the hard control
  - Did not rebrand README title from 'Sandboxed Claude CLI' — Codex adapter exists in code but product positioning hasn't changed yet (reserved for M005)
duration: 
verification_result: passed
completed_at: 2026-04-04T13:33:17.483Z
blocker_discovered: false
---

# T01: Updated README to truthfully reflect M004 safety deliverables: core safety engine, runtime wrappers, safety-audit command, and doctor safety check.

**Updated README to truthfully reflect M004 safety deliverables: core safety engine, runtime wrappers, safety-audit command, and doctor safety check.**

## What Happened

Made four targeted edits to README.md to reflect M004's safety deliverables truthfully:

1. **Developer onboarding section (line 85):** Changed "Command guardrails — block destructive git commands like `push --force` (when scc-safety-net plugin is enabled)" to describe SCC's built-in safety engine as the core capability, with the plugin as additional coverage. This reflects the M004 reality: the shared safety engine in `core/safety_engine.py` provides the cross-provider baseline independent of any plugin.

2. **Enforcement scope section (line 118):** Added a new bullet on runtime safety: "SCC-owned wrappers intercept destructive git commands and explicit network tools (curl, wget, ssh, scp, sftp, rsync) inside the container. Wrappers are defense-in-depth — topology and proxy policy remain the hard network control. Safety policy is fail-closed." This is truthful per Constitution §4 and §9.

3. **Command table (line 289):** Added `scc support safety-audit | Inspect recent safety-check audit events` — the command delivered in S04.

4. **Troubleshooting section (line 384):** Added mention of `scc support safety-audit` for safety diagnostics and noted that `scc doctor` includes a safety-policy health check.

All 5 existing truthfulness guardrail tests pass after edits — no stale terms reintroduced.

## Verification

Ran existing truthfulness tests to confirm no regression: 5/5 passed. Verified key strings present in README via grep.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` | 0 | ✅ pass | 1170ms |
| 2 | `grep -q 'safety-audit' README.md` | 0 | ✅ pass | 10ms |
| 3 | `grep -q 'safety engine' README.md` | 0 | ✅ pass | 10ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `README.md`
