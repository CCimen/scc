# S05: Verification, docs truthfulness, and milestone closeout

**Goal:** All user-facing strings, README claims, and test fixtures use the current network mode vocabulary (open / web-egress-enforced / locked-down-web), README accurately describes Docker requirements and enforcement model per Constitution §3/§4, and guardrail tests prevent regression. Full exit gate passes.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Updated all stale network-mode vocabulary (isolated→locked-down-web, corp-proxy-only→web-egress-enforced, unrestricted→open) in source, tests, and README; removed Docker Desktop hard-dependency claim** — ## Description

Fixes all stale network-mode names across source code, test fixtures, and README. After S01-S04 landed the new NetworkPolicy enum (open / web-egress-enforced / locked-down-web), several user-facing strings and the README still reference the old vocabulary (unrestricted, corp-proxy-only, isolated-as-network-mode). This task makes every user-facing surface truthful.

## Steps

1. In `src/scc_cli/application/compute_effective_config.py`, change `blocked_by="network_policy=isolated"` to `blocked_by="network_policy=locked-down-web"` on lines 563 and 712. The enum comparison on the preceding lines already uses `NetworkPolicy.LOCKED_DOWN_WEB.value` — only the user-facing blocked_by string is stale.

2. In `src/scc_cli/commands/config.py`, change the warning string on line 530 from `"network_policy is corp-proxy-only but no proxy env vars are set"` to `"network_policy is web-egress-enforced but no proxy env vars are set"`. The condition on line 527 already checks `NetworkPolicy.WEB_EGRESS_ENFORCED.value`.

3. In `tests/test_config_explain.py`, update the `effective_config_full` fixture: change `network_policy="corp-proxy"` (line 125) to `network_policy="web-egress-enforced"`, and change the ConfigDecision `value="corp-proxy"` (line 148) to `value="web-egress-enforced"`. Also fix the docstring on line 672 from "corp-proxy-only" to "web-egress-enforced".

4. In `README.md` line 32, change `**Requires:** Python 3.10+, Docker Desktop 4.50+, Git 2.30+` to `**Requires:** Python 3.10+, Docker (Engine, Desktop, OrbStack, or Colima), Git 2.30+`. Constitution §3 prohibits Docker Desktop as a hard dependency.

5. In `README.md` around line 117, replace the stale enforcement scope bullet `network_policy is partially enforced (proxy env injection + MCP suppression under isolated), not a full egress firewall.` with an accurate description: `network_policy enforcement: web-egress-enforced uses topology-based isolation (internal Docker network + proxy sidecar) for HTTP/HTTPS egress control. locked-down-web applies --network=none. Enforcement is IPv4-only in v1; raw TCP/UDP beyond HTTP(S) is not filtered.`

6. In `README.md` around line 144, in the org config example JSON, change `"network_policy": "unrestricted"` to `"network_policy": "open"`.

7. In `README.md` around line 386, in the troubleshooting table, change `Start Docker Desktop` to `Start Docker (Desktop, Engine, or compatible daemon)`.

## Must-Haves

- [ ] No `blocked_by` string in `compute_effective_config.py` contains `isolated` as a network mode name
- [ ] Warning string in `config.py` says `web-egress-enforced`, not `corp-proxy-only`
- [ ] Test fixtures in `test_config_explain.py` use `web-egress-enforced`, not `corp-proxy`
- [ ] README does not claim `Docker Desktop` as a hard requirement
- [ ] README org config example uses `open`, not `unrestricted`
- [ ] README enforcement description mentions topology-based isolation and IPv4-only disclosure
- [ ] `uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q` passes (existing tests still pass with updated vocabulary)

## Verification

