---
estimated_steps: 24
estimated_files: 4
skills_used: []
---

# T01: Fix stale network-mode vocabulary in source, tests, and README

## Description

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

## Inputs

- ``src/scc_cli/application/compute_effective_config.py` — contains two `blocked_by="network_policy=isolated"` strings at lines 563 and 712`
- ``src/scc_cli/commands/config.py` — contains stale `corp-proxy-only` warning at line 530`
- ``tests/test_config_explain.py` — fixtures use `corp-proxy` at lines 125, 148; docstring at 672`
- ``README.md` — lines 32, 117, 144, 386 contain stale vocabulary and Docker Desktop hard dependency`

## Expected Output

- ``src/scc_cli/application/compute_effective_config.py` — blocked_by strings updated to locked-down-web`
- ``src/scc_cli/commands/config.py` — warning string updated to web-egress-enforced`
- ``tests/test_config_explain.py` — fixtures and docstring updated to web-egress-enforced`
- ``README.md` — Docker requirement, enforcement scope, example JSON, and troubleshooting updated`

## Verification

uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q && test $(grep -c 'network_policy=isolated' src/scc_cli/application/compute_effective_config.py) -eq 0 && test $(grep -c 'corp-proxy-only' src/scc_cli/commands/config.py) -eq 0 && test $(grep -c '"unrestricted"' README.md) -eq 0
