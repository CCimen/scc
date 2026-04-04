# S05 — Research: Verification, docs truthfulness, and milestone closeout

**Date:** 2026-04-04

## Summary

S05 is a verification and cleanup slice with no new architecture. The codebase is green (3432 tests, ruff clean, mypy clean across 249 source files), but four categories of truthfulness debt remain from pre-M003 code: (1) stale network mode names in user-facing strings and BlockedItem metadata, (2) README claims that violate Constitution §3 (Docker Desktop hard dependency) and §4 (enforcement description doesn't match the topology-based reality built in S03/S04), (3) missing guardrail tests to prevent vocabulary regression, and (4) the spec's requirement to disclose IPv4-only enforcement. After fixing these, the milestone exit gate (ruff + mypy + full pytest) must pass from a fresh rerun.

The work is straightforward — surgical string fixes, README section updates, and a small number of new guardrail tests following established patterns (tokenizer-based scanning from `test_runtime_detection_hotspots.py`). No new modules, no new architecture, no risky integration.

## Recommendation

Split into four tasks: (T01) fix stale vocabulary in source and test files, (T02) update README and examples to match current enforcement reality, (T03) add guardrail tests that prevent vocabulary and truthfulness regression, (T04) full milestone exit gate rerun. T01 and T02 are independent. T03 depends on T01/T02 (it validates their fixes). T04 depends on all three.

## Implementation Landscape

### Key Files

#### Stale vocabulary fixes (T01)

- `src/scc_cli/application/compute_effective_config.py` — Lines 563 and 712: `blocked_by="network_policy=isolated"` must become `blocked_by="network_policy=locked-down-web"`. The enum comparison on lines 559 and 706 already uses `NetworkPolicy.LOCKED_DOWN_WEB.value` correctly — only the user-facing `blocked_by` string is stale.
- `src/scc_cli/commands/config.py` — Line 530: warning string `"network_policy is corp-proxy-only but no proxy env vars are set"` must say `"web-egress-enforced"`. The condition on line 527 already checks `NetworkPolicy.WEB_EGRESS_ENFORCED.value` correctly.
- `tests/test_config_explain.py` — Lines 125, 148: fixture `effective_config_full` uses `network_policy="corp-proxy"` and a matching `ConfigDecision(value="corp-proxy")`. Update to `"web-egress-enforced"`. Line 672: docstring says "corp-proxy-only" — update to match.

#### README and docs truthfulness (T02)

- `README.md` line 32: `**Requires:** Python 3.10+, Docker Desktop 4.50+, Git 2.30+` — Constitution §3 says no hard Docker Desktop dependency. After M003, SCC works on Docker Engine, OrbStack, and Colima. Change to `Python 3.10+, Docker (Engine, Desktop, OrbStack, or Colima), Git 2.30+`.
- `README.md` line 117: `network_policy is partially enforced (proxy env injection + MCP suppression under isolated)` — stale on two counts: uses old name "isolated" and understates enforcement after S03 topology work. Rewrite to describe topology-based enforcement for `web-egress-enforced` and `locked-down-web`, noting v1 is HTTP/HTTPS-focused and IPv4-only.
- `README.md` line 144: `"network_policy": "unrestricted"` in the org config example JSON — change to `"open"`.
- `README.md` line 386: troubleshooting table says `Start Docker Desktop` — should say `Start Docker (Desktop, Engine, or compatible daemon)`.

#### Guardrail tests (T03)

- `tests/test_docs_truthfulness.py` — New file. Tests to add:
  1. Scan `README.md` for old network mode names (`unrestricted`, `corp-proxy-only`, `isolated` used as a network mode name — exclude legitimate uses like "isolated feature development").
  2. Scan `README.md` to confirm it does NOT claim Docker Desktop is a hard requirement (regex for "Requires.*Docker Desktop" without alternatives).
  3. Scan all `examples/*.json` files for `"network_policy"` values and assert they are valid `NetworkPolicy` enum members.
  4. Scan `src/scc_cli/` for `blocked_by=` strings containing old network mode names.
  5. Scan user-facing warning/error strings in `src/scc_cli/commands/` for old network mode names.

Pattern to follow: `tests/test_runtime_detection_hotspots.py` uses Python's `tokenize` module for scanning NAME tokens. For string-literal scanning (the `blocked_by` case), a simpler `ast.literal_eval` or regex over `.py` files is sufficient since we're matching string content, not identifiers.

#### Milestone exit gate (T04)

- Run: `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest --rootdir "$PWD" -q`
- Confirm: no regressions from T01-T03, test count ≥ 3432 + new guardrail tests

### Build Order

1. **T01 (vocabulary fixes)** and **T02 (README updates)** can run in parallel — they touch disjoint files.
2. **T03 (guardrail tests)** depends on T01 + T02 — the tests validate the fixed state, so they must run after the fixes land.
3. **T04 (exit gate)** depends on all — it's the final fresh rerun confirming everything is clean.

### Verification Approach

**Per-task verification:**
- T01: `uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q` (existing tests still pass with updated vocabulary)
- T02: Manual review of README diff; `uv run pytest --rootdir "$PWD" -q` (no test breakage from doc changes)
- T03: `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -q` (new tests pass)
- T04: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q` (full exit gate)

**Slice-level verification:** Full exit gate from T04 plus test count assertion (≥ 3432 + new tests).

## Constraints

- Constitution §3: Docker Desktop must not appear as a hard requirement anywhere user-facing.
- Constitution §4: Security language must match actual enforcement. After M003, `web-egress-enforced` is topology-enforced (internal network + proxy sidecar), not just proxy env injection.
- Spec 04 Truthfulness Requirements: must disclose IPv4-only enforcement; must not claim "isolated" or "cannot reach company systems" unless the runtime actually enforces it.
- KNOWLEDGE.md: "For milestone closeout, trust only a fresh rerun of the exact exit gate from the active worktree plus a rendered validation artifact."
- PLAN.md test plan: exit gate is `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest`.

## Common Pitfalls

- **Overbroad regex for "isolated"** — The word "isolated" appears legitimately in the codebase for non-network contexts ("isolated feature development" in worktree prompts, "IO is isolated to the stores layer" in evaluation module). Guardrail tests must be scoped to network-mode contexts only — e.g. match `network_policy.*isolated` or `blocked_by.*isolated`, not bare "isolated".
- **README example JSON validity** — The README inline JSON example on line 144 uses `"unrestricted"`. Changing it to `"open"` is correct but the example must remain valid against the org schema. Verify with `scc org validate` or schema check.
- **Test fixture coupling** — `test_config_explain.py` fixtures at lines 125/148 use `"corp-proxy"`. These are test data, not runtime logic — the fix is straightforward but the test assertions downstream must still align (check that display/formatting tests don't hardcode the old string in expected output).
