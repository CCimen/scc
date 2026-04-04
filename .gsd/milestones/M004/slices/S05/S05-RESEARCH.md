# M004/S05 — Research

**Date:** 2026-04-04

## Summary

S05 is the final slice for M004. Its job is threefold: (1) update user-facing docs/README to reflect M004 deliverables truthfully, (2) add guardrail tests preventing safety-related truthfulness regression, and (3) run the full exit gate and produce milestone validation/closeout artifacts.

This is straightforward work following the established M003/S05 pattern. M003/S05 did the same thing for network-mode vocabulary — scanning for stale claims, fixing README, adding guardrail tests in `test_docs_truthfulness.py`. M004/S05 extends the same file with safety-specific guardrails.

Key findings: the README currently has no mention of the `scc support safety-audit` command (added S04), the doctor safety-policy check (S04), or the SCC-owned shared safety engine / runtime wrappers (S01/S02). Line 85 says "Command guardrails — block destructive git commands like `push --force` (when scc-safety-net plugin is enabled)" which is now understated — the SCC core safety engine provides this baseline independent of the plugin. The command table at line 280 is missing the `scc support safety-audit` entry. The troubleshooting section doesn't mention `scc support safety-audit` or `scc doctor` safety checks.

Per the OVERRIDES.md directive: "In M004, only document current truth and verify truthful safety/provider messaging; do not implement the new team-pack pipeline there."

## Recommendation

Two tasks matching the M003/S05 shape:

**T01: README truthfulness updates for M004 safety deliverables.** Update the README to reflect the SCC-owned safety engine as a core capability (not just plugin-dependent). Add `scc support safety-audit` to the command table. Update the developer onboarding and enforcement scope sections. Keep claims truthful — the engine is in-core, wrappers are defense-in-depth for explicit network tools, topology + proxy remain the hard network control.

**T02: Safety-specific guardrail tests and full exit gate.** Extend `tests/test_docs_truthfulness.py` with tests that: (a) verify the README mentions the safety audit command, (b) verify the README doesn't claim safety is plugin-only (it should mention core engine), (c) verify the safety adapter boundary guardrail test exists and passes. Then run the full exit gate: ruff + mypy + pytest.

After both tasks, run milestone validation and closeout.

## Implementation Landscape

### Key Files

- `README.md` — Needs truthfulness updates: add `scc support safety-audit` to command table, update developer onboarding section to reflect core safety engine, update enforcement scope to mention runtime wrappers as defense-in-depth
- `tests/test_docs_truthfulness.py` — Existing M003 guardrail tests (5 tests on network vocabulary). Extend with M004 safety-specific guardrails
- `tests/test_safety_engine_boundary.py` — Existing boundary guardrail (1 test). Already correct, just needs verification during exit gate
- `tests/test_safety_eval_sync.py` — Existing sync guardrail (3 tests). Already correct, just needs verification during exit gate
- `src/scc_cli/commands/support.py` — Contains the `safety-audit` command. Reference for verifying README accuracy

### Build Order

1. **T01 first** — Fix the README so the guardrail tests in T02 pass against the corrected content.
2. **T02 second** — Add guardrail tests that lock in the truthfulness of the T01 updates, then run the full exit gate.

### Verification Approach

- `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` — all tests pass (5 existing + new)
- `uv run pytest --rootdir "$PWD" tests/test_safety_engine_boundary.py tests/test_safety_eval_sync.py -v` — boundary guardrails pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — clean
- `uv run pytest --rootdir "$PWD" -q` — full suite ≥3790 (current baseline) + new guardrail tests

## Constraints

- Per OVERRIDES.md: document current truth only — do not implement new team-pack pipeline or Codex-specific surfaces in README beyond truthful status
- Per Constitution §4: security language must match actual enforcement — don't overstate what runtime wrappers enforce
- Per Constitution §9: runtime-level safety beats provider luck — position the shared engine correctly as the cross-provider baseline
- README currently says "Sandboxed Claude CLI" in the title — Codex support is real in code but the product positioning hasn't changed. Keep README truthful about what exists without rebranding.

## Common Pitfalls

- **Overstating wrapper enforcement** — Wrappers are defense-in-depth for explicit network tools. Topology + proxy remain the hard network control. Don't claim wrappers "block all network access."
- **Claiming Codex parity in README** — Codex adapter exists in code but the product README still targets Claude CLI users. Add factual mentions of multi-provider safety but don't rebrand.
- **Breaking existing truthfulness tests** — The 5 existing tests in `test_docs_truthfulness.py` scan for stale network vocabulary. New README changes must not reintroduce stale terms.