- `uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q` — existing tests pass with updated vocabulary
- `grep -c 'network_policy=isolated' src/scc_cli/application/compute_effective_config.py` returns 0
- `grep -c 'corp-proxy-only' src/scc_cli/commands/config.py` returns 0
- `grep -c '"unrestricted"' README.md` returns 0
- `! grep -q 'Requires.*Docker Desktop' README.md || echo 'FAIL: Docker Desktop still a hard requirement'`
  - Estimate: 30m
  - Files: src/scc_cli/application/compute_effective_config.py, src/scc_cli/commands/config.py, tests/test_config_explain.py, README.md
  - Verify: uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q && test $(grep -c 'network_policy=isolated' src/scc_cli/application/compute_effective_config.py) -eq 0 && test $(grep -c 'corp-proxy-only' src/scc_cli/commands/config.py) -eq 0 && test $(grep -c '"unrestricted"' README.md) -eq 0
- [x] **T02: Added 5 guardrail tests in test_docs_truthfulness.py preventing stale network-mode vocabulary and README truthfulness regression** — ## Description

Creates `tests/test_docs_truthfulness.py` with guardrail tests that scan source, tests, and docs for stale network-mode vocabulary and Constitution violations. These tests prevent regression — if anyone reintroduces old names or Docker Desktop hard-dependency claims, the test suite will catch it.

Follow the established scanning pattern from `tests/test_runtime_detection_hotspots.py` (tokenize-based for code scanning). For string-literal and README scanning, regex is appropriate since we're matching content, not Python identifiers.

## Steps

1. Create `tests/test_docs_truthfulness.py` with these tests:

   a. `test_no_stale_network_modes_in_blocked_by_strings` — Scan all `.py` files in `src/scc_cli/` for `blocked_by=` string arguments containing old network mode names (`unrestricted`, `corp-proxy-only`, `corp-proxy`, `isolated`). Use `ast` module or regex over file content to find string literals in `blocked_by=` kwargs. Must not match non-network uses of "isolated" (e.g. "isolated feature development").

   b. `test_no_stale_network_modes_in_user_warnings` — Scan `src/scc_cli/commands/` for warning/error strings containing old network mode names. Use regex targeting string literals that also mention `network_policy` or `proxy` context.

   c. `test_readme_no_docker_desktop_hard_requirement` — Read `README.md` and assert it does NOT contain a line matching `Requires.*Docker Desktop` without also mentioning alternatives (Engine, OrbStack, Colima).

   d. `test_readme_no_stale_network_mode_names` — Scan `README.md` for old network mode names used as values: `"unrestricted"`, `"corp-proxy-only"`, `"isolated"` in network_policy context. The word "isolated" in prose ("isolated feature", "isolated environment") is fine — only match it as a network_policy value (e.g. in JSON, in backticks, or adjacent to network_policy).

   e. `test_example_json_uses_valid_network_policy_values` — Scan all `examples/*.json` files, find `"network_policy"` values, and assert each is a valid member of the NetworkPolicy enum (`open`, `web-egress-enforced`, `locked-down-web`).

2. Import `NetworkPolicy` from `scc_cli.core.network_policy` (or wherever it's defined) to validate enum membership in test (e).

3. Run the new tests to confirm they pass against the T01-fixed codebase.

4. Run the full test suite as the milestone exit gate: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q`. Confirm test count is ≥3464 (3459 baseline + ≥5 new).

## Must-Haves

- [ ] `tests/test_docs_truthfulness.py` exists with ≥5 test functions
- [ ] Tests scan source for stale `blocked_by` strings
- [ ] Tests scan commands for stale warning strings
- [ ] Tests verify README has no Docker Desktop hard requirement
- [ ] Tests verify README has no stale network mode names
- [ ] Tests verify example JSON files use valid NetworkPolicy values
- [ ] All new tests pass
- [ ] Full exit gate passes: ruff + mypy + pytest
- [ ] Test count ≥3464

## Verification

- `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` — all ≥5 tests pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite passes, count ≥3464
  - Estimate: 45m
  - Files: tests/test_docs_truthfulness.py
  - Verify: uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
